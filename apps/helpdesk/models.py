from django.conf import settings
from django.db import models

from apps.accounts.models import User
from apps.core.models import TimestampedModel
from apps.employees.models import Employee


class HelpdeskCategory(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    owner_role = models.CharField(max_length=20, choices=User.Role.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class HelpdeskTicket(TimestampedModel):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    requester = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="helpdesk_tickets")
    category = models.ForeignKey(HelpdeskCategory, on_delete=models.PROTECT, related_name="tickets")
    subject = models.CharField(max_length=180)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    assigned_role = models.CharField(max_length=20, choices=User.Role.choices, blank=True)
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_helpdesk_tickets",
        null=True,
        blank=True,
    )
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["assigned_role", "status"]),
        ]

    def __str__(self):
        return f"{self.requester.employee_id} - {self.subject}"


class HelpdeskComment(TimestampedModel):
    ticket = models.ForeignKey(HelpdeskTicket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="helpdesk_comments",
        null=True,
        blank=True,
    )
    message = models.TextField()
    is_internal = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.ticket_id} - {self.author_id or 'system'}"

