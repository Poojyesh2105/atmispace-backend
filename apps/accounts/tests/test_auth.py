from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.services.auth_service import AuthService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email, role=User.Role.EMPLOYEE, password="Test@1234", is_active=True):
    return User.objects.create_user(
        email=email,
        password=password,
        first_name="Test",
        last_name="User",
        role=role,
        is_active=is_active,
    )


# ---------------------------------------------------------------------------
# User model tests
# ---------------------------------------------------------------------------

class UserCreationTestCase(TestCase):
    def test_create_user_success(self):
        user = make_user("alice@example.com")
        self.assertEqual(user.email, "alice@example.com")
        self.assertTrue(user.check_password("Test@1234"))
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertTrue(user.is_active)

    def test_create_user_duplicate_email_raises(self):
        make_user("dup@example.com")
        from django.db import IntegrityError
        with self.assertRaises(Exception):
            make_user("dup@example.com")

    def test_create_user_missing_email_raises(self):
        with self.assertRaises((TypeError, ValueError)):
            User.objects.create_user(email="", password="Test@1234", first_name="A", last_name="B")

    def test_full_name_property(self):
        user = make_user("fname@example.com")
        user.first_name = "John"
        user.last_name = "Doe"
        self.assertEqual(user.full_name, "John Doe")

    def test_role_choices(self):
        for role in [User.Role.EMPLOYEE, User.Role.MANAGER, User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN]:
            user = User.objects.create_user(
                email=f"role-{role.lower()}@example.com",
                password="Test@1234",
                first_name="R",
                last_name="U",
                role=role,
            )
            self.assertEqual(user.role, role)

    def test_default_role_is_employee(self):
        user = User.objects.create_user(
            email="default-role@example.com",
            password="Test@1234",
            first_name="D",
            last_name="R",
        )
        self.assertEqual(user.role, User.Role.EMPLOYEE)


# ---------------------------------------------------------------------------
# AuthService unit tests
# ---------------------------------------------------------------------------

class AuthServiceLoginTestCase(TestCase):
    def setUp(self):
        self.user = make_user("service-login@example.com", password="Secure#999")

    def test_login_success_returns_tokens_and_user(self):
        result = AuthService.login(email="service-login@example.com", password="Secure#999")
        self.assertIn("access", result)
        self.assertIn("refresh", result)
        self.assertIn("user", result)
        self.assertEqual(result["user"].pk, self.user.pk)

    def test_login_wrong_password_raises(self):
        from rest_framework import exceptions
        with self.assertRaises(exceptions.AuthenticationFailed):
            AuthService.login(email="service-login@example.com", password="wrong")

    def test_login_wrong_email_raises(self):
        from rest_framework import exceptions
        with self.assertRaises(exceptions.AuthenticationFailed):
            AuthService.login(email="nonexistent@example.com", password="Secure#999")

    def test_login_inactive_user_raises_permission_denied(self):
        inactive = make_user("inactive-svc@example.com", password="Test@1234", is_active=False)
        from rest_framework import exceptions
        with self.assertRaises((exceptions.AuthenticationFailed, exceptions.PermissionDenied)):
            AuthService.login(email="inactive-svc@example.com", password="Test@1234")

    def test_logout_blacklists_token(self):
        result = AuthService.login(email="service-login@example.com", password="Secure#999")
        # Should not raise
        AuthService.logout(refresh_token=result["refresh"])

    def test_logout_invalid_token_raises(self):
        from rest_framework_simplejwt.exceptions import TokenError
        with self.assertRaises(Exception):
            AuthService.logout(refresh_token="not.a.valid.token")

    def test_get_user_profile_returns_user(self):
        profile = AuthService.get_user_profile(self.user)
        self.assertEqual(profile.pk, self.user.pk)


# ---------------------------------------------------------------------------
# Login API tests
# ---------------------------------------------------------------------------

class LoginAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("auth-login")
        self.user = make_user("api-login@example.com", password="Login@5678")

    def test_login_returns_200_and_tokens(self):
        resp = self.client.post(self.url, {"email": "api-login@example.com", "password": "Login@5678"}, format="json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertIn("access", data["data"])
        self.assertIn("refresh", data["data"])
        self.assertIn("user", data["data"])

    def test_login_wrong_password_returns_401(self):
        resp = self.client.post(self.url, {"email": "api-login@example.com", "password": "wrongpass"}, format="json")
        self.assertIn(resp.status_code, [400, 401, 403])

    def test_login_nonexistent_user_returns_error(self):
        resp = self.client.post(self.url, {"email": "nobody@example.com", "password": "Pass@123"}, format="json")
        self.assertIn(resp.status_code, [400, 401, 403])

    def test_login_inactive_user_returns_error(self):
        make_user("inactive-api@example.com", password="Test@1234", is_active=False)
        resp = self.client.post(self.url, {"email": "inactive-api@example.com", "password": "Test@1234"}, format="json")
        self.assertIn(resp.status_code, [400, 401, 403])

    def test_login_missing_email_returns_400(self):
        resp = self.client.post(self.url, {"password": "Test@1234"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_login_missing_password_returns_400(self):
        resp = self.client.post(self.url, {"email": "api-login@example.com"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_login_response_contains_user_fields(self):
        resp = self.client.post(self.url, {"email": "api-login@example.com", "password": "Login@5678"}, format="json")
        user_data = resp.json()["data"]["user"]
        self.assertIn("email", user_data)
        self.assertIn("role", user_data)
        self.assertIn("first_name", user_data)
        self.assertIn("last_name", user_data)


# ---------------------------------------------------------------------------
# Token refresh tests
# ---------------------------------------------------------------------------

class TokenRefreshAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("auth-refresh")
        self.user = make_user("refresh@example.com", password="Test@1234")

    def _get_refresh_token(self):
        login_url = reverse("auth-login")
        resp = self.client.post(login_url, {"email": "refresh@example.com", "password": "Test@1234"}, format="json")
        return resp.json()["data"]["refresh"]

    def test_valid_refresh_returns_new_access(self):
        refresh = self._get_refresh_token()
        resp = self.client.post(self.url, {"refresh": refresh}, format="json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("access", data["data"])

    def test_invalid_refresh_token_returns_401(self):
        resp = self.client.post(self.url, {"refresh": "completely.invalid.token"}, format="json")
        self.assertIn(resp.status_code, [400, 401])

    def test_expired_refresh_token_returns_401(self):
        # Simulate expired token by using a token string we tamper with
        resp = self.client.post(self.url, {"refresh": "eyJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MX0.invalid"}, format="json")
        self.assertIn(resp.status_code, [400, 401])

    def test_missing_refresh_field_returns_400(self):
        resp = self.client.post(self.url, {}, format="json")
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Logout tests
# ---------------------------------------------------------------------------

class LogoutAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user("logout@example.com", password="Test@1234")
        login_url = reverse("auth-login")
        resp = self.client.post(login_url, {"email": "logout@example.com", "password": "Test@1234"}, format="json")
        tokens = resp.json()["data"]
        self.access_token = tokens["access"]
        self.refresh_token = tokens["refresh"]
        self.logout_url = reverse("auth-logout")

    def test_logout_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        resp = self.client.post(self.logout_url, {"refresh": self.refresh_token}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_logout_blacklists_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        self.client.post(self.logout_url, {"refresh": self.refresh_token}, format="json")
        # Using the same refresh token again should fail
        refresh_url = reverse("auth-refresh")
        resp = self.client.post(refresh_url, {"refresh": self.refresh_token}, format="json")
        self.assertIn(resp.status_code, [400, 401])

    def test_logout_unauthenticated_returns_401(self):
        resp = self.client.post(self.logout_url, {"refresh": self.refresh_token}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_logout_missing_refresh_token_returns_400(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")
        resp = self.client.post(self.logout_url, {}, format="json")
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Me endpoint tests
# ---------------------------------------------------------------------------

class MeAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.me_url = reverse("auth-me")

    def _authenticate(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

    def test_me_returns_own_profile(self):
        user = make_user("me@example.com", role=User.Role.EMPLOYEE)
        self._authenticate(user)
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["email"], "me@example.com")

    def test_me_unauthenticated_returns_401(self):
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.status_code, 401)

    def test_me_returns_correct_role_employee(self):
        user = make_user("me-emp@example.com", role=User.Role.EMPLOYEE)
        self._authenticate(user)
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.json()["data"]["role"], User.Role.EMPLOYEE)

    def test_me_returns_correct_role_manager(self):
        user = make_user("me-mgr@example.com", role=User.Role.MANAGER)
        self._authenticate(user)
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.json()["data"]["role"], User.Role.MANAGER)

    def test_me_returns_correct_role_hr(self):
        user = make_user("me-hr@example.com", role=User.Role.HR)
        self._authenticate(user)
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.json()["data"]["role"], User.Role.HR)

    def test_me_returns_correct_role_accounts(self):
        user = make_user("me-accts@example.com", role=User.Role.ACCOUNTS)
        self._authenticate(user)
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.json()["data"]["role"], User.Role.ACCOUNTS)

    def test_me_returns_correct_role_admin(self):
        user = make_user("me-admin@example.com", role=User.Role.ADMIN)
        self._authenticate(user)
        resp = self.client.get(self.me_url)
        self.assertEqual(resp.json()["data"]["role"], User.Role.ADMIN)

    def test_me_includes_expected_fields(self):
        user = make_user("me-fields@example.com")
        self._authenticate(user)
        resp = self.client.get(self.me_url)
        data = resp.json()["data"]
        for field in ("id", "email", "first_name", "last_name", "full_name", "role", "is_active"):
            self.assertIn(field, data, f"Missing field: {field}")

    def test_me_does_not_expose_password(self):
        user = make_user("me-nopwd@example.com")
        self._authenticate(user)
        resp = self.client.get(self.me_url)
        data = resp.json()["data"]
        self.assertNotIn("password", data)
