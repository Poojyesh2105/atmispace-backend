import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120, unique=True)),
                ("code", models.CharField(max_length=20, unique=True)),
                ("description", models.TextField(blank=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Employee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("employee_id", models.CharField(max_length=30, unique=True)),
                ("designation", models.CharField(max_length=150)),
                ("phone_number", models.CharField(blank=True, max_length=20)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("hire_date", models.DateField()),
                ("employment_type", models.CharField(choices=[("FULL_TIME", "Full Time"), ("CONTRACT", "Contract"), ("INTERN", "Intern")], default="FULL_TIME", max_length=20)),
                ("address", models.TextField(blank=True)),
                ("emergency_contact_name", models.CharField(blank=True, max_length=120)),
                ("emergency_contact_phone", models.CharField(blank=True, max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "department",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="employees", to="employees.department"),
                ),
                (
                    "manager",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="team_members", to="employees.employee"),
                ),
                (
                    "user",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="employee_profile", to="accounts.user"),
                ),
            ],
            options={"ordering": ["employee_id"]},
        ),
    ]
