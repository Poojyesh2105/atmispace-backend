from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0003_salarycomponent_paysliptemplate_payslipcomponententry"),
    ]

    operations = [
        migrations.AddField(
            model_name="paysliptemplate",
            name="editor_config",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="No-code editor settings used to generate the template source.",
            ),
        ),
    ]
