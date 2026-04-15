from django.contrib import admin

from .models import Department, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "created_at")
    search_fields = ("name", "code")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "user",
        "designation",
        "department",
        "department_role",
        "shift_name",
        "manager",
        "secondary_manager",
        "hire_date",
    )
    list_filter = ("department", "department_role", "employment_type", "is_active")
    search_fields = ("employee_id", "user__email", "user__first_name", "user__last_name")
