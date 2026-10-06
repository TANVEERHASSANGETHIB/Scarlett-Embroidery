from decimal import Decimal

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.services import issue_verification_code
from apps.core.models import SiteSettings
from apps.orders.models import Order, OrderDraft, OrderFile, PatchDetail, Service
from apps.orders.pricing import compute_estimate

pytestmark = pytest.mark.django_db


def test_flat_pricing(pricing):
    t, ta, p = pricing["tiers"], pricing["turnarounds"], pricing["patches"]
    assert compute_estimate(Service.DIGITIZING, tier=t["left_chest"], turnaround=ta["standard"]) == Decimal(
        "6.00"
    )
    assert compute_estimate(Service.DIGITIZING, tier=t["full_back"], turnaround=ta["standard"]) == Decimal(
        "10.00"
    )
    assert compute_estimate(Service.DIGITIZING, tier=t["complex"], turnaround=ta["rush"]) == Decimal("18.00")
    assert compute_estimate(Service.PATCHES, patch_category=p["iron"], quantity=100) == Decimal("110.00")
    assert compute_estimate(Service.PATCHES) is None


def _digitizing_payload(pricing, make_file, **extra):
    data = {
        "service": "digitizing",
        "contact_name": "Jane Whitfield",
        "contact_email": "jane@shop.com",
        "design_name": "Whitfield crest",
        "tier": pricing["tiers"]["full_back"].pk,
        "turnaround": pricing["turnarounds"]["rush"].pk,
        "fabric": "Cotton twill",
        "placement": "Full back",
        "height_in": "10",
        "width_in": "11",
        "embroidery_formats": ["DST", "PES"],
        "instructions": "Madeira 1147",
        "artwork": [make_file("crest.png"), make_file("crest.ai")],
    }
    data.update(extra)
    return data


def _patch_payload(pricing, make_file, **extra):
    data = {
        "service": "patches",
        "contact_name": "Jane Whitfield",
        "contact_email": "jane@shop.com",
        "design_name": "Varsity patch",
        "instructions": "Gold border, merrowed edge",
        "artwork": [make_file("patch.png")],
        "patch-category": pricing["patches"]["rubber"].pk,
        "patch-backing": PatchDetail.Backing.VELCRO,
        "patch-quantity": "100",
        "patch-width_in": "3.5",
        "patch-height_in": "3",
        "patch-shipping_name": "Jane Whitfield",
        "patch-address_line1": "12 Loom St",
        "patch-city": "Austin",
        "patch-state": "TX",
        "patch-postal_code": "78701",
        "patch-country": "United States",
    }
    data.update(extra)
    return data


def test_order_page_is_open_to_everyone(client):
    """Guests may browse and fill the form; signing in is only needed to send it."""
    resp = client.get(reverse("orders:place"))
    assert resp.status_code == 200


def test_place_digitizing_order(client, customer, pricing, artwork, django_capture_on_commit_callbacks):
    client.force_login(customer)
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))
    assert resp.status_code == 302, resp.content
    order = Order.objects.get()
    assert order.number.startswith("SE-")
    assert order.estimate == Decimal("13.00")  # $10 full back + $3 rush
    assert order.formats == ["DST", "PES"]
    assert order.due_at is not None
    assert order.files.filter(kind=OrderFile.Kind.ARTWORK).count() == 2
    assert order.events.count() == 1
    details = next(m for m in mail.outbox if "Order details" in m.subject)
    notice = next(m for m in mail.outbox if "New order received" in m.subject)
    assert details.to == ["scarletsembroidery@gmail.com"]
    assert details.reply_to == ["jane@shop.com"]
    assert "Jane Whitfield" in details.body
    assert "Full back" in details.body
    assert "DST, PES" in details.body
    assert "table" in details.alternatives[0][0]
    assert "padding:4px 8px" in details.alternatives[0][0]
    assert [attachment[0] for attachment in details.attachments] == ["crest.png", "crest.ai"]
    assert notice.to == ["info@sedigitizer.com"]
    assert notice.body.count("Jane Whitfield") == 0
    assert notice.body.count("crest.png") == 0
    assert {m.to[0] for m in mail.outbox if m.to != ["jane@shop.com"]} == {
        "scarletsembroidery@gmail.com",
        "info@sedigitizer.com",
    }


def test_digitizing_order_requires_tier_and_formats(client, customer, pricing, artwork):
    client.force_login(customer)
    payload = _digitizing_payload(pricing, artwork, tier="", embroidery_formats=[])
    resp = client.post(reverse("orders:place"), payload)
    assert resp.status_code == 200
    assert Order.objects.count() == 0
    assert b"Choose a design type" in resp.content
    assert b"Pick at least one file format" in resp.content


def test_tier_must_match_service(client, customer, pricing, artwork):
    client.force_login(customer)
    payload = _digitizing_payload(pricing, artwork, tier=pricing["tiers"]["vector"].pk)
    resp = client.post(reverse("orders:place"), payload)
    assert resp.status_code == 200
    assert Order.objects.count() == 0


