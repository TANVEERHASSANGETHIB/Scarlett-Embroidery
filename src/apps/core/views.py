from django.contrib import messages
from django.db.models import Avg, Count
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.orders.models import PatchCategory, PricingTier, Service

from .forms import ContactForm
from .models import (
    FAQ,
    BeforeAfter,
    PortfolioCategory,
    PortfolioItem,
    ServiceImage,
    SewOut,
    SiteImage,
    SiteSettings,
    Testimonial,
)
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


PROCESS_STEPS = [
    ("01", "Brief", "You send artwork, fabric, placement and size. Nothing else to fill in."),
    ("02", "Punch", "A digitizer builds the file by hand — no auto-trace, no preset."),
    ("03", "Test-sew", "We run it on a real machine, on your fabric class, and photograph it."),
    ("04", "Deliver", "Proof first, payment after approval, every machine format included."),
]
SERVICE_PERKS = [
    ("Under 4 hours", "Standard turnaround on most designs, with rush options when you need it sooner."),
    ("Free revisions", "Changes inside the original scope are turned around the same day."),
    ("Live humans", "Chat with the digitizer working on your file, any time of day."),
    ("You own the files", "Machine and source formats delivered together. No licence, no lock-in."),
]

SERVICE_PAGES = {
    "embroidery": {
        "service": Service.DIGITIZING,
        "title": "Embroidery Digitizing",
        "kicker": "Service 01",
        "headline": "Stitch files punched by hand, sewn before you get them",
        "lead": "We turn your logo or artwork into a machine-ready embroidery file. A digitizer builds every "
        "column, underlay and trim by hand, then runs it on the fabric class you named.",
        "highlights": [
            (
                "Fabric-specific",
                "Density, underlay and pull compensation are set for the fabric you tell us.",
            ),
            ("Test-sewn", "Every file is run on a real machine and the sew-out photo comes with the file."),
            ("All formats", "DST, PES, EXP, JEF, VP3 and more are included — no format fees."),
            ("Free revisions", "Changes inside the original scope are turned around the same day."),
        ],
        "steps": [
            ("Send artwork", "Upload any file type and tell us the fabric, placement, size and formats."),
            ("We punch & test-sew", "A digitizer builds the file and sews it out on your fabric class."),
            ("You approve", "Review the proof. Pay only once you're happy, then download the files."),
        ],
        "good_for": [
            "Left-chest logos",
            "Caps & beanies",
            "Jacket backs",
            "3D puff & appliqué",
            "Towels & bags",
        ],
        "formats": "DST · PES · EXP · JEF · VP3 · XXX · HUS · EMB",
    },
    "vector": {
        "service": Service.VECTOR,
        "title": "Vector Art Services",
        "kicker": "Service 02",
        "headline": "Clean, scalable artwork rebuilt from any image",
        "lead": "Blurry logo, photo of a sign, hand sketch? We redraw it as crisp vector art that prints, "
        "cuts and embroiders cleanly at any size.",
        "highlights": [
            ("Redrawn, not auto-traced", "Curves are rebuilt by hand so edges stay smooth at 300% zoom."),
            ("Print ready", "Screen print separations, sublimation and signage layouts on request."),
            ("Every format", "AI, EPS, PDF, SVG, CDR and PNG delivered together."),
            ("Pantone matched", "Colours matched to your brand swatches when you provide them."),
        ],
        "steps": [
            ("Send your image", "Any raster, photo or sketch works — the rougher, the more we can help."),
            ("We redraw it", "A designer rebuilds the artwork and sends a proof for your review."),
            ("Download files", "Approve the proof and receive every vector format you asked for."),
        ],
        "good_for": ["Logo rebuilds", "Screen printing", "Sublimation", "Signage & vinyl", "Merch artwork"],
        "formats": "AI · EPS · PDF · SVG · CDR · PNG",
    },
    "patches": {
        "service": Service.PATCHES,
        "title": "Embroidery Patches",
        "kicker": "Service 03",
        "headline": "Custom patches made and shipped to your door",
        "lead": "From design to finished patch: iron-on, embroidered or rubber, with the backing you need, "
        "produced in bulk and shipped to your address.",
        "highlights": [
            ("Three patch types", "Iron-on, embroidery (merrowed or laser-cut) and soft PVC rubber patches."),
            ("Your backing", "Iron-on, velcro, adhesive or sew-on — choose per order."),
            ("Artwork included", "We prepare the artwork and stitch file so you don't have to."),
            (
                "Delivered to you",
                "Add your shipping address on the order and we ship when production is done.",
            ),
        ],
        "steps": [
            ("Choose type & size", "Pick the patch category, backing, size and quantity."),
            ("Approve the proof", "We send a digital proof of your patch before production starts."),
            ("Production & shipping", "Patches are made and shipped to the address on your order."),
        ],
        "good_for": ["Uniforms", "Clubs & teams", "Brand merch", "Caps & jackets", "Events"],
        "formats": "Iron-on · Embroidery · Rubber",
    },
}


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
            "slug": "embroidery",
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
            "slug": "vector",
            "service": Service.VECTOR,
            "title": "Vector Art Services",
            "body": "Clean, print-ready redraws from any raster: screen print separations, sublimation, "
            "signage and full logo rebuilds.",
            "points": ["AI, EPS, PDF, SVG, CDR", "Colour separations on request", "300% zoom-clean curves"],
            "price": f"FROM ${vector_from:,.0f} · PER LOGO" if vector_from is not None else "",
        },
        {
            "no": "03",
            "slug": "patches",
            "service": Service.PATCHES,
            "title": "Embroidery Patches",
            "body": "Custom patches manufactured and shipped — iron-on, embroidered or rubber, with the "
            "backing you sell.",
            "points": ["Iron-on, velcro, adhesive, sew-on", "50-piece minimum", "8–12 day production"],
            "price": f"FROM ${patch_from.unit_price} · PER PATCH" if patch_from else "",
        },
    ]


