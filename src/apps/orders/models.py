import os
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.functional import LazyObject

from apps.core.models import TimeStampedModel


class PrivateStorage(LazyObject):
    """Storage for customer uploads. Lives outside MEDIA_ROOT and has no public URL."""

    def _setup(self):
        self._wrapped = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


private_storage = PrivateStorage()


class Service(models.TextChoices):
    DIGITIZING = "digitizing", "Digitizing"
    VECTOR = "vector", "Vector Art"
    PATCHES = "patches", "Patches"


EMBROIDERY_FORMATS = ["DST", "PES", "EXP", "JEF", "VP3", "XXX", "HUS", "EMB"]
VECTOR_FORMATS = ["AI", "EPS", "PDF", "SVG", "CDR", "PNG"]

FABRIC_CHOICES = [
    "Cotton twill",
    "Piqué polo knit",
    "Fleece / hoodie",
    "Structured cap front",
    "Performance polyester",
    "Leather / vinyl",
    "Towel / terry",
]
PLACEMENT_CHOICES = [
    "Left chest",
    "Cap front",
    "Cap side / back",
    "Full back",
    "Jacket back",
    "Sleeve",
    "Bag panel",
    "Beanie cuff",
]


class PricingTier(models.Model):
    """Flat price for a design class, e.g. Digitizing › Left chest $6."""

    service = models.CharField(max_length=20, choices=[c for c in Service.choices if c[0] != Service.PATCHES])
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=160, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])

    # How this tier is presented on the home page pricing cards.
    plan_name = models.CharField(
        "plan name",
        max_length=40,
        blank=True,
        help_text="Shown on the pricing card, e.g. Base. Defaults to the name.",
    )
    ribbon = models.CharField(
        max_length=16, blank=True, help_text="Corner flag on the card, e.g. BASE. Leave empty for none."
    )
    features = models.TextField(
        blank=True, help_text="What the plan includes — one per line, shown as the card's list."
    )
    is_highlighted = models.BooleanField(
        "highlight this plan", default=False, help_text="Lifts the card and marks it as the popular choice."
    )

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["service", "sort_order", "price"]

    def __str__(self):
        return f"{self.get_service_display()} · {self.name} (${self.price})"

    @property
    def card_name(self):
        return self.plan_name or self.name

    @property
    def feature_list(self):
        return [line.strip() for line in self.features.splitlines() if line.strip()]


class TurnaroundOption(models.Model):
    name = models.CharField(max_length=40)
    hours = models.PositiveIntegerField(help_text="Target hours from a complete order")
    surcharge = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "hours"]

    def __str__(self):
        return self.name


class PatchCategory(models.Model):
    """Iron-on, embroidery and rubber patches — each with a starting price per piece."""

    name = models.CharField(max_length=60)
    description = models.CharField(max_length=160, blank=True)
    unit_price = models.DecimalField(
        "from price / piece", max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "patch categories"

    def __str__(self):
        return self.name


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "In queue"
        IN_PROGRESS = "in_progress", "In production"
        AWAITING_APPROVAL = "awaiting_approval", "Awaiting approval"
        REVISION = "revision", "Revision requested"
        APPROVED = "approved", "Approved"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class Payment(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"
        WAIVED = "waived", "Waived"

    OPEN_STATUSES = [
        Status.PENDING,
        Status.IN_PROGRESS,
        Status.AWAITING_APPROVAL,
        Status.REVISION,
        Status.APPROVED,
    ]

    number = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    service = models.CharField(max_length=20, choices=Service.choices, default=Service.DIGITIZING)

    contact_name = models.CharField("name", max_length=120)
    contact_email = models.EmailField("email")
    design_name = models.CharField("design name / PO reference", max_length=160)

    tier = models.ForeignKey(
        PricingTier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="design type",
    )
    turnaround = models.ForeignKey(
        TurnaroundOption, on_delete=models.PROTECT, null=True, blank=True, related_name="orders"
    )
    fabric = models.CharField(max_length=60, blank=True)
    placement = models.CharField(max_length=60, blank=True)
    height_in = models.DecimalField("height (in)", max_digits=6, decimal_places=2, null=True, blank=True)
    width_in = models.DecimalField("width (in)", max_digits=6, decimal_places=2, null=True, blank=True)
    formats = models.JSONField(default=list, blank=True)
    instructions = models.TextField("instructions / notes", blank=True)

    estimate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_status = models.CharField(max_length=10, choices=Payment.choices, default=Payment.UNPAID)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
        limit_choices_to={"is_staff": True},
    )
    due_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["status", "due_at"]),
        ]

    def __str__(self):
        return f"{self.number} · {self.design_name}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        if creating and self.due_at is None and self.turnaround_id and self.service != Service.PATCHES:
            self.due_at = timezone.now() + timedelta(hours=self.turnaround.hours)
        super().save(*args, **kwargs)
        if not self.number:
            self.number = f"SE-{2900 + self.pk}"
            super().save(update_fields=["number"])

    @property
    def total(self):
        return self.final_price if self.final_price is not None else self.estimate

    @property
    def is_patch(self):
        return self.service == Service.PATCHES

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def size_display(self):
        if self.height_in and self.width_in:
            return f"{self.height_in.normalize():f} × {self.width_in.normalize():f} in"
        return ""

    @property
    def formats_display(self):
        return ", ".join(self.formats) if self.formats else "—"

    @property
    def is_overdue(self):
        return bool(self.due_at and self.is_open and self.due_at < timezone.now())

    @property
    def status_tone(self):
        return {
            self.Status.IN_PROGRESS: "gold",
            self.Status.AWAITING_APPROVAL: "soft",
            self.Status.REVISION: "soft",
            self.Status.PENDING: "gold",
            self.Status.APPROVED: "soft",
        }.get(self.status, "muted")


