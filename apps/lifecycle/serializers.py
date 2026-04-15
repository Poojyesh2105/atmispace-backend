from rest_framework import serializers

from apps.lifecycle.models import (
    EmployeeChangeRequest,
    EmployeeOnboarding,
    EmployeeOnboardingTask,
    OffboardingCase,
    OffboardingTask,
    OnboardingPlan,
    OnboardingTaskTemplate,
)


class OnboardingPlanSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = OnboardingPlan
        fields = (
            "id",
            "name",
            "description",
            "department",
            "department_name",
            "employment_type",
            "default_duration_days",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "department_name", "created_at", "updated_at")


class OnboardingTaskTemplateSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = OnboardingTaskTemplate
        fields = (
            "id",
            "plan",
            "plan_name",
            "title",
            "description",
            "owner_role",
            "task_type",
            "sequence",
            "due_offset_days",
            "is_required",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "plan_name", "created_at", "updated_at")


class EmployeeOnboardingTaskSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.CharField(source="completed_by.full_name", read_only=True)

    class Meta:
        model = EmployeeOnboardingTask
        fields = (
            "id",
            "onboarding",
            "template_task",
            "title",
            "description",
            "owner_role",
            "task_type",
            "sequence",
            "due_date",
            "status",
            "completed_by",
            "completed_by_name",
            "completed_at",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "completed_by_name", "completed_at", "created_at", "updated_at")


class EmployeeOnboardingSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    initiated_by_name = serializers.CharField(source="initiated_by.full_name", read_only=True)
    tasks = EmployeeOnboardingTaskSerializer(many=True, read_only=True)

    class Meta:
        model = EmployeeOnboarding
        fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "plan",
            "plan_name",
            "initiated_by",
            "initiated_by_name",
            "start_date",
            "due_date",
            "status",
            "notes",
            "tasks",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "employee_name", "employee_code", "plan_name", "initiated_by_name", "tasks", "created_at", "updated_at")


class OffboardingTaskSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.CharField(source="completed_by.full_name", read_only=True)

    class Meta:
        model = OffboardingTask
        fields = (
            "id",
            "offboarding_case",
            "title",
            "owner_role",
            "sequence",
            "due_date",
            "status",
            "completed_by",
            "completed_by_name",
            "completed_at",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "completed_by_name", "completed_at", "created_at", "updated_at")


class OffboardingCaseSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    initiated_by_name = serializers.CharField(source="initiated_by.full_name", read_only=True)
    tasks = OffboardingTaskSerializer(many=True, read_only=True)

    class Meta:
        model = OffboardingCase
        fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "initiated_by",
            "initiated_by_name",
            "notice_start_date",
            "last_working_day",
            "actual_exit_date",
            "reason",
            "status",
            "exit_interview_notes",
            "asset_clearance_status",
            "final_settlement_status",
            "handoff_notes",
            "tasks",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "employee_name", "employee_code", "initiated_by_name", "tasks", "created_at", "updated_at")


class EmployeeChangeRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.full_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True)

    class Meta:
        model = EmployeeChangeRequest
        fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "requested_by",
            "requested_by_name",
            "change_type",
            "proposed_designation",
            "proposed_role",
            "proposed_department_role",
            "proposed_ctc_per_annum",
            "proposed_effective_date",
            "justification",
            "status",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "employee_name", "employee_code", "requested_by_name", "approved_by_name", "approved_at", "created_at", "updated_at")


class TaskCompletionSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)

