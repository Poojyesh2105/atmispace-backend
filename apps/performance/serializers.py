from rest_framework import serializers

from apps.performance.models import PerformanceCycle, PerformanceGoal, PerformanceReview, RatingScale


class RatingScaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RatingScale
        fields = ("id", "name", "min_rating", "max_rating", "labels", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class PerformanceCycleSerializer(serializers.ModelSerializer):
    rating_scale_name = serializers.CharField(source="rating_scale.name", read_only=True)

    class Meta:
        model = PerformanceCycle
        fields = (
            "id",
            "name",
            "description",
            "start_date",
            "end_date",
            "self_review_due_date",
            "manager_review_due_date",
            "hr_review_due_date",
            "status",
            "rating_scale",
            "rating_scale_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "rating_scale_name", "created_at", "updated_at")


class PerformanceGoalSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    cycle_name = serializers.CharField(source="cycle.name", read_only=True)

    class Meta:
        model = PerformanceGoal
        fields = (
            "id",
            "cycle",
            "cycle_name",
            "employee",
            "employee_name",
            "employee_code",
            "category",
            "title",
            "description",
            "target_value",
            "progress_value",
            "weight",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "cycle_name", "employee_name", "employee_code", "created_at", "updated_at")


class PerformanceReviewSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    manager_name = serializers.CharField(source="manager.user.full_name", read_only=True)
    cycle_name = serializers.CharField(source="cycle.name", read_only=True)

    class Meta:
        model = PerformanceReview
        fields = (
            "id",
            "cycle",
            "cycle_name",
            "employee",
            "employee_name",
            "employee_code",
            "manager",
            "manager_name",
            "status",
            "self_summary",
            "self_rating",
            "manager_summary",
            "manager_rating",
            "hr_summary",
            "final_rating",
            "submitted_at",
            "manager_reviewed_at",
            "hr_reviewed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "cycle_name",
            "employee_name",
            "employee_code",
            "manager_name",
            "submitted_at",
            "manager_reviewed_at",
            "hr_reviewed_at",
            "created_at",
            "updated_at",
        )


class SelfReviewSubmissionSerializer(serializers.Serializer):
    self_summary = serializers.CharField()
    self_rating = serializers.DecimalField(max_digits=4, decimal_places=1)


class ManagerReviewSubmissionSerializer(serializers.Serializer):
    manager_summary = serializers.CharField()
    manager_rating = serializers.DecimalField(max_digits=4, decimal_places=1)


class HRReviewSubmissionSerializer(serializers.Serializer):
    hr_summary = serializers.CharField()
    final_rating = serializers.DecimalField(max_digits=4, decimal_places=1)

