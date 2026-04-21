import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0004_paysliptemplate_editor_config"),
    ]

    operations = [
        migrations.RenameField(
            model_name="payslip",
            old_name="rule_based_deductions",
            new_name="component_deductions",
        ),
        migrations.AddField(
            model_name="salarycomponent",
            name="base_component",
            field=models.ForeignKey(
                blank=True,
                help_text="Component used as the base when calculation type is % of Component.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dependent_components",
                to="payroll.salarycomponent",
            ),
        ),
        migrations.AddField(
            model_name="salarycomponent",
            name="deduct_employer_contribution",
            field=models.BooleanField(
                default=False,
                help_text="For deductions, include employer contribution in employee deductions when enabled.",
            ),
        ),
        migrations.AddField(
            model_name="salarycomponent",
            name="employer_contribution_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="salarycomponent",
            name="has_employer_contribution",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="salarycomponent",
            name="is_part_of_gross",
            field=models.BooleanField(
                default=True,
                help_text="For earning components, mark whether the amount is already part of monthly gross salary.",
            ),
        ),
        migrations.AddField(
            model_name="payslipcomponententry",
            name="deducts_employer_contribution",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="payslipcomponententry",
            name="employer_contribution_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AlterField(
            model_name="salarycomponent",
            name="calculation_type",
            field=models.CharField(
                choices=[
                    ("FIXED", "Fixed Amount"),
                    ("PERCENT_OF_GROSS", "% of Gross"),
                    ("PERCENT_OF_CTC", "% of CTC"),
                    ("PERCENT_OF_COMPONENT", "% of Component"),
                ],
                default="FIXED",
                max_length=30,
            ),
        ),
        migrations.DeleteModel(
            name="DeductionRule",
        ),
    ]
