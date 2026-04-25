import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_auditlog_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["organization", "timestamp"], name="audit_org_timestamp_idx"),
        ),
    ]
