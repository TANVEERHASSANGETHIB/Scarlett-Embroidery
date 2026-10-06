"""Media page, testimonial photos and the pictures they put on the public site."""

import pytest
from django.urls import reverse

from apps.core.models import BeforeAfter, ServiceImage, SiteImage, Testimonial

pytestmark = pytest.mark.django_db


def test_media_page_requires_staff(client, customer, staff):
    assert client.get(reverse("console:media")).status_code == 302
    client.force_login(customer)
    assert client.get(reverse("console:media")).status_code == 302
    client.force_login(staff)
    assert client.get(reverse("console:media")).status_code == 200


def test_service_pages_show_the_slider_only_for_embroidery_and_vector(client):
    for slug in ("embroidery", "vector"):
        body = client.get(reverse("core:service", args=[slug])).content.decode()
        assert "data-before-after" in body and "ba-range" in body
    assert "data-before-after" not in client.get(reverse("core:service", args=["patches"])).content.decode()


def test_admin_before_after_replaces_the_demo_artwork(client, staff, image_file):
    client.force_login(staff)
    resp = client.post(
        reverse("console:media"),
        {
            "action": "before_after",
            "service": "embroidery",
            "before_image": image_file("b.png"),
            "after_image": image_file("a.png"),
            "before_label": "Sketch",
            "after_label": "Sewn",
            "is_active": "on",
        },
    )
    assert resp.status_code == 302
    pair = BeforeAfter.objects.get(service="embroidery")
    body = client.get(reverse("core:service", args=["embroidery"])).content.decode()
    assert pair.before_image.url in body and pair.after_image.url in body
    assert "Sketch" in body and "Sewn" in body
    assert "embroidery-before.svg" not in body

    # Saving again replaces rather than duplicating, and a photo can be left empty to keep it.
    client.post(
        reverse("console:media"),
        {
            "action": "before_after",
            "service": "embroidery",
            "after_image": image_file("a2.png"),
            "is_active": "on",
        },
    )
    assert BeforeAfter.objects.filter(service="embroidery").count() == 1


def test_before_after_needs_both_photos_the_first_time(client, staff, image_file):
    client.force_login(staff)
    resp = client.post(
        reverse("console:media"),
        {"action": "before_after", "service": "vector", "before_image": image_file("b.png")},
    )
    assert resp.status_code == 200 and not BeforeAfter.objects.exists()


def test_patches_cannot_have_a_slider(client, staff, image_file):
    client.force_login(staff)
    client.post(
        reverse("console:media"),
        {
            "action": "before_after",
            "service": "patches",
            "before_image": image_file(),
            "after_image": image_file(),
        },
    )
    assert not BeforeAfter.objects.exists()


def test_service_pictures_upload_and_show_in_sections(client, staff, image_file):
    client.force_login(staff)
    client.post(
        reverse("console:media"),
        {
            "action": "service_images",
            "service": "vector",
            "images": [image_file(f"p{i}.png") for i in range(4)],
            "caption": "Logo rebuild",
        },
    )
    assert ServiceImage.objects.filter(service="vector").count() == 4
    body = client.get(reverse("core:service", args=["vector"])).content.decode()
    assert body.count("/media/services/") >= 4  # two feature sections + gallery
    hidden = ServiceImage.objects.first()
    client.post(reverse("console:media"), {"action": "service_image_toggle", "id": hidden.pk})
    client.post(reverse("console:media"), {"action": "service_image_delete", "id": hidden.pk})
    assert ServiceImage.objects.count() == 3


def test_site_photo_shows_on_the_about_page(client, staff, image_file):
    assert "/media/site/" not in client.get(reverse("core:about")).content.decode()
    client.force_login(staff)
    client.post(
        reverse("console:media"), {"action": "site_image", "slot": "about_hero", "image": image_file("h.png")}
    )
    assert "/media/site/" in client.get(reverse("core:about")).content.decode()
    # Setting the same slot again replaces it.
    client.post(
        reverse("console:media"),
        {"action": "site_image", "slot": "about_hero", "image": image_file("h2.png")},
    )
    assert SiteImage.objects.filter(slot="about_hero").count() == 1


def test_services_overview_hero_photo_is_admin_managed(client, staff, image_file):
    assert "/media/site/" not in client.get(reverse("core:services")).content.decode()
    client.force_login(staff)
    media_page = client.get(reverse("console:media")).content.decode()
    assert "Services — overview hero photo" in media_page
    assert "1200 × 900 px" in media_page

    client.post(
        reverse("console:media"),
        {"action": "site_image", "slot": "services_hero", "image": image_file("services.png")},
    )
    hero = SiteImage.objects.get(slot="services_hero")
    body = client.get(reverse("core:services")).content.decode()
    assert hero.image.url in body


def test_non_images_are_refused(client, staff, artwork):
    client.force_login(staff)
    resp = client.post(
        reverse("console:media"),
        {"action": "site_image", "slot": "about_hero", "image": artwork("evil.exe", b"MZ")},
    )
    assert resp.status_code == 200 and not SiteImage.objects.exists()


def test_testimonial_photo_is_saved_and_displayed(client, staff, image_file):
    client.force_login(staff)
    client.post(
        reverse("console:testimonials"),
        {
            "quote": "Great",
            "name": "Sam",
            "rating": 5,
            "sort_order": 1,
            "is_published": "on",
            "image": image_file("sam.png"),
        },
    )
    review = Testimonial.objects.get()
    assert review.image
    for url in ("core:home", "core:testimonials"):
        assert review.image.url in client.get(reverse(url)).content.decode()


def test_chat_launcher_is_an_icon_not_text(client):
    body = client.get(reverse("core:home")).content.decode()
    launcher = body[body.index("chat-launch") : body.index("</button>", body.index("chat-launch"))]
    assert "<svg" in launcher and "Live chat <" not in launcher


def test_site_uses_poppins(client):
    css = (__import__("pathlib").Path(__file__).resolve().parents[2] / "static/css/site.css").read_text()
    assert '--f-body: "Poppins", sans-serif;' in css and "Barlow" not in css
