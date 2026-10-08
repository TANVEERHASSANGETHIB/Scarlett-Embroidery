from django.core.cache import cache
from django.db import models
from django.utils.text import slugify


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

    facebook_url = models.URLField("Facebook", max_length=300, blank=True)
    instagram_url = models.URLField("Instagram", max_length=300, blank=True)
    x_url = models.URLField("X (Twitter)", max_length=300, blank=True)
    linkedin_url = models.URLField("LinkedIn", max_length=300, blank=True)
    youtube_url = models.URLField("YouTube", max_length=300, blank=True)
    tiktok_url = models.URLField("TikTok", max_length=300, blank=True)
    pinterest_url = models.URLField("Pinterest", max_length=300, blank=True)
    whatsapp_url = models.URLField("WhatsApp", max_length=300, blank=True)

    notify_on_new_order = models.BooleanField(
        "email me about new orders",
        default=True,
        help_text="Send an alert whenever a customer places an order.",
    )
    order_notification_emails = models.CharField(
        "new-order notice recipients",
        max_length=500,
        blank=True,
        default="info@sedigitizer.com",
        help_text="Receives a short notice when a new order is submitted. Separate addresses with commas.",
    )
    order_details_emails = models.CharField(
        "order details and artwork recipients",
        max_length=500,
        default="scarletsembroidery@gmail.com",
        help_text="Receives the full order specification and submitted artwork files. Separate addresses with commas.",
    )
    contact_notification_emails = models.CharField(
        "contact form recipients",
        max_length=500,
        default="support@sedigitizer.com",
        help_text="Receives contact form submissions. Separate addresses with commas.",
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

    SOCIAL_FIELDS = [
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("x", "X"),
        ("linkedin", "LinkedIn"),
        ("youtube", "YouTube"),
        ("tiktok", "TikTok"),
        ("pinterest", "Pinterest"),
        ("whatsapp", "WhatsApp"),
    ]

    @property
    def social_links(self):
        """(key, label, url) for every network the admin has filled in."""
        links = [(key, label, getattr(self, f"{key}_url")) for key, label in self.SOCIAL_FIELDS]
        return [link for link in links if link[2]]

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
        """Addresses that receive short new-order notices."""
        from django.conf import settings as django_settings

        addresses = [a.strip() for a in self.order_notification_emails.split(",") if a.strip()]
        return addresses or [django_settings.STAFF_NOTIFY_EMAIL]

    @property
    def order_details_recipients(self):
        """Addresses that receive full order details and order-activity alerts."""
        return [a.strip() for a in self.order_details_emails.split(",") if a.strip()]

    @property
    def contact_recipients(self):
        """Addresses that receive contact form submissions."""
        return [a.strip() for a in self.contact_notification_emails.split(",") if a.strip()]

    @classmethod
    def load(cls):
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 300)
        return obj


class PortfolioCategory(models.Model):
    """A filter on the portfolio page — the admin can add, rename and reorder these."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=40, unique=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "portfolio categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:36] or "category"
            slug, n = base, 2
            while PortfolioCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def tag(self):
        return self.name.split()[0][:7].upper() if self.name else ""


class PortfolioItem(TimeStampedModel):
    class Category(models.TextChoices):
        """The categories every site starts with (seeded as PortfolioCategory rows)."""

        CAPS = "caps", "Caps"
        LEFT_CHEST = "left_chest", "Left chest"
        JACKET_BACK = "jacket_back", "Jacket back"
        PATCHES = "patches", "Patches"
        VECTOR = "vector", "Vector"

    # Slug of a PortfolioCategory (kept as text so deleting a category never deletes photos).
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=40, blank=True, db_index=True)
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
    def category_obj(self):
        if hasattr(self, "cached_category"):
            return self.cached_category
        return PortfolioCategory.objects.filter(slug=self.category).first()

    @property
    def category_name(self):
        cat = self.category_obj
        return cat.name if cat else ""

    def get_category_display(self):
        return self.category_name or self.category.replace("_", " ").title()

    @property
    def tag(self):
        cat = self.category_obj
        return cat.tag if cat else ""

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
    image = models.ImageField(
        "photo",
        upload_to="testimonials/",
        blank=True,
        help_text="Optional photo or logo shown with the review.",
    )
    work_photo = models.ImageField(
        "sew-out photo",
        upload_to="testimonials/work/",
        blank=True,
        help_text="Optional photo of the sewn result, shown on top of the review (about 800 × 600 px).",
    )
    rating = models.PositiveSmallIntegerField(default=5)
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name}: {self.quote[:40]}"


class SewOut(models.Model):
    """A photo of a client's finished embroidery, shown in the gallery on the testimonials page."""

    image = models.ImageField("photo", upload_to="sewouts/", help_text="Recommended 1000 × 1000 px.")
    title = models.CharField(max_length=120, help_text="e.g. Left-chest logo on polo")
    client = models.CharField(max_length=80, blank=True, help_text="Client or shop name (optional).")
    details = models.CharField(
        max_length=160, blank=True, help_text="e.g. Pique polo · 3.5 in · 8,200 stitches"
    )
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "-id"]
        verbose_name = "client sew-out"

    def __str__(self):
        return self.title


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


