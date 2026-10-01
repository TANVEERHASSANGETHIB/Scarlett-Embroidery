"""The quote-request page: same questions as an order, but no prices shown or stored."""

import pytest
from django.core import mail
from django.urls import reverse

from apps.orders.models import Order, OrderDraft
from apps.orders.tests import _digitizing_payload, _patch_payload

pytestmark = pytest.mark.django_db


def test_quote_page_is_open_and_hides_every_price(client, pricing):
    resp = client.get(reverse("orders:quote"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Get a quote" in body and "Request my quote" in body
    assert "Estimate" not in body
    assert "$6" not in body and "$10" not in body and "1.10" not in body and "1.60" not in body
    # The JSON the page script reads carries no prices either.
    for hidden in ('"price"', '"surcharge"', '"unitPrice"'):
        assert hidden not in body


def test_order_page_still_shows_prices(client, pricing):
    body = client.get(reverse("orders:place")).content.decode()
    assert "$6" in body and "Estimate" in body


def test_quote_request_is_saved_without_an_estimate(
    client, customer, pricing, artwork, django_capture_on_commit_callbacks
):
    client.force_login(customer)
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(reverse("orders:quote"), _digitizing_payload(pricing, artwork))
    assert resp.status_code == 302
    order = Order.objects.get()
    assert order.is_quote and order.number.startswith("QT-")
    assert order.estimate is None and order.final_price is None
    assert order.files.count() == 2
    subjects = " | ".join(m.subject for m in mail.outbox)
    assert "Quote request" in subjects and "quote request" in subjects.lower()
    customer_mail = next(m for m in mail.outbox if m.to == ["jane@shop.com"])
    assert "$" not in customer_mail.body


def test_patch_quote_asks_for_category_address_and_instructions(client, customer, pricing, artwork):
    body = client.get(reverse("orders:quote")).content.decode()
    for needle in ("patch-category", "Iron-on patch", "Shipping address", "Additional instructions"):
        assert needle in body
    client.force_login(customer)
    resp = client.post(reverse("orders:quote"), _patch_payload(pricing, artwork))
    assert resp.status_code == 302
    order = Order.objects.get()
    assert order.is_quote and order.patch.category == pricing["patches"]["rubber"]
    assert order.patch.address_line1 == "12 Loom St"
    assert order.instructions == "Gold border, merrowed edge"


def test_guest_quote_is_parked_and_returns_to_the_quote_page(client, pricing, artwork):
    resp = client.post(reverse("orders:quote"), _digitizing_payload(pricing, artwork))
    assert resp.status_code == 200
    assert OrderDraft.objects.count() == 1 and Order.objects.count() == 0
    body = resp.content.decode()
    assert "quote request" in body
    assert "next=%2Forder%2Fquote%2F" in body


def test_customer_list_has_no_status_column(client, customer, pricing, artwork):
    client.force_login(customer)
    client.post(reverse("orders:place"), _digitizing_payload(pricing, artwork))
    body = client.get(reverse("accounts:dashboard")).content.decode()
    table = body[body.index("<thead>") : body.index("</table>")]
    assert "Status" not in table
    for word in ("In queue", "Delivered", "Unpaid", "Paid", "Pending"):
        assert word not in table
