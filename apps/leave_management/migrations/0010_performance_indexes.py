"""
Performance indexes for the leave_management app.
NOTE: LeaveBalance model Meta already defines:
  - Index(["employee", "leave_type"])
  - Index(["organization", "leave_type"])
LeaveRequest already defines:
  - Index(["status", "start_date"])
  - Index(["employee", "status"])
  - Index(["organization", "status", "start_date"])
This migration only adds NEW indexes not present in the initial migration.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leave_management", "0009_organization_scope"),
    ]

    operations = [
        # LeaveRequest: date-range overlap queries (start_date AND end_date needed)
        migrations.AddIndex(
            model_name="leaverequest",
            index=models.Index(
                fields=["employee", "start_date", "end_date"],
                name="leave_req_emp_date_range_idx",
            ),
        ),
        # LeaveRequest: org-scoped pending leaves for HR dashboard
        migrations.AddIndex(
            model_name="leaverequest",
            index=models.Index(
                fields=["organization", "status"],
                name="leave_req_org_status_idx",
            ),
        ),
    ]
