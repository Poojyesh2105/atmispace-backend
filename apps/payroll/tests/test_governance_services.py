from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.payroll.models import PayrollCycle
from apps.payroll.services.payroll_governance_service import PayrollGovernanceService


class PayrollGovernanceServiceTestCase(TestCase):
    def setUp(self):
        department = Department.objects.create(name="Finance", code="FIN")
        self.accounts_user = User.objects.create_user(email="accounts-pay@test.com", password="Accounts@123", first_name="Accounts", last_name="User", role=User.Role.ACCOUNTS)
        employee_user = User.objects.create_user(email="employee-pay@test.com", password="Employee@123", first_name="Employee", last_name="User", role=User.Role.EMPLOYEE)
        self.employee = Employee.objects.create(
            user=employee_user,
            employee_id="EMP400",
            designation="Associate",
            department=department,
            hire_date=date.today(),
            ctc_per_annum=Decimal("600000.00"),
        )
        self.cycle = PayrollCycle.objects.create(
            name="Apr 2026",
            payroll_month=date(2026, 4, 1),
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )

    def test_generate_run_creates_payroll_run(self):
        run = PayrollGovernanceService.generate_run(self.accounts_user, self.cycle)
        self.assertEqual(run.total_employees, 1)
        self.assertEqual(run.status, run.Status.DRAFT)

    def test_generate_run_skips_employee_without_ctc(self):
        skipped_user = User.objects.create_user(
            email="employee-nocost@test.com",
            password="Employee@123",
            first_name="No",
            last_name="Compensation",
            role=User.Role.EMPLOYEE,
        )
        Employee.objects.create(
            user=skipped_user,
            employee_id="EMP401",
            designation="Contractor",
            department=self.employee.department,
            hire_date=date.today(),
            ctc_per_annum=Decimal("0.00"),
        )

        run = PayrollGovernanceService.generate_run(self.accounts_user, self.cycle)

        self.assertEqual(run.total_employees, 1)
        self.assertIn("EMP401", run.notes)
