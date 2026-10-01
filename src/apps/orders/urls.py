from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.place_order, name="place"),
    path("quote/", views.place_order, {"quote": True}, name="quote"),
    path("files/<int:pk>/", views.download_file, name="download"),
    path("saved-file/<int:pk>/remove/", views.remove_saved_file, name="remove_saved_file"),
    path("<str:number>/", views.order_detail, name="detail"),
    path("<str:number>/action/", views.order_action, name="action"),
]
