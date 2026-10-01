from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("portfolio/", views.portfolio, name="portfolio"),
    path("services/", views.services, name="services"),
    path("services/<slug:slug>/", views.service_page, name="service"),
    path("testimonials/", views.testimonials, name="testimonials"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("privacy-policy/", views.legal, {"page": "privacy"}, name="privacy"),
    path("terms-and-conditions/", views.legal, {"page": "terms"}, name="terms"),
    path("healthz/", views.health, name="health"),
]
