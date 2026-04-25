import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("holidays", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="holidaycalendar",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="holidays_holidaycalendar_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="holiday",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="holidays_holiday_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="employeeholidayassignment",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="holidays_employeeholidayassignment_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="holiday",
            index=models.Index(fields=["organization", "date"], name="holiday_org_date_idx"),
        ),
    ]
