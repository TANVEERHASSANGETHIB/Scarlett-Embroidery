from decimal import Decimal

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import PortfolioItem, SiteSettings, Testimonial
from apps.orders.models import Order, OrderFile, PricingTier

pytestmark = pytest.mark.django_db


@pytest.fixture
def order(customer, pricing):
    return Order.objects.create(
        customer=customer,
        service="digitizing",
        contact_name="Jane",
        contact_email=customer.email,
        design_name="Crest",
        tier=pricing["tiers"]["left_chest"],
        turnaround=pricing["turnarounds"]["standard"],
        formats=["DST"],
        estimate=Decimal("6.00"),
    )


@pytest.mark.parametrize(
    "name",
    [
        "console:chat",
        "console:orders",
        "console:customers",
        "console:inbox",
        "console:blogs",
        "console:settings",
    ],
)
def test_console_pages_require_staff(client, customer, staff, name):
    assert client.get(reverse(name)).status_code == 302
    client.force_login(customer)
    resp = client.get(reverse(name))
    assert resp.status_code == 302 and reverse("console:login") in resp.url
    client.force_login(staff)
    assert client.get(reverse(name)).status_code == 200


def test_customer_cannot_log_into_console(client, customer):
    resp = client.post(reverse("console:login"), {"email": customer.email, "password": "Str0ng-pass!"})
    assert resp.status_code == 200
    assert "_auth_user_id" not in client.session


def test_staff_login(client, staff):
    resp = client.post(reverse("console:login"), {"email": staff.email, "password": "Str0ng-pass!"})
    assert resp.status_code == 302


def test_staff_updates_order_and_customer_is_emailed(
    client, staff, order, django_capture_on_commit_callbacks
):
    client.force_login(staff)
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(
            reverse("console:order_detail", args=[order.number]),
            {
                "section": "update",
                "upd-status": "in_progress",
                "upd-final_price": "8.50",
                "upd-payment_status": "unpaid",
                "upd-assigned_to": staff.pk,
            },
        )
    assert resp.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.IN_PROGRESS
    assert order.final_price == Decimal("8.50")
    assert order.assigned_to == staff
    assert any(m.to == [order.contact_email] for m in mail.outbox)


def test_staff_uploads_proof_moves_to_awaiting_approval(client, staff, order):
    client.force_login(staff)
    proof = SimpleUploadedFile("proof.jpg", b"\xff\xd8\xff fake", content_type="image/jpeg")
    resp = client.post(
        reverse("console:order_detail", args=[order.number]),
        {
            "section": "upload",
            "up-kind": "proof",
            "up-files": [proof],
            "up-mark_status": "on",
        },
    )
    assert resp.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.AWAITING_APPROVAL
    assert order.files.filter(kind=OrderFile.Kind.PROOF).count() == 1


def test_staff_edits_pricing_tier(client, staff, pricing):
    client.force_login(staff)
    tiers = list(PricingTier.objects.order_by("pk"))
    data = {
        "section": "tiers",
        "tiers-TOTAL_FORMS": str(len(tiers)),
        "tiers-INITIAL_FORMS": str(len(tiers)),
        "tiers-MIN_NUM_FORMS": "0",
        "tiers-MAX_NUM_FORMS": "1000",
    }
    for i, t in enumerate(tiers):
        data.update(
            {
                f"tiers-{i}-id": t.pk,
                f"tiers-{i}-service": t.service,
                f"tiers-{i}-name": t.name,
                f"tiers-{i}-description": t.description,
                f"tiers-{i}-price": str(t.price),
                f"tiers-{i}-sort_order": t.sort_order,
                f"tiers-{i}-is_active": "on",
            }
        )
    data["tiers-0-price"] = "7.00"
    resp = client.post(reverse("console:settings"), data)
    assert resp.status_code == 302
    tiers[0].refresh_from_db()
    assert tiers[0].price == Decimal("7.00")


def test_invite_admin(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("console:settings"),
        {
            "section": "invite",
            "full_name": "New Admin",
            "email": "new@sedigitizer.com",
            "password": "An0ther-str0ng!",
        },
    )
    assert resp.status_code == 302
    new = User.objects.get(email="new@sedigitizer.com")
    assert new.is_staff and new.email_verified


def test_blog_publish(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("console:blogs"),
        {
            "title": "Choosing stabiliser by fabric",
            "body": "## Hello\n\nWorld",
            "status": "draft",
            "author_title": "Head Digitizer",
            "action": "publish",
        },
    )
    assert resp.status_code == 302
    resp = client.get(reverse("blog:detail", args=["choosing-stabiliser-by-fabric"]))
    assert resp.status_code == 200
    client.logout()
    assert client.get(reverse("blog:list")).status_code == 200


