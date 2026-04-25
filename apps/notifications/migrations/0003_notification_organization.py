import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("notifications", "0002_alter_notification_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications_notification_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["organization", "is_read", "created_at"], name="notify_org_read_created_idx"),
        ),
    ]
