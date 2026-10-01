"""Chat operations shared by the WebSocket consumers and the console HTTP views."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from .models import BlockedIP, ChatMessage, ChatSession

STAFF_GROUP = "chat_staff"
MAX_MESSAGE_LENGTH = 2000


def is_blocked(ip):
    return bool(ip) and BlockedIP.objects.filter(ip_address=ip).exists()


def broadcast(group, payload):
    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.group_send)(group, {"type": "chat.event", "payload": payload})


def _publish_after_commit(session, message=None):
    def send():
        session.refresh_from_db()
        summary = session.summary()
        if message is not None:
            data = message.as_dict()
            broadcast(session.group_name, {"event": "message", "message": data})
            broadcast(STAFF_GROUP, {"event": "message", "message": data, "session": summary})
        else:
            broadcast(STAFF_GROUP, {"event": "session", "session": summary})
            broadcast(session.group_name, {"event": "status", "status": session.status})

    transaction.on_commit(send)


@transaction.atomic
def post_visitor_message(session, body):
    body = (body or "").strip()[:MAX_MESSAGE_LENGTH]
    if not body:
        return None
    message = ChatMessage.objects.create(session=session, sender=ChatMessage.Sender.VISITOR, body=body)
    session.last_message_at = message.created_at
    fields = ["last_message_at"]
    if session.status == ChatSession.Status.RESOLVED:
        session.status = ChatSession.Status.WAITING
        fields.append("status")
    session.save(update_fields=fields)
    _publish_after_commit(session, message)
    return message


@transaction.atomic
def post_staff_message(session, staff_user, body):
    body = (body or "").strip()[:MAX_MESSAGE_LENGTH]
    if not body:
        return None
    message = ChatMessage.objects.create(
        session=session, sender=ChatMessage.Sender.STAFF, staff_user=staff_user, body=body
    )
    session.last_message_at = message.created_at
    session.status = ChatSession.Status.OPEN
    if session.assigned_to_id is None:
        session.assigned_to = staff_user
    session.save(update_fields=["last_message_at", "status", "assigned_to"])
    _publish_after_commit(session, message)
    return message


@transaction.atomic
def set_session_status(session, status):
    session.status = status
    session.save(update_fields=["status"])
    _publish_after_commit(session)


@transaction.atomic
def assign_session(session, staff_user):
    session.assigned_to = staff_user
    if session.status == ChatSession.Status.WAITING:
        session.status = ChatSession.Status.OPEN
    session.save(update_fields=["assigned_to", "status"])
    _publish_after_commit(session)


def transcript_text(session):
    lines = [
        f"Chat transcript — {session.display_name}",
        f"Email: {session.contact_email or '—'}  IP: {session.ip_address or '—'}",
        f"Started: {timezone.localtime(session.created_at):%Y-%m-%d %H:%M %Z}",
        "",
    ]
    for m in session.messages.select_related("staff_user"):
        who = (
            session.display_name
            if m.sender == ChatMessage.Sender.VISITOR
            else (m.staff_user.get_full_name() if m.staff_user_id else "System")
        )
        lines.append(f"[{timezone.localtime(m.created_at):%Y-%m-%d %H:%M}] {who}: {m.body}")
    return "\n".join(lines) + "\n"