# ── Settings: notifications ──────────────────────────────
def test_settings_page_has_every_tab(client, staff):
    client.force_login(staff)
    html = client.get(reverse("console:settings")).content.decode()
    for label in ["Pricing", "Turnaround", "Patches", "Notifications", "Site details", "Team", "Security"]:
        assert f">{label}<" in html


def test_settings_opens_requested_tab(client, staff):
    client.force_login(staff)
    html = client.get(reverse("console:settings") + "?tab=notifications").content.decode()
    assert 'data-active-tab="notifications"' in html


def test_notification_recipients_can_be_edited(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("console:settings"),
        {
            "section": "notifications",
            "notify_on_new_order": "on",
            "order_notification_emails": " shop@gmail.com ,  second@shop.com ",
        },
    )
    assert resp.status_code == 302
    assert resp.url.endswith("tab=notifications")
    site = SiteSettings.load()
    assert site.notification_recipients == ["shop@gmail.com", "second@shop.com"]
    assert site.notify_on_new_order


def test_invalid_recipient_is_rejected(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("console:settings"),
        {"section": "notifications", "notify_on_new_order": "on", "order_notification_emails": "nope"},
    )
    assert resp.status_code == 200
    assert "is not a valid email address" in resp.content.decode()


def test_alerts_on_requires_an_address(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("console:settings"),
        {"section": "notifications", "notify_on_new_order": "on", "order_notification_emails": ""},
    )
    assert resp.status_code == 200
    assert "Add at least one address" in resp.content.decode()


def test_send_test_email(client, staff):
    site = SiteSettings.load()
    site.order_notification_emails = "shop@gmail.com"
    site.save()
    client.force_login(staff)
    resp = client.post(reverse("console:settings"), {"section": "test_email"}, follow=True)
    assert resp.status_code == 200
    assert "Test email sent to shop@gmail.com" in resp.content.decode()
    assert mail.outbox[-1].to == ["shop@gmail.com"]


