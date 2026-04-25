from rest_framework.permissions import BasePermission

from apps.core.role_utils import (
    ELEVATED_ROLES,
    SUPER_ADMIN,
    can_access_employee,
    can_approve_workflow,
    get_user_org_role,
)

# ---------------------------------------------------------------------------
# Role-based permission helpers
# ---------------------------------------------------------------------------

PRIVILEGED_ROLES = {"HR", "ADMIN", "SUPER_ADMIN"}
ALL_STAFF_ROLES = {"MANAGER", "HR", "ACCOUNTS", "ADMIN", "SUPER_ADMIN"}


class RolePermission(BasePermission):
    """
    Base class for role-based permissions.
    Uses get_user_org_role() so multi-org memberships and SUPER_ADMIN bypass
    are handled centrally.
    """
    allowed_roles: set = set()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        org = getattr(request, "organization", None)
        role = get_user_org_role(request.user, org)
        return role in self.allowed_roles


class IsSuperAdmin(RolePermission):
    """Only platform-level SUPER_ADMIN users."""
    allowed_roles = {SUPER_ADMIN}


class IsAdminOrHR(RolePermission):
    allowed_roles = {"HR", "ADMIN", SUPER_ADMIN}


class IsAccountsOrAdmin(RolePermission):
    """Payroll / salary access."""
    allowed_roles = {"ACCOUNTS", "ADMIN", SUPER_ADMIN}


class IsManagerOrAbove(RolePermission):
    allowed_roles = {"MANAGER", "HR", "ADMIN", SUPER_ADMIN}


class IsWorkflowAdmin(RolePermission):
    allowed_roles = {"HR", "ADMIN", SUPER_ADMIN}


class IsSelfOrPrivileged(BasePermission):
    """Object-level: user is viewing their own record, or is an elevated role."""

    def has_object_permission(self, request, view, obj):
        org = getattr(request, "organization", None)
        role = get_user_org_role(request.user, org)
        if role in ELEVATED_ROLES:
            return True
        employee = getattr(request.user, "employee_profile", None)
        return bool(employee and obj.pk == employee.pk)


class IsOwnerManagerOrPrivileged(BasePermission):
    """Object-level: user owns the record, is its manager, or is elevated."""
    employee_attr = "employee"

    def has_object_permission(self, request, view, obj):
        org = getattr(request, "organization", None)
        role = get_user_org_role(request.user, org)
        if role in ELEVATED_ROLES:
            return True

        target_employee = getattr(obj, self.employee_attr, None)
        if target_employee is None:
            return False
        return can_access_employee(request.user, target_employee, org)


class IsEmployeeAccessible(BasePermission):
    """
    Object-level guard for Employee records.
    Delegates entirely to can_access_employee() in role_utils.
    """

    def has_object_permission(self, request, view, obj):
        org = getattr(request, "organization", None)
        return can_access_employee(request.user, obj, org)


class IsWorkflowApprover(BasePermission):
    """Object-level guard for workflow approval actions."""

    def has_object_permission(self, request, view, obj):
        org = getattr(request, "organization", None)
        return can_approve_workflow(request.user, obj, org)


class IsSameOrganization(BasePermission):
    """
    Object-level guard: ensures the object belongs to the same org as the
    request's resolved tenant. SUPER_ADMIN bypasses this.
    """

    def has_object_permission(self, request, view, obj):
        if getattr(request.user, "role", None) == SUPER_ADMIN:
            return True
        request_org = getattr(request, "organization", None)
        obj_org_id = getattr(obj, "organization_id", None)
        if request_org is None or obj_org_id is None:
            return True  # can't enforce what we can't resolve
        return obj_org_id == request_org.pk
