from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.orders.models import PatchCategory, PricingTier, Service

from .forms import ContactForm
from .models import FAQ, PortfolioItem, SiteSettings, Testimonial
from .utils import get_client_ip, rate_limited, send_templated_email

HERO_STATS = [
    ("18,400+", "files delivered"),
    ("4 hrs", "standard turnaround"),
    ("99.2%", "first-pass approval"),
    ("34", "countries served"),
]
BRANDS = ["TAJIMA", "BARUDAN", "BERNINA", "JANOME", "MELCO", "RICOMA"]
STEPS = [
    (
        "1",
        "Send artwork and specs",
        "Any file type. Tell us fabric, placement, finished size and the formats your machine reads.",
        "2 minutes",
    ),
    (
        "2",
        "We punch and test-sew",
        "A digitizer builds the file by hand, then runs it on the same fabric class before signing it off.",
        "under 4 hours",
    ),
    (
        "3",
        "You approve, then pay",
        "File pack plus the sew-out photo. Revisions inside scope are free and turned around same day.",
        "same day",
    ),
]
WHY_US = [
    ("Punched by hand", "No auto-digitizing. Every column, underlay and trim is a decision someone made."),
    ("Test-sewn", "We run the file before you do, on the fabric class you named, and send the photo."),
    ("24/7 humans", "A digitizer on live chat around the clock — not a bot, not a ticket queue."),
    ("You own the file", "Source and machine formats delivered together. No licence, no lock-in."),
]
ABOUT_FACTS = [
    ("2016", "studio founded"),
    ("11", "digitizers on staff"),
    ("34", "countries served"),
    ("24/7", "chat coverage"),
]
ABOUT_VALUES = [
    (
        "01",
        "The machine decides",
        "If it doesn't sew clean on the test head, it doesn't ship. That single rule shapes every file we build.",
    ),
    (
        "02",
        "One digitizer per file",
        "Your job isn't split across a queue. The person who punched it answers your questions about it.",
    ),
    (
        "03",
        "Plain pricing",
        "Flat price per design, quoted up front, invoiced after approval. No setup fees, no format fees.",
    ),
]


def _services_overview():
    tiers = list(PricingTier.objects.filter(is_active=True))
    patch_from = PatchCategory.objects.filter(is_active=True).order_by("unit_price").first()

    def cheapest(service):
        prices = [t.price for t in tiers if t.service == service]
        return min(prices) if prices else None

    digit_from = cheapest(Service.DIGITIZING)
    vector_from = cheapest(Service.VECTOR)
    return [
        {
            "no": "01",
            "service": Service.DIGITIZING,
            "title": "Embroidery Digitizing",
            "body": "Manual punching for caps, flats, 3D puff, appliqué and towels — built for the fabric "
            "you named, not a generic preset.",
            "points": [
                "Fabric-specific density & pull comp",
                "All machine formats included",
                "Sew-out photo with every file",
            ],
            "price": f"FROM ${digit_from:,.0f} · FLAT PRICE" if digit_from is not None else "",
        },
        {
            "no": "02",
            "service": Service.VECTOR,
            "title": "Vector Art Services",
            "body": "Clean, print-ready redraws from any raster: screen print separations, sublimation, "
            "signage and full logo rebuilds.",
            "points": ["AI, EPS, PDF, SVG, CDR", "Colour separations on request", "300% zoom-clean curves"],
            "price": f"FROM ${vector_from:,.0f} · PER LOGO" if vector_from is not None else "",
        },
        {
            "no": "03",
            "service": Service.PATCHES,
            "title": "Embroidery Patches",
            "body": "Custom patches manufactured and shipped — iron-on, embroidered or rubber, with the "
            "backing you sell.",
            "points": ["Iron-on, velcro, adhesive, sew-on", "50-piece minimum", "8–12 day production"],
            "price": f"FROM ${patch_from.unit_price} · PER PATCH" if patch_from else "",
        },
    ]


def home(request):
    showcase = list(PortfolioItem.objects.filter(is_published=True, show_on_home=True)[:6])
    showcase_data = [
        {
            "name": p.name,
            "tag": p.showcase_tag or p.get_category_display(),
            "specs": p.specs,
            "image": p.image.url if p.image else "",
        }
        for p in showcase
    ]
    context = {
        "showcase_data": showcase_data,
        "hero_stats": HERO_STATS,
        "brands": BRANDS,
        "services": _services_overview(),
        "showcase": showcase,
        "steps": STEPS,
        "digitizing_tiers": PricingTier.objects.filter(is_active=True, service=Service.DIGITIZING),
        "vector_tier": PricingTier.objects.filter(is_active=True, service=Service.VECTOR).first(),
        "patch_from": PatchCategory.objects.filter(is_active=True)
        .order_by("unit_price")
        .values_list("unit_price", flat=True)
        .first(),
        "why_us": WHY_US,
        "testimonials": Testimonial.objects.filter(is_published=True),
        "faqs": FAQ.objects.filter(is_published=True),
    }
    return render(request, "core/home.html", context)


def portfolio(request):
    categories = PortfolioItem.Category
    active = request.GET.get("category", "")
    items = PortfolioItem.objects.filter(is_published=True)
    if active in categories.values:
        items = items.filter(category=active)
    else:
        active = ""
    return render(
        request, "core/portfolio.html", {"items": items, "categories": categories.choices, "active": active}
    )


def about(request):
    return render(request, "core/about.html", {"facts": ABOUT_FACTS, "values": ABOUT_VALUES})


@require_http_methods(["GET", "POST"])
def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST":
        ip = get_client_ip(request.META)
        if rate_limited(f"contact:{ip}", limit=5, window_seconds=3600):
            messages.error(
                request, "Too many messages from your connection. Please try again later or use live chat."
            )
        elif form.is_valid():
            msg = form.save(commit=False)
            msg.ip_address = ip
            msg.save()
            send_templated_email(
                f"New contact message: {msg.subject or msg.name}",
                "contact_staff",
                {"msg": msg},
                SiteSettings.load().notification_recipients,
                reply_to=msg.email,
            )
            messages.success(request, "Message sent. A digitizer will reply within 30 minutes.")
            return redirect("core:contact")
    return render(request, "core/contact.html", {"form": form})


def legal(request, page="privacy"):
    if page not in ("privacy", "terms"):
        page = "privacy"
    return render(request, f"core/legal_{page}.html", {"page": page})


def error_404(request, exception):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)


def health(request):
    from django.http import JsonResponse

    return JsonResponse({"status": "ok"})
