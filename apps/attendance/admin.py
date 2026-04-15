from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "attendance_date",
        "check_in",
        "break_started_at",
        "check_out",
        "break_minutes",
        "status",
        "total_work_minutes",
    )
    list_filter = ("status", "attendance_date")
    search_fields = ("employee__employee_id", "employee__user__email")
