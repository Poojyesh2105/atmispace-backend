from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User
from apps.audit.services.audit_service import AuditService
from apps.employees.models import Employee
from apps.leave_management.models import LeaveBalance, LeaveRequest
from apps.leave_management.services.leave_service import LeaveRequestService
from apps.payroll.models import Payslip


class PayslipService:
    VIEW_ROLES = {User.Role.MANAGER, User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}
    GENERATE_ROLES = {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}

    @staticmethod
    def can_view_compensation(user, employee=None):
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if user.role in PayslipService.VIEW_ROLES:
            return True
        current_employee = getattr(user, "employee_profile", None)
        return bool(employee and current_employee and current_employee.pk == employee.pk)

    @staticmethod
    def can_generate_payslip(user):
        return bool(user and getattr(user, "is_authenticated", False) and user.role in PayslipService.GENERATE_ROLES)

    @staticmethod
    def normalize_payroll_month(payroll_month):
        return payroll_month.replace(day=1)

    @staticmethod
    def get_month_bounds(payroll_month):
        normalized_month = PayslipService.normalize_payroll_month(payroll_month)
        days_in_month = monthrange(normalized_month.year, normalized_month.month)[1]
        month_end = date(normalized_month.year, normalized_month.month, days_in_month)
        return normalized_month, month_end, days_in_month

    @staticmethod
    def get_queryset_for_user(user):
        queryset = Payslip.objects.select_related("employee__user", "generated_by", "employee__department")
        employee = getattr(user, "employee_profile", None)
        if user.role in PayslipService.VIEW_ROLES:
            return queryset
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def _get_request_lop_days_for_month(leave_request, month_key):
        lop_days = Decimal(str(getattr(leave_request, "lop_days_applied", 0) or 0))
        if lop_days <= 0 and leave_request.leave_type == LeaveBalance.LeaveType.LOP:
            lop_days = Decimal(str(leave_request.total_days))
        if lop_days <= 0:
            return Decimal("0.00")

        days_by_month = LeaveRequestService._get_days_by_month(
            {
                "start_date": leave_request.start_date,
                "end_date": leave_request.end_date,
                "duration_type": leave_request.duration_type,
            },
            leave_request.employee,
        )
        total_days = sum(days_by_month.values(), Decimal("0.00"))
        month_days = days_by_month.get(month_key, Decimal("0.00"))
        if total_days <= 0 or month_days <= 0:
            return Decimal("0.00")
        return (lop_days * month_days / total_days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_lop_days(employee, payroll_month):
        month_start, month_end, _ = PayslipService.get_month_bounds(payroll_month)
        month_key = month_start.strftime("%Y-%m")
        leave_requests = LeaveRequest.objects.filter(
            employee=employee,
            status=LeaveRequest.Status.APPROVED,
            start_date__lte=month_end,
            end_date__gte=month_start,
        )

        lop_days = Decimal("0.00")
        for leave_request in leave_requests:
            lop_days += PayslipService._get_request_lop_days_for_month(leave_request, month_key)
        return lop_days.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_payout(employee, payroll_month):
        if (employee.ctc_per_annum or Decimal("0")) <= 0:
            raise exceptions.ValidationError({"employee": "CTC per annum must be configured before generating a payslip."})

        month_start, _, days_in_month = PayslipService.get_month_bounds(payroll_month)
        gross_monthly_salary = (employee.ctc_per_annum / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        fixed_deductions = Decimal(str(employee.monthly_fixed_deductions or 0)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        lop_days = PayslipService.calculate_lop_days(employee, month_start)
        lop_deduction = (
            (gross_monthly_salary / Decimal(days_in_month)) * lop_days
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_deductions = (fixed_deductions + lop_deduction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net_pay = max(gross_monthly_salary - total_deductions, Decimal("0.00")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        payable_days = max(Decimal(days_in_month) - lop_days, Decimal("0.00")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        return {
            "payroll_month": month_start,
            "gross_monthly_salary": gross_monthly_salary,
            "fixed_deductions": fixed_deductions,
            "lop_days": lop_days,
            "lop_deduction": lop_deduction,
            "total_deductions": total_deductions,
            "net_pay": net_pay,
            "days_in_month": days_in_month,
            "payable_days": payable_days,
        }

    @staticmethod
    @transaction.atomic
    def generate_payslip(
        user,
        employee,
        payroll_month,
        notes="",
        payroll_cycle=None,
        additional_earnings=Decimal("0.00"),
        rule_based_deductions=Decimal("0.00"),
        adjustment_deductions=Decimal("0.00"),
    ):
        if not PayslipService.can_generate_payslip(user):
            raise exceptions.PermissionDenied("You are not allowed to generate payslips.")

        calculation = PayslipService.calculate_payout(employee, payroll_month)
        total_deductions = (
            calculation["fixed_deductions"] + calculation["lop_deduction"] + rule_based_deductions + adjustment_deductions
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net_pay = max(calculation["gross_monthly_salary"] + additional_earnings - total_deductions, Decimal("0.00")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        payslip, _ = Payslip.objects.update_or_create(
            employee=employee,
            payroll_month=calculation["payroll_month"],
            defaults={
                **calculation,
                "payroll_cycle": payroll_cycle,
                "additional_earnings": additional_earnings,
                "rule_based_deductions": rule_based_deductions,
                "adjustment_deductions": adjustment_deductions,
                "total_deductions": total_deductions,
                "net_pay": net_pay,
                "generated_by": user,
                "notes": notes,
                "generated_at": timezone.now(),
            },
        )
        AuditService.log(
            actor=user,
            action="payroll.payslip.generated",
            entity=payslip,
            after={
                "employee_id": employee.employee_id,
                "payroll_month": payslip.payroll_month.isoformat(),
                "net_pay": str(payslip.net_pay),
                "lop_days": str(payslip.lop_days),
            },
        )
        return payslip
