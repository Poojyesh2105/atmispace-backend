import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("attendance", "0006_biometric_attendance"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="attendance_attendance_records",
                to="core.organization",
            ),
        ),
        migrations.AddField(
            model_name="biometricdevice",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="attendance_biometricdevice_records",
                to="core.organization",
            ),
        ),
        migrations.AddField(
            model_name="biometricattendanceevent",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="attendance_biometricattendanceevent_records",
                to="core.organization",
            ),
        ),
        migrations.AddField(
            model_name="attendanceregularization",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="attendance_attendanceregularization_records",
                to="core.organization",
            ),
        ),
        migrations.AddIndex(
            model_name="attendance",
            index=models.Index(fields=["organization", "attendance_date", "status"], name="attendance_org_date_status_idx"),
        ),
        migrations.AddIndex(
            model_name="biometricattendanceevent",
            index=models.Index(fields=["organization", "occurred_at", "status"], name="attendance_org_event_status_idx"),
        ),
        migrations.AddIndex(
            model_name="attendanceregularization",
            index=models.Index(fields=["organization", "date", "status"], name="attendance_org_reg_status_idx"),
        ),
    ]
