import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
        ("employees", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Attendance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("attendance_date", models.DateField()),
                ("check_in", models.DateTimeField(blank=True, null=True)),
                ("check_out", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("PRESENT", "Present"), ("HALF_DAY", "Half Day"), ("REMOTE", "Remote"), ("ABSENT", "Absent")], default="PRESENT", max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("total_work_minutes", models.PositiveIntegerField(default=0)),
                (
                    "employee",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendances", to="employees.employee"),
                ),
            ],
            options={"ordering": ["-attendance_date", "-check_in"]},
        ),
        migrations.AddConstraint(
            model_name="attendance",
            constraint=models.UniqueConstraint(fields=("employee", "attendance_date"), name="unique_daily_attendance"),
        ),
    ]
