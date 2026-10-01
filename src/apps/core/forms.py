from django import forms

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    # Honeypot: real visitors never see or fill this field.
    website = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"})
    )

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Jane Whitfield"}),
            "email": forms.EmailInput(attrs={"placeholder": "jane@shop.com"}),
            "subject": forms.TextInput(attrs={"placeholder": "Cap logo — 3.5in wide, DST"}),
            "message": forms.Textarea(
                attrs={"rows": 6, "placeholder": "Tell us the fabric, size and format you need."}
            ),
        }

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Spam detected.")
        return ""
