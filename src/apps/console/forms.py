import markdown
from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.forms import PasswordChangeForm
from django.core.validators import validate_email

from apps.accounts.models import User
from apps.blog.models import Category, Post, looks_like_html
from apps.core.models import (
    BeforeAfter,
    PageService,
    PortfolioCategory,
    PortfolioItem,
    SiteImage,
    SiteSettings,
    Testimonial,
)
from apps.orders.forms import MultipleFileField
from apps.orders.models import Order, OrderFile, PatchCategory, PricingTier, TurnaroundOption
from apps.orders.validators import validate_upload


class ConsoleLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"autocomplete": "username", "placeholder": "admin@sedigitizer.com"})
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class OrderUpdateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["status", "final_price", "payment_status", "assigned_to"]
        labels = {"final_price": "Final price ($)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.staff().filter(is_active=True)
        self.fields["assigned_to"].label_from_instance = lambda u: u.get_full_name()
        self.fields["assigned_to"].empty_label = "Unassigned"
        self.fields["final_price"].widget.attrs.update({"step": "0.01", "min": "0"})


class OrderNoteForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message or note…"}), max_length=4000
    )
    internal = forms.BooleanField(required=False, label="Internal note (hidden from customer)")


class OrderFileUploadForm(forms.Form):
    kind = forms.ChoiceField(
        choices=[(OrderFile.Kind.PROOF, "Sew-out proof"), (OrderFile.Kind.DELIVERABLE, "Final files")]
    )
    files = MultipleFileField(required=True, allowed_extensions=settings.DELIVERABLE_EXTENSIONS)
    mark_status = forms.BooleanField(
        required=False, initial=True, label="Update status (proof → awaiting approval, final → delivered)"
    )