class PatchDetail(models.Model):
    class Backing(models.TextChoices):
        IRON_ON = "iron_on", "Iron-on"
        VELCRO = "velcro", "Velcro (hook & loop)"
        ADHESIVE = "adhesive", "Adhesive"
        SEW_ON = "sew_on", "Sew-on"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="patch")
    category = models.ForeignKey(
        PatchCategory, on_delete=models.PROTECT, related_name="patch_orders", verbose_name="patch category"
    )
    backing = models.CharField(max_length=20, choices=Backing.choices, default=Backing.IRON_ON)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    width_in = models.DecimalField("width (in)", max_digits=6, decimal_places=2)
    height_in = models.DecimalField("height (in)", max_digits=6, decimal_places=2)

    shipping_name = models.CharField("recipient name", max_length=120)
    shipping_phone = models.CharField("phone", max_length=40, blank=True)
    address_line1 = models.CharField("address line 1", max_length=200)
    address_line2 = models.CharField("address line 2", max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField("state / province", max_length=100, blank=True)
    postal_code = models.CharField("postal code", max_length=20)
    country = models.CharField(max_length=100, default="United States")

    def __str__(self):
        return f"{self.quantity} × {self.category} for {self.order.number}"

    @property
    def size_display(self):
        return f"{self.width_in.normalize():f} × {self.height_in.normalize():f} in"

    @property
    def address_lines(self):
        city_line = ", ".join(p for p in [self.city, self.state] if p)
        city_line = f"{city_line} {self.postal_code}".strip()
        return [
            line
            for line in [
                self.shipping_name,
                self.address_line1,
                self.address_line2,
                city_line,
                self.country,
                self.shipping_phone,
            ]
            if line
        ]


def order_file_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"orders/{instance.order.number or 'new'}/{instance.kind}/{uuid.uuid4().hex}{ext}"


class OrderFile(models.Model):
    class Kind(models.TextChoices):
        ARTWORK = "artwork", "Artwork"
        PROOF = "proof", "Sew-out proof"
        DELIVERABLE = "deliverable", "Final file"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="files")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.ARTWORK)
    file = models.FileField(upload_to=order_file_path, storage=private_storage, max_length=255)
    original_name = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.original_name

    @property
    def is_image(self):
        return os.path.splitext(self.original_name)[1].lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}


class OrderEvent(models.Model):
    class Kind(models.TextChoices):
        CREATED = "created", "Order placed"
        STATUS = "status", "Status changed"
        PRICE = "price", "Price set"
        FILE = "file", "Files added"
        MESSAGE = "message", "Message"
        NOTE = "note", "Internal note"
        APPROVED = "approved", "Proof approved"
        REVISION = "revision", "Revision requested"
        PAYMENT = "payment", "Payment"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    message = models.TextField(blank=True)
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.order.number}: {self.get_kind_display()}"


def draft_file_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"drafts/{instance.draft_id}/{uuid.uuid4().hex}{ext}"


class OrderDraft(models.Model):
    """A half-finished order kept for a visitor who isn't signed in yet.

    Guests can fill in the whole form, including artwork. When they submit we
    park it here, ask them to sign in, then put it back on screen exactly as
    they left it. Drafts are found through the visitor's own session only.
    """

    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="order_drafts"
    )
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Draft #{self.pk} ({self.data.get('design_name') or 'untitled'})"

    def delete(self, *args, **kwargs):
        for draft_file in self.files.all():
            draft_file.file.delete(save=False)
        return super().delete(*args, **kwargs)


class OrderDraftFile(models.Model):
    draft = models.ForeignKey(OrderDraft, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to=draft_file_path, storage=private_storage, max_length=255)
    original_name = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.original_name
