from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.accounts.models import User
from apps.core.models import OrganizationScopedModel


class Workflow(OrganizationScopedModel):
    class Module(models.TextChoices):
        LEAVE_REQUEST = "leave_request", "Leave Request"
        ATTENDANCE_REGULARIZATION = "attendance_regularization", "Attendance Regularization"
        PERFORMANCE_REVIEW = "performance_review", "Performance Review"
        LIFECYCLE_CASE = "lifecycle_case", "Lifecycle Case"
        PAYROLL_RELEASE = "payroll_release", "Payroll Release"

    class ConditionOperator(models.TextChoices):
        ALWAYS = "ALWAYS", "Always"
        EQUALS = "EQUALS", "Equals"
        NOT_EQUALS = "NOT_EQUALS", "Not Equals"
        GREATER_THAN_EQUAL = "GTE", "Greater Than Or Equal"
        LESS_THAN_EQUAL = "LTE", "Less Than Or Equal"
        IN = "IN", "In"

    name = models.CharField(max_length=160)
    module = models.CharField(max_length=64, choices=Module.choices, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)
    condition_field = models.CharField(max_length=120, blank=True)
    condition_operator = models.CharField(
        max_length=20,
        choices=ConditionOperator.choices,
        default=ConditionOperator.ALWAYS,
    )
    condition_value = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["module", "priority", "name"]
        indexes = [
            models.Index(fields=["module", "is_active", "priority"]),
        ]

    def __str__(self):
        return f"{self.module} - {self.name}"


class WorkflowStep(OrganizationScopedModel):
    class AssignmentType(models.TextChoices):
        ROLE = "ROLE", "Role"
        PRIMARY_MANAGER = "PRIMARY_MANAGER", "Primary Manager"
        SECONDARY_MANAGER = "SECONDARY_MANAGER", "Secondary Manager"
        USER = "USER", "Specific User"

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="steps")
    name = models.CharField(max_length=160)
    sequence = models.PositiveIntegerField()
    assignment_type = models.CharField(max_length=30, choices=AssignmentType.choices)
    role = models.CharField(max_length=20, choices=User.Role.choices, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_steps",
    )
    is_active = models.BooleanField(default=True)
    condition_field = models.CharField(max_length=120, blank=True)
    condition_operator = models.CharField(
        max_length=20,
        choices=Workflow.ConditionOperator.choices,
        default=Workflow.ConditionOperator.ALWAYS,
    )
    condition_value = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["sequence", "id"]
        constraints = [
            models.UniqueConstraint(fields=["workflow", "sequence"], name="unique_workflow_step_sequence"),
        ]

    def __str__(self):
        return f"{self.workflow.name} - {self.sequence} - {self.name}"


class WorkflowAssignment(OrganizationScopedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    workflow = models.ForeignKey(Workflow, on_delete=models.PROTECT, related_name="assignments")
    module = models.CharField(max_length=64, choices=Workflow.Module.choices, db_index=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_assignments",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    current_step_sequence = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    context = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["module", "status"]),
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["organization", "module", "status"]),
        ]

    def __str__(self):
        return f"{self.module} #{self.object_id} - {self.status}"


class ApprovalInstance(OrganizationScopedModel):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SKIPPED = "SKIPPED", "Skipped"

    workflow_assignment = models.ForeignKey(
        WorkflowAssignment,
        on_delete=models.CASCADE,
        related_name="approval_instances",
    )
    step = models.ForeignKey(WorkflowStep, on_delete=models.PROTECT, related_name="approval_instances")
    sequence = models.PositiveIntegerField()
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_instances",
    )
    assigned_role = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    acted_at = models.DateTimeField(null=True, blank=True)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence", "created_at"]
        indexes = [
            models.Index(fields=["assigned_user", "status"]),
            models.Index(fields=["workflow_assignment", "status"]),
            models.Index(fields=["organization", "status", "assigned_user"]),
        ]

    def __str__(self):
        return f"{self.workflow_assignment_id} - {self.sequence} - {self.status}"


class ApprovalAction(OrganizationScopedModel):
    class Action(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        COMMENTED = "COMMENTED", "Commented"
        SYSTEM = "SYSTEM", "System"

    approval_instance = models.ForeignKey(
        ApprovalInstance,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_actions",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    comments = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.approval_instance_id} - {self.action}"
