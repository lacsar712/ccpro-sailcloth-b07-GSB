from django.db import migrations, models
from django.utils import timezone


def backfill_dip_date(apps, schema_editor):
    DipRun = apps.get_model("core", "DipRun")
    for run in DipRun.objects.all():
        run.dip_date = timezone.localdate(run.started_at)
        run.save(update_fields=["dip_date"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="diprun",
            name="dip_date",
            field=models.DateField(editable=False, null=True),
        ),
        migrations.RunPython(backfill_dip_date, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="diprun",
            name="dip_date",
            field=models.DateField(editable=False),
        ),
        migrations.AddConstraint(
            model_name="diprun",
            constraint=models.UniqueConstraint(
                fields=("roll", "dip_date"), name="uniq_diprun_roll_dip_date"
            ),
        ),
    ]
