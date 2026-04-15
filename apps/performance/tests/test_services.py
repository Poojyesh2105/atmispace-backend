from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.performance.models import PerformanceCycle, PerformanceReview, RatingScale
from apps.performance.services.performance_service import PerformanceReviewService


class PerformanceReviewServiceTestCase(TestCase):
    def setUp(self):
        department = Department.objects.create(name="Engineering", code="ENG")
        self.hr_user = User.objects.create_user(email="hr@test.com", password="Hr@12345", first_name="HR", last_name="User", role=User.Role.HR)
        self.manager_user = User.objects.create_user(email="manager@test.com", password="Manager@123", first_name="Manager", last_name="User", role=User.Role.MANAGER)
        self.employee_user = User.objects.create_user(email="employee@test.com", password="Employee@123", first_name="Employee", last_name="User", role=User.Role.EMPLOYEE)
        self.manager = Employee.objects.create(user=self.manager_user, employee_id="EMP100", designation="Manager", department=department, hire_date=date.today())
        self.employee = Employee.objects.create(
            user=self.employee_user,
            employee_id="EMP101",
            designation="Engineer",
            department=department,
            manager=self.manager,
            hire_date=date.today(),
        )
        self.scale = RatingScale.objects.create(name="Standard", min_rating=Decimal("1.0"), max_rating=Decimal("5.0"))
        self.cycle = PerformanceCycle.objects.create(
            name="FY Review",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=60),
            self_review_due_date=date.today() + timedelta(days=10),
            manager_review_due_date=date.today() + timedelta(days=20),
            hr_review_due_date=date.today() + timedelta(days=30),
            rating_scale=self.scale,
            status=PerformanceCycle.Status.ACTIVE,
        )
        self.review = PerformanceReviewService.ensure_review(self.cycle, self.employee)

    def test_self_review_submission_moves_review_to_manager_pending(self):
        review = PerformanceReviewService.submit_self_review(
            self.employee_user,
            self.review,
            {"self_summary": "Delivered all goals", "self_rating": Decimal("4.5")},
        )
        self.assertEqual(review.status, PerformanceReview.Status.MANAGER_PENDING)
        self.assertEqual(review.manager_id, self.manager.pk)

