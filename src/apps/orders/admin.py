from django.contrib import admin

from .models import Order, OrderEvent, OrderFile, PatchCategory, PatchDetail, PricingTier, TurnaroundOption


@admin.register(PricingTier)
class PricingTierAdmin(admin.ModelAdmin):
    list_display = ["name", "service", "price", "is_active", "sort_order"]
    list_filter = ["service", "is_active"]
    list_editable = ["price", "is_active", "sort_order"]


@admin.register(TurnaroundOption)
class TurnaroundOptionAdmin(admin.ModelAdmin):
    list_display = ["name", "hours", "surcharge", "is_default", "is_active", "sort_order"]
    list_editable = ["hours", "surcharge", "is_default", "is_active", "sort_order"]


@admin.register(PatchCategory)
class PatchCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "unit_price", "is_active", "sort_order"]
    list_editable = ["unit_price", "is_active", "sort_order"]


class PatchDetailInline(admin.StackedInline):
    model = PatchDetail
    extra = 0


class OrderFileInline(admin.TabularInline):
    model = OrderFile
    extra = 0
    readonly_fields = ["original_name", "size", "uploaded_by", "created_at"]


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ["actor", "kind", "message", "is_internal", "created_at"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "customer",
        "service",
        "design_name",
        "status",
        "payment_status",
        "estimate",
        "final_price",
        "created_at",
    ]
    list_filter = ["service", "status", "payment_status"]
    search_fields = ["number", "design_name", "customer__email", "customer__company"]
    readonly_fields = ["number", "created_at", "updated_at"]
    inlines = [PatchDetailInline, OrderFileInline, OrderEventInline]
