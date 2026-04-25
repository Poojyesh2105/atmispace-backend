from django.conf import settings
from django.db import models

from apps.accounts.models import User
from apps.core.models import OrganizationScopedModel
from apps.employees.models import Department


class Announcement(OrganizationScopedModel):
    class AudienceType(models.TextChoices):
        ALL = "ALL", "All Employees"
        ROLE = "ROLE", "Role"
        DEPARTMENT = "DEPARTMENT", "Department"
        INDIVIDUAL = "INDIVIDUAL", "Individual"

    title = models.CharField(max_length=180)
    summary = models.CharField(max_length=240, blank=True)
    body = models.TextField()
    audience_type = models.CharField(max_length=20, choices=AudienceType.choices, default=AudienceType.ALL)
    role = models.CharField(max_length=20, choices=User.Role.choices, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="announcements",
        null=True,
        blank=True,
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="targeted_announcements",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_announcements",
        null=True,
        blank=True,
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    show_on_dashboard = models.BooleanField(default=True)
    requires_acknowledgement = models.BooleanField(default=False)

    class Meta:
        ordering = ["-starts_at", "-created_at"]
        indexes = [
            models.Index(fields=["is_published", "starts_at"]),
            models.Index(fields=["audience_type", "role"]),
            models.Index(fields=["organization", "is_published", "starts_at"]),
        ]

    def __str__(self):
        return self.title


class AnnouncementAcknowledgement(OrganizationScopedModel):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="acknowledgements")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="announcement_acknowledgements",
    )
    acknowledged_at = models.DateTimeField()

    class Meta:
        ordering = ["-acknowledged_at"]
        constraints = [
            models.UniqueConstraint(fields=["announcement", "user"], name="unique_announcement_acknowledgement")
        ]
        indexes = [
            models.Index(fields=["user", "acknowledged_at"]),
            models.Index(fields=["organization", "acknowledged_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.announcement.title}"
