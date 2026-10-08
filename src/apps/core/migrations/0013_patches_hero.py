from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0012_alter_siteimage_slot")]

    operations = [
        migrations.AlterField(
            model_name="beforeafter",
            name="service",
            field=models.CharField(max_length=20, unique=True, choices=[
                ("embroidery", "Embroidery digitizing"),
                ("vector", "Vector art"),
                ("patches", "Patches"),
            ]),
        ),
        migrations.AlterField(
            model_name="beforeafter",
            name="after_image",
            field=models.ImageField(upload_to="before-after/", blank=True),
        ),
    ]
