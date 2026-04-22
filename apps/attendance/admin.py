from django.contrib import admin

from .models import Attendance, BiometricAttendanceEvent, BiometricDevice


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "attendance_date",
        "check_in",
        "break_started_at",
        "check_out",
        "break_minutes",
        "break_count",
        "status",
        "source",
        "total_work_minutes",
    )
    list_filter = ("status", "source", "attendance_date")
    search_fields = ("employee__employee_id", "employee__user__email")


@admin.register(BiometricDevice)
class BiometricDeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "device_code", "location_name", "is_active", "last_seen_at")
    list_filter = ("is_active",)
    search_fields = ("name", "device_code", "location_name")


@admin.register(BiometricAttendanceEvent)
class BiometricAttendanceEventAdmin(admin.ModelAdmin):
    list_display = (
        "device",
        "employee",
        "device_user_id",
        "event_type",
        "occurred_at",
        "status",
        "attendance",
    )
    list_filter = ("status", "event_type", "device")
    search_fields = (
        "device__device_code",
        "device_user_id",
        "external_event_id",
        "employee__employee_id",
        "employee__user__email",
    )
