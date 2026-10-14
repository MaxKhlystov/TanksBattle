from django.db import migrations, models


def rotate_exposed_totp_keys(apps, schema_editor):
    # Все прежние секреты были доступны любой залогиненной сессии через get-totp,
    # поэтому считаем их скомпрометированными: сотрудники пройдут привязку заново.
    Crewman = apps.get_model("tanks", "Crewman")
    Crewman.objects.exclude(totp_key__isnull=True).update(totp_key=None)


class Migration(migrations.Migration):

    dependencies = [
        ("tanks", "0005_alter_tank_picture_tankphoto"),
    ]

    operations = [
        migrations.AddField(
            model_name="crewman",
            name="totp_confirmed",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(rotate_exposed_totp_keys, migrations.RunPython.noop),
    ]