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
from apps.payroll.models import Payslip, PayslipComponentEntry, SalaryComponent, SalaryComponentTemplate
from apps.payroll.services.payroll_component_service import SalaryComponentService


class PayslipService:
    VIEW_ROLES = {User.Role.MANAGER, User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}
    GENERATE_ROLES = {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}
    LOP_COMPONENT_NAME = "Loss of Pay"
    LOP_COMPONENT_CODE = "LOP"
    LOP_COMPONENT_DISPLAY_ORDER = 9000

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
        lop_days = PayslipService.calculate_lop_days(employee, month_start)
        lop_deduction = (
            (gross_monthly_salary / Decimal(days_in_month)) * lop_days
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_deductions = lop_deduction.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
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
            "lop_days": lop_days,
            "lop_deduction": lop_deduction,
            "total_deductions": total_deductions,
            "net_pay": net_pay,
            "days_in_month": days_in_month,
            "payable_days": payable_days,
        }

    @staticmethod
    def _compute_component_entries(employee, gross_monthly_salary, salary_component_template=None):
        """
        Compute PayslipComponentEntry data for all active SalaryComponents.
        Returns a tuple of (component_entries_data, additional_component_earnings, total_component_deductions).
        """
        template = salary_component_template or SalaryComponentService.get_template_for_employee(employee)
        components = list(
            SalaryComponent.objects.filter(template=template, is_active=True)
            .select_related("base_component")
            .order_by("display_order", "name", "id")
        )
        components = [
            component for component in components
            if str(component.code).upper() != PayslipService.LOP_COMPONENT_CODE
        ]
        components_by_id = {component.id: component for component in components}
        entries_data = []
        additional_earnings = Decimal("0.00")
        total_deductions = Decimal("0.00")
        calculated: dict[int, dict[str, Decimal]] = {}

        ctc_monthly = (
            (employee.ctc_per_annum / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if (employee.ctc_per_annum or Decimal("0")) > 0
            else Decimal("0.00")
        )

        def calculate_value(component, value, stack):
            calc_type = component.calculation_type
            if calc_type == SalaryComponent.CalculationType.FIXED:
                return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            elif calc_type == SalaryComponent.CalculationType.PERCENT_OF_GROSS:
                return (Decimal(str(value)) / Decimal("100") * gross_monthly_salary).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            elif calc_type == SalaryComponent.CalculationType.PERCENT_OF_CTC:
                return (Decimal(str(value)) / Decimal("100") * ctc_monthly).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            elif calc_type == SalaryComponent.CalculationType.PERCENT_OF_COMPONENT:
                base_component = component.base_component
                if not base_component or base_component.id not in components_by_id:
                    raise exceptions.ValidationError(
                        {"salary_components": f"{component.name} requires an active base component in {template.name}."}
                    )
                base_amount = resolve_component(base_component, stack)["base_amount"]
                return (Decimal(str(value)) / Decimal("100") * base_amount).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            return Decimal("0.00")

        def resolve_component(component, stack=None):
            stack = stack or set()
            if component.id in calculated:
                return calculated[component.id]
            if component.id in stack:
                raise exceptions.ValidationError({"salary_components": "Component calculation cycle detected."})

            stack.add(component.id)
            base_amount = calculate_value(component, component.value, stack)
            employer_contribution_amount = Decimal("0.00")
            if component.has_employer_contribution:
                employer_contribution_amount = calculate_value(component, component.employer_contribution_value, stack)
            stack.remove(component.id)

            calculated_amount = base_amount
            if (
                component.component_type == SalaryComponent.ComponentType.DEDUCTION
                and component.has_employer_contribution
                and component.deduct_employer_contribution
            ):
                calculated_amount += employer_contribution_amount

            result = {
                "base_amount": base_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "calculated_amount": calculated_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                "employer_contribution_amount": employer_contribution_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            }
            calculated[component.id] = result
            return result

        for component in components:
            amounts = resolve_component(component)
            amount = amounts["calculated_amount"]

            entries_data.append({
                "component": component,
                "component_name": component.name,
                "component_code": component.code,
                "component_type": component.component_type,
                "calculated_amount": amount,
                "employer_contribution_amount": amounts["employer_contribution_amount"],
                "deducts_employer_contribution": component.deduct_employer_contribution,
                "display_order": component.display_order,
            })

            if component.component_type == SalaryComponent.ComponentType.EARNING:
                if not component.is_part_of_gross:
                    additional_earnings += amount
            else:
                total_deductions += amount

        return template, entries_data, additional_earnings, total_deductions

    @staticmethod
    def _build_lop_component_entry(lop_deduction):
        amount = Decimal(str(lop_deduction or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return {
            "component": None,
            "component_name": PayslipService.LOP_COMPONENT_NAME,
            "component_code": PayslipService.LOP_COMPONENT_CODE,
            "component_type": SalaryComponent.ComponentType.DEDUCTION,
            "calculated_amount": amount,
            "employer_contribution_amount": Decimal("0.00"),
            "deducts_employer_contribution": False,
            "display_order": PayslipService.LOP_COMPONENT_DISPLAY_ORDER,
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
        component_deductions=Decimal("0.00"),
        adjustment_deductions=Decimal("0.00"),
        salary_component_template: SalaryComponentTemplate | None = None,
    ):
        if not PayslipService.can_generate_payslip(user):
            raise exceptions.PermissionDenied("You are not allowed to generate payslips.")

        if salary_component_template:
            SalaryComponentService.assign_template_to_employee(employee, salary_component_template, user)
        resolved_template = salary_component_template or SalaryComponentService.get_template_for_employee(employee)
        calculation = PayslipService.calculate_payout(employee, payroll_month)
        gross_monthly_salary = calculation["gross_monthly_salary"]

        # Compute salary component entries
        resolved_template, component_entries_data, component_earnings, calculated_component_deductions = PayslipService._compute_component_entries(
            employee, gross_monthly_salary, resolved_template
        )

        # Merge component-derived amounts with any caller-supplied overrides
        final_additional_earnings = (additional_earnings + component_earnings).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        final_component_deductions = (component_deductions + calculated_component_deductions).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        component_entries_data.append(PayslipService._build_lop_component_entry(calculation["lop_deduction"]))

        total_deductions = (
            calculation["lop_deduction"] + final_component_deductions + adjustment_deductions
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net_pay = max(gross_monthly_salary + final_additional_earnings - total_deductions, Decimal("0.00")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        payslip, _ = Payslip.objects.update_or_create(
            employee=employee,
            payroll_month=calculation["payroll_month"],
            defaults={
                **calculation,
                "payroll_cycle": payroll_cycle,
                "salary_component_template": resolved_template,
                "salary_component_template_name": resolved_template.name,
                "additional_earnings": final_additional_earnings,
                "component_deductions": final_component_deductions,
                "adjustment_deductions": adjustment_deductions,
                "total_deductions": total_deductions,
                "net_pay": net_pay,
                "generated_by": user,
                "notes": notes,
                "generated_at": timezone.now(),
            },
        )

        # Recreate component entries (delete old ones first on regeneration)
        PayslipComponentEntry.objects.filter(payslip=payslip).delete()
        PayslipComponentEntry.objects.bulk_create([
            PayslipComponentEntry(payslip=payslip, **entry_data)
            for entry_data in component_entries_data
        ])

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
