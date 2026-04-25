"""
Custom DRF throttle classes for Atmispace.

Hierarchy:
  - AuthBurstThrottle        — login / token endpoints, tight burst limit
  - AuthSustainedThrottle    — login / token endpoints, hourly cap
  - PlatformBurstThrottle    — /platform/* SUPER_ADMIN endpoints, burst
  - PlatformSustainedThrottle — /platform/* SUPER_ADMIN endpoints, daily cap
  - OrgApiThrottle           — standard org-scoped API calls, per-user
  - OrgApiAnonThrottle       — anonymous/unauthenticated org API calls

Rate strings follow DRF convention: "<count>/<period>" where period is
one of: second, minute, hour, day.
"""

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle


class AuthBurstThrottle(SimpleRateThrottle):
    """
    Tight burst limit on auth endpoints (login, token refresh).
    Keyed by IP address so it applies even before a user is authenticated.
    """
    scope = "auth_burst"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class AuthSustainedThrottle(SimpleRateThrottle):
    """Hourly sustained limit on auth endpoints, keyed by IP."""
    scope = "auth_sustained"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class PlatformBurstThrottle(UserRateThrottle):
    """
    Burst limit on /platform/* endpoints.
    Keyed by authenticated user so SUPER_ADMIN burst is tracked per-user.
    """
    scope = "platform_burst"


class PlatformSustainedThrottle(UserRateThrottle):
    """Daily cap on /platform/* endpoints per SUPER_ADMIN user."""
    scope = "platform_sustained"


class OrgApiThrottle(UserRateThrottle):
    """Standard per-user rate limit for org-scoped API views."""
    scope = "org_api"


class OrgApiAnonThrottle(AnonRateThrottle):
    """Rate limit for anonymous / pre-auth requests to org API endpoints."""
    scope = "org_api_anon"
