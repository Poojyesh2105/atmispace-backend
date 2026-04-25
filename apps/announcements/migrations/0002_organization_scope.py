import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("announcements", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="announcement",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="announcements_announcement_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="announcementacknowledgement",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="announcements_announcementacknowledgement_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="announcement",
            index=models.Index(fields=["organization", "is_published", "starts_at"], name="announce_org_publish_start_idx"),
        ),
        migrations.AddIndex(
            model_name="announcementacknowledgement",
            index=models.Index(fields=["organization", "acknowledged_at"], name="announce_ack_org_ack_idx"),
        ),
    ]
