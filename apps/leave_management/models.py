from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models import UniqueConstraint

from apps.core.models import OrganizationScopedModel
from apps.employees.models import Employee


class LeaveBalance(OrganizationScopedModel):
    class LeaveType(models.TextChoices):
        CASUAL = "CASUAL", "Casual"
        SICK = "SICK", "Sick"
        EARNED = "EARNED", "Earned"
        LOP = "LOP", "Loss Of Pay"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_balances")
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices)
    allocated_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    used_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    class Meta:
        ordering = ["employee__employee_id", "leave_type"]
        indexes = [
            models.Index(fields=["employee", "leave_type"]),
            models.Index(fields=["organization", "leave_type"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["employee", "leave_type"], name="unique_leave_balance_type"),
            models.CheckConstraint(check=Q(allocated_days__gte=0), name="leave_balance_allocated_non_negative"),
            models.CheckConstraint(check=Q(used_days__gte=0), name="leave_balance_used_non_negative"),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.leave_type}"

    @property
    def available_days(self):
        return self.allocated_days - self.used_days


class LeavePolicy(OrganizationScopedModel):
    class CarryForwardFrequency(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        YEARLY = "YEARLY", "Yearly"

    casual_days_onboarding = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    sick_days_onboarding = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    earned_days_onboarding = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    monthly_sick_leave_limit = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    monthly_earned_leave_limit = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    compensate_with_earned_leave = models.BooleanField(default=True)
    excess_leave_becomes_lop = models.BooleanField(default=True)
    enable_carry_forward = models.BooleanField(default=False)
    max_carry_forward_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    carry_forward_leave_types = models.JSONField(default=list)
    carry_forward_frequency = models.CharField(
        max_length=20,
        choices=CarryForwardFrequency.choices,
        default=CarryForwardFrequency.MONTHLY,
    )

    class Meta:
        verbose_name_plural = "Leave policies"
        constraints = [
            models.UniqueConstraint(
                fields=["organization"],
                condition=Q(organization__isnull=False),
                name="unique_leave_policy_per_org",
            )
        ]

    def __str__(self):
        return "Leave Policy"


class LeaveRequest(OrganizationScopedModel):
    class DurationType(models.TextChoices):
        FULL_DAY = "FULL_DAY", "Full Day"
        HALF_DAY = "HALF_DAY", "Half Day"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=20, choices=LeaveBalance.LeaveType.choices)
    duration_type = models.CharField(
        max_length=20,
        choices=DurationType.choices,
        default=DurationType.FULL_DAY,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total_days = models.DecimalField(max_digits=5, decimal_places=1)
    lop_days_applied = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="leave_approvals",
        null=True,
        blank=True,
    )
    approver_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "start_date"]),
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["organization", "status", "start_date"]),
        ]
        constraints = [
            models.CheckConstraint(check=Q(total_days__gt=0), name="leave_request_total_days_positive"),
            models.CheckConstraint(check=Q(lop_days_applied__gte=0), name="leave_request_lop_days_non_negative"),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.leave_type} - {self.status}"


class EarnedLeaveAdjustment(OrganizationScopedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="earned_leave_adjustments")
    work_date = models.DateField(db_index=True)
    days = models.DecimalField(max_digits=5, decimal_places=1)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="earned_leave_adjustment_reviews",
        null=True,
        blank=True,
    )
    approver_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee", "work_date", "status"]),
            models.Index(fields=["organization", "work_date", "status"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.work_date} - {self.status}"


class LeaveCarryForwardLog(OrganizationScopedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="carry_forward_logs")
    leave_type = models.CharField(max_length=20, choices=LeaveBalance.LeaveType.choices)
    from_month = models.DateField()
    to_month = models.DateField()
    unused_days = models.DecimalField(max_digits=5, decimal_places=1)
    carried_forward_days = models.DecimalField(max_digits=5, decimal_places=1)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            UniqueConstraint(
                fields=["employee", "leave_type", "from_month"],
                name="unique_carry_forward_per_month",
            )
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.leave_type} - {self.from_month}"
