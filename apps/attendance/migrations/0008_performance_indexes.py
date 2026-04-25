"""
Performance indexes for the attendance app.
All originally planned indexes already exist in the model Meta
(created by the initial migration).  This migration adds one
genuinely new index for biometric-source reporting.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0007_organization_scope"),
    ]

    operations = [
        # org + source: fast split of BIOMETRIC vs MANUAL attendance within an org
        migrations.AddIndex(
            model_name="attendance",
            index=models.Index(
                fields=["organization", "source"],
                name="attendance_org_source_idx",
            ),
        ),
    ]
