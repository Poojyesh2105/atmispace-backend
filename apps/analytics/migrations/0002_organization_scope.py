import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("analytics", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="analyticssnapshot",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="analytics_analyticssnapshot_records", to="core.organization"),
        ),
        migrations.RemoveConstraint(
            model_name="analyticssnapshot",
            name="unique_analytics_snapshot_scope",
        ),
        migrations.AddConstraint(
            model_name="analyticssnapshot",
            constraint=models.UniqueConstraint(fields=("organization", "snapshot_date", "metric_key", "role_scope"), name="unique_analytics_snapshot_scope"),
        ),
        migrations.AddIndex(
            model_name="analyticssnapshot",
            index=models.Index(fields=["organization", "metric_key", "snapshot_date"], name="analytics_org_metric_date_idx"),
        ),
    ]
