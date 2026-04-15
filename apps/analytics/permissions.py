from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class CanViewAnalytics(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in {User.Role.MANAGER, User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}
        )

