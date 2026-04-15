from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from apps.accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_active",
            "date_joined",
        )
        read_only_fields = ("id", "date_joined")


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class TokenRefreshRequestSerializer(TokenRefreshSerializer):
    pass

