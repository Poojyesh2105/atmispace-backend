from django.conf import settings
from django.db import models

from apps.accounts.models import User
from apps.core.models import OrganizationScopedModel
from apps.employees.models import Department, Employee


class OnboardingPlan(OrganizationScopedModel):
    name = models.CharField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="onboarding_plans",
        null=True,
        blank=True,
    )
    employment_type = models.CharField(max_length=20, blank=True)
    default_duration_days = models.PositiveIntegerField(default=7)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OnboardingTaskTemplate(OrganizationScopedModel):
    class TaskType(models.TextChoices):
        DOCUMENT = "DOCUMENT", "Document"
        POLICY = "POLICY", "Policy"
        ACCESS = "ACCESS", "Access"
        TRAINING = "TRAINING", "Training"

    plan = models.ForeignKey(OnboardingPlan, on_delete=models.CASCADE, related_name="task_templates")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    owner_role = models.CharField(max_length=20, choices=User.Role.choices, default=User.Role.HR)
    task_type = models.CharField(max_length=20, choices=TaskType.choices, default=TaskType.DOCUMENT)
    sequence = models.PositiveIntegerField(default=1)
    due_offset_days = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["plan", "sequence", "id"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "sequence", "title"], name="unique_onboarding_task_template")
        ]

    def __str__(self):
        return f"{self.plan.name} - {self.title}"


class EmployeeOnboarding(OrganizationScopedModel):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not Started"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="onboardings")
    plan = models.ForeignKey(OnboardingPlan, on_delete=models.SET_NULL, related_name="employee_onboardings", null=True, blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="initiated_onboardings",
        null=True,
        blank=True,
    )
    start_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date", "employee__employee_id"]
        indexes = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["organization", "status", "start_date"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.status}"


class EmployeeOnboardingTask(OrganizationScopedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        SKIPPED = "SKIPPED", "Skipped"

    onboarding = models.ForeignKey(EmployeeOnboarding, on_delete=models.CASCADE, related_name="tasks")
    template_task = models.ForeignKey(
        OnboardingTaskTemplate,
        on_delete=models.SET_NULL,
        related_name="instantiated_tasks",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    owner_role = models.CharField(max_length=20, choices=User.Role.choices, default=User.Role.HR)
    task_type = models.CharField(max_length=20, choices=OnboardingTaskTemplate.TaskType.choices)
    sequence = models.PositiveIntegerField(default=1)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="completed_onboarding_tasks",
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["onboarding", "sequence", "id"]
        indexes = [
            models.Index(fields=["onboarding", "status"]),
            models.Index(fields=["organization", "status", "due_date"]),
        ]

    def __str__(self):
        return f"{self.onboarding.employee.employee_id} - {self.title}"


class OffboardingCase(OrganizationScopedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Approval"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"

    class SettlementStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        HANDED_OFF = "HANDED_OFF", "Handed Off"
        SETTLED = "SETTLED", "Settled"

    class ClearanceStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CLEARED = "CLEARED", "Cleared"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="offboarding_cases")
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="initiated_offboarding_cases",
        null=True,
        blank=True,
    )
    notice_start_date = models.DateField()
    last_working_day = models.DateField()
    actual_exit_date = models.DateField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    exit_interview_notes = models.TextField(blank=True)
    asset_clearance_status = models.CharField(
        max_length=20,
        choices=ClearanceStatus.choices,
        default=ClearanceStatus.PENDING,
    )
    final_settlement_status = models.CharField(
        max_length=20,
        choices=SettlementStatus.choices,
        default=SettlementStatus.PENDING,
    )
    handoff_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["organization", "status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.status}"


class OffboardingTask(OrganizationScopedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"

    offboarding_case = models.ForeignKey(OffboardingCase, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=180)
    owner_role = models.CharField(max_length=20, choices=User.Role.choices, default=User.Role.HR)
    sequence = models.PositiveIntegerField(default=1)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="completed_offboarding_tasks",
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["offboarding_case", "sequence", "id"]
        indexes = [
            models.Index(fields=["offboarding_case", "status"]),
            models.Index(fields=["organization", "status", "due_date"]),
        ]

    def __str__(self):
        return f"{self.offboarding_case.employee.employee_id} - {self.title}"


class EmployeeChangeRequest(OrganizationScopedModel):
    class ChangeType(models.TextChoices):
        CONFIRMATION = "CONFIRMATION", "Probation Confirmation"
        PROMOTION = "PROMOTION", "Promotion"
        ROLE_CHANGE = "ROLE_CHANGE", "Role Change"
        COMPENSATION_REVISION = "COMPENSATION_REVISION", "Compensation Revision"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="change_requests")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="employee_change_requests",
        null=True,
        blank=True,
    )
    change_type = models.CharField(max_length=30, choices=ChangeType.choices, db_index=True)
    proposed_designation = models.CharField(max_length=150, blank=True)
    proposed_role = models.CharField(max_length=20, choices=User.Role.choices, blank=True)
    proposed_department_role = models.CharField(max_length=20, choices=Employee.DepartmentRole.choices, blank=True)
    proposed_ctc_per_annum = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    proposed_effective_date = models.DateField()
    justification = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_employee_change_requests",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee", "change_type", "status"]),
            models.Index(fields=["organization", "status", "change_type"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.change_type}"
