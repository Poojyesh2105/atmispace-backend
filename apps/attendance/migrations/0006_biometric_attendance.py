import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0009_employee_biometric_id"),
        ("attendance", "0005_attendance_location_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="break_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="attendance",
            name="source",
            field=models.CharField(
                choices=[
                    ("MANUAL", "Manual"),
                    ("BIOMETRIC", "Biometric"),
                    ("REGULARIZATION", "Regularization"),
                ],
                db_index=True,
                default="MANUAL",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="BiometricDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=140)),
                ("device_code", models.CharField(max_length=80, unique=True)),
                ("secret_key", models.CharField(max_length=160)),
                ("location_name", models.CharField(blank=True, max_length=140)),
                ("is_active", models.BooleanField(default=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["name", "device_code"],
            },
        ),
        migrations.CreateModel(
            name="BiometricAttendanceEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("device_user_id", models.CharField(max_length=80)),
                ("external_event_id", models.CharField(blank=True, max_length=120, null=True)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("CHECK_IN", "Check In"),
                            ("CHECK_OUT", "Check Out"),
                            ("BREAK_START", "Break Start"),
                            ("BREAK_END", "Break End"),
                            ("AUTO", "Auto"),
                        ],
                        max_length=20,
                    ),
                ),
                ("occurred_at", models.DateTimeField(db_index=True)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PROCESSED", "Processed"),
                            ("IGNORED", "Ignored"),
                            ("FAILED", "Failed"),
                        ],
                        db_index=True,
                        default="PROCESSED",
                        max_length=20,
                    ),
                ),
                ("message", models.TextField(blank=True)),
                (
                    "attendance",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="biometric_events",
                        to="attendance.attendance",
                    ),
                ),
                (
                    "device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="attendance_events",
                        to="attendance.biometricdevice",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="biometric_events",
                        to="employees.employee",
                    ),
                ),
            ],
            options={
                "ordering": ["-occurred_at", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="biometricattendanceevent",
            constraint=models.UniqueConstraint(
                fields=("device", "external_event_id"),
                name="unique_biometric_device_external_event",
            ),
        ),
        migrations.AddIndex(
            model_name="biometricattendanceevent",
            index=models.Index(
                fields=["device", "device_user_id", "occurred_at"],
                name="attendance__device__41cbd1_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="biometricattendanceevent",
            index=models.Index(
                fields=["employee", "occurred_at"],
                name="attendance__employe_795da9_idx",
            ),
        ),
    ]
