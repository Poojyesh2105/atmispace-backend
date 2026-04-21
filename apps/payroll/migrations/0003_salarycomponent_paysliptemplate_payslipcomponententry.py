# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0002_deductionrule_payrollrun_salaryrevision_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SalaryComponent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=140)),
                ('code', models.CharField(max_length=40, unique=True)),
                ('component_type', models.CharField(choices=[('EARNING', 'Earning'), ('DEDUCTION', 'Deduction')], max_length=20)),
                ('calculation_type', models.CharField(
                    choices=[('FIXED', 'Fixed Amount'), ('PERCENT_OF_GROSS', '% of Gross'), ('PERCENT_OF_CTC', '% of CTC')],
                    default='FIXED',
                    max_length=30,
                )),
                ('value', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('is_taxable', models.BooleanField(default=False)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['component_type', 'display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='PayslipTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=140, unique=True)),
                ('description', models.TextField(blank=True)),
                ('is_default', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('header_html', models.TextField(blank=True, help_text='HTML for the header section')),
                ('body_html', models.TextField(blank=True, help_text='HTML template body. Use {{employee_name}}, {{payroll_month}}, {{net_pay}}, {{components}} etc.')),
                ('footer_html', models.TextField(blank=True, help_text='HTML for the footer section')),
                ('css_styles', models.TextField(blank=True, help_text='Custom CSS for the template')),
                ('show_component_breakdown', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['-is_default', 'name'],
            },
        ),
        migrations.CreateModel(
            name='PayslipComponentEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('component_name', models.CharField(max_length=140)),
                ('component_code', models.CharField(max_length=40)),
                ('component_type', models.CharField(choices=[('EARNING', 'Earning'), ('DEDUCTION', 'Deduction')], max_length=20)),
                ('calculated_amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('payslip', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='component_entries', to='payroll.payslip')),
                ('component', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='payslip_entries',
                    to='payroll.salarycomponent',
                )),
            ],
            options={
                'ordering': ['component_type', 'display_order', 'component_name'],
            },
        ),
    ]
