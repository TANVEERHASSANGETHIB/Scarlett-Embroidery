import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings as django_settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.blog.models import Category, Post
from apps.core.models import FAQ, PortfolioItem, SiteSettings, Testimonial
from apps.orders.models import PatchCategory, PricingTier, Service, TurnaroundOption

PRICING_TIERS = [
    # service, name, plan name, ribbon, price, sort, highlighted, features
    (
        Service.DIGITIZING,
        "Left chest",
        "Base",
        "BASE",
        "6.00",
        1,
        False,
        [
            "Left chest / hat logo",
            "PDF proof before delivery",
            "All required machine formats",
            'Up to 5" x 5" (W x H)',
        ],
    ),
    (
        Service.DIGITIZING,
        "Full back",
        "Premium",
        "EXTRA",
        "10.00",
        2,
        True,
        [
            "Full back logo",
            "PDF proof before delivery",
            "All required machine formats",
            'Larger than 5" x 5" (W x H)',
        ],
    ),
    (
        Service.DIGITIZING,
        "Complex design",
        "Performance",
        "FULL",
        "15.00",
        3,
        False,
        [
            "Complex logo design",
            "PDF proof before delivery",
            "All required machine formats",
            'Larger than 5" x 5" (W x H)',
        ],
    ),
    (Service.VECTOR, "Standard vector", "Vector", "", "10.00", 1, False, ["Clean redraw of a logo"]),
    (
        Service.VECTOR,
        "Colour separation",
        "Separations",
        "",
        "18.00",
        2,
        False,
        ["Screen-print ready separations"],
    ),
]
TURNAROUNDS = [
    ("Standard · 4 hr", 4, "0.00", True, 1),
    ("Rush · 2 hr", 2, "3.00", False, 2),
    ("Same hour", 1, "9.00", False, 3),
]
PATCH_CATEGORIES = [
    ("Iron-on patch", "Heat-seal backing, ready to press", "1.10", 1),
    ("Embroidery patch", "Merrowed or laser-cut embroidered patch", "1.25", 2),
    ("Rubber patch", "Soft PVC rubber, 2D or 3D", "1.60", 3),
]
PORTFOLIO = [
    (
        "Whitfield crest",
        "left_chest",
        "left chest · 6,480 st",
        "Left chest · twill",
        "Left chest · 3.5 in",
        "Cotton twill",
        6480,
        "DST · PES · EMB",
        "3 h 12 m",
        True,
    ),
    (
        "Ridgeline cap",
        "caps",
        "cap front · 4,120 st",
        "Cap front · foam",
        "Cap front · 4.2 in",
        "Structured foam front",
        4120,
        "DST · EXP",
        "2 h 40 m",
        True,
    ),
    (
        "Harbor & Oak",
        "jacket_back",
        "jacket back · 9,860 st",
        "Jacket back · fleece",
        "Jacket back · 11 in",
        "Heavy fleece",
        9860,
        "DST · PES · JEF",
        "5 h 05 m",
        True,
    ),
    (
        "Pet portrait",
        "left_chest",
        "canvas · 22,400 st",
        "Canvas · photoreal",
        "Panel · 8 in",
        "Cotton canvas",
        22400,
        "DST · EMB",
        "11 h",
        True,
    ),
    (
        "Fire dept. shield",
        "left_chest",
        "left chest · 12,050 st",
        "Left chest · duck",
        "Left chest · 4 in",
        "Duck cloth",
        12050,
        "DST · VP3",
        "4 h 20 m",
        True,
    ),
    (
        "Monogram set",
        "caps",
        "cap side · 1,980 st",
        "Piqué · 4 mm text",
        "Left chest · 1.6 in",
        "Piqué polo knit",
        1980,
        "DST · PES",
        "1 h 15 m",
        True,
    ),
    ("Merrowed edge patch", "patches", "3.5in · twill", "", "", "", None, "", "", False),
    ("Auto Werks", "vector", "vector redraw · AI", "", "", "", None, "", "", False),
    ("Chenille varsity C", "patches", "8in · wool felt", "", "", "", None, "", "", False),
    ("3D puff wordmark", "caps", "cap front · 5,240 st", "", "", "", 5240, "", "", False),
    ("Sublimation pack", "vector", "6-colour separation", "", "", "", None, "", "", False),
    ("Union local 214", "jacket_back", "jacket back · 14,700 st", "", "", "", 14700, "", "", False),
]
TESTIMONIALS = [
    (
        "First shop that actually asks what fabric it's going on. Thread breaks dropped to almost nothing.",
        "Sarah Mitchell",
        "Owner · Stitch Perfect",
    ),
    (
        "Sent a mess of a JPEG at 11pm, had a clean DST plus sew-out photo before my morning run.",
        "James Chen",
        "Production Manager · Clear Apparel",
    ),
    (
        "Their small-lettering work is the best I've bought. 4mm text that still reads on piqué.",
        "Maria Rodriguez",
        "Cap & Promo Specialist",
    ),
]
FAQS = [
    (
        "What exactly is embroidery digitizing?",
        "It is the process of converting your artwork into a stitch file your machine can read — deciding stitch "
        "type, direction, density, underlay and sequence. Done well, it sews clean at speed; done badly, it breaks "
        "thread and puckers fabric.",
    ),
    (
        "How much does a design cost?",
        "Pricing is flat per design: $6 for a left chest or cap front, $10 for a full back and $15 for complex "
        "designs. Rush turnaround adds a small surcharge shown at checkout.",
    ),
    (
        "Are revisions included?",
        "Yes. Any revision within the original brief is free and usually back the same day. New artwork or a "
        "different size counts as a new file.",
    ),
    (
        "Which file formats do you deliver?",
        "DST, PES, EXP, JEF, VP3, XXX, HUS, EMB and the source file. Tell us your machine and we'll include "
        "everything it reads.",
    ),
    (
        "What patch types do you make?",
        "Iron-on, embroidered and rubber (PVC) patches with iron-on, velcro, adhesive or sew-on backing. "
        "Minimum 50 pieces, shipped to the address you give us.",
    ),
]
POSTS = [
    (
        "Why your cap logo puckers — and the four settings that fix it",
        "Technique",
        True,
        "Pull compensation, center-out sequencing, underlay choice and density. A walkthrough with stitch counts "
        "from a real job.",
        """A cap panel is a curved, unstable, foam-backed surface being pushed through a frame that only holds it at the edges. Nothing about it forgives a flat-goods file.

Most puckering we see comes from four decisions made before the first stitch: underlay type, density, pull compensation and sequencing. Get them right and the same artwork sews clean on twill, foam-front and unstructured six-panels alike.

## 1. Underlay does the flattening

Edge-walk plus zig-zag under every satin column. On foam fronts, add a centre-run to tack the foam before the column locks it down. Skipping underlay to save 400 stitches costs you the whole run.

## 2. Pull compensation is per-column

Thin columns need proportionally more compensation than wide ones. A flat 0.2mm across the file narrows your small letters and bloats the big ones.

> Rule of thumb: if a column is under 1.2mm wide, it is a run stitch. Satin at that width will always look ragged on twill.

## 3. Sew centre-out, bottom-up

Cap frames fight you from the middle outward. Sequencing the file the same direction keeps the fabric from bunching ahead of the needle.

## 4. Density follows the fabric

Structured fronts take standard density; unstructured caps need it opened up by 10–15% so the panel doesn't stiffen into a shield.
""",
    ),
    (
        "DST vs PES vs EXP: what actually changes in the file",
        "Formats",
        False,
        "",
        "Every machine format stores the same thing — needle moves — but not the same metadata.\n\n"
        "## DST\n\nTajima's format stores stitches and colour stops only. No thread colours.\n\n"
        "## PES\n\nBrother and Babylock. Stores thread colours and a preview image.\n\n"
        "## EXP\n\nMelco and Bernina. Stitch data with separate colour files.",
    ),
    (
        "Small lettering that survives piqué knit",
        "Technique",
        False,
        "",
        "Piqué has a texture that swallows thin columns. Use a light fill underlay, open the density and keep "
        "letters above 4 mm cap height.",
    ),
    (
        "22,400 stitches: a pet portrait, start to finish",
        "Case study",
        False,
        "",
        "Photo-real portraits are built in layers: base fills, mid tones, then detail runs on top.",
    ),
]


