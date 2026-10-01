from django.contrib import admin

from .models import BlockedIP, ChatMessage, ChatSession


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ["sender", "staff_user", "body", "created_at"]


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ["__str__", "email", "ip_address", "status", "assigned_to", "last_message_at"]
    list_filter = ["status"]
    search_fields = ["name", "email", "ip_address"]
    inlines = [ChatMessageInline]


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ["ip_address", "reason", "created_by", "created_at"]
