import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("employees", "0009_employee_biometric_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="department",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employees_department_records",
                to="core.organization",
            ),
        ),
        migrations.AddField(
            model_name="organizationsettings",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employees_organizationsettings_records",
                to="core.organization",
            ),
        ),
        migrations.AddField(
            model_name="shifttemplate",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employees_shifttemplate_records",
                to="core.organization",
            ),
        ),
        migrations.AddField(
            model_name="employee",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employees_employee_records",
                to="core.organization",
            ),
        ),
        migrations.AddConstraint(
            model_name="organizationsettings",
            constraint=models.UniqueConstraint(
                condition=Q(organization__isnull=False),
                fields=("organization",),
                name="unique_organization_settings_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.CheckConstraint(
                check=Q(ctc_per_annum__gte=0),
                name="employee_ctc_non_negative",
            ),
        ),
        migrations.AddIndex(
            model_name="employee",
            index=models.Index(fields=["organization", "employee_id"], name="employees_emp_org_empid_idx"),
        ),
        migrations.AddIndex(
            model_name="employee",
            index=models.Index(fields=["organization", "is_active"], name="employees_emp_org_active_idx"),
        ),
    ]
