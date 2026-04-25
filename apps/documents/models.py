from django.conf import settings
from django.db import models

from apps.core.models import OrganizationScopedModel
from apps.employees.models import Department, Employee


class DocumentType(OrganizationScopedModel):
    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    requires_expiry = models.BooleanField(default=False)
    is_mandatory_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MandatoryDocumentRule(OrganizationScopedModel):
    name = models.CharField(max_length=160)
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE, related_name="mandatory_rules")
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="mandatory_document_rules",
        null=True,
        blank=True,
    )
    employment_type = models.CharField(max_length=20, blank=True)
    due_days_from_joining = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["document_type", "is_active"]),
            models.Index(fields=["organization", "is_active"]),
        ]

    def __str__(self):
        return self.name


class EmployeeDocument(OrganizationScopedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="documents")
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE, related_name="employee_documents")
    title = models.CharField(max_length=180)
    file_name = models.CharField(max_length=240, blank=True)
    file_url = models.URLField(blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    remarks = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="verified_documents",
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["employee__employee_id", "document_type__name"]
        indexes = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["document_type", "status"]),
            models.Index(fields=["organization", "status", "expiry_date"]),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.document_type.name}"
