from django.contrib import admin

from .models import LeaveBalance, LeaveRequest


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "allocated_days", "used_days")
    list_filter = ("leave_type",)
    search_fields = ("employee__employee_id", "employee__user__email")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "duration_type", "start_date", "end_date", "status", "approver")
    list_filter = ("leave_type", "status")
    search_fields = ("employee__employee_id", "employee__user__email")