class PostForm(forms.ModelForm):
    new_category = forms.CharField(required=False, max_length=60, label="…or new category")

    class Meta:
        model = Post
        fields = [
            "title",
            "category",
            "slug",
            "excerpt",
            "cover",
            "body",
            "status",
            "is_featured",
            "author_title",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Choosing stabiliser by fabric"}),
            "slug": forms.TextInput(attrs={"placeholder": "choosing-stabiliser (auto if blank)"}),
            "excerpt": forms.Textarea(attrs={"rows": 2}),
            "body": forms.Textarea(attrs={"rows": 14, "data-rich-editor": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        # Older posts were written in Markdown: show them as HTML in the visual editor.
        body = self.instance.body if self.instance.pk else ""
        if body and not looks_like_html(body):
            self.initial["body"] = markdown.markdown(body, extensions=["extra", "sane_lists"])
        self.fields["category"].queryset = Category.objects.all()
        self.fields["category"].required = False

    def clean_slug(self):
        slug = self.cleaned_data.get("slug", "").strip("/ ").lower()
        if slug and Post.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another post already uses this slug.")
        return slug

    def save(self, commit=True):
        post = super().save(commit=False)
        new_cat = self.cleaned_data.get("new_category", "").strip()
        if new_cat:
            post.category, _ = Category.objects.get_or_create(name=new_cat)
        if commit:
            post.save()
        return post


def category_choices():
    return [(c.slug, c.name) for c in PortfolioCategory.objects.all()]


class PortfolioCategoryForm(forms.ModelForm):
    class Meta:
        model = PortfolioCategory
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": "e.g. Hoodies"})}
        labels = {"name": "Category name"}


class PortfolioUploadForm(forms.Form):
    """Add one or many portfolio photos at once, all filed under the same category."""

    images = MultipleFileField(
        label="Photos",
        allowed_extensions=settings.IMAGE_EXTENSIONS,
        max_bytes=settings.PORTFOLIO_IMAGE_MAX_BYTES,
    )
    category = forms.ChoiceField(choices=[])
    name = forms.CharField(
        required=False,
        max_length=120,
        help_text="Leave blank to name each photo after its file.",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Ridgeline cap"}),
    )
    meta = forms.CharField(
        required=False,
        max_length=120,
        help_text="Small line under the name.",
        widget=forms.TextInput(attrs={"placeholder": "cap front · 4,120 st"}),
    )
    show_on_home = forms.BooleanField(required=False, label="Also feature in the home page showcase")
    is_published = forms.BooleanField(required=False, initial=True, label="Visible on the website")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].choices = category_choices()


class PortfolioItemForm(forms.ModelForm):
    """Edit one portfolio piece, including replacing its photo."""

    class Meta:
        model = PortfolioItem
        fields = [
            "name",
            "category",
            "image",
            "meta",
            "showcase_tag",
            "placement",
            "fabric",
            "stitches",
            "formats",
            "turnaround",
            "show_on_home",
            "is_published",
            "sort_order",
        ]
        widgets = {
            "meta": forms.TextInput(attrs={"placeholder": "cap front · 4,120 st"}),
            "showcase_tag": forms.TextInput(attrs={"placeholder": "Cap front · foam"}),
            "placement": forms.TextInput(attrs={"placeholder": "Cap front · 4.2 in"}),
            "fabric": forms.TextInput(attrs={"placeholder": "Structured foam front"}),
            "formats": forms.TextInput(attrs={"placeholder": "DST · EXP"}),
            "turnaround": forms.TextInput(attrs={"placeholder": "2 h 40 m"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].required = False  # keep the current photo unless a new one is picked
        choices = category_choices()
        if self.instance.pk and self.instance.category not in {c[0] for c in choices}:
            choices.append((self.instance.category, self.instance.get_category_display()))
        self.fields["category"] = forms.ChoiceField(choices=choices, label="Category")

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and hasattr(image, "size"):
            validate_upload(image, settings.IMAGE_EXTENSIONS, settings.PORTFOLIO_IMAGE_MAX_BYTES)
        return image


class TestimonialForm(forms.ModelForm):
    """A customer quote for the home page carousel."""

    class Meta:
        model = Testimonial
        fields = ["quote", "name", "role", "image", "rating", "is_published", "sort_order"]
        widgets = {
            "quote": forms.Textarea(
                attrs={"rows": 5, "placeholder": "What the customer said — no quote marks needed."}
            ),
            "name": forms.TextInput(attrs={"placeholder": "Sarah Mitchell"}),
            "role": forms.TextInput(attrs={"placeholder": "Owner · Stitch Perfect"}),
            "rating": forms.NumberInput(attrs={"min": "1", "max": "5", "step": "1"}),
        }
        labels = {"role": "Role / company", "sort_order": "Order"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].required = False

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and hasattr(image, "size"):
            validate_upload(image, settings.IMAGE_EXTENSIONS, settings.PORTFOLIO_IMAGE_MAX_BYTES)
        return image

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if not 1 <= rating <= 5:
            raise forms.ValidationError("Choose a rating between 1 and 5 stars.")
        return rating


class SiteSettingsForm(forms.ModelForm):
    """Contact details shown on the public site."""

    # Declared so a pasted URL without a scheme means https (Django 6 default).
    map_embed_url = forms.URLField(
        required=False,
        assume_scheme="https",
        label="custom map embed URL",
        help_text="Optional. Paste the src from Google Maps > Share > Embed a map. "
        "Leave empty to map the address above.",
        widget=forms.URLInput(attrs={"placeholder": "https://www.google.com/maps/embed?pb=…"}),
    )

    class Meta:
        model = SiteSettings
        fields = [
            "phone",
            "email",
            "orders_email",
            "hours",
            "business_name",
            "address",
            "map_embed_url",
            "show_map",
            "announcement",
            "patch_production_note",
            "patch_min_quantity",
        ]
        widgets = {
            "address": forms.TextInput(attrs={"placeholder": "12 Loom St, Austin, TX 78701"}),
        }


class SocialLinksForm(forms.ModelForm):
    """Social profiles shown as icons in the site footer. Leave a box empty to hide that icon."""

    class Meta:
        model = SiteSettings
        fields = [f"{key}_url" for key, _ in SiteSettings.SOCIAL_FIELDS]
        widgets = {
            "facebook_url": forms.URLInput(attrs={"placeholder": "https://facebook.com/yourpage"}),
            "instagram_url": forms.URLInput(attrs={"placeholder": "https://instagram.com/yourhandle"}),
            "x_url": forms.URLInput(attrs={"placeholder": "https://x.com/yourhandle"}),
            "linkedin_url": forms.URLInput(attrs={"placeholder": "https://linkedin.com/company/yourcompany"}),
            "youtube_url": forms.URLInput(attrs={"placeholder": "https://youtube.com/@yourchannel"}),
            "tiktok_url": forms.URLInput(attrs={"placeholder": "https://tiktok.com/@yourhandle"}),
            "pinterest_url": forms.URLInput(attrs={"placeholder": "https://pinterest.com/yourprofile"}),
            "whatsapp_url": forms.URLInput(attrs={"placeholder": "https://wa.me/15125550148"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.assume_scheme = "https"


class AdminPasswordChangeForm(PasswordChangeForm):
    """Lets the signed-in admin change their own password."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Current password"
        self.fields["new_password1"].label = "New password"
        self.fields["new_password2"].label = "Confirm new password"
        self.fields["old_password"].widget.attrs.update({"autocomplete": "current-password"})
        self.fields["new_password1"].widget.attrs.update({"autocomplete": "new-password"})
        self.fields["new_password2"].widget.attrs.update({"autocomplete": "new-password"})


class NotificationSettingsForm(forms.ModelForm):
    """Who gets told when an order comes in."""

    class Meta:
        model = SiteSettings
        fields = ["notify_on_new_order", "order_notification_emails"]
        widgets = {
            "order_notification_emails": forms.TextInput(
                attrs={"placeholder": "you@gmail.com, team@yourshop.com", "autocomplete": "off"}
            )
        }

    def clean_order_notification_emails(self):
        raw = self.cleaned_data["order_notification_emails"]
        addresses = [a.strip() for a in raw.split(",") if a.strip()]
        for address in addresses:
            try:
                validate_email(address)
            except forms.ValidationError as exc:
                raise forms.ValidationError(f"“{address}” is not a valid email address.") from exc
        if self.cleaned_data.get("notify_on_new_order") and not addresses:
            raise forms.ValidationError("Add at least one address, or turn new-order alerts off.")
        return ", ".join(addresses)


def _row_widgets(**overrides):
    base = {
        "name": forms.TextInput(attrs={"placeholder": "Name"}),
        "description": forms.TextInput(attrs={"placeholder": "Short description (optional)"}),
        "sort_order": forms.NumberInput(attrs={"min": "0", "step": "1"}),
    }
    base.update(overrides)
    return base


PricingTierFormSet = forms.modelformset_factory(
    PricingTier,
    fields=[
        "service",
        "name",
        "plan_name",
        "price",
        "ribbon",
        "sort_order",
        "is_highlighted",
        "is_active",
        "features",
    ],
    widgets=_row_widgets(
        price=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        plan_name=forms.TextInput(attrs={"placeholder": "Base"}),
        ribbon=forms.TextInput(attrs={"placeholder": "BASE"}),
        features=forms.Textarea(attrs={"rows": 4, "placeholder": "One line per feature"}),
    ),
    extra=0,
    can_delete=True,
)
TurnaroundFormSet = forms.modelformset_factory(
    TurnaroundOption,
    fields=["name", "hours", "surcharge", "sort_order", "is_default", "is_active"],
    widgets=_row_widgets(
        hours=forms.NumberInput(attrs={"min": "1", "step": "1"}),
        surcharge=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
    ),
    extra=0,
    can_delete=True,
)
PatchCategoryFormSet = forms.modelformset_factory(
    PatchCategory,
    fields=[
        "name",
        "description",
        "unit_price",
        "ribbon",
        "features",
        "sort_order",
        "is_highlighted",
        "is_active",
    ],
    widgets=_row_widgets(
        unit_price=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        ribbon=forms.TextInput(attrs={"placeholder": "POPULAR"}),
        features=forms.Textarea(attrs={"rows": 4, "placeholder": "One line per feature"}),
    ),
    extra=0,
    can_delete=True,
)


class InviteAdminForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Share it privately; they can change it after signing in.",
    )

    class Meta:
        model = User
        fields = ["full_name", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        password_validation.validate_password(password)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.is_staff = True
        user.email_verified = True
        if commit:
            user.save()
        return user


def _validated_image(field_name):
    def clean(self):
        image = self.cleaned_data.get(field_name)
        if image and hasattr(image, "size"):
            validate_upload(image, settings.IMAGE_EXTENSIONS, settings.PORTFOLIO_IMAGE_MAX_BYTES)
        return image

    return clean


class BeforeAfterForm(forms.ModelForm):
    """Upload (or replace) the before/after pair for embroidery or vector. One pair per service."""

    class Meta:
        model = BeforeAfter
        fields = ["service", "before_image", "after_image", "before_label", "after_label", "is_active"]
        labels = {
            "before_image": "Before photo",
            "after_image": "After photo",
            "is_active": "Show on the page",
        }

    clean_before_image = _validated_image("before_image")
    clean_after_image = _validated_image("after_image")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["before_image"].required = False
        self.fields["after_image"].required = False

    def clean(self):
        cleaned = super().clean()
        service = cleaned.get("service")
        existing = BeforeAfter.objects.filter(service=service).first() if service else None
        for name in ("before_image", "after_image"):
            if not cleaned.get(name) and not (existing and getattr(existing, name)):
                self.add_error(name, "Choose a photo.")
        return cleaned

    def validate_unique(self):
        pass  # saving replaces the existing pair for that service

    def save(self, commit=True):
        service = self.cleaned_data["service"]
        pair = BeforeAfter.objects.filter(service=service).first() or BeforeAfter(service=service)
        for name in ("before_image", "after_image"):
            if self.cleaned_data.get(name):
                setattr(pair, name, self.cleaned_data[name])
        pair.before_label = self.cleaned_data.get("before_label") or "Before"
        pair.after_label = self.cleaned_data.get("after_label") or "After"
        pair.is_active = self.cleaned_data.get("is_active", False)
        pair.save()
        return pair


class ServiceImageUploadForm(forms.Form):
    """Add one or many pictures to a service page."""

    service = forms.ChoiceField(choices=PageService.choices)
    images = MultipleFileField(
        label="Photos",
        allowed_extensions=settings.IMAGE_EXTENSIONS,
        max_bytes=settings.PORTFOLIO_IMAGE_MAX_BYTES,
    )
    caption = forms.CharField(
        required=False, max_length=120, widget=forms.TextInput(attrs={"placeholder": "Optional caption"})
    )


class SiteImageForm(forms.ModelForm):
    """Set the photo for a named place on the site (About page, Home hero…)."""

    class Meta:
        model = SiteImage
        fields = ["slot", "image"]
        labels = {"slot": "Where it appears", "image": "Photo"}

    clean_image = _validated_image("image")

    def validate_unique(self):
        pass

    def save(self, commit=True):
        obj = SiteImage.objects.filter(slot=self.cleaned_data["slot"]).first() or SiteImage(
            slot=self.cleaned_data["slot"]
        )
        obj.image = self.cleaned_data["image"]
        obj.save()
        return obj