def test_place_patch_order_collects_address_category_and_instructions(client, customer, pricing, artwork):
    client.force_login(customer)
    resp = client.post(reverse("orders:place"), _patch_payload(pricing, artwork))
    assert resp.status_code == 302, resp.content
    order = Order.objects.get()
    assert order.service == Service.PATCHES
    assert order.tier is None and order.turnaround is None
    assert order.instructions == "Gold border, merrowed edge"
    patch = order.patch
    assert patch.category.name == "Rubber patch"
    assert patch.backing == PatchDetail.Backing.VELCRO
    assert patch.quantity == 100
    assert patch.city == "Austin"
    assert order.estimate == Decimal("160.00")


def test_patch_order_validates_minimum_and_address(client, customer, pricing, artwork):
    client.force_login(customer)
    payload = _patch_payload(pricing, artwork, **{"patch-quantity": "10", "patch-address_line1": ""})
    resp = client.post(reverse("orders:place"), payload)
    assert resp.status_code == 200
    assert Order.objects.count() == 0
    assert b"minimum order is 50" in resp.content


def test_rejects_disallowed_file_type(client, customer, pricing, artwork):
    client.force_login(customer)
    payload = _digitizing_payload(pricing, artwork, artwork=[artwork("evil.exe")])
    resp = client.post(reverse("orders:place"), payload)
    assert resp.status_code == 200
    assert Order.objects.count() == 0


def test_customers_cannot_see_each_others_orders_or_files(client, customer, other_customer, pricing, artwork):
    client.force_login(customer)
    client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))
    order = Order.objects.get()
    f = order.files.first()

    client.force_login(other_customer)
    assert client.get(reverse("orders:detail", args=[order.number])).status_code == 404
    assert client.get(reverse("orders:download", args=[f.pk])).status_code == 404

    client.force_login(customer)
    assert client.get(reverse("orders:detail", args=[order.number])).status_code == 200
    assert client.get(reverse("orders:download", args=[f.pk])).status_code == 200


def test_customer_approves_proof(client, customer, pricing, artwork):
    client.force_login(customer)
    client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))
    order = Order.objects.get()

    resp = client.post(reverse("orders:action", args=[order.number]), {"action": "approve"})
    order.refresh_from_db()
    assert order.status == Order.Status.PENDING  # nothing to approve yet

    Order.objects.filter(pk=order.pk).update(status=Order.Status.AWAITING_APPROVAL)
    resp = client.post(reverse("orders:action", args=[order.number]), {"action": "approve"})
    assert resp.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.APPROVED


def test_customer_requests_revision(client, customer, pricing, artwork):
    client.force_login(customer)
    client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))
    order = Order.objects.get()
    Order.objects.filter(pk=order.pk).update(status=Order.Status.AWAITING_APPROVAL)
    client.post(
        reverse("orders:action", args=[order.number]), {"action": "revision", "message": "Thicker outline"}
    )
    order.refresh_from_db()
    assert order.status == Order.Status.REVISION
    assert order.events.filter(message="Thicker outline").exists()


def test_order_details_and_new_order_notice_use_separate_recipients(
    client, customer, pricing, artwork, django_capture_on_commit_callbacks
):
    site = SiteSettings.load()
    site.order_details_emails = "shop@gmail.com, manager@shop.com"
    site.order_notification_emails = "info@shop.com"
    site.save()

    client.force_login(customer)
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))

    details = next(m for m in mail.outbox if "Order details" in m.subject)
    notice = next(m for m in mail.outbox if "New order received" in m.subject)
    assert details.to == ["shop@gmail.com", "manager@shop.com"]
    assert details.reply_to == ["jane@shop.com"]  # replying reaches the customer
    assert notice.to == ["info@shop.com"]
    order = Order.objects.get()
    assert order.number in details.subject and order.design_name in details.body
    assert order.design_name not in notice.body


def test_short_notice_can_be_switched_off_without_suppressing_order_details(
    client, customer, pricing, artwork, django_capture_on_commit_callbacks
):
    site = SiteSettings.load()
    site.notify_on_new_order = False
    site.order_notification_emails = "shop@gmail.com"
    site.save()

    client.force_login(customer)
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))

    assert not [m for m in mail.outbox if "New order received" in m.subject]
    assert [m for m in mail.outbox if "Order details" in m.subject]
    assert [m for m in mail.outbox if m.to == ["jane@shop.com"]]  # customer still gets their copy


def test_patch_order_alert_includes_address_and_patch_details(
    client, customer, pricing, artwork, django_capture_on_commit_callbacks
):
    site = SiteSettings.load()
    site.order_notification_emails = "shop@gmail.com"
    site.save()

    client.force_login(customer)
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("orders:place"), _patch_payload(pricing, artwork))

    details = next(m for m in mail.outbox if "Order details" in m.subject)
    assert "Rubber patch" in details.body
    assert "12 Loom St" in details.body
    assert "Gold border, merrowed edge" in details.body
    notice = next(m for m in mail.outbox if "New order received" in m.subject)
    assert "12 Loom St" not in notice.body


# ── Guests: fill in first, sign in to send ───────────────
def test_guests_can_open_the_order_form(client):
    resp = client.get(reverse("orders:place"))
    assert resp.status_code == 200
    assert b"sign in when you send it" in resp.content


