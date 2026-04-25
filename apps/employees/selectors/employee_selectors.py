from django.db.models import Q

from apps.accounts.models import User
from apps.employees.models import Department, Employee, OrganizationSettings, ShiftTemplate


class EmployeeSelectors:
    @staticmethod
    def base_employee_queryset(user=None):
        return Employee.objects.for_current_org(user).select_related(
            "user",
            "department",
            "manager__user",
            "secondary_manager__user",
            "shift_template",
        )

    @staticmethod
    def get_team_member_ids(viewer_employee):
        if not viewer_employee:
            return []
        return list(
            Employee.objects.filter(
                Q(manager=viewer_employee) | Q(secondary_manager=viewer_employee)
            ).values_list("pk", flat=True)
        )

    @staticmethod
    def get_queryset_for_user(user):
        queryset = EmployeeSelectors.base_employee_queryset(user)
        employee = getattr(user, "employee_profile", None)

        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            team_ids = EmployeeSelectors.get_team_member_ids(employee)
            return queryset.filter(Q(pk=employee.pk) | Q(pk__in=team_ids))
        if employee:
            return queryset.filter(pk=employee.pk)
        return queryset.none()

    @staticmethod
    def can_view_compensation(user, employee):
        if not user or not getattr(user, "is_authenticated", False) or not employee:
            return False
        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return True
        current_employee = getattr(user, "employee_profile", None)
        if not current_employee:
            return False
        if employee.pk == current_employee.pk:
            return True
        if user.role == User.Role.MANAGER:
            return employee.manager_id == current_employee.pk or employee.secondary_manager_id == current_employee.pk
        return False

    @staticmethod
    def get_department_queryset(user=None):
        return Department.objects.for_current_org(user).prefetch_related("employees")

    @staticmethod
    def get_shift_queryset(user=None):
        return ShiftTemplate.objects.for_current_org(user)

    @staticmethod
    def get_settings_queryset(user=None):
        return OrganizationSettings.objects.for_current_org(user)
