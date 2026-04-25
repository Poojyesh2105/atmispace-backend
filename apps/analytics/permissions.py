from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class CanViewAnalytics(BasePermission):
    def has_permission(self, request, view):
        allowed_roles = {
            User.Role.MANAGER,
            User.Role.HR,
            User.Role.ACCOUNTS,
            User.Role.ADMIN,
            User.Role.SUPER_ADMIN,
        }
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in allowed_roles
        )
