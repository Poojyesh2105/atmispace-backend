from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0006_remove_payslip_fixed_deductions"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="salarycomponent",
            options={"ordering": ["display_order", "name"]},
        ),
        migrations.AlterModelOptions(
            name="payslipcomponententry",
            options={"ordering": ["display_order", "component_name"]},
        ),
    ]
