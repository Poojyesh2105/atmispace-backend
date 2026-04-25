import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("payroll", "0009_backfill_lop_component_entries"),
    ]

    operations = [
        migrations.AddField(
            model_name="payrollcycle",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payroll_payrollcycle_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="payrollrun",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payroll_payrollrun_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="payrolladjustment",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payroll_payrolladjustment_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="salaryrevision",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payroll_salaryrevision_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="payslip",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payroll_payslip_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="salarycomponenttemplate",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payroll_salarycomponenttemplate_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="employeesalarycomponenttemplate",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payroll_employeesalarycomponenttemplate_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="salarycomponent",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payroll_salarycomponent_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="payslipcomponententry",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payroll_payslipcomponententry_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="paysliptemplate",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payroll_paysliptemplate_records", to="core.organization"),
        ),
        migrations.AddConstraint(
            model_name="payrolladjustment",
            constraint=models.CheckConstraint(check=Q(amount__gte=0), name="payroll_adjustment_amount_non_negative"),
        ),
        migrations.AddConstraint(
            model_name="salaryrevision",
            constraint=models.CheckConstraint(check=Q(previous_ctc__gte=0), name="salary_revision_previous_ctc_non_negative"),
        ),
        migrations.AddConstraint(
            model_name="salaryrevision",
            constraint=models.CheckConstraint(check=Q(new_ctc__gt=0), name="salary_revision_new_ctc_positive"),
        ),
        migrations.AddIndex(
            model_name="payrollcycle",
            index=models.Index(fields=["organization", "payroll_month", "status"], name="payroll_cycle_org_month_idx"),
        ),
        migrations.AddIndex(
            model_name="payrollrun",
            index=models.Index(fields=["organization", "status"], name="payroll_run_org_status_idx"),
        ),
        migrations.AddIndex(
            model_name="payrolladjustment",
            index=models.Index(fields=["organization", "status", "cycle"], name="payroll_adj_org_status_idx"),
        ),
        migrations.AddIndex(
            model_name="salaryrevision",
            index=models.Index(fields=["organization", "effective_date"], name="payroll_rev_org_effective_idx"),
        ),
        migrations.AddIndex(
            model_name="payslip",
            index=models.Index(fields=["organization", "payroll_month"], name="payroll_payslip_org_month_idx"),
        ),
    ]
