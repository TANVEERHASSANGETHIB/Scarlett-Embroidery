from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("session/", views.visitor_session, name="session"),
]
