from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("email_verified", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(email, password, **extra)

    def customers(self):
        return self.filter(is_staff=False)

    def staff(self):
        return self.filter(is_staff=True)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("email address", unique=True)
    full_name = models.CharField(max_length=120)
    company = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    default_formats = models.CharField(max_length=80, blank=True, help_text="e.g. DST + PES")
    machine = models.CharField(max_length=120, blank=True, help_text="e.g. Tajima TMBP-SC · 15 needle")

    class ConsoleTheme(models.TextChoices):
        DARK = "dark", "Dark"
        LIGHT = "light", "Light"

    email_verified = models.BooleanField(default=False)
    console_theme = models.CharField(
        "admin console theme",
        max_length=10,
        choices=ConsoleTheme.choices,
        default=ConsoleTheme.DARK,
        help_text="Each admin picks their own look for the console.",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can sign in to the admin console.")
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def get_full_name(self):
        return self.full_name or self.email

    def get_short_name(self):
        return (self.full_name or self.email).split()[0]

    @property
    def initials(self):
        parts = [p for p in (self.full_name or self.email).replace("@", " ").split() if p]
        return "".join(p[0] for p in parts[:2]).upper()


class EmailVerification(models.Model):
    """A single-use 6-digit code emailed to a customer to confirm their address."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verifications")
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"Verification for {self.user} at {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_usable(self):
        return self.consumed_at is None and not self.is_expired
