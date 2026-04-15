from rest_framework import serializers

from apps.employees.models import Employee, ShiftTemplate
from apps.scheduling.models import ScheduleConflict, ShiftRosterEntry, ShiftRotationRule


class ShiftRotationRuleSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = ShiftRotationRule
        fields = (
            "id",
            "name",
            "description",
            "department",
            "department_name",
            "rotation_pattern",
            "holiday_strategy",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "department_name", "created_at", "updated_at")


class ShiftRosterEntrySerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    shift_name = serializers.CharField(source="shift_template.name", read_only=True)

    class Meta:
        model = ShiftRosterEntry
        fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "roster_date",
            "shift_template",
            "shift_name",
            "source",
            "is_holiday",
            "is_conflicted",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "employee_name", "employee_code", "shift_name", "is_holiday", "is_conflicted", "created_at", "updated_at")


class ScheduleConflictSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="roster_entry.employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="roster_entry.employee.employee_id", read_only=True)

    class Meta:
        model = ScheduleConflict
        fields = (
            "id",
            "roster_entry",
            "employee_name",
            "employee_code",
            "conflict_type",
            "message",
            "is_resolved",
            "reported_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "employee_name", "employee_code", "created_at", "updated_at")


class BulkShiftAssignmentSerializer(serializers.Serializer):
    employees = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.select_related("user"), many=True)
    shift_template = serializers.PrimaryKeyRelatedField(queryset=ShiftTemplate.objects.filter(is_active=True))
    start_date = serializers.DateField()
    end_date = serializers.DateField()

