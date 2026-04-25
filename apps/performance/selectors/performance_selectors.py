from django.db.models import Q

from apps.accounts.models import User
from apps.performance.models import PerformanceCycle, PerformanceGoal, PerformanceReview, RatingScale


class PerformanceSelectors:
    @staticmethod
    def get_rating_scale_queryset(user=None):
        return RatingScale.objects.for_current_org(user)

    @staticmethod
    def get_cycle_queryset(user=None):
        return PerformanceCycle.objects.for_current_org(user).select_related("rating_scale")

    @staticmethod
    def get_goal_queryset_for_user(user):
        queryset = PerformanceGoal.objects.for_current_org(user).select_related("employee__user", "cycle", "employee__manager__user")
        employee = getattr(user, "employee_profile", None)

        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(
                Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee)
            )
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def get_review_queryset_for_user(user):
        queryset = PerformanceReview.objects.for_current_org(user).select_related("employee__user", "cycle", "manager__user", "employee__manager__user")
        employee = getattr(user, "employee_profile", None)

        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(
                Q(employee=employee)
                | Q(employee__manager=employee)
                | Q(employee__secondary_manager=employee)
                | Q(manager=employee)
            )
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def get_review_inbox_for_user(user):
        queryset = PerformanceSelectors.get_review_queryset_for_user(user)
        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return queryset.filter(status=PerformanceReview.Status.HR_PENDING)
        if user.role == User.Role.MANAGER:
            return queryset.filter(status=PerformanceReview.Status.MANAGER_PENDING)
        return queryset.filter(status=PerformanceReview.Status.SELF_PENDING)
