import pytest
from django.core import mail
from django.core.management import call_command
from django.urls import reverse

from apps.core.models import ContactMessage, SiteSettings, Testimonial
from apps.orders.models import PatchCategory, PricingTier

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "name",
    [
        "core:home",
        "core:portfolio",
        "core:about",
        "core:contact",
        "core:privacy",
        "core:terms",
        "blog:list",
        "accounts:login",
        "accounts:signup",
        "core:health",
    ],
)
def test_public_pages_render(client, name):
    call_command("seed", "--no-demo")
    assert client.get(reverse(name)).status_code == 200


def test_home_with_demo_content(client):
    call_command("seed")
    resp = client.get(reverse("core:home"))
    assert resp.status_code == 200
    assert b"Left chest" in resp.content
    assert b"$6" in resp.content


def test_pricing_section_is_available_on_home_services_and_service_pages(client, pricing):
    pages = [
        ("core:home", None, "embroidery"),
        ("core:services", None, "embroidery"),
        ("core:service", ["embroidery"], "embroidery"),
        ("core:service", ["vector"], "vector"),
        ("core:service", ["patches"], "patches"),
    ]
    for route, args, active_tab in pages:
        response = client.get(reverse(route, args=args or []))
        body = response.content.decode()
        assert 'id="pricing"' in body
        assert "Left chest" in body and "Standard vector" in body and "Iron-on patch" in body
        assert f'data-price-tab="{active_tab}"' in body
        assert f'data-price-panel="{active_tab}"' in body


def test_footer_shows_phone_payment_methods_and_branded_social_links(client):
    site = SiteSettings.load()
    site.phone = "+1 512 555 0148"
    site.facebook_url = "https://facebook.com/example"
    site.save()

    body = client.get(reverse("core:home")).content.decode()
    assert 'href="tel:%2B1%20512%20555%200148"' in body
    assert "Visa, Mastercard, American Express, PayPal and Apple Pay" in body
    assert 'class="container footer-payment"' in body
    assert 'class="social-facebook"' in body


def test_seed_is_idempotent():
    call_command("seed")
    call_command("seed")
    assert PricingTier.objects.filter(name="Left chest").count() == 1
    assert PatchCategory.objects.count() == 3


def test_contact_form_saves_and_notifies(client, django_capture_on_commit_callbacks):
    resp = client.post(
        reverse("core:contact"),
        {
            "name": "Jane",
            "email": "jane@shop.com",
            "subject": "Cap logo",
            "message": "3.5in DST please",
        },
    )
    assert resp.status_code == 302
    assert ContactMessage.objects.count() == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["support@sedigitizer.com"]
    assert mail.outbox[0].reply_to == ["jane@shop.com"]
    assert "3.5in DST please" in mail.outbox[0].body


def test_contact_honeypot_blocks_spam(client):
    resp = client.post(
        reverse("core:contact"),
        {
            "name": "Bot",
            "email": "bot@spam.com",
            "message": "buy",
            "website": "http://spam",
        },
    )
    assert resp.status_code == 200
    assert ContactMessage.objects.count() == 0


# ── Home page pricing cards ──────────────────────────────
def test_pricing_cards_show_each_plan(client, pricing):
    tiers = pricing["tiers"]
    tiers["left_chest"].plan_name = "Base"
    tiers["left_chest"].ribbon = "BASE"
    tiers["left_chest"].features = "Left chest / hat logo\nPDF proof before delivery"
    tiers["left_chest"].save()
    tiers["full_back"].plan_name = "Premium"
    tiers["full_back"].ribbon = "EXTRA"
    tiers["full_back"].is_highlighted = True
    tiers["full_back"].features = "Full back logo"
    tiers["full_back"].save()

    body = client.get(reverse("core:home")).content.decode()

    assert "plan-card" in body
    assert "Base" in body and "Premium" in body
    assert ">BASE<" in body and ">EXTRA<" in body  # corner flags
    assert "Left chest / hat logo" in body and "PDF proof before delivery" in body
    assert "is-featured" in body  # the highlighted plan stands out
    assert f'href="/order/?service=digitizing&amp;tier={tiers["left_chest"].pk}"' in body


def test_pricing_card_falls_back_to_the_tier_name(client, pricing):
    """A plan with no card content still renders something sensible."""
    tier = pricing["tiers"]["complex"]
    tier.description = "Photoreal, 3D puff or dense artwork"
    tier.save()

    body = client.get(reverse("core:home")).content.decode()
    assert "Complex design" in body
    assert "Photoreal, 3D puff or dense artwork" in body


