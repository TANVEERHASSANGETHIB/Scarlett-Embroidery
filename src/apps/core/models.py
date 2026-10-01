from django.core.cache import cache
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SiteSettings(models.Model):
    """Singleton holding contact details shown across the public site."""

    CACHE_KEY = "core:site-settings"

    phone = models.CharField(max_length=40, default="+1 (512) 555-0148")
    email = models.EmailField(default="hello@sedigitizer.com")
    orders_email = models.EmailField(default="orders@sedigitizer.com")
    hours = models.CharField(max_length=120, default="Live chat 24/7 · Studio 8am–8pm CT")
    announcement = models.CharField(max_length=80, default="4-hour standard turnaround")
    patch_production_note = models.CharField(max_length=80, default="8–12 day production")
    patch_min_quantity = models.PositiveIntegerField(default=50)

    business_name = models.CharField(
        max_length=120,
        default="Scarlett Embroidery",
        help_text="Used for the map pin label, so the listing shows on the contact page map.",
    )
    address = models.CharField(
        "studio address",
        max_length=250,
        blank=True,
        help_text="Shown on the contact page and used for the map, e.g. 12 Loom St, Austin, TX 78701.",
    )
    map_embed_url = models.URLField(
        "custom map embed URL",
        max_length=500,
        blank=True,
        help_text="Optional. Paste the src from Google Maps > Share > Embed a map. Leave empty to map the address above.",
    )
    show_map = models.BooleanField("show the map on the contact page", default=True)

    notify_on_new_order = models.BooleanField(
        "email me about new orders",
        default=True,
        help_text="Send an alert whenever a customer places an order.",
    )
    order_notification_emails = models.CharField(
        "order alerts go to",
        max_length=500,
        blank=True,
        help_text="Where new-order alerts are sent. Separate several addresses with commas.",
    )

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    @property
    def map_src(self):
        """What the contact page iframe loads: a pasted embed, or the address."""
        from urllib.parse import quote

        if not self.show_map:
            return ""
        if self.map_embed_url:
            return self.map_embed_url
        if self.address:
            place = f"{self.business_name}, {self.address}" if self.business_name else self.address
            return f"https://www.google.com/maps?q={quote(place)}&output=embed&z=15"
        return ""

    @property
    def map_link(self):
        """Where "Get directions" goes."""
        from urllib.parse import quote

        if not self.address:
            return ""
        return f"https://www.google.com/maps/search/?api=1&query={quote(self.address)}"

    @property
    def notification_recipients(self):
        """Addresses that receive new-order and order-activity alerts."""
        from django.conf import settings as django_settings

        addresses = [a.strip() for a in self.order_notification_emails.split(",") if a.strip()]
        return addresses or [django_settings.STAFF_NOTIFY_EMAIL]

    @classmethod
    def load(cls):
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 300)
        return obj


class PortfolioItem(TimeStampedModel):
    class Category(models.TextChoices):
        CAPS = "caps", "Caps"
        LEFT_CHEST = "left_chest", "Left chest"
        JACKET_BACK = "jacket_back", "Jacket back"
        PATCHES = "patches", "Patches"
        VECTOR = "vector", "Vector"

    TAGS = {
        "caps": "CAP",
        "left_chest": "CHEST",
        "jacket_back": "BACK",
        "patches": "PATCH",
        "vector": "VECTOR",
    }

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices)
    image = models.ImageField(upload_to="portfolio/", blank=True)
    meta = models.CharField(max_length=120, blank=True, help_text="Short line, e.g. 'cap front · 4,120 st'")
    showcase_tag = models.CharField(max_length=60, blank=True, help_text="e.g. 'Cap front · foam'")
    placement = models.CharField(max_length=80, blank=True)
    fabric = models.CharField(max_length=80, blank=True)
    stitches = models.PositiveIntegerField(null=True, blank=True)
    formats = models.CharField(max_length=80, blank=True)
    turnaround = models.CharField(max_length=40, blank=True)
    show_on_home = models.BooleanField(default=False, help_text="Include in the home page sew-out showcase")
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.name

    @property
    def tag(self):
        return self.TAGS.get(self.category, "")

    @property
    def short_name(self):
        return self.name.split()[0] if self.name else ""

    @property
    def specs(self):
        rows = [
            ("Placement", self.placement),
            ("Fabric", self.fabric),
            ("Stitches", f"{self.stitches:,}" if self.stitches else ""),
            ("Formats", self.formats),
            ("Turnaround", self.turnaround),
        ]
        return [(k, v) for k, v in rows if v]


class Testimonial(models.Model):
    quote = models.TextField()
    name = models.CharField(max_length=80)
    role = models.CharField(max_length=120, blank=True)
    rating = models.PositiveSmallIntegerField(default=5)
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name}: {self.quote[:40]}"


class FAQ(models.Model):
    question = models.CharField(max_length=200)
    answer = models.TextField()
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.subject or 'No subject'}"
