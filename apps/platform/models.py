"""
Platform-level SaaS models for Atmispace.

These models belong to the platform layer — they are NOT org-scoped in the same
way as HR models. Most reference Organization as a FK but are managed exclusively
by SUPER_ADMIN.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import Organization, TimestampedModel


# ──────────────────────────────────────────────────────────────────────────────
# Subscription / Billing
# ──────────────────────────────────────────────────────────────────────────────

class SubscriptionPlan(TimestampedModel):
    """Platform-defined plans (Starter, Growth, Enterprise, etc.)."""

    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True, default="")
    price_monthly = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_users = models.PositiveIntegerField(
        default=0, help_text="0 = unlimited"
    )
    included_modules = models.JSONField(
        default=list,
        help_text="List of feature-flag keys included in this plan",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "price_monthly"]

    def __str__(self):
        return self.name


class OrganizationSubscription(TimestampedModel):
    """Active subscription record linking an org to a plan."""

    class BillingCycle(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        YEARLY = "YEARLY", "Yearly"

    class Status(models.TextChoices):
        TRIAL = "TRIAL", "Trial"
        ACTIVE = "ACTIVE", "Active"
        PAST_DUE = "PAST_DUE", "Past Due"
        SUSPENDED = "SUSPENDED", "Suspended"
        CANCELLED = "CANCELLED", "Cancelled"

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        null=True,
        blank=True,
    )
    billing_cycle = models.CharField(
        max_length=10,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL,
        db_index=True,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    trial_end_date = models.DateField(null=True, blank=True)
    next_billing_date = models.DateField(null=True, blank=True)
    mrr = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Monthly Recurring Revenue snapshot for this subscription",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization.name} — {self.plan}"

    @property
    def is_trial_expired(self):
        if self.trial_end_date:
            return timezone.localdate() > self.trial_end_date
        return False


class Invoice(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        PAID = "PAID", "Paid"
        VOID = "VOID", "Void"
        OVERDUE = "OVERDUE", "Overdue"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invoices"
    )
    subscription = models.ForeignKey(
        OrganizationSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=80, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    due_date = models.DateField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.invoice_number} — {self.organization.name}"


class Payment(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="payments"
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    provider = models.CharField(max_length=60, default="manual")
    provider_reference = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]


# ──────────────────────────────────────────────────────────────────────────────
# Organization Onboarding
# ──────────────────────────────────────────────────────────────────────────────

class OrganizationOnboarding(TimestampedModel):
    """Tracks the multi-step provisioning flow for a new organization."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        ROLLED_BACK = "ROLLED_BACK", "Rolled Back"

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="onboarding",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    current_step = models.PositiveSmallIntegerField(default=1)
    # Stores form state so the stepper can be resumed
    step_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    provisioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provisioned_onboardings",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        org_name = self.organization.name if self.organization else "Pending"
        return f"Onboarding: {org_name} [{self.status}]"


# ──────────────────────────────────────────────────────────────────────────────
# Usage Analytics
# ──────────────────────────────────────────────────────────────────────────────

class UsageEvent(models.Model):
    """
    Lightweight usage event log for tracking per-org module activity.
    Intentionally does NOT extend TimestampedModel (no updated_at needed).
    Write-only — never updated after creation.
    """

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="usage_events", db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    module = models.CharField(max_length=60, db_index=True)   # e.g. "payroll", "leave"
    action = models.CharField(max_length=120, db_index=True)  # e.g. "payslip_downloaded"
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "module", "created_at"]),
            models.Index(fields=["organization", "created_at"]),
        ]

    def __str__(self):
        return f"{self.organization_id} / {self.module} / {self.action}"


# ──────────────────────────────────────────────────────────────────────────────
# Platform Support
# ──────────────────────────────────────────────────────────────────────────────

class PlatformSupportTicket(TimestampedModel):
    """
    Platform-level support tickets raised by customer organizations.
    Distinct from the internal HR helpdesk (HelpdeskTicket).
    """

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        WAITING = "WAITING", "Waiting on Customer"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="support_tickets"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_support_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )
    subject = models.CharField(max_length=300)
    description = models.TextField()
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM, db_index=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    internal_notes = models.TextField(blank=True, default="")
    sla_due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    related_audit_log = models.ForeignKey(
        "audit.AuditLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_tickets",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["status", "priority"]),
        ]

    def __str__(self):
        return f"[{self.status}] {self.subject}"

    @property
    def is_sla_breached(self):
        if self.sla_due_at and self.status not in (self.Status.RESOLVED, self.Status.CLOSED):
            return timezone.now() > self.sla_due_at
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Security Events
# ──────────────────────────────────────────────────────────────────────────────

class SecurityEvent(models.Model):
    """
    Platform-wide security event log.
    Write-only — never updated after creation.
    """

    class EventType(models.TextChoices):
        FAILED_LOGIN = "FAILED_LOGIN", "Failed Login"
        UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS", "Unauthorized Access"
        PERMISSION_DENIED = "PERMISSION_DENIED", "Permission Denied"
        SUSPICIOUS_TOKEN = "SUSPICIOUS_TOKEN", "Suspicious Token"
        ORG_CONTEXT_MISMATCH = "ORG_CONTEXT_MISMATCH", "Org Context Mismatch"
        RATE_LIMITED = "RATE_LIMITED", "Rate Limited"
        PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password Changed"
        ACCOUNT_LOCKED = "ACCOUNT_LOCKED", "Account Locked"
        SUPER_ADMIN_ACTION = "SUPER_ADMIN_ACTION", "Super Admin Action"

    class Severity(models.TextChoices):
        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
    )
    event_type = models.CharField(
        max_length=40, choices=EventType.choices, db_index=True
    )
    severity = models.CharField(
        max_length=20, choices=Severity.choices, default=Severity.INFO, db_index=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    path = models.CharField(max_length=500, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["severity", "created_at"]),
            models.Index(fields=["organization", "event_type"]),
        ]

    def __str__(self):
        return f"{self.event_type} / {self.severity} / {self.created_at}"


# ──────────────────────────────────────────────────────────────────────────────
# Failed Background Jobs
# ──────────────────────────────────────────────────────────────────────────────

class FailedJob(TimestampedModel):
    """Tracks failed Celery tasks for monitoring and manual retry."""

    class Status(models.TextChoices):
        FAILED = "FAILED", "Failed"
        RETRYING = "RETRYING", "Retrying"
        RESOLVED = "RESOLVED", "Resolved"
        IGNORED = "IGNORED", "Ignored"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="failed_jobs",
        db_index=True,
    )
    task_name = models.CharField(max_length=300, db_index=True)
    task_id = models.CharField(max_length=200, unique=True)
    args = models.JSONField(default=list, blank=True)
    kwargs = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    traceback = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.FAILED, db_index=True
    )
    retry_count = models.PositiveSmallIntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_jobs",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        return f"{self.task_name} [{self.status}]"
