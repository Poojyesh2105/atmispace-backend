from django.db.models import Q

from apps.accounts.models import User
from apps.lifecycle.models import EmployeeChangeRequest, EmployeeOnboarding, EmployeeOnboardingTask, OffboardingCase, OffboardingTask, OnboardingPlan, OnboardingTaskTemplate


class LifecycleSelectors:
    @staticmethod
    def get_onboarding_plan_queryset(user=None):
        return OnboardingPlan.objects.for_current_org(user).select_related("department").prefetch_related("task_templates")

    @staticmethod
    def get_onboarding_task_template_queryset(user=None):
        return OnboardingTaskTemplate.objects.for_current_org(user).select_related("plan")

    @staticmethod
    def get_employee_onboarding_queryset_for_user(user):
        queryset = EmployeeOnboarding.objects.for_current_org(user).select_related("employee__user", "plan", "initiated_by").prefetch_related("tasks")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def get_employee_onboarding_task_queryset_for_user(user):
        queryset = EmployeeOnboardingTask.objects.for_current_org(user).select_related("onboarding__employee__user", "completed_by")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(
                Q(onboarding__employee=employee)
                | Q(onboarding__employee__manager=employee)
                | Q(onboarding__employee__secondary_manager=employee)
                | Q(owner_role=user.role)
            )
        if employee:
            return queryset.filter(Q(onboarding__employee=employee) | Q(owner_role=user.role))
        return queryset.none()

    @staticmethod
    def get_offboarding_queryset_for_user(user):
        queryset = OffboardingCase.objects.for_current_org(user).select_related("employee__user", "initiated_by").prefetch_related("tasks")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ADMIN, User.Role.ACCOUNTS}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def get_offboarding_task_queryset_for_user(user):
        queryset = OffboardingTask.objects.for_current_org(user).select_related("offboarding_case__employee__user", "completed_by")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ADMIN, User.Role.ACCOUNTS}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(
                Q(offboarding_case__employee=employee)
                | Q(offboarding_case__employee__manager=employee)
                | Q(offboarding_case__employee__secondary_manager=employee)
                | Q(owner_role=user.role)
            )
        if employee:
            return queryset.filter(Q(offboarding_case__employee=employee) | Q(owner_role=user.role))
        return queryset.none()

    @staticmethod
    def get_change_request_queryset_for_user(user):
        queryset = EmployeeChangeRequest.objects.for_current_org(user).select_related("employee__user", "requested_by", "approved_by")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()
