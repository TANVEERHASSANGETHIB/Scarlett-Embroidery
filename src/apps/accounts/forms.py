from django import forms
from django.contrib.auth import authenticate, password_validation

from .models import User


class SignupForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••", "autocomplete": "new-password"})
    )

    class Meta:
        model = User
        fields = ["full_name", "company", "email"]
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Jane Whitfield", "autocomplete": "name"}),
            "company": forms.TextInput(
                attrs={"placeholder": "Whitfield Uniforms", "autocomplete": "organization"}
            ),
            "email": forms.EmailInput(attrs={"placeholder": "jane@shop.com", "autocomplete": "email"}),
        }
        labels = {"full_name": "Full name"}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Log in instead.")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            candidate = User(email=cleaned.get("email", ""), full_name=cleaned.get("full_name", ""))
            try:
                password_validation.validate_password(password, candidate)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.email_verified = False
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "jane@shop.com", "autocomplete": "email"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••", "autocomplete": "current-password"})
    )

    error_messages = {"invalid": "Email or password is incorrect."}

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").strip().lower()
        password = cleaned.get("password")
        if email and password:
            self.user = authenticate(self.request, email=email, password=password)
            if self.user is None:
                raise forms.ValidationError(self.error_messages["invalid"])
        return cleaned


class VerifyCodeForm(forms.Form):
    code = forms.RegexField(
        regex=r"^\s*\d{6}\s*$",
        error_messages={"invalid": "Enter the 6-digit code from the email."},
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "maxlength": "6",
                "placeholder": "000000",
                "class": "code-input",
            }
        ),
    )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "company", "email", "phone", "default_formats", "machine"]
        labels = {"full_name": "Full name", "default_formats": "Default format"}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email
