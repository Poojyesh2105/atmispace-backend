from django.conf import settings
from django.db import models

from apps.core.models import OrganizationScopedModel


class Notification(OrganizationScopedModel):
    class Type(models.TextChoices):
        LEAVE_APPLIED = "LEAVE_APPLIED", "Leave Applied"
        LEAVE_APPROVED = "LEAVE_APPROVED", "Leave Approved"
        LEAVE_REJECTED = "LEAVE_REJECTED", "Leave Rejected"
        WORKFLOW_PENDING = "WORKFLOW_PENDING", "Workflow Pending"
        MISSING_ATTENDANCE = "MISSING_ATTENDANCE", "Missing Attendance"
        REGULARIZATION = "REGULARIZATION", "Attendance Regularization"
        DOCUMENT_EXPIRY = "DOCUMENT_EXPIRY", "Document Expiry"
        DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED", "Document Verified"
        PERFORMANCE_REVIEW = "PERFORMANCE_REVIEW", "Performance Review"
        ONBOARDING = "ONBOARDING", "Onboarding"
        OFFBOARDING = "OFFBOARDING", "Offboarding"
        LIFECYCLE = "LIFECYCLE", "Lifecycle"
        PAYROLL = "PAYROLL", "Payroll"
        ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement"
        HELPDESK = "HELPDESK", "Helpdesk"
        GENERIC = "GENERIC", "Generic"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=40, choices=Type.choices, default=Type.GENERIC)
    title = models.CharField(max_length=180)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
            models.Index(fields=["organization", "is_read", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title}"
