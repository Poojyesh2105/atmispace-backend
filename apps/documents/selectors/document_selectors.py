from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.documents.models import DocumentType, EmployeeDocument, MandatoryDocumentRule


class DocumentSelectors:
    @staticmethod
    def get_document_type_queryset(user=None):
        return DocumentType.objects.for_current_org(user)

    @staticmethod
    def get_mandatory_rule_queryset(user=None):
        return MandatoryDocumentRule.objects.for_current_org(user).select_related("document_type", "department")

    @staticmethod
    def get_document_queryset_for_user(user):
        queryset = EmployeeDocument.objects.for_current_org(user).select_related(
            "employee__user",
            "employee__manager__user",
            "document_type",
            "verified_by",
        )
        employee = getattr(user, "employee_profile", None)

        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def get_expiring_documents(days=30):
        today = timezone.localdate()
        threshold = today + timedelta(days=days)
        return EmployeeDocument.objects.select_related("employee__user", "document_type").filter(
            expiry_date__isnull=False,
            expiry_date__gte=today,
            expiry_date__lte=threshold,
            status__in=[EmployeeDocument.Status.PENDING, EmployeeDocument.Status.VERIFIED],
        )
