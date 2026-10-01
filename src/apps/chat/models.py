import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ChatSession(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_sessions",
    )
    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=60, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)
    device = models.CharField(max_length=60, blank=True)
    current_page = models.CharField(max_length=300, blank=True)
    referrer = models.CharField(max_length=300, blank=True)
    pages_viewed = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WAITING, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_chats",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"{self.display_name} ({self.get_status_display()})"

    @property
    def display_name(self):
        if self.user_id:
            return self.user.full_name or self.user.email
        return self.name or "Guest"

    @property
    def contact_email(self):
        if self.user_id:
            return self.user.email
        return self.email

    @property
    def last_message(self):
        return self.messages.order_by("-created_at").first()

    @property
    def group_name(self):
        return f"chat_visitor_{self.token.hex}"

    def summary(self):
        last = self.last_message
        return {
            "id": self.pk,
            "name": self.display_name,
            "email": self.contact_email or "—",
            "ip": self.ip_address or "—",
            "status": self.status,
            "statusLabel": self.get_status_display(),
            "page": self.current_page or "—",
            "preview": last.body[:120] if last else "",
            "time": timezone.localtime(self.last_message_at).strftime("%H:%M"),
            "assignedTo": self.assigned_to.full_name if self.assigned_to_id else "",
        }


class ChatMessage(models.Model):
    class Sender(models.TextChoices):
        VISITOR = "visitor", "Visitor"
        STAFF = "staff", "Staff"
        SYSTEM = "system", "System"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=10, choices=Sender.choices)
    staff_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender}: {self.body[:40]}"

    def as_dict(self):
        who = (
            "You"
            if self.sender == self.Sender.VISITOR
            else (self.staff_user.get_short_name() if self.staff_user_id else "Scarlett Embroidery")
        )
        return {
            "id": self.pk,
            "session": self.session_id,
            "sender": self.sender,
            "body": self.body,
            "who": who,
            "time": timezone.localtime(self.created_at).strftime("%H:%M"),
        }


class BlockedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    reason = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "blocked IP"
        verbose_name_plural = "blocked IPs"

    def __str__(self):
        return self.ip_address
