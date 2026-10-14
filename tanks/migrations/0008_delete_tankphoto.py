from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tanks", "0007_protect_fks_repair_battles"),
    ]

    operations = [
        migrations.DeleteModel(
            name="TankPhoto",
        ),
    ]