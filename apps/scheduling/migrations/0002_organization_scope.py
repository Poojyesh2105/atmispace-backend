import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("scheduling", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="shiftrotationrule",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scheduling_shiftrotationrule_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="shiftrosterentry",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scheduling_shiftrosterentry_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="scheduleconflict",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="scheduling_scheduleconflict_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="shiftrosterentry",
            index=models.Index(fields=["organization", "roster_date", "is_conflicted"], name="schedule_roster_org_date_idx"),
        ),
        migrations.AddIndex(
            model_name="scheduleconflict",
            index=models.Index(fields=["organization", "conflict_type", "is_resolved"], name="schedule_conflict_org_idx"),
        ),
    ]
