import logging
import time
import uuid

from django.core.cache import cache

from apps.core.logging import clear_request_context, set_request_context
from apps.core.metrics import MetricsService


request_logger = logging.getLogger("atmispace.request")
tenant_logger = logging.getLogger("atmispace.tenant")

# ---------------------------------------------------------------------------
# Tenant Middleware
# ---------------------------------------------------------------------------
_ORG_CACHE_TTL = 60  # seconds


class TenantMiddleware:
    """
    Resolves the current Organization for every request and attaches it to
    ``request.organization`` and ``request.org_id``.

    Resolution order (first match wins):
      1. ``X-Organization-ID`` header  — explicit org ID sent by the frontend
      2. Subdomain   — e.g. ``acme.atmispace.com`` → org with subdomain="acme"
      3. Custom domain — ``Host`` header matched against Organization.domain
      4. Authenticated user's primary org membership
      5. The platform default org (is_default=True)

    SUPER_ADMIN users are exempt from tenant isolation — they can operate
    across all orgs and we do NOT force an org onto their request.
    """

    # Paths that don't need tenant resolution (auth, health, admin)
    _EXEMPT_PREFIXES = ("/admin/", "/api/v1/auth/", "/api/v1/platform/health/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._authenticate_jwt_user(request)
        self._resolve_tenant(request)
        return self.get_response(request)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_tenant(self, request):
        # Always set a safe default so downstream code never AttributeErrors
        request.organization = None
        request.org_id = None

        if self._is_exempt(request):
            return

        org = (
            self._from_header(request)
            or self._from_subdomain(request)
            or self._from_custom_domain(request)
            or self._from_user(request)
        )

        user = getattr(request, "user", None)
        if org is None and not getattr(user, "is_authenticated", False):
            org = self._from_default()

        if org is not None:
            request.organization = org
            request.org_id = org.pk
            tenant_logger.debug(
                "tenant.resolved",
                extra={"org_id": org.pk, "org_name": org.name, "path": request.path},
            )

    def _is_exempt(self, request) -> bool:
        return any(request.path.startswith(p) for p in self._EXEMPT_PREFIXES)

    @staticmethod
    def _authenticate_jwt_user(request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return

        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication

            result = JWTAuthentication().authenticate(request)
        except Exception:
            return

        if result is None:
            return

        request.user, request.auth = result
        request._cached_user = request.user

    @staticmethod
    def _get_org_by_id(org_id):
        cache_key = f"org:id:{org_id}"
        org = cache.get(cache_key)
        if org is None:
            from apps.core.models import Organization
            org = Organization.objects.filter(pk=org_id, is_active=True).first()
            if org:
                cache.set(cache_key, org, _ORG_CACHE_TTL)
        return org

    @staticmethod
    def _get_org_by_subdomain(subdomain):
        if not subdomain:
            return None
        cache_key = f"org:subdomain:{subdomain}"
        org = cache.get(cache_key)
        if org is None:
            from apps.core.models import Organization
            org = Organization.objects.filter(subdomain=subdomain, is_active=True).first()
            if org:
                cache.set(cache_key, org, _ORG_CACHE_TTL)
        return org

    @staticmethod
    def _get_org_by_domain(domain):
        if not domain:
            return None
        cache_key = f"org:domain:{domain}"
        org = cache.get(cache_key)
        if org is None:
            from apps.core.models import Organization
            org = Organization.objects.filter(domain=domain, is_active=True).first()
            if org:
                cache.set(cache_key, org, _ORG_CACHE_TTL)
        return org

    @staticmethod
    def _from_header(request):
        raw = request.headers.get("X-Organization-ID", "").strip()
        if raw and raw.isdigit():
            return TenantMiddleware._get_org_by_id(int(raw))
        return None

    @staticmethod
    def _from_subdomain(request):
        host = request.headers.get("Host", "").split(":")[0].lower()
        # Match <subdomain>.atmispace.com or <subdomain>.atmispace.local etc.
        parts = host.split(".")
        if len(parts) >= 3:
            subdomain = parts[0]
            return TenantMiddleware._get_org_by_subdomain(subdomain)
        return None

    @staticmethod
    def _from_custom_domain(request):
        host = request.headers.get("Host", "").split(":")[0].lower()
        return TenantMiddleware._get_org_by_domain(host)

    @staticmethod
    def _from_user(request):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None
        # SUPER_ADMIN: don't force an org, they operate cross-org
        if getattr(user, "role", None) == "SUPER_ADMIN":
            return None
        # Direct FK on user is the canonical org for single-org admins.
        org_id = getattr(user, "organization_id", None)
        if org_id:
            return TenantMiddleware._get_org_by_id(org_id)
        # Try OrganizationMembership primary org first (V3 path)
        try:
            membership = (
                user.org_memberships.filter(is_active=True)
                .select_related("organization")
                .order_by("-is_primary", "id")
                .first()
            )
            if membership:
                return membership.organization
        except Exception:
            pass
        return None

    @staticmethod
    def _from_default():
        from apps.core.models import get_default_organization
        return get_default_organization()


class RequestContextLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.request_id = request_id
        response = None

        try:
            response = self.get_response(request)
            return response
        finally:
            user = getattr(request, "user", None)
            module = self._resolve_module(request.path)
            action = f"{request.method} {module}"
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            status_code = getattr(response, "status_code", 500)
            organization_id = getattr(user, "organization_id", None) if getattr(user, "is_authenticated", False) else None

            set_request_context(
                request_id=request_id,
                user_id=getattr(user, "pk", None) if getattr(user, "is_authenticated", False) else None,
                role=getattr(user, "role", None) if getattr(user, "is_authenticated", False) else None,
                organization_id=organization_id,
            )
            MetricsService.record_api_request(
                module=module,
                action=request.method,
                status_code=status_code,
                duration_ms=duration_ms,
                organization_id=organization_id,
            )
            request_logger.info(
                "request.complete",
                extra={
                    "event": "request.complete",
                    "module_name": module,
                    "action": action,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "method": request.method,
                    "path": request.path,
                },
            )
            clear_request_context()

    @staticmethod
    def _resolve_module(path):
        parts = [part for part in path.strip("/").split("/") if part]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
            return parts[2]
        return parts[0] if parts else "root"