def test_settings_never_exposes_the_mail_password(client, staff, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "smtp.gmail.com"
    settings.EMAIL_HOST_USER = "shop@gmail.com"
    settings.EMAIL_HOST_PASSWORD = "sup3r-secret-app-password"
    client.force_login(staff)
    html = client.get(reverse("console:settings") + "?tab=notifications").content.decode()
    assert "sup3r-secret-app-password" not in html
    assert "Saved securely on the server" in html


def test_pricing_row_can_be_added_and_removed(client, staff, pricing):
    client.force_login(staff)
    tiers = list(PricingTier.objects.order_by("pk"))
    data = {
        "section": "tiers",
        "tiers-TOTAL_FORMS": str(len(tiers) + 1),
        "tiers-INITIAL_FORMS": str(len(tiers)),
        "tiers-MIN_NUM_FORMS": "0",
        "tiers-MAX_NUM_FORMS": "1000",
    }
    for i, t in enumerate(tiers):
        data.update(
            {
                f"tiers-{i}-id": t.pk,
                f"tiers-{i}-service": t.service,
                f"tiers-{i}-name": t.name,
                f"tiers-{i}-description": t.description,
                f"tiers-{i}-price": str(t.price),
                f"tiers-{i}-sort_order": t.sort_order,
                f"tiers-{i}-is_active": "on",
            }
        )
    # delete the first, add a brand-new one in the trailing blank form
    data["tiers-0-DELETE"] = "on"
    new = len(tiers)
    data.update(
        {
            f"tiers-{new}-id": "",
            f"tiers-{new}-service": "digitizing",
            f"tiers-{new}-name": "Sleeve",
            f"tiers-{new}-description": "Small sleeve logo",
            f"tiers-{new}-price": "5.00",
            f"tiers-{new}-sort_order": "9",
            f"tiers-{new}-is_active": "on",
        }
    )
    resp = client.post(reverse("console:settings"), data)
    assert resp.status_code == 302
    names = set(PricingTier.objects.values_list("name", flat=True))
    assert "Sleeve" in names
    assert tiers[0].name not in names


# ── Console appearance (dark / light) ────────────────────
def test_console_is_dark_by_default(client, staff):
    client.force_login(staff)
    html = client.get(reverse("console:chat")).content.decode()
    assert staff.console_theme == User.ConsoleTheme.DARK
    assert 'data-theme="dark"' in html
    assert "data-theme-toggle" in html  # the sidebar toggle
    assert 'aria-checked="false"' in html  # off = dark


def test_toggle_reflects_the_saved_theme(client, staff):
    staff.console_theme = User.ConsoleTheme.LIGHT
    staff.save(update_fields=["console_theme"])
    client.force_login(staff)
    html = client.get(reverse("console:chat")).content.decode()
    assert 'aria-checked="true"' in html
    assert "Light mode" in html
    # With JavaScript off, submitting the toggle flips to the other theme.
    assert 'name="theme" value="dark"' in html


def test_admin_switches_to_light_and_it_sticks(client, staff):
    client.force_login(staff)
    resp = client.post(reverse("console:set_theme"), {"theme": "light", "next": "/console/orders/"})
    assert resp.status_code == 302
    assert resp.url == "/console/orders/"

    staff.refresh_from_db()
    assert staff.console_theme == User.ConsoleTheme.LIGHT

    html = client.get(reverse("console:settings")).content.decode()
    assert 'data-theme="light"' in html  # every console page follows the choice


def test_theme_switch_answers_json_for_background_saves(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("console:set_theme"), {"theme": "light"}, headers={"x-requested-with": "XMLHttpRequest"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"theme": "light"}


def test_unknown_theme_is_refused(client, staff):
    client.force_login(staff)
    resp = client.post(reverse("console:set_theme"), {"theme": "neon"})
    assert resp.status_code == 400
    staff.refresh_from_db()
    assert staff.console_theme == User.ConsoleTheme.DARK


def test_theme_is_per_admin(client, staff):
    other = User.objects.create_user(
        email="second@sedigitizer.com", password="Str0ng-pass!", full_name="Second Admin", is_staff=True
    )
    client.force_login(staff)
    client.post(reverse("console:set_theme"), {"theme": "light"})

    client.force_login(other)
    html = client.get(reverse("console:chat")).content.decode()
    assert 'data-theme="dark"' in html  # unaffected by a colleague's choice


def test_customers_cannot_change_the_console_theme(client, customer):
    resp = client.post(reverse("console:set_theme"), {"theme": "light"})
    assert resp.status_code == 302 and reverse("console:login") in resp.url


# ── Portfolio manager ────────────────────────────────────
def test_portfolio_upload_creates_items_under_the_chosen_category(client, staff, image_file):
    client.force_login(staff)
    resp = client.post(
        reverse("console:portfolio"),
        {
            "action": "upload",
            "category": PortfolioItem.Category.CAPS,
            "name": "",
            "meta": "cap front · 4,120 st",
            "is_published": "on",
            "images": [image_file("ridgeline-cap.png"), image_file("harbor cap.png")],
        },
    )
    assert resp.status_code == 302

    items = PortfolioItem.objects.order_by("sort_order")
    assert [i.name for i in items] == ["Ridgeline Cap", "Harbor Cap"]  # named after the files
    assert {i.category for i in items} == {PortfolioItem.Category.CAPS}
    assert all(i.image.name.startswith("portfolio/") for i in items)
    assert all(i.meta == "cap front · 4,120 st" and i.is_published for i in items)


def test_uploaded_photo_appears_on_the_public_site(client, staff, image_file):
    client.force_login(staff)
    client.post(
        reverse("console:portfolio"),
        {
            "action": "upload",
            "category": PortfolioItem.Category.PATCHES,
            "name": "Varsity patch",
            "meta": "8in · wool felt",
            "is_published": "on",
            "images": [image_file()],
        },
    )
    item = PortfolioItem.objects.get()

    client.logout()
    body = client.get(reverse("core:portfolio")).content.decode()
    assert "Varsity patch" in body
    assert item.image.url in body
    assert "Varsity patch" in client.get(reverse("core:portfolio") + "?category=patches").content.decode()
    assert "Varsity patch" not in client.get(reverse("core:portfolio") + "?category=caps").content.decode()


def test_photo_can_be_edited_and_recategorised(client, staff, image_file):
    client.force_login(staff)
    client.post(
        reverse("console:portfolio"),
        {
            "action": "upload",
            "category": PortfolioItem.Category.CAPS,
            "name": "Cap",
            "meta": "",
            "is_published": "on",
            "images": [image_file()],
        },
    )
    item = PortfolioItem.objects.get()
    original_image = item.image.name

    resp = client.post(
        reverse("console:portfolio_edit", args=[item.pk]),
        {
            "action": "save",
            "name": "Ridgeline cap",
            "category": PortfolioItem.Category.JACKET_BACK,
            "meta": "jacket back · 9,860 st",
            "sort_order": "3",
            "showcase_tag": "Jacket back · fleece",
            "placement": "Jacket back · 11 in",
            "fabric": "Heavy fleece",
            "stitches": "9860",
            "formats": "DST · PES",
            "turnaround": "5 h",
            "is_published": "on",
            "show_on_home": "on",
        },
    )
    assert resp.status_code == 302

    item.refresh_from_db()
    assert item.name == "Ridgeline cap"
    assert item.category == PortfolioItem.Category.JACKET_BACK
    assert item.show_on_home
    assert item.image.name == original_image  # photo kept when no new file is picked

    home = client.get(reverse("core:home")).content.decode()
    assert "Heavy fleece" in home  # now part of the home page showcase


def test_photo_can_be_hidden_then_deleted(client, staff, image_file):
    client.force_login(staff)
    client.post(
        reverse("console:portfolio"),
        {
            "action": "upload",
            "category": PortfolioItem.Category.VECTOR,
            "name": "Auto Werks",
            "meta": "",
            "is_published": "on",
            "images": [image_file()],
        },
    )
    item = PortfolioItem.objects.get()
    storage, path = item.image.storage, item.image.name

    client.post(reverse("console:portfolio"), {"action": "toggle_published", "id": item.pk})
    item.refresh_from_db()
    assert not item.is_published
    assert "Auto Werks" not in client.get(reverse("core:portfolio")).content.decode()

    resp = client.post(reverse("console:portfolio"), {"action": "delete", "id": item.pk})
    assert resp.status_code == 302
    assert PortfolioItem.objects.count() == 0
    assert not storage.exists(path)  # the file goes too, not just the row


def test_portfolio_rejects_files_that_are_not_images(client, staff):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client.force_login(staff)
    resp = client.post(
        reverse("console:portfolio"),
        {
            "action": "upload",
            "category": PortfolioItem.Category.CAPS,
            "name": "",
            "meta": "",
            "is_published": "on",
            "images": [SimpleUploadedFile("notes.pdf", b"%PDF-1.4 fake", content_type="application/pdf")],
        },
    )
    assert resp.status_code == 200
    assert PortfolioItem.objects.count() == 0
    assert "not an accepted file type" in resp.content.decode()


def test_only_staff_can_manage_the_portfolio(client, customer):
    assert client.get(reverse("console:portfolio")).status_code == 302
    client.force_login(customer)
    resp = client.get(reverse("console:portfolio"))
    assert resp.status_code == 302 and reverse("console:login") in resp.url


# ── Reviews (testimonials) ───────────────────────────────
def test_admin_adds_a_review(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("console:testimonials"),
        {
            "quote": "Clean DST first time, and the sew-out photo sold me.",
            "name": "Dana Whitfield",
            "role": "Whitfield Uniforms",
            "rating": "5",
            "sort_order": "0",
            "is_published": "on",
        },
    )
    assert resp.status_code == 302
    review = Testimonial.objects.get()
    assert review.name == "Dana Whitfield"
    assert review.is_published
    assert review.sort_order == 1  # placed after the others automatically

    assert "Dana Whitfield" in client.get(reverse("core:home")).content.decode()


def test_admin_edits_and_deletes_a_review(client, staff):
    review = Testimonial.objects.create(quote="Great work", name="Marcus Lee", role="Lee Apparel", rating=4)
    client.force_login(staff)

    resp = client.post(
        reverse("console:testimonial_edit", args=[review.pk]),
        {
            "quote": "Great work, every time.",
            "name": "Marcus Lee",
            "role": "Owner · Lee Apparel",
            "rating": "5",
            "sort_order": "2",
            "is_published": "on",
        },
    )
    assert resp.status_code == 302
    review.refresh_from_db()
    assert review.quote == "Great work, every time."
    assert review.rating == 5

    resp = client.post(reverse("console:testimonials"), {"action": "delete", "id": review.pk})
    assert resp.status_code == 302
    assert Testimonial.objects.count() == 0


def test_hidden_review_leaves_the_home_page(client, staff):
    review = Testimonial.objects.create(quote="Nice", name="Priya Raman", rating=5)
    client.force_login(staff)

    client.post(reverse("console:testimonials"), {"action": "toggle_published", "id": review.pk})
    review.refresh_from_db()
    assert not review.is_published
    assert "Priya Raman" not in client.get(reverse("core:home")).content.decode()


def test_rating_must_be_one_to_five(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("console:testimonials"),
        {"quote": "Nine stars", "name": "Over Rater", "role": "", "rating": "9", "sort_order": "0"},
    )
    assert resp.status_code == 200
    assert Testimonial.objects.count() == 0


def test_only_staff_can_manage_reviews(client, customer):
    assert client.get(reverse("console:testimonials")).status_code == 302
    client.force_login(customer)
    resp = client.get(reverse("console:testimonials"))
    assert resp.status_code == 302 and reverse("console:login") in resp.url
