from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from apps.core.models import SewOut

ORANGE = "#F0A84C"
GOLD = "#C98A3D"
BLACK = "#111111"
WHITE = "#FFFFFF"

# title, client, details, garment colour, thread colour, shape
SAMPLES = [
    (
        "Left-chest logo on polo",
        "Sample client",
        "Pique polo · 3.5 in · 8,200 stitches",
        "#E6E8EB",
        ORANGE,
        "ring",
    ),
    (
        "Cap front, 3D puff",
        "Sample client",
        "Structured cap · 2.5 in · 9,600 stitches",
        "#2A2A2A",
        ORANGE,
        "bars",
    ),
    (
        "Full-back jacket crest",
        "Sample client",
        "Twill jacket · 10 in · 38,000 stitches",
        "#C9CDD2",
        GOLD,
        "ring",
    ),
    ("Name patch", "Sample client", "Twill patch · 3 in · 5,400 stitches", "#FFFFFF", BLACK, "bars"),
    (
        "Hoodie sleeve script",
        "Sample client",
        "Fleece hoodie · 4 in · 6,100 stitches",
        "#3A3A3A",
        WHITE,
        "ring",
    ),
    ("Tote bag emblem", "Sample client", "Canvas tote · 5 in · 11,300 stitches", "#F3EFE8", GOLD, "bars"),
]


def make_image(garment, thread, shape, size=1000):
    img = Image.new("RGB", (size, size), garment)
    d = ImageDraw.Draw(img)
    # fabric weave
    for y in range(0, size, 8):
        d.line([(0, y), (size, y)], fill=_shade(garment, -6), width=1)
    c = size // 2
    if shape == "ring":
        for r, w in ((300, 26), (230, 14), (120, 40)):
            d.ellipse([c - r, c - r, c + r, c + r], outline=thread, width=w)
    else:
        for i, y in enumerate(range(260, 760, 62)):
            d.rounded_rectangle([200 + (i % 2) * 40, y, 800 - (i % 3) * 50, y + 38], radius=19, fill=thread)
    # stitch texture
    for y in range(0, size, 6):
        d.line([(0, y), (size, y)], fill=garment, width=1)
    return img


def _shade(hex_colour, delta):
    h = hex_colour.lstrip("#")
    r, g, b = (max(0, min(255, int(h[i : i + 2], 16) + delta)) for i in (0, 2, 4))
    return f"#{r:02x}{g:02x}{b:02x}"


class Command(BaseCommand):
    help = "Create placeholder client sew-outs so the testimonials gallery can be previewed."

    def handle(self, *args, **options):
        made = 0
        for i, (title, client, details, garment, thread, shape) in enumerate(SAMPLES, start=1):
            if SewOut.objects.filter(title=title, client=client).exists():
                continue
            buf = BytesIO()
            make_image(garment, thread, shape).save(buf, "JPEG", quality=85)
            obj = SewOut(title=title, client=client, details=details, sort_order=i)
            obj.image.save(f"sample-{i}.jpg", ContentFile(buf.getvalue()), save=False)
            obj.save()
            made += 1
        self.stdout.write(self.style.SUCCESS(f"Created {made} placeholder sew-outs."))
