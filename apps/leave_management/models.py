from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel
from apps.employees.models import Employee


class LeaveBalance(TimestampedModel):
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
        constraints = [
            models.UniqueConstraint(fields=["employee", "leave_type"], name="unique_leave_balance_type")
        ]
        indexes = [
            models.Index(fields=["employee", "leave_type"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.leave_type}"

    @property
    def available_days(self):
        return self.allocated_days - self.used_days


class LeavePolicy(TimestampedModel):
    casual_days_onboarding = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    sick_days_onboarding = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    earned_days_onboarding = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    monthly_sick_leave_limit = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    monthly_earned_leave_limit = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    compensate_with_earned_leave = models.BooleanField(default=True)
    excess_leave_becomes_lop = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Leave policies"

    def __str__(self):
        return "Leave Policy"


class LeaveRequest(TimestampedModel):
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
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.leave_type} - {self.status}"


class EarnedLeaveAdjustment(TimestampedModel):
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
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.work_date} - {self.status}"
