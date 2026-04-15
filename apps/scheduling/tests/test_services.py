from datetime import date

from django.test import TestCase

from apps.accounts.models import User
from apps.employees.models import Department, Employee, ShiftTemplate
from apps.scheduling.services.scheduling_service import SchedulingService


class SchedulingServiceTestCase(TestCase):
    def setUp(self):
        department = Department.objects.create(name="Operations", code="OPS2")
        self.manager_user = User.objects.create_user(email="manager-schedule@test.com", password="Manager@123", first_name="Manager", last_name="User", role=User.Role.MANAGER)
        employee_user = User.objects.create_user(email="employee-schedule@test.com", password="Employee@123", first_name="Employee", last_name="User", role=User.Role.EMPLOYEE)
        self.manager = Employee.objects.create(user=self.manager_user, employee_id="EMP500", designation="Manager", department=department, hire_date=date.today())
        self.employee = Employee.objects.create(user=employee_user, employee_id="EMP501", designation="Associate", department=department, manager=self.manager, hire_date=date.today())
        self.shift = ShiftTemplate.objects.create(name="Morning Test", start_time="09:00", end_time="18:00")

    def test_assign_shift_creates_roster_entry(self):
        entry = SchedulingService.assign_shift(self.employee, date.today(), self.shift, self.manager_user)
        self.assertEqual(entry.employee_id, self.employee.pk)
        self.assertEqual(entry.shift_template_id, self.shift.pk)

