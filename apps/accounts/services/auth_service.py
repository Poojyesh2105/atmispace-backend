from django.contrib.auth import authenticate
from rest_framework import exceptions
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User


class AuthService:
    @staticmethod
    def login(*, email: str, password: str):
        user = authenticate(email=email, password=password)
        if not user:
            raise exceptions.AuthenticationFailed("Invalid email or password.")
        if not user.is_active:
            raise exceptions.PermissionDenied("This user account is inactive.")

        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user,
        }

    @staticmethod
    def logout(*, refresh_token: str):
        token = RefreshToken(refresh_token)
        token.blacklist()

    @staticmethod
    def get_user_profile(user: User):
        return user

