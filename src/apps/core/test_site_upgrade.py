"""Header, footer, services pages, portfolio categories and hero numbers."""

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.core.models import PortfolioCategory, PortfolioItem, SiteSettings, Testimonial

pytestmark = pytest.mark.django_db


# ── Header ───────────────────────────────────────────────
def test_header_menu_and_no_phone_number(client):
    SiteSettings.objects.update_or_create(pk=1, defaults={"phone": "+1 (512) 555-0148"})
    body = client.get(reverse("core:home")).content.decode()
    header = body[body.index("<header") : body.index("</header>")]
    for label in ("Home", "Services", "Portfolio", "Blog", "Contact us", "Testimonials", "More"):
        assert label in header
    for label in ("Embroidery Digitizing", "Vector Art", "Patches"):
        assert label in header
    assert "555-0148" not in header
    assert "24/7" not in header


# ── Services pages ───────────────────────────────────────
@pytest.mark.parametrize("slug", ["embroidery", "vector", "patches"])
def test_service_pages_offer_order_and_quote(client, slug):
    resp = client.get(reverse("core:service", args=[slug]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert reverse("orders:place") in body
    assert reverse("orders:quote") in body


def test_services_overview_and_unknown_service(client):
    assert client.get(reverse("core:services")).status_code == 200
    assert client.get("/services/unknown/").status_code == 404


def test_testimonials_page_lists_published_reviews(client):
    Testimonial.objects.create(quote="Sews clean", name="Sam", rating=5)
    Testimonial.objects.create(quote="Hidden one", name="Hal", rating=4, is_published=False)
    body = client.get(reverse("core:testimonials")).content.decode()
    assert "Sews clean" in body and "Hidden one" not in body


# ── Hero numbers ─────────────────────────────────────────
def test_hero_numbers_are_marked_for_count_up(client):
    body = client.get(reverse("core:home")).content.decode()
    assert body.count("data-count-up") == 4
    assert "18,400+" in body  # final value stays in the HTML for no-JS visitors


# ── Footer social icons ──────────────────────────────────
def test_footer_shows_only_filled_in_social_links(client):
    body = client.get(reverse("core:home")).content.decode()
    assert "social-links" not in body

    site = SiteSettings.load()
    site.instagram_url = "https://instagram.com/scarlett"
    site.youtube_url = "https://youtube.com/@scarlett"
    site.save()
    body = client.get(reverse("core:home")).content.decode()
    assert 'href="https://instagram.com/scarlett"' in body
    assert 'href="https://youtube.com/@scarlett"' in body
    assert "facebook.com" not in body


# ── Portfolio categories ─────────────────────────────────
def test_default_portfolio_categories_exist():
    slugs = set(PortfolioCategory.objects.values_list("slug", flat=True))
    assert {"caps", "left_chest", "jacket_back", "patches", "vector"} <= slugs


def test_new_category_slug_is_unique_and_filters_the_public_page(client):
    hoodies = PortfolioCategory.objects.create(name="Hoodies")
    again = PortfolioCategory.objects.create(name="Hoodies!")
    assert hoodies.slug == "hoodies" and again.slug == "hoodies-2"
    PortfolioItem.objects.create(name="Zip hoodie", category="hoodies")
    PortfolioItem.objects.create(name="Dad cap", category="caps")

    body = client.get(reverse("core:portfolio")).content.decode()
    assert "Hoodies" in body and "category=hoodies" in body

    body = client.get(reverse("core:portfolio") + "?category=hoodies").content.decode()
    assert "Zip hoodie" in body and "Dad cap" not in body


def test_seed_still_runs_with_categories():
    call_command("seed")
    assert PortfolioItem.objects.exists()
