import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("core", "0001_initial"),
        ("employees", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeaveRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("leave_type", models.CharField(choices=[("CASUAL", "Casual"), ("SICK", "Sick"), ("EARNED", "Earned")], max_length=20)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("reason", models.TextField()),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")], default="PENDING", max_length=20)),
                ("total_days", models.DecimalField(decimal_places=1, max_digits=5)),
                ("approver_note", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "approver",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="leave_approvals", to="accounts.user"),
                ),
                (
                    "employee",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leave_requests", to="employees.employee"),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="LeaveBalance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("leave_type", models.CharField(choices=[("CASUAL", "Casual"), ("SICK", "Sick"), ("EARNED", "Earned")], max_length=20)),
                ("allocated_days", models.DecimalField(decimal_places=1, default=0, max_digits=5)),
                ("used_days", models.DecimalField(decimal_places=1, default=0, max_digits=5)),
                (
                    "employee",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leave_balances", to="employees.employee"),
                ),
            ],
            options={"ordering": ["employee__employee_id", "leave_type"]},
        ),
        migrations.AddConstraint(
            model_name="leavebalance",
            constraint=models.UniqueConstraint(fields=("employee", "leave_type"), name="unique_leave_balance_type"),
        ),
    ]
