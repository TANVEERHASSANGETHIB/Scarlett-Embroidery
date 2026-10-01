from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import EmailVerification, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["email", "full_name", "company", "email_verified", "is_staff", "is_active", "date_joined"]
    list_filter = ["is_staff", "is_active", "email_verified"]
    search_fields = ["email", "full_name", "company"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "company", "phone", "default_formats", "machine")}),
        (
            "Status",
            {
                "fields": (
                    "email_verified",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),
    )


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "expires_at", "attempts", "consumed_at"]
    readonly_fields = ["user", "code_hash", "created_at", "expires_at", "attempts", "consumed_at"]
