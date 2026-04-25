"""
Performance indexes for the payroll app.
All originally planned indexes already exist in model Meta
(Payslip: payroll_month, employee+payroll_month, org+payroll_month;
 PayrollRun: status, org+status).
This migration is a safe no-op placeholder that preserves
the migration chain for future additions.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0010_organization_scope"),
    ]

    operations = []
