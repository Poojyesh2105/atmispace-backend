from rest_framework import status
from rest_framework.response import Response


def success_response(data=None, message="", status_code=status.HTTP_200_OK):
    return Response({"success": True, "message": message, "data": data or {}}, status=status_code)


def error_response(message="", data=None, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "message": message, "data": data or {}}, status=status_code)

