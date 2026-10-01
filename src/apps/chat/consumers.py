import json
import uuid

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.core.utils import describe_device, get_client_ip, rate_limited

from . import services
from .models import ChatSession

VISITOR_COOKIE = "se_chat"


def scope_meta(scope):
    """Translate ASGI headers/client into a request.META-like dict."""
    headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])}
    meta = {
        "HTTP_X_FORWARDED_FOR": headers.get("x-forwarded-for", ""),
        "HTTP_X_REAL_IP": headers.get("x-real-ip", ""),
        "HTTP_USER_AGENT": headers.get("user-agent", ""),
        "HTTP_CF_IPCOUNTRY": headers.get("cf-ipcountry", ""),
        "REMOTE_ADDR": (scope.get("client") or [None])[0],
    }
    return meta


class _JsonConsumer(AsyncWebsocketConsumer):
    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))

    async def chat_event(self, event):
        await self.send_json(event["payload"])

    def parse(self, text_data):
        try:
            data = json.loads(text_data or "{}")
        except ValueError:
            return None
        return data if isinstance(data, dict) else None


class VisitorChatConsumer(_JsonConsumer):
    """One WebSocket per browser tab of a site visitor, identified by the `se_chat` cookie."""

    async def connect(self):
        self.meta = scope_meta(self.scope)
        self.ip = get_client_ip(self.meta)
        token = self.scope.get("cookies", {}).get(VISITOR_COOKIE)
        try:
            self.token = uuid.UUID(token) if token else None
        except ValueError:
            self.token = None
        if self.token is None or await database_sync_to_async(services.is_blocked)(self.ip):
            await self.close(code=4403)
            return
        self.group = f"chat_visitor_{self.token.hex}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if getattr(self, "group", None):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        data = self.parse(text_data)
        if not data:
            return
        kind = data.get("type")
        if kind == "page":
            await self.track_page(str(data.get("path", ""))[:300], str(data.get("referrer", ""))[:300])
        elif kind == "message":
            limited = await database_sync_to_async(rate_limited)(f"chatmsg:{self.token.hex}", 20, 60)
            if limited:
                await self.send_json({"event": "error", "error": "You're sending messages too quickly."})
                return
            await self.post_message(
                body=str(data.get("body", "")),
                name=str(data.get("name", ""))[:120],
                email=str(data.get("email", ""))[:254],
                path=str(data.get("path", ""))[:300],
                referrer=str(data.get("referrer", ""))[:300],
            )

    @database_sync_to_async
    def track_page(self, path, referrer):
        session = ChatSession.objects.filter(token=self.token).first()
        if session:
            session.current_page = path
            session.pages_viewed += 1
            if referrer and not session.referrer:
                session.referrer = referrer
            session.save(update_fields=["current_page", "pages_viewed", "referrer"])
            services._publish_after_commit(session)  # noqa: SLF001 - pushes updated visitor details to staff

    @database_sync_to_async
    def post_message(self, body, name, email, path, referrer):
        user = self.scope.get("user")
        session, created = ChatSession.objects.get_or_create(
            token=self.token,
            defaults={
                "ip_address": self.ip,
                "user_agent": self.meta["HTTP_USER_AGENT"][:400],
                "device": describe_device(self.meta["HTTP_USER_AGENT"]),
                "country": self.meta["HTTP_CF_IPCOUNTRY"][:60],
                "current_page": path,
                "referrer": referrer,
                "pages_viewed": 1,
            },
        )
        changed = []
        if user is not None and user.is_authenticated and session.user_id is None:
            session.user = user
            changed.append("user")
        if name and not session.name:
            session.name = name
            changed.append("name")
        if email and not session.email:
            session.email = email
            changed.append("email")
        if changed:
            session.save(update_fields=changed)
        return services.post_visitor_message(session, body)


class StaffChatConsumer(_JsonConsumer):
    """Admin console socket: receives every chat event, sends replies."""

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated or not user.is_staff:
            await self.close(code=4401)
            return
        await self.channel_layer.group_add(services.STAFF_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(services.STAFF_GROUP, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        data = self.parse(text_data)
        if not data or data.get("type") != "message":
            return
        try:
            session_id = int(data.get("session"))
        except (TypeError, ValueError):
            return
        ok = await self.reply(session_id, str(data.get("body", "")))
        if not ok:
            await self.send_json({"event": "error", "error": "Conversation not found."})

    @database_sync_to_async
    def reply(self, session_id, body):
        session = ChatSession.objects.filter(pk=session_id).first()
        if session is None:
            return False
        services.post_staff_message(session, self.scope["user"], body)
        return True
