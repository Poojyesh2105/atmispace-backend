from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import OrganizationScopedModel
from apps.employees.models import Employee


class PayrollCycle(OrganizationScopedModel):
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
            models.Index(fields=["organization", "payroll_month", "status"]),
        ]

    def __str__(self):
        return self.name


class PayrollRun(OrganizationScopedModel):
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
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        return f"{self.cycle.name} - {self.status}"


class PayrollAdjustment(OrganizationScopedModel):
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
            models.Index(fields=["organization", "status", "cycle"]),
        ]
        constraints = [
            models.CheckConstraint(check=Q(amount__gte=0), name="payroll_adjustment_amount_non_negative"),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.adjustment_type}"


class SalaryRevision(OrganizationScopedModel):
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
            models.Index(fields=["organization", "effective_date"]),
        ]
        constraints = [
            models.CheckConstraint(check=Q(previous_ctc__gte=0), name="salary_revision_previous_ctc_non_negative"),
            models.CheckConstraint(check=Q(new_ctc__gt=0), name="salary_revision_new_ctc_positive"),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.effective_date.isoformat()}"


class Payslip(OrganizationScopedModel):
    payroll_cycle = models.ForeignKey(
        PayrollCycle,
        on_delete=models.SET_NULL,
        related_name="payslips",
        null=True,
        blank=True,
    )
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payslips")
    salary_component_template = models.ForeignKey(
        "SalaryComponentTemplate",
        on_delete=models.SET_NULL,
        related_name="payslips",
        null=True,
        blank=True,
    )
    salary_component_template_name = models.CharField(max_length=140, blank=True)
    payroll_month = models.DateField(help_text="Normalized to the first day of the payroll month.")
    gross_monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    additional_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    component_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
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
            models.Index(fields=["organization", "payroll_month"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.payroll_month.isoformat()}"


class SalaryComponentTemplate(OrganizationScopedModel):
    name = models.CharField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def __str__(self):
        return self.name


class EmployeeSalaryComponentTemplate(OrganizationScopedModel):
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="salary_component_template_assignment",
    )
    template = models.ForeignKey(
        SalaryComponentTemplate,
        on_delete=models.PROTECT,
        related_name="employee_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_salary_component_templates",
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["employee__employee_id"]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.template.name}"


class SalaryComponent(OrganizationScopedModel):
    class ComponentType(models.TextChoices):
        EARNING = "EARNING", "Earning"
        DEDUCTION = "DEDUCTION", "Deduction"

    class CalculationType(models.TextChoices):
        FIXED = "FIXED", "Fixed Amount"
        PERCENT_OF_GROSS = "PERCENT_OF_GROSS", "% of Gross"
        PERCENT_OF_CTC = "PERCENT_OF_CTC", "% of CTC"
        PERCENT_OF_COMPONENT = "PERCENT_OF_COMPONENT", "% of Component"

    template = models.ForeignKey(
        SalaryComponentTemplate,
        on_delete=models.CASCADE,
        related_name="components",
    )
    name = models.CharField(max_length=140)
    code = models.CharField(max_length=40)
    component_type = models.CharField(max_length=20, choices=ComponentType.choices)
    calculation_type = models.CharField(max_length=30, choices=CalculationType.choices, default=CalculationType.FIXED)
    base_component = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="dependent_components",
        null=True,
        blank=True,
        help_text="Component used as the base when calculation type is % of Component.",
    )
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_taxable = models.BooleanField(default=False)
    is_part_of_gross = models.BooleanField(
        default=True,
        help_text="For earning components, mark whether the amount is already part of monthly gross salary.",
    )
    has_employer_contribution = models.BooleanField(default=False)
    employer_contribution_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deduct_employer_contribution = models.BooleanField(
        default=False,
        help_text="For deductions, include employer contribution in employee deductions when enabled.",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["template__name", "display_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["template", "code"], name="unique_salary_component_template_code")
        ]

    def __str__(self):
        return f"{self.template.name} - {self.name} ({self.code})"


class PayslipComponentEntry(OrganizationScopedModel):
    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="component_entries")
    component = models.ForeignKey(SalaryComponent, on_delete=models.SET_NULL, null=True, blank=True, related_name="payslip_entries")
    component_name = models.CharField(max_length=140)   # snapshot
    component_code = models.CharField(max_length=40)    # snapshot
    component_type = models.CharField(max_length=20, choices=SalaryComponent.ComponentType.choices)
    calculated_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    employer_contribution_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deducts_employer_contribution = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "component_name"]

    def __str__(self):
        return f"{self.payslip} - {self.component_name}"


class PayslipTemplate(OrganizationScopedModel):
    name = models.CharField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    header_html = models.TextField(blank=True, help_text="HTML for the header section")
    body_html = models.TextField(blank=True, help_text="HTML template body. Use {{employee_name}}, {{payroll_month}}, {{net_pay}}, {{components}} etc.")
    footer_html = models.TextField(blank=True, help_text="HTML for the footer section")
    css_styles = models.TextField(blank=True, help_text="Custom CSS for the template")
    editor_config = models.JSONField(blank=True, default=dict, help_text="No-code editor settings used to generate the template source.")
    show_component_breakdown = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def __str__(self):
        return self.name
