from django.db.models import Q

from apps.accounts.models import User
from apps.employees.selectors import EmployeeSelectors
from apps.payroll.models import PayrollAdjustment, PayrollCycle, PayrollRun, SalaryRevision


class PayrollGovernanceSelectors:
    @staticmethod
    def get_cycle_queryset_for_user(user):
        queryset = PayrollCycle.objects.for_current_org(user)
        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        return queryset.none()

    @staticmethod
    def get_run_queryset_for_user(user):
        queryset = PayrollRun.objects.for_current_org(user).select_related("cycle", "generated_by", "released_by")
        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        return queryset.none()

    @staticmethod
    def get_adjustment_queryset_for_user(user):
        queryset = PayrollAdjustment.objects.for_current_org(user).select_related("cycle", "employee__user", "created_by")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            team_ids = EmployeeSelectors.get_team_member_ids(employee)
            return queryset.filter(Q(employee=employee) | Q(employee_id__in=team_ids))
        return queryset.none()

    @staticmethod
    def get_revision_queryset_for_user(user):
        queryset = SalaryRevision.objects.for_current_org(user).select_related("employee__user", "approved_by")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            team_ids = EmployeeSelectors.get_team_member_ids(employee)
            return queryset.filter(Q(employee=employee) | Q(employee_id__in=team_ids))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()
