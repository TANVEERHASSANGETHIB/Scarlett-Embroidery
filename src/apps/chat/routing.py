from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/chat/", consumers.VisitorChatConsumer.as_asgi()),
    path("ws/console/chat/", consumers.StaffChatConsumer.as_asgi()),
]
