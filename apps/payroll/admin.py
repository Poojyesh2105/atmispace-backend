from django.contrib import admin

from apps.payroll.models import Payslip


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "payroll_month",
        "gross_monthly_salary",
        "total_deductions",
        "net_pay",
        "generated_by",
        "generated_at",
    )
    list_filter = ("payroll_month", "employee__department", "employee__user__role")
    search_fields = ("employee__employee_id", "employee__user__first_name", "employee__user__last_name")

