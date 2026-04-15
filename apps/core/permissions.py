from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    allowed_roles = set()

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


class IsAdminOrHR(RolePermission):
    allowed_roles = {"HR", "ADMIN"}


class IsManagerOrAbove(RolePermission):
    allowed_roles = {"MANAGER", "HR", "ADMIN"}


class IsWorkflowAdmin(RolePermission):
    allowed_roles = {"HR", "ADMIN"}


class IsSelfOrPrivileged(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role in {"HR", "ADMIN"}:
            return True
        employee = getattr(request.user, "employee_profile", None)
        return bool(employee and obj.pk == employee.pk)


class IsOwnerManagerOrPrivileged(BasePermission):
    employee_attr = "employee"

    def has_object_permission(self, request, view, obj):
        if request.user.role in {"HR", "ADMIN"}:
            return True

        target_employee = getattr(obj, self.employee_attr, None)
        current_employee = getattr(request.user, "employee_profile", None)
        if not target_employee or not current_employee:
            return False

        if target_employee.pk == current_employee.pk:
            return True

        return bool(
            target_employee.manager_id == current_employee.pk
            or getattr(target_employee, "secondary_manager_id", None) == current_employee.pk
        )
