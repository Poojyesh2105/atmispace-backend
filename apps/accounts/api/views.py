from rest_framework import serializers as drf_serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.serializers import (
    LoginSerializer,
    LogoutSerializer,
    TokenRefreshRequestSerializer,
    UserSerializer,
)
from apps.accounts.services.auth_service import AuthService
from apps.core.responses import success_response


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = AuthService.login(**serializer.validated_data)
        return success_response(
            data={
                "access": payload["access"],
                "refresh": payload["refresh"],
                "user": UserSerializer(payload["user"]).data,
            },
            message="Login successful.",
        )


class RefreshTokenView(TokenRefreshView):
    permission_classes = [AllowAny]
    serializer_class = TokenRefreshRequestSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.data = {
            "success": True,
            "message": "Token refreshed.",
            "data": response.data,
        }
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.logout(refresh_token=serializer.validated_data["refresh"])
        return success_response(message="Logout successful.")


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = AuthService.get_user_profile(request.user)
        return success_response(data=UserSerializer(user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        new_password = request.data.get("new_password", "")
        current_password = request.data.get("current_password", "")

        if not new_password:
            raise drf_serializers.ValidationError({"new_password": "This field is required."})

        if not user.force_password_reset:
            if not current_password:
                raise drf_serializers.ValidationError({"current_password": "This field is required."})
            if not user.check_password(current_password):
                raise drf_serializers.ValidationError({"current_password": "Current password is incorrect."})

        user.set_password(new_password)
        user.force_password_reset = False
        user.save(update_fields=["password", "force_password_reset"])
        return success_response(message="Password changed successfully.")

