from apps.attendance.models import Attendance
from apps.attendance.services.attendance_service import AttendanceService
from apps.employees.models import Employee
from apps.employees.services.employee_service import EmployeeService
from apps.leave_management.models import LeaveRequest
from apps.leave_management.services.leave_service import LeaveRequestService


class ReportService:
    @staticmethod
    def get_attendance_queryset(user, params):
        queryset = AttendanceService.get_queryset_for_user(user)
        if params.get("date_from"):
            queryset = queryset.filter(attendance_date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(attendance_date__lte=params["date_to"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("employee"):
            queryset = queryset.filter(employee_id=params["employee"])
        return queryset.order_by("-attendance_date", "employee__employee_id")

    @staticmethod
    def get_leave_queryset(user, params):
        queryset = LeaveRequestService.get_queryset_for_user(user)
        if params.get("date_from"):
            queryset = queryset.filter(start_date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(end_date__lte=params["date_to"])
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("employee"):
            queryset = queryset.filter(employee_id=params["employee"])
        return queryset.order_by("-created_at")

    @staticmethod
    def get_employee_queryset(user, params):
        queryset = EmployeeService.get_employee_queryset_for_user(user)
        if params.get("department"):
            queryset = queryset.filter(department_id=params["department"])
        if params.get("role"):
            queryset = queryset.filter(user__role=params["role"])
        if params.get("is_active") in {"true", "false"}:
            queryset = queryset.filter(is_active=params["is_active"] == "true")
        return queryset.order_by("employee_id")

    @staticmethod
    def get_report_columns(report_type):
        columns = {
            "attendance": [
                {"key": "employee_name", "label": "Employee"},
                {"key": "employee_code", "label": "Employee Code"},
                {"key": "attendance_date", "label": "Date"},
                {"key": "shift_name", "label": "Shift"},
                {"key": "status", "label": "Status"},
                {"key": "source", "label": "Source"},
                {"key": "check_in", "label": "Check In"},
                {"key": "check_out", "label": "Check Out"},
                {"key": "break_minutes", "label": "Break Minutes"},
                {"key": "break_count", "label": "Break Count"},
                {"key": "worked_minutes", "label": "Worked Minutes"},
            ],
            "leave": [
                {"key": "employee_name", "label": "Employee"},
                {"key": "employee_code", "label": "Employee Code"},
                {"key": "leave_type", "label": "Leave Type"},
                {"key": "status", "label": "Status"},
                {"key": "start_date", "label": "Start Date"},
                {"key": "end_date", "label": "End Date"},
                {"key": "total_days", "label": "Total Days"},
            ],
            "employee": [
                {"key": "full_name", "label": "Employee"},
                {"key": "employee_id", "label": "Employee Code"},
                {"key": "designation", "label": "Designation"},
                {"key": "department_name", "label": "Department"},
                {"key": "role", "label": "Role"},
                {"key": "department_role", "label": "Department Role"},
                {"key": "is_active", "label": "Is Active"},
            ],
        }
        return columns[report_type]
