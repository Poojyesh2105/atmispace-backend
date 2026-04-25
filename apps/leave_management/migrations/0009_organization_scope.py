import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("leave_management", "0008_leavepolicy_carry_forward_frequency"),
    ]

    operations = [
        migrations.AddField(
            model_name="leavebalance",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="leave_management_leavebalance_records",
                to="core.organization",
            ),
        ),
        migrations.AddField(
            model_name="leavepolicy",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="leave_management_leavepolicy_records",
                to="core.organization",
            ),
        ),
        migrations.AddField(
            model_name="leaverequest",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="leave_management_leaverequest_records",
                to="core.organization",
            ),
        ),
        migrations.AddField(
            model_name="earnedleaveadjustment",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="leave_management_earnedleaveadjustment_records",
                to="core.organization",
            ),
        ),
        migrations.AddField(
            model_name="leavecarryforwardlog",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="leave_management_leavecarryforwardlog_records",
                to="core.organization",
            ),
        ),
        migrations.AddConstraint(
            model_name="leavebalance",
            constraint=models.CheckConstraint(check=Q(allocated_days__gte=0), name="leave_balance_allocated_non_negative"),
        ),
        migrations.AddConstraint(
            model_name="leavebalance",
            constraint=models.CheckConstraint(check=Q(used_days__gte=0), name="leave_balance_used_non_negative"),
        ),
        migrations.AddConstraint(
            model_name="leavepolicy",
            constraint=models.UniqueConstraint(
                condition=Q(organization__isnull=False),
                fields=("organization",),
                name="unique_leave_policy_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="leaverequest",
            constraint=models.CheckConstraint(check=Q(total_days__gt=0), name="leave_request_total_days_positive"),
        ),
        migrations.AddConstraint(
            model_name="leaverequest",
            constraint=models.CheckConstraint(check=Q(lop_days_applied__gte=0), name="leave_request_lop_days_non_negative"),
        ),
        migrations.AddIndex(
            model_name="leavebalance",
            index=models.Index(fields=["organization", "leave_type"], name="leave_org_type_idx"),
        ),
        migrations.AddIndex(
            model_name="leaverequest",
            index=models.Index(fields=["organization", "status", "start_date"], name="leave_org_status_start_idx"),
        ),
        migrations.AddIndex(
            model_name="earnedleaveadjustment",
            index=models.Index(fields=["organization", "work_date", "status"], name="leave_org_work_status_idx"),
        ),
    ]
