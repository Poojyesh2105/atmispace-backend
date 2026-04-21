from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_default_component_template(apps, schema_editor):
    SalaryComponentTemplate = apps.get_model("payroll", "SalaryComponentTemplate")
    SalaryComponent = apps.get_model("payroll", "SalaryComponent")
    Payslip = apps.get_model("payroll", "Payslip")

    template, _ = SalaryComponentTemplate.objects.get_or_create(
        name="Standard Salary Structure",
        defaults={
            "description": "Default salary component package used when no employee-specific package is assigned.",
            "is_default": True,
            "is_active": True,
        },
    )
    SalaryComponentTemplate.objects.exclude(pk=template.pk).filter(is_default=True).update(is_default=False)
    if not template.is_default or not template.is_active:
        template.is_default = True
        template.is_active = True
        template.save(update_fields=["is_default", "is_active", "updated_at"])

    SalaryComponent.objects.filter(template__isnull=True).update(template=template)
    Payslip.objects.filter(salary_component_template__isnull=True).update(
        salary_component_template=template,
        salary_component_template_name=template.name,
    )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payroll", "0007_update_salary_component_ordering"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalaryComponentTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=140, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["-is_default", "name"],
            },
        ),
        migrations.CreateModel(
            name="EmployeeSalaryComponentTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("notes", models.TextField(blank=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assigned_salary_component_templates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "employee",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="salary_component_template_assignment",
                        to="employees.employee",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_assignments",
                        to="payroll.salarycomponenttemplate",
                    ),
                ),
            ],
            options={
                "ordering": ["employee__employee_id"],
            },
        ),
        migrations.AddField(
            model_name="payslip",
            name="salary_component_template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payslips",
                to="payroll.salarycomponenttemplate",
            ),
        ),
        migrations.AddField(
            model_name="payslip",
            name="salary_component_template_name",
            field=models.CharField(blank=True, max_length=140),
        ),
        migrations.AddField(
            model_name="salarycomponent",
            name="template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="components",
                to="payroll.salarycomponenttemplate",
            ),
        ),
        migrations.RunPython(create_default_component_template, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="salarycomponent",
            name="template",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="components",
                to="payroll.salarycomponenttemplate",
            ),
        ),
        migrations.AlterField(
            model_name="salarycomponent",
            name="code",
            field=models.CharField(max_length=40),
        ),
        migrations.AlterModelOptions(
            name="salarycomponent",
            options={"ordering": ["template__name", "display_order", "name"]},
        ),
        migrations.AddConstraint(
            model_name="salarycomponent",
            constraint=models.UniqueConstraint(fields=("template", "code"), name="unique_salary_component_template_code"),
        ),
    ]
