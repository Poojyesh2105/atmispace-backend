from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0005_salary_component_flexibility"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="payslip",
            name="fixed_deductions",
        ),
    ]