class Command(BaseCommand):
    help = "Seed pricing, site content and the initial admin account. Safe to run more than once."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-demo", action="store_true", help="Skip demo content (portfolio, blog, etc.)"
        )
        parser.add_argument("--admin-email", default=None)
        parser.add_argument("--admin-password", default=None)

    @transaction.atomic
    def handle(self, *args, **opts):
        site = SiteSettings.load()
        if not site.order_notification_emails:
            site.order_notification_emails = django_settings.STAFF_NOTIFY_EMAIL
            site.save(update_fields=["order_notification_emails"])

        for service, name, plan, ribbon, price, order, highlighted, features in PRICING_TIERS:
            PricingTier.objects.get_or_create(
                service=service,
                name=name,
                defaults={
                    "plan_name": plan,
                    "ribbon": ribbon,
                    "price": Decimal(price),
                    "sort_order": order,
                    "is_highlighted": highlighted,
                    "features": chr(10).join(features),
                },
            )
        for name, hours, surcharge, default, order in TURNAROUNDS:
            TurnaroundOption.objects.get_or_create(
                name=name,
                defaults={
                    "hours": hours,
                    "surcharge": Decimal(surcharge),
                    "is_default": default,
                    "sort_order": order,
                },
            )
        for name, desc, price, order in PATCH_CATEGORIES:
            PatchCategory.objects.get_or_create(
                name=name, defaults={"description": desc, "unit_price": Decimal(price), "sort_order": order}
            )
        self.stdout.write(self.style.SUCCESS("Pricing tiers, turnarounds and patch categories ready."))

        email = (opts["admin_email"] or os.environ.get("ADMIN_EMAIL") or "").strip().lower()
        password = opts["admin_password"] or os.environ.get("ADMIN_PASSWORD")
        if email and password:
            admin, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "full_name": "Studio Admin",
                    "is_staff": True,
                    "is_superuser": True,
                    "email_verified": True,
                },
            )
            if created:
                admin.set_password(password)
                admin.save()
                self.stdout.write(self.style.SUCCESS(f"Admin account created: {email}"))
            else:
                self.stdout.write(f"Admin account already exists: {email}")

        if opts["no_demo"]:
            return

        if not PortfolioItem.objects.exists():
            for i, (name, cat, meta, tag, placement, fabric, st, formats, ta, home) in enumerate(PORTFOLIO):
                PortfolioItem.objects.create(
                    name=name,
                    category=cat,
                    meta=meta,
                    showcase_tag=tag,
                    placement=placement,
                    fabric=fabric,
                    stitches=st,
                    formats=formats,
                    turnaround=ta,
                    show_on_home=home,
                    sort_order=i,
                )
        if not Testimonial.objects.exists():
            for i, (quote, name, role) in enumerate(TESTIMONIALS):
                Testimonial.objects.create(quote=quote, name=name, role=role, sort_order=i)
        if not FAQ.objects.exists():
            for i, (q, a) in enumerate(FAQS):
                FAQ.objects.create(question=q, answer=a, sort_order=i)
        if not Post.objects.exists():
            author = User.objects.staff().first()
            for i, (title, cat, featured, excerpt, body) in enumerate(POSTS):
                category, _ = Category.objects.get_or_create(name=cat)
                Post.objects.create(
                    title=title,
                    category=category,
                    is_featured=featured,
                    excerpt=excerpt,
                    body=body,
                    status=Post.Status.PUBLISHED,
                    author=author,
                    published_at=timezone.now() - timedelta(days=i * 12),
                )
        self.stdout.write(self.style.SUCCESS("Demo content loaded."))
