from django.contrib import admin

from .models import FAQ, ContactMessage, PortfolioItem, SewOut, SiteSettings, Testimonial


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "show_on_home", "is_published", "sort_order"]
    list_filter = ["category", "show_on_home", "is_published"]
    list_editable = ["show_on_home", "is_published", "sort_order"]
    search_fields = ["name", "meta"]


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ["name", "role", "is_published", "sort_order"]
    list_editable = ["is_published", "sort_order"]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["question", "is_published", "sort_order"]
    list_editable = ["is_published", "sort_order"]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "subject", "is_read", "created_at"]
    list_filter = ["is_read"]
    search_fields = ["name", "email", "subject", "message"]


@admin.register(SewOut)
class SewOutAdmin(admin.ModelAdmin):
    list_display = ["title", "client", "is_published", "sort_order"]
    list_editable = ["is_published", "sort_order"]
