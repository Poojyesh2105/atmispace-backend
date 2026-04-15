from datetime import date

from django.test import TestCase

from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.helpdesk.models import HelpdeskCategory
from apps.helpdesk.services.helpdesk_service import HelpdeskService


class HelpdeskServiceTestCase(TestCase):
    def setUp(self):
        department = Department.objects.create(name="Support", code="SUP")
        self.employee_user = User.objects.create_user(
            email="helpdesk-employee@test.com",
            password="Employee@123",
            first_name="Helpdesk",
            last_name="Employee",
            role=User.Role.EMPLOYEE,
        )
        self.hr_user = User.objects.create_user(
            email="helpdesk-hr@test.com",
            password="Hr@12345",
            first_name="Helpdesk",
            last_name="HR",
            role=User.Role.HR,
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            employee_id="EMP-HLP",
            designation="Associate",
            department=department,
            hire_date=date.today(),
        )
        self.category = HelpdeskCategory.objects.create(name="HR Query", owner_role=User.Role.HR)

    def test_create_ticket_assigns_owner_role(self):
        ticket = HelpdeskService.create_ticket(
            {
                "requester": self.employee,
                "category": self.category,
                "subject": "Letter request",
                "description": "Need an employment letter.",
            },
            actor=self.employee_user,
        )
        self.assertEqual(ticket.assigned_role, User.Role.HR)

