import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def repair_battle_state(apps, schema_editor):
    Tank = apps.get_model("tanks", "Tank")
    BattleRecord = apps.get_model("tanks", "BattleRecord")

    pending = BattleRecord.objects.filter(result="pending")

    Tank.objects.filter(is_in_battle=True).exclude(
        pk__in=pending.values("tank_id")
    ).update(is_in_battle=False)

    pending.filter(tank__is_in_battle=False).update(
        result="defeat", finished_at=timezone.now()
    )


class Migration(migrations.Migration):

    dependencies = [
        ("tanks", "0006_crewman_totp_confirmed"),
    ]

    operations = [
        migrations.RunPython(repair_battle_state, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tank",
            name="level",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tanks",
                to="tanks.level",
            ),
        ),
        migrations.AlterField(
            model_name="tank",
            name="nation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tanks",
                to="tanks.nation",
            ),
        ),
        migrations.AlterField(
            model_name="battlerecord",
            name="battle_level",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="battles",
                to="tanks.level",
            ),
        ),
    ]