"""Client sew-out gallery on the testimonials page."""

import pytest
from django.urls import reverse

from apps.core.models import SewOut

pytestmark = pytest.mark.django_db


def test_sewouts_console_requires_staff(client, customer, staff):
    assert client.get(reverse("console:sewouts")).status_code == 302
    client.force_login(customer)
    assert client.get(reverse("console:sewouts")).status_code == 302
    client.force_login(staff)
    assert client.get(reverse("console:sewouts")).status_code == 200


def test_staff_adds_sewout_and_it_shows_publicly(client, staff, image_file):
    client.force_login(staff)
    resp = client.post(
        reverse("console:sewouts"),
        {
            "image": image_file("s.png"),
            "title": "Polo logo",
            "client": "Stitch Perfect",
            "is_published": "on",
        },
    )
    assert resp.status_code == 302, resp.context["form"].errors
    assert SewOut.objects.get().title == "Polo logo"
    client.logout()
    body = client.get(reverse("core:testimonials")).content.decode()
    assert "Polo logo" in body and "data-lightbox" in body


def test_hidden_sewout_is_not_public_and_can_be_deleted(client, staff, image_file):
    s = SewOut.objects.create(image=image_file("s.png"), title="Secret", is_published=False)
    assert "Secret" not in client.get(reverse("core:testimonials")).content.decode()
    client.force_login(staff)
    client.post(reverse("console:sewouts"), {"action": "delete", "id": s.pk})
    assert not SewOut.objects.exists()