def _service_thumbs():
    """{slug: url} — the first published picture of each service, for the home page rows."""
    thumbs = {}
    for img in ServiceImage.objects.filter(is_published=True):
        thumbs.setdefault(img.service, img.image.url)
    return thumbs


_OTHER_ART = {
    "embroidery": "img/demo/labubu-embroidery.jpg",
    "vector": "img/demo/labubu-vector.jpg",
    "patches": "img/demo/hoop.svg",
}


def _other_services(current):
    """Cards for the other service pages: admin picture if there is one, else built-in artwork."""
    thumbs = _service_thumbs()
    return [
        {
            "key": key,
            "title": page["title"],
            "lead": page["lead"],
            "kicker": page["kicker"],
            "thumb": thumbs.get(key),
            "art": _OTHER_ART[key],
        }
        for key, page in SERVICE_PAGES.items()
        if key != current
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
        "vector_tiers": PricingTier.objects.filter(is_active=True, service=Service.VECTOR),
        "patch_categories": PatchCategory.objects.filter(is_active=True),
        "why_us": WHY_US,
        "testimonials": Testimonial.objects.filter(is_published=True),
        "faqs": FAQ.objects.filter(is_published=True),
        "photos": SiteImage.urls(),
        "service_thumbs": _service_thumbs(),
    }
    return render(request, "core/home.html", context)


def portfolio(request):
    categories = list(PortfolioCategory.objects.all())
    active = request.GET.get("category", "")
    items = PortfolioItem.objects.filter(is_published=True)
    if active in {c.slug for c in categories}:
        items = items.filter(category=active)
    else:
        active = ""
    names = {c.slug: c for c in categories}
    items = list(items)
    for item in items:  # avoid one query per card
        item.cached_category = names.get(item.category)
    return render(
        request,
        "core/portfolio.html",
        {"items": items, "categories": [(c.slug, c.name) for c in categories], "active": active},
    )


def testimonials(request):
    quotes = Testimonial.objects.filter(is_published=True)
    agg = quotes.aggregate(avg=Avg("rating"), n=Count("id"))
    stats = {"count": agg["n"], "avg": round(agg["avg"], 1) if agg["avg"] else None}
    return render(
        request,
        "core/testimonials.html",
        {"testimonials": quotes, "sewouts": SewOut.objects.filter(is_published=True), "stats": stats},
    )


def services(request):
    thumbs = _service_thumbs()
    services_list = _services_overview()
    for sv in services_list:
        sv["thumb"] = thumbs.get(sv["slug"], "")
    return render(
        request,
        "core/services.html",
        {
            "services": services_list,
            "process": PROCESS_STEPS,
            "perks": SERVICE_PERKS,
            "photos": SiteImage.urls(),
        },
    )


def service_page(request, slug):
    page = SERVICE_PAGES.get(slug)
    if page is None:
        raise Http404
    overview = {sv["service"]: sv for sv in _services_overview()}
    pictures = list(ServiceImage.objects.filter(service=slug, is_published=True))
    before_after = (
        BeforeAfter.objects.filter(service=slug, is_active=True).first() if slug != "patches" else None
    )
    return render(
        request,
        "core/service_detail.html",
        {
            "page": page,
            "slug": slug,
            "price_line": overview[page["service"]]["price"],
            "others": _other_services(slug),
            "faqs": FAQ.objects.filter(is_published=True)[:4],
            "pictures": pictures,
            "gallery": pictures[2:],
            "before_after": before_after,
            "has_slider": slug != "patches",
            "stats": HERO_STATS[:3],
        },
    )


def about(request):
    return render(
        request,
        "core/about.html",
        {
            "facts": ABOUT_FACTS,
            "values": ABOUT_VALUES,
            "process": PROCESS_STEPS,
            "brands": BRANDS,
            "photos": SiteImage.urls(),
            "perks": SERVICE_PERKS,
        },
    )


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
                SiteSettings.load().contact_recipients,
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
