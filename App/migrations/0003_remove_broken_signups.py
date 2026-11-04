from django.conf import settings
from django.db import migrations


def forwards(apps, schema_editor):
    from App.signups import remove_broken_signups

    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    remove_broken_signups(apps.get_model(app_label, model_name))


class Migration(migrations.Migration):
    dependencies = [
        ("App", "0002_email_verification"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
