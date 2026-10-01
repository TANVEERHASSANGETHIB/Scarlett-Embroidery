from django import forms
from django.conf import settings

from apps.core.models import SiteSettings

from .models import (
    EMBROIDERY_FORMATS,
    FABRIC_CHOICES,
    PLACEMENT_CHOICES,
    VECTOR_FORMATS,
    Order,
    PatchCategory,
    PatchDetail,
    PricingTier,
    Service,
    TurnaroundOption,
)
from .validators import validate_upload


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, allowed_extensions=None, max_bytes=None, **kwargs):
        self.allowed_extensions = allowed_extensions or settings.ARTWORK_EXTENSIONS
        self.max_bytes = max_bytes
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            files = [single(d, initial) for d in data if d]
        else:
            files = [single(data, initial)] if data else []
        if self.required and not files:
            raise forms.ValidationError(self.error_messages["required"], code="required")
        errors = []
        for f in files:
            try:
                validate_upload(f, self.allowed_extensions, self.max_bytes)
            except forms.ValidationError as exc:
                errors.extend(exc.messages)
        if errors:
            raise forms.ValidationError(errors)
        return files


def _choices(values):
    return [(v, v) for v in values]


class OrderForm(forms.ModelForm):
    service = forms.ChoiceField(choices=Service.choices, widget=forms.RadioSelect)
    tier = forms.ModelChoiceField(
        queryset=PricingTier.objects.none(),
        required=False,
        widget=forms.RadioSelect,
        empty_label=None,
        label="Design type",
    )
    turnaround = forms.ModelChoiceField(
        queryset=TurnaroundOption.objects.none(), required=False, widget=forms.RadioSelect, empty_label=None
    )
    fabric = forms.ChoiceField(choices=_choices(FABRIC_CHOICES), required=False)
    placement = forms.ChoiceField(choices=_choices(PLACEMENT_CHOICES), required=False)
    embroidery_formats = forms.MultipleChoiceField(
        choices=_choices(EMBROIDERY_FORMATS),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Required file formats",
    )
    vector_formats = forms.MultipleChoiceField(
        choices=_choices(VECTOR_FORMATS),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Required file formats",
    )
    artwork = MultipleFileField(required=True, label="Artwork")

    class Meta:
        model = Order
        fields = [
            "service",
            "contact_name",
            "contact_email",
            "design_name",
            "tier",
            "turnaround",
            "fabric",
            "placement",
            "height_in",
            "width_in",
            "instructions",
        ]
        widgets = {
            "design_name": forms.TextInput(attrs={"placeholder": "Whitfield crest — left chest"}),
            "height_in": forms.NumberInput(attrs={"step": "0.1", "min": "0.1", "placeholder": "2.5"}),
            "width_in": forms.NumberInput(attrs={"step": "0.1", "min": "0.1", "placeholder": "3.5"}),
            "instructions": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Thread brand, exact colour codes, what to drop, anything that must stay legible at size.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        # Artwork already saved with a draft counts as supplied, so a returning
        # visitor isn't asked to pick their files a second time.
        self.saved_file_count = kwargs.pop("saved_file_count", 0)
        super().__init__(*args, **kwargs)
        if self.saved_file_count:
            self.fields["artwork"].required = False
        self.fields["tier"].queryset = PricingTier.objects.filter(is_active=True)
        self.fields["turnaround"].queryset = TurnaroundOption.objects.filter(is_active=True)
        default_turnaround = self.fields["turnaround"].queryset.filter(is_default=True).first()
        if default_turnaround and not self.is_bound:
            self.initial.setdefault("turnaround", default_turnaround.pk)
        self.initial.setdefault("service", Service.DIGITIZING)
        self.initial.setdefault("embroidery_formats", ["DST", "PES", "EMB"])
        self.initial.setdefault("vector_formats", ["AI", "PDF"])

    def clean(self):
        cleaned = super().clean()
        service = cleaned.get("service")
        if service in (Service.DIGITIZING, Service.VECTOR):
            tier = cleaned.get("tier")
            if tier is None:
                self.add_error("tier", "Choose a design type.")
            elif tier.service != service:
                self.add_error("tier", "That design type doesn't belong to the selected service.")
            if cleaned.get("turnaround") is None:
                self.add_error("turnaround", "Choose a turnaround.")
            formats_field = "embroidery_formats" if service == Service.DIGITIZING else "vector_formats"
            if not cleaned.get(formats_field):
                self.add_error(formats_field, "Pick at least one file format.")
            cleaned["formats"] = cleaned.get(formats_field) or []
        if service == Service.DIGITIZING:
            for name in ("fabric", "placement"):
                if not cleaned.get(name):
                    self.add_error(name, "This field is required for digitizing.")
        if service == Service.PATCHES:
            cleaned["tier"] = None
            cleaned["turnaround"] = None
            cleaned["formats"] = []
        return cleaned

    def save(self, commit=True):
        order = super().save(commit=False)
        service = self.cleaned_data["service"]
        order.formats = self.cleaned_data.get("formats", [])
        if service != Service.DIGITIZING:
            order.fabric = ""
            order.placement = ""
        if service == Service.PATCHES:
            order.tier = None
            order.turnaround = None
            order.height_in = None
            order.width_in = None
        if commit:
            order.save()
        return order


class PatchDetailForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=PatchCategory.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
        label="Patch category",
    )
    backing = forms.ChoiceField(choices=PatchDetail.Backing.choices, widget=forms.RadioSelect)

    class Meta:
        model = PatchDetail
        fields = [
            "category",
            "backing",
            "quantity",
            "width_in",
            "height_in",
            "shipping_name",
            "shipping_phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
        ]
        widgets = {
            "quantity": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "width_in": forms.NumberInput(attrs={"step": "0.1", "min": "0.5", "placeholder": "3.5"}),
            "height_in": forms.NumberInput(attrs={"step": "0.1", "min": "0.5", "placeholder": "3"}),
            "address_line1": forms.TextInput(
                attrs={"placeholder": "Street address", "autocomplete": "address-line1"}
            ),
            "address_line2": forms.TextInput(
                attrs={"placeholder": "Suite, unit (optional)", "autocomplete": "address-line2"}
            ),
            "city": forms.TextInput(attrs={"autocomplete": "address-level2"}),
            "state": forms.TextInput(attrs={"autocomplete": "address-level1"}),
            "postal_code": forms.TextInput(attrs={"autocomplete": "postal-code"}),
            "country": forms.TextInput(attrs={"autocomplete": "country-name"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = PatchCategory.objects.filter(is_active=True)
        self.min_quantity = SiteSettings.load().patch_min_quantity
        self.fields["quantity"].widget.attrs["min"] = str(self.min_quantity)
        if not self.is_bound:
            self.initial.setdefault("quantity", self.min_quantity)
            self.initial.setdefault("backing", PatchDetail.Backing.IRON_ON)
            first = self.fields["category"].queryset.first()
            if first:
                self.initial.setdefault("category", first.pk)

    def clean_quantity(self):
        qty = self.cleaned_data["quantity"]
        if qty < self.min_quantity:
            raise forms.ValidationError(f"The minimum order is {self.min_quantity} patches.")
        return qty


class RevisionRequestForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "What should change?"}), max_length=4000
    )


class AdditionalArtworkForm(forms.Form):
    files = MultipleFileField(required=True)
    note = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.TextInput(attrs={"placeholder": "Optional note for the digitizer"}),
    )
