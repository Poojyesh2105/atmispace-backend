"""
Centralized role-checking utilities.
Always include SUPER_ADMIN in privileged checks so the platform owner
can access everything without needing per-service updates.
"""
from typing import Optional


# Role sets (as string literals — safe to import without model dependency)
SUPER_ADMIN = "SUPER_ADMIN"
ADMIN = "ADMIN"
HR = "HR"
ACCOUNTS = "ACCOUNTS"
MANAGER = "MANAGER"
EMPLOYEE = "EMPLOYEE"

# Ordered privilege levels (higher index = more access)
_PRIVILEGE_ORDER = [EMPLOYEE, MANAGER, ACCOUNTS, HR, ADMIN, SUPER_ADMIN]

# Common role groupings
ELEVATED_ROLES = frozenset({HR, ADMIN, SUPER_ADMIN})
FINANCIAL_ROLES = frozenset({ACCOUNTS, HR, ADMIN, SUPER_ADMIN})
MANAGEMENT_ROLES = frozenset({MANAGER, HR, ADMIN, SUPER_ADMIN})
ALL_PRIVILEGED = frozenset({MANAGER, HR, ACCOUNTS, ADMIN, SUPER_ADMIN})


def is_super_admin(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False) and getattr(user, "role", None) == SUPER_ADMIN)


def is_elevated(user) -> bool:
    """HR, ADMIN, or SUPER_ADMIN."""
    return bool(user and getattr(user, "is_authenticated", False) and getattr(user, "role", None) in ELEVATED_ROLES)


def is_financial(user) -> bool:
    """ACCOUNTS, HR, ADMIN, or SUPER_ADMIN — payroll/salary access."""
    return bool(user and getattr(user, "is_authenticated", False) and getattr(user, "role", None) in FINANCIAL_ROLES)


def is_manager_or_above(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False) and getattr(user, "role", None) in MANAGEMENT_ROLES)


def has_role_in(user, roles) -> bool:
    """Check if user's role is in the given set, always including SUPER_ADMIN."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "role", None)
    if role == SUPER_ADMIN:
        return True  # Super admin passes all role checks
    return role in roles


def mask_salary(user, data: dict, fields: Optional[list] = None) -> dict:
    """
    Remove salary/compensation fields from data for users who should not see them.
    ACCOUNTS, HR, ADMIN, SUPER_ADMIN can see salary. Others cannot.
    """
    if is_financial(user):
        return data
    SALARY_FIELDS = fields or [
        "ctc_per_annum", "monthly_gross_salary", "gross_monthly_salary",
        "net_pay", "total_deductions", "basic_salary",
    ]
    return {k: v for k, v in data.items() if k not in SALARY_FIELDS}


# ---------------------------------------------------------------------------
# Org-scoped RBAC helpers (Task 14)
# ---------------------------------------------------------------------------

def get_user_org_role(user, organization=None):
    """
    Return the effective role string for *user* within *organization*.

    Resolution order:
      1. SUPER_ADMIN → always returns "SUPER_ADMIN" (cross-org)
      2. OrganizationMembership for the given org (V3 multi-org path)
      3. user.role (legacy / single-org path)
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None

    role = getattr(user, "role", None)
    if role == SUPER_ADMIN:
        return SUPER_ADMIN

    if organization is not None:
        try:
            membership = user.org_memberships.filter(
                organization=organization, is_active=True
            ).values_list("role", flat=True).first()
            if membership:
                return membership
        except Exception:
            pass

    return role  # legacy fallback


def can_access_employee(user, employee, organization=None) -> bool:
    """
    Return True if *user* is allowed to view/edit *employee*.
    Rules:
      - SUPER_ADMIN → always
      - Elevated (HR/ADMIN) → any employee in their org
      - MANAGER → self + direct/secondary reports
      - EMPLOYEE → self only
      - Cross-org access → denied (org check)
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    role = get_user_org_role(user, organization)

    if role == SUPER_ADMIN:
        return True

    # Org isolation: employee must belong to the same org as the user
    user_org_id = _resolve_org_id(user, organization)
    if user_org_id and getattr(employee, "organization_id", None) != user_org_id:
        return False

    if role in ELEVATED_ROLES:
        return True

    current_employee = getattr(user, "employee_profile", None)
    if current_employee is None:
        return False

    if employee.pk == current_employee.pk:
        return True

    if role == MANAGER:
        return (
            getattr(employee, "manager_id", None) == current_employee.pk
            or getattr(employee, "secondary_manager_id", None) == current_employee.pk
        )

    return False


def can_manage_payroll(user, organization=None) -> bool:
    """Return True if the user can generate/view payroll for the given org."""
    role = get_user_org_role(user, organization)
    return role in FINANCIAL_ROLES


def can_approve_workflow(user, workflow_item, organization=None) -> bool:
    """
    Return True if the user can approve/reject a workflow item.
    HR, ADMIN, SUPER_ADMIN can approve anything.
    MANAGER can approve items for their direct reports.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    role = get_user_org_role(user, organization)

    if role in ELEVATED_ROLES:
        return True

    if role == MANAGER:
        current_employee = getattr(user, "employee_profile", None)
        target_employee = getattr(workflow_item, "employee", None) or getattr(workflow_item, "requester", None)
        if current_employee and target_employee:
            return (
                getattr(target_employee, "manager_id", None) == current_employee.pk
                or getattr(target_employee, "secondary_manager_id", None) == current_employee.pk
            )

    return False


def get_accessible_org_ids(user) -> Optional[list]:
    """
    Return list of org IDs the user may access, or None for SUPER_ADMIN
    (meaning unrestricted).
    """
    if is_super_admin(user):
        return None  # None = all orgs

    org_ids = []
    try:
        org_ids = list(
            user.org_memberships.filter(is_active=True).values_list("organization_id", flat=True)
        )
    except Exception:
        pass

    if not org_ids:
        org_id = getattr(user, "organization_id", None)
        if org_id:
            org_ids = [org_id]

    return org_ids


def _resolve_org_id(user, organization=None) -> Optional[int]:
    """Internal: get the integer org PK we care about for this request."""
    if organization is not None:
        return getattr(organization, "pk", None)
    return getattr(user, "organization_id", None)
