from rest_framework import serializers

from apps.attendance.models import Attendance
from apps.employees.models import Employee
from apps.leave_management.models import LeaveRequest


class AttendanceReportRowSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    shift_name = serializers.CharField(source="employee.shift_name", read_only=True)
    break_minutes = serializers.IntegerField(read_only=True)
    worked_minutes = serializers.IntegerField(source="total_work_minutes", read_only=True)

    class Meta:
        model = Attendance
        fields = (
            "id",
            "employee_name",
            "employee_code",
            "attendance_date",
            "shift_name",
            "status",
            "check_in",
            "check_out",
            "break_minutes",
            "worked_minutes",
        )


class LeaveReportRowSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = (
            "id",
            "employee_name",
            "employee_code",
            "leave_type",
            "status",
            "start_date",
            "end_date",
            "total_days",
        )


class EmployeeReportRowSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Employee
        fields = (
            "id",
            "full_name",
            "employee_id",
            "designation",
            "department_name",
            "role",
            "department_role",
            "is_active",
        )
