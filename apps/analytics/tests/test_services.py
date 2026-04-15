from datetime import date

from django.test import TestCase

from apps.accounts.models import User
from apps.analytics.services.analytics_service import AnalyticsService
from apps.employees.models import Department, Employee


class AnalyticsServiceTestCase(TestCase):
    def setUp(self):
        department = Department.objects.create(name="Analytics", code="ANL")
        self.admin = User.objects.create_user(
            email="analytics-admin@test.com",
            password="Admin@123",
            first_name="Analytics",
            last_name="Admin",
            role=User.Role.ADMIN,
        )
        Employee.objects.create(
            user=self.admin,
            employee_id="EMP-ANL",
            designation="Admin",
            department=department,
            hire_date=date.today(),
        )

    def test_dashboard_returns_cards(self):
        payload = AnalyticsService.get_dashboard(self.admin)
        self.assertIn("cards", payload)

