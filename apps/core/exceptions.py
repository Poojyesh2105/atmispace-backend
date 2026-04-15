from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler


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


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    if isinstance(exc, ValidationError):
        message = _extract_validation_message(response.data) or "Validation failed."
    else:
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        message = detail if isinstance(detail, str) else "Request failed."

    response.data = {
        "success": False,
        "message": message,
        "data": response.data if isinstance(response.data, dict) else {},
    }
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        response.data["message"] = "Authentication credentials were invalid or missing."
    return response
