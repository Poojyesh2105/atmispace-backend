from rest_framework import serializers

from apps.holidays.models import EmployeeHolidayAssignment, Holiday, HolidayCalendar


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ("id", "calendar", "name", "date", "is_optional", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class HolidayCalendarSerializer(serializers.ModelSerializer):
    holidays = HolidaySerializer(many=True, read_only=True)

    class Meta:
        model = HolidayCalendar
        fields = ("id", "name", "country_code", "description", "is_default", "holidays", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class EmployeeHolidayAssignmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    calendar_name = serializers.CharField(source="calendar.name", read_only=True)

    class Meta:
        model = EmployeeHolidayAssignment
        fields = ("id", "employee", "employee_name", "employee_code", "calendar", "calendar_name", "created_at", "updated_at")
        read_only_fields = ("id", "employee_name", "employee_code", "calendar_name", "created_at", "updated_at")
