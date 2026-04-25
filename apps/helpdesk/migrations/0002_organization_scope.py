import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("helpdesk", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="helpdeskcategory",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="helpdesk_helpdeskcategory_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="helpdeskticket",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="helpdesk_helpdeskticket_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="helpdeskcomment",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="helpdesk_helpdeskcomment_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="helpdeskticket",
            index=models.Index(fields=["organization", "status", "priority"], name="helpdesk_ticket_org_idx"),
        ),
    ]
