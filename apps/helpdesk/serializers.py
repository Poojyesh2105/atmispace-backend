from rest_framework import serializers

from apps.employees.models import Employee
from apps.helpdesk.models import HelpdeskCategory, HelpdeskComment, HelpdeskTicket


class HelpdeskCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = HelpdeskCategory
        fields = ("id", "name", "description", "owner_role", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class HelpdeskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True)

    class Meta:
        model = HelpdeskComment
        fields = ("id", "author", "author_name", "message", "is_internal", "created_at")
        read_only_fields = ("id", "author", "author_name", "created_at")


class HelpdeskTicketSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(source="requester.user.full_name", read_only=True)
    requester_code = serializers.CharField(source="requester.employee_id", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    assigned_user_name = serializers.CharField(source="assigned_user.full_name", read_only=True)
    comments = HelpdeskCommentSerializer(many=True, read_only=True)
    requester = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.select_related("user"),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = HelpdeskTicket
        fields = (
            "id",
            "requester",
            "requester_name",
            "requester_code",
            "category",
            "category_name",
            "subject",
            "description",
            "priority",
            "status",
            "assigned_role",
            "assigned_user",
            "assigned_user_name",
            "resolution_notes",
            "resolved_at",
            "comments",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "requester_name",
            "requester_code",
            "category_name",
            "assigned_user_name",
            "resolved_at",
            "comments",
            "created_at",
            "updated_at",
        )


class HelpdeskCommentCreateSerializer(serializers.Serializer):
    message = serializers.CharField()
    is_internal = serializers.BooleanField(required=False, default=False)
