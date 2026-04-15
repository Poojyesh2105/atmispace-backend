from datetime import date, timedelta

from django.test import TestCase

from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.lifecycle.models import OnboardingPlan, OnboardingTaskTemplate
from apps.lifecycle.services.lifecycle_service import EmployeeOnboardingService


class EmployeeOnboardingServiceTestCase(TestCase):
    def setUp(self):
        department = Department.objects.create(name="Operations", code="OPS")
        self.hr_user = User.objects.create_user(email="hr-life@test.com", password="Hr@12345", first_name="HR", last_name="User", role=User.Role.HR)
        self.employee_user = User.objects.create_user(email="employee-life@test.com", password="Employee@123", first_name="Employee", last_name="User", role=User.Role.EMPLOYEE)
        self.employee = Employee.objects.create(
            user=self.employee_user,
            employee_id="EMP300",
            designation="Coordinator",
            department=department,
            hire_date=date.today(),
        )
        self.plan = OnboardingPlan.objects.create(name="Default Plan", default_duration_days=10)
        OnboardingTaskTemplate.objects.create(plan=self.plan, title="Upload identity proof", owner_role=User.Role.EMPLOYEE, task_type=OnboardingTaskTemplate.TaskType.DOCUMENT, sequence=1)

    def test_create_onboarding_generates_tasks(self):
        onboarding = EmployeeOnboardingService.create_onboarding(
            {
                "employee": self.employee,
                "plan": self.plan,
                "start_date": date.today(),
                "due_date": date.today() + timedelta(days=10),
                "notes": "",
            },
            actor=self.hr_user,
        )
        self.assertEqual(onboarding.tasks.count(), 1)
        self.assertEqual(onboarding.status, onboarding.Status.IN_PROGRESS)

