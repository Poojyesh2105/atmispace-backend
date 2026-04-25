import logging

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.views import exception_handler

security_logger = logging.getLogger("atmispace.security")


def _extract_validation_message(payload):
    if isinstance(payload, list) and payload:
        first = payload[0]
        return str(first)
    if isinstance(payload, dict):
        for value in payload.values():
            message = _extract_validation_message(value)
            if message:
                return message
    if isinstance(payload, str):
        return payload
    return None


# Safe, generic messages that don't leak implementation details
_SAFE_MESSAGES = {
    status.HTTP_400_BAD_REQUEST: "The request could not be processed. Please check your input.",
    status.HTTP_401_UNAUTHORIZED: "Authentication credentials were invalid or missing.",
    status.HTTP_403_FORBIDDEN: "You do not have permission to perform this action.",
    status.HTTP_404_NOT_FOUND: "The requested resource was not found.",
    status.HTTP_405_METHOD_NOT_ALLOWED: "This method is not allowed.",
    status.HTTP_429_TOO_MANY_REQUESTS: "Too many requests. Please slow down and try again later.",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "An unexpected error occurred. Please try again later.",
}


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    # Determine a user-safe message
    if isinstance(exc, ValidationError):
        # Validation errors are safe to surface — they come from our own serializers
        message = _extract_validation_message(response.data) or "Validation failed."
    elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        message = _SAFE_MESSAGES[status.HTTP_401_UNAUTHORIZED]
    elif isinstance(exc, PermissionDenied):
        message = _SAFE_MESSAGES[status.HTTP_403_FORBIDDEN]
    elif isinstance(exc, Throttled):
        wait = exc.wait
        if wait is not None:
            message = f"Too many requests. Please try again in {int(wait)} second{'s' if wait != 1 else ''}."
        else:
            message = _SAFE_MESSAGES[status.HTTP_429_TOO_MANY_REQUESTS]
    else:
        # For everything else, use the safe fallback — do NOT echo internal detail strings
        message = _SAFE_MESSAGES.get(response.status_code, "Request failed.")

    # Log 5xx as errors with context (for alerting), 4xx as warnings
    request = context.get("request")
    view = context.get("view")
    log_extra = {
        "status_code": response.status_code,
        "exc_type": type(exc).__name__,
        "view": type(view).__name__ if view else None,
        "user_id": getattr(getattr(request, "user", None), "pk", None),
        "org_id": getattr(getattr(request, "organization", None), "pk", None),
        "path": getattr(getattr(request, "_request", request), "path", None),
    }
    if response.status_code >= 500:
        security_logger.error("api.5xx_error", extra=log_extra, exc_info=True)
    elif response.status_code in (401, 403):
        security_logger.warning("api.auth_error", extra=log_extra)

    response.data = {
        "success": False,
        "message": message,
        "data": None,
    }
    return response