def test_order_now_preselects_that_plan(client, customer, pricing):
    client.force_login(customer)
    tier = pricing["tiers"]["full_back"]
    body = client.get(reverse("orders:place") + f"?service=digitizing&tier={tier.pk}").content.decode()
    assert f'name="tier" value="{tier.pk}" checked' in body


def test_home_pricing_has_embroidery_vector_and_patch_tabs(client, pricing):
    body = client.get(reverse("core:home")).content.decode()
    for tab in ("embroidery", "vector", "patches"):
        assert f'data-price-tab="{tab}"' in body
        assert f'data-price-panel="{tab}"' in body
    # Embroidery is the tab open by default; the others start hidden.
    assert 'data-price-tab="embroidery"' in body and 'class="price-tab is-active"' in body
    assert 'data-price-panel="vector" hidden' in body
    assert "Standard vector" in body and "Iron-on patch" in body


def test_patch_plan_card_is_editable_from_the_category(client, pricing):
    cat = pricing["patches"]["iron"]
    cat.ribbon, cat.features, cat.is_highlighted = "POPULAR", "Heat-seal backing\nFree artwork prep", True
    cat.save()
    body = client.get(reverse("core:home")).content.decode()
    assert "POPULAR" in body and "Free artwork prep" in body and "is-featured" in body


# ── Contact page map ─────────────────────────────────────
def test_map_appears_once_an_address_is_set(client):
    site = SiteSettings.load()
    assert "map-frame" not in client.get(reverse("core:contact")).content.decode()  # nothing set yet

    site.address = "12 Loom Street, Austin, TX 78701"
    site.save()

    body = client.get(reverse("core:contact")).content.decode()
    assert "map-band" in body and "map-frame" in body  # full-width band under the contact section
    assert "12 Loom Street, Austin, TX 78701" in body  # also listed in the contact details
    assert "google.com/maps?q=Scarlett%20Embroidery%2C%2012%20Loom%20Street" in body  # pin shows the business


def test_admin_can_paste_their_own_embed(client):
    site = SiteSettings.load()
    site.address = "12 Loom Street, Austin, TX 78701"
    site.map_embed_url = "https://www.google.com/maps/embed?pb=custom-embed"
    site.save()

    body = client.get(reverse("core:contact")).content.decode()
    assert "maps/embed?pb=custom-embed" in body  # the pasted embed wins


def test_map_can_be_switched_off(client):
    site = SiteSettings.load()
    site.address = "12 Loom Street, Austin, TX 78701"
    site.show_map = False
    site.save()

    body = client.get(reverse("core:contact")).content.decode()
    assert "map-frame" not in body
    assert "12 Loom Street, Austin, TX 78701" in body  # the address still shows in the details


def test_admin_sets_the_address_from_the_console(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("console:settings"),
        {
            "section": "site",
            "phone": "+1 (512) 555-0148",
            "email": "hello@sedigitizer.com",
            "orders_email": "orders@sedigitizer.com",
            "hours": "Live chat 24/7",
            "business_name": "Scarlett Embroidery",
            "address": "9 Bobbin Road, Austin, TX 78702",
            "map_embed_url": "",
            "show_map": "on",
            "announcement": "4-hour standard turnaround",
            "patch_production_note": "8-12 day production",
            "patch_min_quantity": "50",
        },
    )
    assert resp.status_code == 302
    assert SiteSettings.load().address == "9 Bobbin Road, Austin, TX 78702"


# ── Reviews carousel ─────────────────────────────────────
def test_home_shows_every_published_review_in_a_carousel(client):
    for i in range(5):
        Testimonial.objects.create(quote=f"Review number {i}", name=f"Customer {i}", rating=5, sort_order=i)
    Testimonial.objects.create(quote="Hidden one", name="Not Shown", rating=5, is_published=False)

    body = client.get(reverse("core:home")).content.decode()

    assert "carousel-track" in body
    assert body.count("carousel-item") == 5  # all five, not just the first three
    assert "Review number 4" in body
    assert "Not Shown" not in body


def test_robots_and_sitemap(client, db):
    r = client.get("/robots.txt")
    assert r.status_code == 200 and b"Disallow: /console/" in r.content and b"sitemap.xml" in r.content
    s = client.get("/sitemap.xml")
    assert s.status_code == 200 and b"/services/embroidery/" in s.content