def test_guest_submission_is_saved_and_asks_them_to_sign_in(client, pricing, artwork):
    resp = client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))

    assert resp.status_code == 200
    assert Order.objects.count() == 0  # nothing is ordered until they sign in
    body = resp.content.decode()
    assert "Sign in to send your order" in body
    assert "/account/login/?next=" in body and "/account/signup/?next=" in body

    draft = OrderDraft.objects.get()
    assert draft.data["design_name"] == "Whitfield crest"
    assert draft.data["tier"] == str(pricing["tiers"]["full_back"].pk)
    assert draft.data["embroidery_formats"] == ["DST", "PES"]
    assert [f.original_name for f in draft.files.all()] == ["crest.png", "crest.ai"]
    assert client.session["order_draft_id"] == draft.pk


def test_draft_is_restored_after_signing_in(client, customer, pricing, artwork):
    client.post(reverse("orders:place"), _patch_payload(pricing, artwork))
    assert OrderDraft.objects.count() == 1

    client.force_login(customer)  # session (and so the draft) survives signing in
    body = client.get(reverse("orders:place")).content.decode()

    assert "we kept your order exactly as you left it" in body
    assert 'value="Varsity patch"' in body
    assert 'value="12 Loom St"' in body
    assert 'value="100"' in body
    assert "Gold border, merrowed edge" in body
    assert "patch.png" in body  # the file they attached is still on the order
    assert "Sign in to send your order" in body  # markup present…
    assert "data-login-gate hidden" in body  # …but the dialog stays closed


def test_saved_artwork_is_used_when_the_order_is_finally_placed(
    client, customer, pricing, artwork, django_capture_on_commit_callbacks
):
    client.post(reverse("orders:place"), _patch_payload(pricing, artwork))
    client.force_login(customer)

    payload = _patch_payload(pricing, artwork)
    payload.pop("artwork")  # they don't re-pick the file
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(reverse("orders:place"), payload)

    assert resp.status_code == 302
    order = Order.objects.get()
    assert [f.original_name for f in order.files.all()] == ["patch.png"]
    assert order.files.first().file.read().startswith(bytes([0x89]))  # the real bytes moved across
    assert order.patch.address_line1 == "12 Loom St"
    assert OrderDraft.objects.count() == 0  # draft cleared once the order exists


def test_one_visitor_cannot_see_another_visitors_draft(client, pricing, artwork):
    client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))
    assert OrderDraft.objects.count() == 1

    other = Client()
    body = other.get(reverse("orders:place")).content.decode()
    assert 'value="Whitfield crest"' not in body  # the placeholder text is not a value
    assert "crest.png" not in body
    assert "we kept your order exactly as you left it" not in body


def test_guest_can_remove_a_saved_file(client, pricing, artwork):
    client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))
    draft = OrderDraft.objects.get()
    first = draft.files.first()

    resp = client.post(reverse("orders:remove_saved_file", args=[first.pk]))
    assert resp.status_code == 302
    assert [f.original_name for f in draft.files.all()] == ["crest.ai"]

    other = Client()
    assert other.post(reverse("orders:remove_saved_file", args=[draft.files.first().pk])).status_code == 404


def test_signed_in_users_never_see_the_gate(client, customer, pricing, artwork):
    client.force_login(customer)
    body = client.get(reverse("orders:place")).content.decode()
    assert "sign in when you send it" not in body


def test_draft_keeps_the_visitors_own_contact_details(client, customer, pricing, artwork):
    payload = _digitizing_payload(pricing, artwork)
    payload["contact_email"] = "different@shop.com"
    payload["contact_name"] = "Someone Else"
    client.post(reverse("orders:place"), payload)

    client.force_login(customer)
    body = client.get(reverse("orders:place")).content.decode()
    assert 'value="different@shop.com"' in body  # what they typed wins over the account default
    assert 'value="Someone Else"' in body


def test_expired_drafts_are_purged(client, pricing, artwork, settings):
    from datetime import timedelta

    from django.utils import timezone

    from apps.orders import drafts as drafts_module

    client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))
    draft = OrderDraft.objects.get()
    OrderDraft.objects.filter(pk=draft.pk).update(
        updated_at=timezone.now() - timedelta(days=drafts_module.DRAFT_TTL_DAYS + 1)
    )

    drafts_module.purge_expired()
    assert OrderDraft.objects.count() == 0


def test_unverified_signup_keeps_the_draft_through_verification(client, pricing, artwork):
    client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))
    client.post(
        reverse("accounts:signup"),
        {"full_name": "Guest Gary", "email": "gary@shop.com", "password": "Str0ng-pass!", "next": "/order/"},
    )
    user = User.objects.get(email="gary@shop.com")
    code = issue_verification_code(user)
    resp = client.post(reverse("accounts:verify"), {"code": code, "next": "/order/"})

    assert resp.status_code == 302
    assert resp.url == "/order/"
    body = client.get(reverse("orders:place")).content.decode()
    assert "we kept your order exactly as you left it" in body
    assert "crest.png" in body
