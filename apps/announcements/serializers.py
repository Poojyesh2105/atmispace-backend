from rest_framework import serializers

from apps.announcements.models import Announcement, AnnouncementAcknowledgement


class AnnouncementAcknowledgementSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = AnnouncementAcknowledgement
        fields = ("id", "user", "user_name", "acknowledged_at", "created_at")
        read_only_fields = fields


class AnnouncementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    target_user_name = serializers.CharField(source="target_user.full_name", read_only=True)
    acknowledgement_count = serializers.IntegerField(source="acknowledgements.count", read_only=True)
    has_acknowledged = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = (
            "id",
            "title",
            "summary",
            "body",
            "audience_type",
            "role",
            "department",
            "department_name",
            "target_user",
            "target_user_name",
            "created_by",
            "created_by_name",
            "starts_at",
            "ends_at",
            "is_published",
            "published_at",
            "show_on_dashboard",
            "requires_acknowledgement",
            "acknowledgement_count",
            "has_acknowledged",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_by",
            "created_by_name",
            "department_name",
            "target_user_name",
            "published_at",
            "acknowledgement_count",
            "has_acknowledged",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        audience_type = attrs.get("audience_type", getattr(self.instance, "audience_type", Announcement.AudienceType.ALL))
        role = attrs.get("role", getattr(self.instance, "role", ""))
        department = attrs.get("department", getattr(self.instance, "department", None))
        target_user = attrs.get("target_user", getattr(self.instance, "target_user", None))

        if audience_type == Announcement.AudienceType.ROLE and not role:
            raise serializers.ValidationError({"role": "Role is required for role-based announcements."})
        if audience_type == Announcement.AudienceType.DEPARTMENT and not department:
            raise serializers.ValidationError({"department": "Department is required for department announcements."})
        if audience_type == Announcement.AudienceType.INDIVIDUAL and not target_user:
            raise serializers.ValidationError({"target_user": "Target user is required for individual announcements."})
        return attrs

    def get_has_acknowledged(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.acknowledgements.filter(user=request.user).exists()

