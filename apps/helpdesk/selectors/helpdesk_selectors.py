from django.db.models import Q

from apps.accounts.models import User
from apps.helpdesk.models import HelpdeskCategory, HelpdeskTicket


class HelpdeskSelectors:
    @staticmethod
    def get_category_queryset(user=None):
        return HelpdeskCategory.objects.for_current_org(user)

    @staticmethod
    def get_ticket_queryset_for_user(user):
        queryset = HelpdeskTicket.objects.for_current_org(user).select_related("requester__user", "category", "assigned_user").prefetch_related("comments__author")
        employee = getattr(user, "employee_profile", None)

        if user.role == User.Role.ADMIN:
            return queryset
        if user.role in {User.Role.HR, User.Role.ACCOUNTS}:
            return queryset.filter(Q(category__owner_role=user.role) | Q(assigned_user=user))
        if employee:
            return queryset.filter(Q(requester=employee) | Q(assigned_user=user))
        return queryset.none()
