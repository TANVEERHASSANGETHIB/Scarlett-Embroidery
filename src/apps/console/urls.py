from django.urls import path

from . import views

app_name = "console"

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.console_login, name="login"),
    path("logout/", views.console_logout, name="logout"),
    path("theme/", views.set_theme, name="set_theme"),
    path("chat/", views.chat, name="chat"),
    path("chat/<int:pk>/action/", views.chat_action, name="chat_action"),
    path("chat/<int:pk>/transcript/", views.chat_transcript, name="chat_transcript"),
    path("orders/", views.orders, name="orders"),
    path("orders/<str:number>/", views.order_detail, name="order_detail"),
    path("customers/", views.customers, name="customers"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("inbox/", views.inbox, name="inbox"),
    path("portfolio/", views.portfolio, name="portfolio"),
    path("portfolio/<int:pk>/", views.portfolio, name="portfolio_edit"),
    path("testimonials/", views.testimonials, name="testimonials"),
    path("testimonials/<int:pk>/", views.testimonials, name="testimonial_edit"),
    path("blogs/", views.blogs, name="blogs"),
    path("blogs/<int:pk>/", views.blogs, name="blog_edit"),
    path("settings/", views.settings_view, name="settings"),
]
