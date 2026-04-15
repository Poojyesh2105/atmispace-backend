from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel
from apps.employees.models import Employee


class DeductionRule(TimestampedModel):
    class CalculationType(models.TextChoices):
        FIXED = "FIXED", "Fixed"
        PERCENT = "PERCENT", "Percent"

    name = models.CharField(max_length=140)
    code = models.CharField(max_length=40, unique=True)
    description = models.TextField(blank=True)
    calculation_type = models.CharField(max_length=20, choices=CalculationType.choices, default=CalculationType.FIXED)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PayrollCycle(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        LOCKED = "LOCKED", "Locked"
        RELEASE_PENDING = "RELEASE_PENDING", "Release Pending"
        RELEASED = "RELEASED", "Released"

    name = models.CharField(max_length=140, unique=True)
    payroll_month = models.DateField(help_text="Normalized to the first day of the payroll month.")
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-payroll_month", "name"]
        indexes = [
            models.Index(fields=["payroll_month", "status"]),
        ]

    def __str__(self):
        return self.name


class PayrollRun(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        LOCKED = "LOCKED", "Locked"
        RELEASE_PENDING = "RELEASE_PENDING", "Release Pending"
        RELEASED = "RELEASED", "Released"

    cycle = models.OneToOneField(PayrollCycle, on_delete=models.CASCADE, related_name="run")
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="generated_payroll_runs",
        null=True,
        blank=True,
    )
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="released_payroll_runs",
        null=True,
        blank=True,
    )
    total_employees = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-cycle__payroll_month"]
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.cycle.name} - {self.status}"


class PayrollAdjustment(TimestampedModel):
    class AdjustmentType(models.TextChoices):
        EARNING = "EARNING", "Earning"
        DEDUCTION = "DEDUCTION", "Deduction"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPLIED = "APPLIED", "Applied"
        CANCELLED = "CANCELLED", "Cancelled"

    cycle = models.ForeignKey(PayrollCycle, on_delete=models.CASCADE, related_name="adjustments")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payroll_adjustments")
    adjustment_type = models.CharField(max_length=20, choices=AdjustmentType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_payroll_adjustments",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["cycle", "employee", "status"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.adjustment_type}"


class SalaryRevision(TimestampedModel):
    class Status(models.TextChoices):
        APPLIED = "APPLIED", "Applied"
        SCHEDULED = "SCHEDULED", "Scheduled"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="salary_revisions")
    previous_ctc = models.DecimalField(max_digits=12, decimal_places=2)
    new_ctc = models.DecimalField(max_digits=12, decimal_places=2)
    effective_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APPLIED, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_salary_revisions",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-effective_date", "-created_at"]
        indexes = [
            models.Index(fields=["employee", "effective_date"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.effective_date.isoformat()}"


class Payslip(TimestampedModel):
    payroll_cycle = models.ForeignKey(
        PayrollCycle,
        on_delete=models.SET_NULL,
        related_name="payslips",
        null=True,
        blank=True,
    )
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payslips")
    payroll_month = models.DateField(help_text="Normalized to the first day of the payroll month.")
    gross_monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    additional_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fixed_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rule_based_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    adjustment_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lop_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    lop_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    days_in_month = models.PositiveSmallIntegerField(default=0)
    payable_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="generated_payslips",
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payroll_month", "employee__employee_id"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "payroll_month"], name="unique_employee_payroll_month")
        ]
        indexes = [
            models.Index(fields=["payroll_month"]),
            models.Index(fields=["employee", "payroll_month"]),
            models.Index(fields=["payroll_cycle", "employee"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.payroll_month.isoformat()}"
