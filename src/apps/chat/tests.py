import uuid

import pytest
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

from apps.chat.models import BlockedIP, ChatMessage, ChatSession
from apps.chat.routing import websocket_urlpatterns
from apps.chat.services import transcript_text

application = URLRouter(websocket_urlpatterns)


def _communicator(path, user=None, token=None, ip="203.0.113.9"):
    headers = [(b"user-agent", b"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1")]
    comm = WebsocketCommunicator(application, path, headers=headers)
    comm.scope["user"] = user or AnonymousUser()
    comm.scope["cookies"] = {"se_chat": str(token)} if token else {}
    comm.scope["client"] = (ip, 12345)
    return comm


@pytest.mark.django_db(transaction=True)
async def test_visitor_message_reaches_staff_and_reply_reaches_visitor(staff):
    token = uuid.uuid4()
    staff_ws = _communicator("/ws/console/chat/", user=staff)
    connected, _ = await staff_ws.connect()
    assert connected

    visitor = _communicator("/ws/chat/", token=token)
    connected, _ = await visitor.connect()
    assert connected

    await visitor.send_json_to(
        {
            "type": "message",
            "body": "Do you do chenille patches?",
            "name": "Guest Gary",
            "path": "/services/patches",
        }
    )
    event = await staff_ws.receive_json_from(timeout=3)
    assert event["event"] == "message"
    assert event["message"]["body"] == "Do you do chenille patches?"
    assert event["session"]["name"] == "Guest Gary"
    assert event["session"]["status"] == "waiting"

    # visitor also receives their own echo
    echo = await visitor.receive_json_from(timeout=3)
    assert echo["message"]["sender"] == "visitor"

    session_id = event["session"]["id"]
    await staff_ws.send_json_to({"type": "message", "session": session_id, "body": "Yes — from $1.25 each."})
    reply = await visitor.receive_json_from(timeout=3)
    assert reply["message"]["sender"] == "staff"
    assert reply["message"]["body"] == "Yes — from $1.25 each."

    session = await database_sync_to_async(ChatSession.objects.get)(pk=session_id)
    assert session.status == ChatSession.Status.OPEN
    assert session.device == "iPhone · Safari"
    assert session.current_page == "/services/patches"
    assert await database_sync_to_async(ChatMessage.objects.filter(session=session).count)() == 2

    await visitor.disconnect()
    await staff_ws.disconnect()


@pytest.mark.django_db(transaction=True)
async def test_non_staff_cannot_open_staff_socket(customer):
    comm = _communicator("/ws/console/chat/", user=customer)
    connected, _ = await comm.connect()
    assert not connected


@pytest.mark.django_db(transaction=True)
async def test_visitor_without_cookie_is_rejected():
    comm = _communicator("/ws/chat/")
    connected, _ = await comm.connect()
    assert not connected


@pytest.mark.django_db(transaction=True)
async def test_blocked_ip_is_rejected():
    await database_sync_to_async(BlockedIP.objects.create)(ip_address="198.51.100.7")
    comm = _communicator("/ws/chat/", token=uuid.uuid4(), ip="198.51.100.7")
    connected, _ = await comm.connect()
    assert not connected


@pytest.mark.django_db
def test_session_endpoint_sets_cookie(client):
    resp = client.get(reverse("chat:session"))
    assert resp.status_code == 200
    assert "se_chat" in resp.cookies
    assert resp.json()["messages"] == []


@pytest.mark.django_db
def test_transcript(staff):
    s = ChatSession.objects.create(name="Marcus", ip_address="72.14.201.8")
    ChatMessage.objects.create(session=s, sender="visitor", body="Sent the AI file")
    ChatMessage.objects.create(session=s, sender="staff", staff_user=staff, body="Got it")
    text = transcript_text(s)
    assert "Marcus: Sent the AI file" in text
    assert "Studio Admin: Got it" in text
