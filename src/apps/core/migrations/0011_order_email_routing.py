from django.db import migrations, models


def route_new_order_notices(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.using(schema_editor.connection.alias).all().update(
        order_notification_emails="info@sedigitizer.com"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_sewouts"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="order_notification_emails",
            field=models.CharField(
                blank=True,
                default="info@sedigitizer.com",
                help_text="Receives a short notice when a new order is submitted. Separate addresses with commas.",
                max_length=500,
                verbose_name="new-order notice recipients",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="order_details_emails",
            field=models.CharField(
                default="scarletsembroidery@gmail.com",
                help_text="Receives the full order specification and submitted artwork files. Separate addresses with commas.",
                max_length=500,
                verbose_name="order details and artwork recipients",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="contact_notification_emails",
            field=models.CharField(
                default="support@sedigitizer.com",
                help_text="Receives contact form submissions. Separate addresses with commas.",
                max_length=500,
                verbose_name="contact form recipients",
            ),
        ),
        migrations.RunPython(route_new_order_notices, migrations.RunPython.noop),
    ]
