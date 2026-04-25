"""
V3.1 — OrganizationSettings model.
Per-org JSON config blobs for attendance, leave, payroll, features, branding.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_organization_v3_membership"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("attendance_config", models.JSONField(blank=True, default=dict)),
                ("leave_config", models.JSONField(blank=True, default=dict)),
                ("payroll_config", models.JSONField(blank=True, default=dict)),
                ("feature_config", models.JSONField(blank=True, default=dict)),
                ("branding_config", models.JSONField(blank=True, default=dict)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="settings",
                        to="core.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Organization Settings",
                "verbose_name_plural": "Organization Settings",
            },
        ),
    ]
