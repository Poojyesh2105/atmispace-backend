from rest_framework import serializers

from apps.documents.models import DocumentType, EmployeeDocument, MandatoryDocumentRule


class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = (
            "id",
            "name",
            "category",
            "description",
            "requires_expiry",
            "is_mandatory_default",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class MandatoryDocumentRuleSerializer(serializers.ModelSerializer):
    document_type_name = serializers.CharField(source="document_type.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = MandatoryDocumentRule
        fields = (
            "id",
            "name",
            "document_type",
            "document_type_name",
            "department",
            "department_name",
            "employment_type",
            "due_days_from_joining",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "document_type_name", "department_name", "created_at", "updated_at")


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    document_type_name = serializers.CharField(source="document_type.name", read_only=True)
    verified_by_name = serializers.CharField(source="verified_by.full_name", read_only=True)

    class Meta:
        model = EmployeeDocument
        fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "document_type",
            "document_type_name",
            "title",
            "file_name",
            "file_url",
            "issued_date",
            "expiry_date",
            "status",
            "remarks",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "employee_name",
            "employee_code",
            "document_type_name",
            "verified_by_name",
            "verified_at",
            "created_at",
            "updated_at",
        )


class DocumentVerificationSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True)

