"""Order estimate rules — the single source of truth for what a customer is quoted.

* Digitizing and vector art use a flat price per design type (PricingTier) plus
  the turnaround surcharge.
* Patches are priced per piece from the category's starting price × quantity.
The admin can override with `final_price` once the artwork has been reviewed.
"""

from decimal import ROUND_HALF_UP, Decimal

from .models import PatchCategory, PricingTier, Service, TurnaroundOption

CENT = Decimal("0.01")


def compute_estimate(service, tier=None, turnaround=None, patch_category=None, quantity=None):
    if service == Service.PATCHES:
        if patch_category is None or not quantity:
            return None
        return (patch_category.unit_price * Decimal(quantity)).quantize(CENT, ROUND_HALF_UP)

    if tier is None:
        return None
    total = tier.price
    if turnaround is not None:
        total += turnaround.surcharge
    return total.quantize(CENT, ROUND_HALF_UP)


def pricing_payload(hide_prices=False):
    """Serializable pricing data for the live estimate on the order form.

    With ``hide_prices`` (the quote form) only names and ids are sent, never a price.
    """
    data = {
        "tiers": [
            {
                "id": t.pk,
                "service": t.service,
                "name": t.name,
                "price": str(t.price),
                "description": t.description,
            }
            for t in PricingTier.objects.filter(is_active=True)
        ],
        "turnarounds": [
            {"id": t.pk, "name": t.name, "surcharge": str(t.surcharge), "hours": t.hours}
            for t in TurnaroundOption.objects.filter(is_active=True)
        ],
        "patchCategories": [
            {"id": c.pk, "name": c.name, "unitPrice": str(c.unit_price)}
            for c in PatchCategory.objects.filter(is_active=True)
        ],
    }
    if hide_prices:
        for key in ("tiers", "turnarounds", "patchCategories"):
            for row in data[key]:
                for field in ("price", "surcharge", "unitPrice"):
                    row.pop(field, None)
    return data
