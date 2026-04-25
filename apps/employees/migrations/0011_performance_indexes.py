"""
Performance indexes for the employees app.
NOTE: The model Meta already defines:
  - Index(["organization", "employee_id"])
  - Index(["organization", "is_active"])
This migration only adds NEW composite indexes not present in the initial migration.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0010_organization_scope"),
    ]

    operations = [
        # org + manager: fast team-roster lookups by manager within an org
        migrations.AddIndex(
            model_name="employee",
            index=models.Index(
                fields=["organization", "manager"],
                name="employee_org_manager_idx",
            ),
        ),
        # org + department: fast dept-roster lookups within an org
        migrations.AddIndex(
            model_name="employee",
            index=models.Index(
                fields=["organization", "department"],
                name="employee_org_dept_idx",
            ),
        ),
    ]
