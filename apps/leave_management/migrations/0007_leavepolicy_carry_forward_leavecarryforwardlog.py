import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0006_employee_personal_email"),
        ("leave_management", "0006_leaverequest_lop_days_applied"),
    ]

    operations = [
        migrations.AddField(
            model_name="leavepolicy",
            name="enable_carry_forward",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="leavepolicy",
            name="max_carry_forward_days",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="leavepolicy",
            name="carry_forward_leave_types",
            field=models.JSONField(default=list),
        ),
        migrations.CreateModel(
            name="LeaveCarryForwardLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "leave_type",
                    models.CharField(
                        choices=[("CASUAL", "Casual"), ("SICK", "Sick"), ("EARNED", "Earned"), ("LOP", "Loss Of Pay")],
                        max_length=20,
                    ),
                ),
                ("from_month", models.DateField()),
                ("to_month", models.DateField()),
                ("unused_days", models.DecimalField(decimal_places=1, max_digits=5)),
                ("carried_forward_days", models.DecimalField(decimal_places=1, max_digits=5)),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="carry_forward_logs",
                        to="employees.employee",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="leavecarryforwardlog",
            constraint=models.UniqueConstraint(
                fields=("employee", "leave_type", "from_month"),
                name="unique_carry_forward_per_month",
            ),
        ),
    ]
