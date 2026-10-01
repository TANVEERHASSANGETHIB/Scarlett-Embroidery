from django.db import migrations

DEFAULTS = [
    ("Caps", "caps"),
    ("Left chest", "left_chest"),
    ("Jacket back", "jacket_back"),
    ("Patches", "patches"),
    ("Vector", "vector"),
]


def seed(apps, schema_editor):
    Category = apps.get_model("core", "PortfolioCategory")
    Item = apps.get_model("core", "PortfolioItem")
    for order, (name, slug) in enumerate(DEFAULTS, start=1):
        Category.objects.get_or_create(slug=slug, defaults={"name": name, "sort_order": order})
    # Keep any other category an existing photo already uses.
    known = set(Category.objects.values_list("slug", flat=True))
    for slug in Item.objects.exclude(category="").values_list("category", flat=True).distinct():
        if slug not in known:
            Category.objects.create(name=slug.replace("_", " ").title(), slug=slug, sort_order=99)


class Migration(migrations.Migration):
    dependencies = [("core", "0005_site_upgrade")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
