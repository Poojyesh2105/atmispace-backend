from django.db.models import Q

from apps.accounts.models import User
from apps.payroll.models import DeductionRule, PayrollAdjustment, PayrollCycle, PayrollRun, SalaryRevision


class PayrollGovernanceSelectors:
    @staticmethod
    def get_cycle_queryset_for_user(user):
        queryset = PayrollCycle.objects.all()
        if user.role in {User.Role.MANAGER, User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        return queryset.none()

    @staticmethod
    def get_run_queryset_for_user(user):
        queryset = PayrollRun.objects.select_related("cycle", "generated_by", "released_by")
        if user.role in {User.Role.MANAGER, User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        return queryset.none()

    @staticmethod
    def get_adjustment_queryset_for_user(user):
        queryset = PayrollAdjustment.objects.select_related("cycle", "employee__user", "created_by")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee))
        return queryset.none()

    @staticmethod
    def get_revision_queryset_for_user(user):
        queryset = SalaryRevision.objects.select_related("employee__user", "approved_by")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def get_deduction_rule_queryset():
        return DeductionRule.objects.all()

