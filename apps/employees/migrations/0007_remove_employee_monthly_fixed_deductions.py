from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0006_employee_personal_email"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="employee",
            name="monthly_fixed_deductions",
        ),
    ]
