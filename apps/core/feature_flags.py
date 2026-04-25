"""
Feature flag enforcement utilities
====================================
Provides:
  - FeatureFlagRequired  — DRF permission class
  - require_feature()    — view-level decorator
  - FEATURE_MODULE_MAP   — which flag gates which URL prefix

Usage in a view:
    class PayrollListView(APIView):
        permission_classes = [IsAuthenticated, FeatureFlagRequired("enable_payroll")]

Usage as decorator:
    @require_feature("enable_payroll")
    class PayrollListView(APIView): ...
"""
import functools
import logging

from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.core.models import FeatureFlag

logger = logging.getLogger("atmispace.platform")

# ---------------------------------------------------------------------------
# Map: URL prefix segment → feature flag key
# Used by the middleware to auto-block entire modules.
# ---------------------------------------------------------------------------
FEATURE_MODULE_MAP: dict[str, str] = {
    "payroll":      FeatureFlag.ENABLE_PAYROLL,
    "performance":  FeatureFlag.ENABLE_PERFORMANCE,
    "lifecycle":    FeatureFlag.ENABLE_LIFECYCLE,
    "documents":    FeatureFlag.ENABLE_DOCUMENTS,
    "scheduling":   FeatureFlag.ENABLE_SCHEDULING,
    "attendance/biometric": FeatureFlag.ENABLE_BIOMETRIC,
    "helpdesk":     FeatureFlag.ENABLE_HELPDESK,
    "analytics":    FeatureFlag.ENABLE_ANALYTICS,
}


def _resolve_org(request):
    """Pull org from the tenant-resolved request attribute."""
    org = getattr(request, "organization", None)
    if org is not None:
        return org

    from apps.core.models import resolve_current_organization
    return resolve_current_organization(actor=getattr(request, "user", None))


def is_feature_enabled(flag_key: str, request) -> bool:
    """
    Return True if the feature is enabled for the request's resolved org.
    Superadmins always pass.
    """
    from apps.core.role_utils import is_super_admin
    if is_super_admin(request.user):
        return True
    org = _resolve_org(request)
    return FeatureFlag.is_enabled_for(flag_key, org)


# ---------------------------------------------------------------------------
# DRF Permission class
# ---------------------------------------------------------------------------

class FeatureFlagRequired(BasePermission):
    """
    Deny access if the feature flag `flag_key` is disabled for the request org.

    Instantiate with the flag key:
        permission_classes = [IsAuthenticated, FeatureFlagRequired("enable_payroll")]
    """
    message = "This feature is not enabled for your organization."

    def __init__(self, flag_key: str):
        self.flag_key = flag_key

    # DRF calls has_permission without arguments — we override __call__ for
    # class-based instantiation compatibility.
    def has_permission(self, request, view):
        enabled = is_feature_enabled(self.flag_key, request)
        if not enabled:
            logger.info(
                "feature_flag.blocked",
                extra={
                    "event": "feature_flag.blocked",
                    "flag_key": self.flag_key,
                    "org_id": getattr(request, "org_id", None),
                    "path": request.path,
                },
            )
        return enabled


def feature_flag_permission(flag_key: str):
    """
    Factory that returns a FeatureFlagRequired instance bound to flag_key.
    Allows use in permission_classes lists:
        permission_classes = [IsAuthenticated, feature_flag_permission("enable_payroll")]
    """
    class _BoundPermission(BasePermission):
        message = "This feature is not enabled for your organization."
        _flag_key = flag_key

        def has_permission(self, request, view):
            return is_feature_enabled(self._flag_key, request)

    _BoundPermission.__name__ = f"FeatureFlagRequired_{flag_key}"
    return _BoundPermission


# ---------------------------------------------------------------------------
# Decorator for class-based views
# ---------------------------------------------------------------------------

def require_feature(flag_key: str):
    """
    Class decorator that prepends a feature-flag check to the view's
    permission_classes.

    @require_feature("enable_payroll")
    class PayrollView(APIView): ...
    """
    def decorator(cls):
        existing = list(getattr(cls, "permission_classes", []))
        cls.permission_classes = [feature_flag_permission(flag_key)] + existing
        return cls
    return decorator


# ---------------------------------------------------------------------------
# Middleware-level auto-blocking (optional — registered in settings)
# ---------------------------------------------------------------------------

class FeatureFlagMiddleware:
    """
    Optional middleware that checks the URL prefix against FEATURE_MODULE_MAP
    and returns 403 before the view is even reached if the feature is disabled.

    Add AFTER TenantMiddleware and AuthenticationMiddleware in MIDDLEWARE list:
        "apps.core.feature_flags.FeatureFlagMiddleware",
    """
    _BLOCKED_RESPONSE_BODY = (
        b'{"success":false,"message":"This feature is not enabled for your organization."}'
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        flag_key = self._resolve_flag(request.path)
        user = getattr(request, "user", None)
        if flag_key and not getattr(user, "is_authenticated", False):
            return self.get_response(request)

        if flag_key and not is_feature_enabled(flag_key, request):
            from django.http import HttpResponse
            logger.info(
                "feature_flag.middleware_blocked",
                extra={
                    "event": "feature_flag.middleware_blocked",
                    "flag_key": flag_key,
                    "org_id": getattr(request, "org_id", None),
                    "path": request.path,
                },
            )
            return HttpResponse(
                self._BLOCKED_RESPONSE_BODY,
                content_type="application/json",
                status=403,
            )
        return self.get_response(request)

    @staticmethod
    def _resolve_flag(path: str):
        """Return the flag key matching the URL path, or None."""
        # Strip /api/v1/ prefix
        stripped = path.lstrip("/")
        for segment in ("api/v1/", "api/"):
            if stripped.startswith(segment):
                stripped = stripped[len(segment):]
                break
        for prefix, flag_key in FEATURE_MODULE_MAP.items():
            if stripped.startswith(prefix):
                return flag_key
        return None
