from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.orders.models import PatchCategory, PricingTier, Service, TurnaroundOption


@pytest.fixture(autouse=True)
def _locmem_cache_reset():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def customer(db):
    return User.objects.create_user(
        email="jane@shop.com",
        password="Str0ng-pass!",
        full_name="Jane Whitfield",
        company="Whitfield Uniforms",
        email_verified=True,
    )


@pytest.fixture
def other_customer(db):
    return User.objects.create_user(
        email="other@shop.com", password="Str0ng-pass!", full_name="Other Person", email_verified=True
    )


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        email="admin@sedigitizer.com",
        password="Str0ng-pass!",
        full_name="Studio Admin",
        is_staff=True,
        email_verified=True,
    )


@pytest.fixture
def pricing(db):
    tiers = {
        "left_chest": PricingTier.objects.create(
            service=Service.DIGITIZING, name="Left chest", price=Decimal("6")
        ),
        "full_back": PricingTier.objects.create(
            service=Service.DIGITIZING, name="Full back", price=Decimal("10")
        ),
        "complex": PricingTier.objects.create(
            service=Service.DIGITIZING, name="Complex design", price=Decimal("15")
        ),
        "vector": PricingTier.objects.create(
            service=Service.VECTOR, name="Standard vector", price=Decimal("10")
        ),
    }
    turnarounds = {
        "standard": TurnaroundOption.objects.create(
            name="Standard", hours=4, surcharge=Decimal("0"), is_default=True
        ),
        "rush": TurnaroundOption.objects.create(name="Rush", hours=2, surcharge=Decimal("3")),
    }
    patches = {
        "iron": PatchCategory.objects.create(name="Iron-on patch", unit_price=Decimal("1.10")),
        "rubber": PatchCategory.objects.create(name="Rubber patch", unit_price=Decimal("1.60")),
    }
    return {"tiers": tiers, "turnarounds": turnarounds, "patches": patches}


@pytest.fixture
def artwork():
    def make(name="logo.png", content=b"\x89PNG\r\n\x1a\nfake"):
        return SimpleUploadedFile(name, content, content_type="image/png")

    return make


@pytest.fixture
def image_file():
    """A real (tiny) PNG, so ImageField validation passes."""
    import struct
    import zlib

    signature = bytes([137, 80, 78, 71, 13, 10, 26, 10])
    gold = bytes([224, 165, 60])

    def chunk(kind, payload):
        body = kind + payload
        return struct.pack("!I", len(payload)) + body + struct.pack("!I", zlib.crc32(body) & 0xFFFFFFFF)

    def make(name="photo.png"):
        rows = (bytes([0]) + gold * 4) * 4  # 4x4 pixels, each row filter byte 0
        data = (
            signature
            + chunk(b"IHDR", struct.pack("!IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows))
            + chunk(b"IEND", b"")
        )
        return SimpleUploadedFile(name, data, content_type="image/png")

    return make