class PageService(models.TextChoices):
    EMBROIDERY = "embroidery", "Embroidery digitizing"
    VECTOR = "vector", "Vector art"
    PATCHES = "patches", "Patches"


class BeforeAfter(models.Model):
    """The draggable before/after comparison in the hero of a service page (embroidery and vector)."""

    service = models.CharField(
        max_length=20,
        unique=True,
        choices=PageService.choices,
    )
    before_image = models.ImageField(upload_to="before-after/")
    after_image = models.ImageField(upload_to="before-after/", blank=True)
    before_label = models.CharField(max_length=20, default="Before")
    after_label = models.CharField(max_length=20, default="After")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "before / after"
        verbose_name_plural = "before / after pairs"

    def __str__(self):
        return f"Before/after · {self.get_service_display()}"


class ServiceImage(TimeStampedModel):
    """Pictures shown on a service page (gallery and feature sections)."""

    service = models.CharField(max_length=20, choices=PageService.choices, db_index=True)
    image = models.ImageField(upload_to="services/")
    caption = models.CharField(max_length=120, blank=True)
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return f"{self.get_service_display()} · {self.caption or self.image.name}"


class SiteImage(models.Model):
    """One named photo slot on a page (About, Home hero…). Empty slots show built-in artwork."""

    class Slot(models.TextChoices):
        HOME_HERO = "home_hero", "Home — hero photo"
        ABOUT_HERO = "about_hero", "About — main photo"
        ABOUT_STORY = "about_story", "About — story photo"
        ABOUT_STUDIO = "about_studio", "About — studio photo"
        ABOUT_TEAM = "about_team", "About — team photo"
        BLOG_DEFAULT = "blog_default", "Blog — default cover (posts without one)"
        PORTFOLIO_DEFAULT = "portfolio_default", "Portfolio — fallback sew-out photo"
        SERVICES_HERO = "services_hero", "Services — overview hero photo"
        CTA_PHOTO = "cta_photo", "Call-to-action banner (bottom of pages)"

    # Recommended pixel size for each place, shown to the admin and on empty spots.
    SIZES = {
        "home_hero": "1200 × 1260 px",
        "about_hero": "1000 × 1250 px",
        "about_story": "1200 × 900 px",
        "about_studio": "900 × 1200 px",
        "about_team": "900 × 1200 px",
        "blog_default": "1600 × 900 px",
        "portfolio_default": "1000 × 1000 px",
        "services_hero": "1200 × 900 px",
        "cta_photo": "900 × 700 px",
    }

    slot = models.CharField(max_length=30, unique=True, choices=Slot.choices)
    image = models.ImageField(upload_to="site/")

    def __str__(self):
        return self.get_slot_display()

    @property
    def size(self):
        return self.SIZES.get(self.slot, "")

    @classmethod
    def urls(cls):
        """{slot: url} for every slot that has a photo."""
        return {row.slot: row.image.url for row in cls.objects.all() if row.image}
