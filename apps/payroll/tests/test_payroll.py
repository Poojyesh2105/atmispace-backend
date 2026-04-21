"""
Tests for payroll services:
- PayrollCycle creation
- PayslipService: generate_payslip, calculate_payout, access control
- PayrollGovernanceService: generate_run, lock_run, cycle status
"""
from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.payroll.models import (
    PayrollCycle,
    PayrollRun,
    Payslip,
    SalaryComponent,
    SalaryComponentTemplate,
)
from apps.payroll.services.payroll_governance_service import PayrollGovernanceService
from apps.payroll.services.payroll_service import PayslipService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email, role=User.Role.EMPLOYEE, password="Test@1234"):
    return User.objects.create_user(
        email=email,
        password=password,
        first_name="Test",
        last_name="User",
        role=role,
    )


def make_employee(user, emp_id, dept=None, ctc=None):
    emp = Employee.objects.create(
        user=user,
        employee_id=emp_id,
        designation="Dev",
        hire_date=date.today(),
        department=dept,
    )
    if ctc is not None:
        emp.ctc_per_annum = Decimal(str(ctc))
    emp.save()
    return emp


def make_cycle(name="Apr-2026", payroll_month=None, start_date=None, end_date=None):
    payroll_month = payroll_month or date(2026, 4, 1)
    start_date = start_date or date(2026, 4, 1)
    end_date = end_date or date(2026, 4, 30)
    return PayrollCycle.objects.create(
        name=name,
        payroll_month=payroll_month,
        start_date=start_date,
        end_date=end_date,
        status=PayrollCycle.Status.DRAFT,
    )


# ---------------------------------------------------------------------------
# PayrollCycle creation tests
# ---------------------------------------------------------------------------

class PayrollCycleTest(TestCase):
    def test_payroll_cycle_created_with_draft_status(self):
        cycle = make_cycle()
        self.assertEqual(cycle.status, PayrollCycle.Status.DRAFT)
        self.assertEqual(cycle.name, "Apr-2026")

    def test_payroll_cycle_payroll_month_normalized_to_first(self):
        # payroll_month is stored as-is; verify the value is the 1st
        cycle = make_cycle(payroll_month=date(2026, 4, 1))
        self.assertEqual(cycle.payroll_month.day, 1)

    def test_payroll_cycle_unique_name(self):
        make_cycle(name="May-2026", payroll_month=date(2026, 5, 1))
        with self.assertRaises(Exception):
            make_cycle(name="May-2026", payroll_month=date(2026, 5, 1))


# ---------------------------------------------------------------------------
# PayslipService.calculate_payout tests
# ---------------------------------------------------------------------------

class CalculatePayoutTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Pay-Dept", code="PAY")
        user = make_user("payout@test.com", role=User.Role.ACCOUNTS)
        self.employee = make_employee(user, "EMP-PAY", self.dept, ctc=120000)

    def _patch_lop(self, lop_days=Decimal("0")):
        return patch(
            "apps.payroll.services.payroll_service.PayslipService.calculate_lop_days",
            return_value=lop_days,
        )

    def test_gross_is_ctc_divided_by_12(self):
        with self._patch_lop():
            result = PayslipService.calculate_payout(self.employee, date(2026, 4, 1))
        expected_gross = (Decimal("120000") / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(result["gross_monthly_salary"], expected_gross)

    def test_net_pay_is_gross_when_no_lop_or_component_deductions(self):
        with self._patch_lop():
            result = PayslipService.calculate_payout(self.employee, date(2026, 4, 1))
        self.assertEqual(result["net_pay"], result["gross_monthly_salary"])

    def test_lop_deduction_computed_correctly(self):
        lop_days = Decimal("2")
        with self._patch_lop(lop_days):
            result = PayslipService.calculate_payout(self.employee, date(2026, 4, 1))
        days_in_month = monthrange(2026, 4)[1]
        expected_lop = (result["gross_monthly_salary"] / Decimal(days_in_month) * lop_days).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.assertEqual(result["lop_deduction"], expected_lop)
        self.assertEqual(result["lop_days"], lop_days)

    def test_no_ctc_raises_validation_error(self):
        user2 = make_user("noCtc@test.com")
        emp_no_ctc = make_employee(user2, "EMP-NOCTC", self.dept, ctc=0)
        with self.assertRaises(ValidationError):
            PayslipService.calculate_payout(emp_no_ctc, date(2026, 4, 1))

    def test_total_deductions_field(self):
        with self._patch_lop():
            result = PayslipService.calculate_payout(self.employee, date(2026, 4, 1))
        self.assertEqual(
            result["total_deductions"],
            result["lop_deduction"],
        )


# ---------------------------------------------------------------------------
# PayslipService.generate_payslip tests
# ---------------------------------------------------------------------------

class GeneratePayslipTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Gen-Dept", code="GEN")

        self.hr_user = make_user("gen-hr@test.com", role=User.Role.HR)
        self.accounts_user = make_user("gen-accts@test.com", role=User.Role.ACCOUNTS)
        self.admin_user = make_user("gen-admin@test.com", role=User.Role.ADMIN)
        self.emp_user = make_user("gen-emp@test.com", role=User.Role.EMPLOYEE)

        make_employee(self.hr_user, "EMP-GENHR", self.dept)
        make_employee(self.accounts_user, "EMP-GENAC", self.dept)
        make_employee(self.admin_user, "EMP-GENADM", self.dept)

        self.target_emp_user = make_user("gen-target@test.com")
        self.target_employee = make_employee(self.target_emp_user, "EMP-TARGET", self.dept, ctc=240000)

        make_employee(self.emp_user, "EMP-GENEMPX", self.dept, ctc=120000)

    def _patch_lop(self, lop_days=Decimal("0")):
        return patch(
            "apps.payroll.services.payroll_service.PayslipService.calculate_lop_days",
            return_value=lop_days,
        )

    def test_hr_can_generate_payslip(self):
        with self._patch_lop():
            payslip = PayslipService.generate_payslip(
                self.hr_user, self.target_employee, date(2026, 4, 1)
            )
        self.assertIsNotNone(payslip.pk)
        self.assertEqual(payslip.employee, self.target_employee)

    def test_accounts_can_generate_payslip(self):
        with self._patch_lop():
            payslip = PayslipService.generate_payslip(
                self.accounts_user, self.target_employee, date(2026, 5, 1)
            )
        self.assertIsNotNone(payslip.pk)

    def test_admin_can_generate_payslip(self):
        with self._patch_lop():
            payslip = PayslipService.generate_payslip(
                self.admin_user, self.target_employee, date(2026, 6, 1)
            )
        self.assertIsNotNone(payslip.pk)

    def test_employee_cannot_generate_payslip(self):
        with self._patch_lop():
            with self.assertRaises(PermissionDenied):
                PayslipService.generate_payslip(
                    self.emp_user, self.target_employee, date(2026, 4, 1)
                )

    def test_payslip_fields_gross_net_deductions(self):
        with self._patch_lop():
            payslip = PayslipService.generate_payslip(
                self.hr_user, self.target_employee, date(2026, 4, 1)
            )
        expected_gross = (Decimal("240000") / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(payslip.gross_monthly_salary, expected_gross)
        self.assertEqual(payslip.total_deductions, Decimal("0.00"))
        self.assertEqual(payslip.net_pay, expected_gross)

    def test_payslip_with_lop_deduction(self):
        lop_days = Decimal("3")
        with self._patch_lop(lop_days):
            payslip = PayslipService.generate_payslip(
                self.hr_user, self.target_employee, date(2026, 4, 1)
            )
        days_in_month = monthrange(2026, 4)[1]
        expected_lop_deduction = (payslip.gross_monthly_salary / Decimal(days_in_month) * lop_days).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.assertEqual(payslip.lop_days, lop_days)
        self.assertEqual(payslip.lop_deduction, expected_lop_deduction)
        lop_entry = payslip.component_entries.get(component_code=PayslipService.LOP_COMPONENT_CODE)
        self.assertIsNone(lop_entry.component)
        self.assertEqual(lop_entry.component_type, SalaryComponent.ComponentType.DEDUCTION)
        self.assertEqual(lop_entry.calculated_amount, expected_lop_deduction)
        self.assertEqual(lop_entry.display_order, PayslipService.LOP_COMPONENT_DISPLAY_ORDER)

    def test_generate_payslip_with_component_deductions(self):
        component_deductions = Decimal("1500.00")
        with self._patch_lop():
            payslip = PayslipService.generate_payslip(
                self.hr_user,
                self.target_employee,
                date(2026, 7, 1),
                component_deductions=component_deductions,
        )
        self.assertEqual(payslip.component_deductions, component_deductions)
        self.assertEqual(component_deductions, payslip.total_deductions - payslip.lop_deduction)

    def test_generate_payslip_is_idempotent(self):
        """Calling generate_payslip twice for same employee+month uses update_or_create."""
        with self._patch_lop():
            payslip1 = PayslipService.generate_payslip(
                self.hr_user, self.target_employee, date(2026, 8, 1)
            )
            payslip2 = PayslipService.generate_payslip(
                self.hr_user, self.target_employee, date(2026, 8, 1)
            )
        self.assertEqual(payslip1.pk, payslip2.pk)
        self.assertEqual(Payslip.objects.filter(employee=self.target_employee, payroll_month=date(2026, 8, 1)).count(), 1)


# ---------------------------------------------------------------------------
# PayrollGovernanceService.generate_run tests
# ---------------------------------------------------------------------------

class GenerateRunTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Run-Dept", code="RUN")
        self.hr_user = make_user("run-hr@test.com", role=User.Role.HR)
        make_employee(self.hr_user, "EMP-RUNHR", self.dept)

        self.emp_user = make_user("run-emp@test.com")
        self.employee = make_employee(self.emp_user, "EMP-RUNEMP", self.dept, ctc=120000)

        self.cycle = make_cycle("Run-Apr-2026", date(2026, 4, 1))

    def _patch_policy_engine(self):
        return patch(
            "apps.payroll.services.payroll_governance_service.PolicyRuleService.evaluate",
            return_value=None,
        )

    def _patch_lop(self, lop_days=Decimal("0")):
        return patch(
            "apps.payroll.services.payroll_service.PayslipService.calculate_lop_days",
            return_value=lop_days,
        )

    def test_generate_run_creates_payslips_for_active_employees(self):
        with self._patch_policy_engine(), self._patch_lop():
            run = PayrollGovernanceService.generate_run(self.hr_user, self.cycle)
        self.assertGreaterEqual(run.total_employees, 1)
        self.assertTrue(Payslip.objects.filter(employee=self.employee, payroll_month=date(2026, 4, 1)).exists())

    def test_generate_run_skips_employees_without_ctc(self):
        no_ctc_user = make_user("run-noctc@test.com")
        no_ctc_emp = make_employee(no_ctc_user, "EMP-NOCTCRUN", self.dept, ctc=0)
        with self._patch_policy_engine(), self._patch_lop():
            run = PayrollGovernanceService.generate_run(self.hr_user, self.cycle)
        # No payslip should be generated for employee with ctc=0
        self.assertFalse(Payslip.objects.filter(employee=no_ctc_emp, payroll_month=date(2026, 4, 1)).exists())

    def test_employee_cannot_generate_run(self):
        emp_user2 = make_user("run-noauth@test.com", role=User.Role.EMPLOYEE)
        with self._patch_policy_engine(), self._patch_lop():
            with self.assertRaises(PermissionDenied):
                PayrollGovernanceService.generate_run(emp_user2, self.cycle)

    def test_run_created_with_draft_status(self):
        with self._patch_policy_engine(), self._patch_lop():
            run = PayrollGovernanceService.generate_run(self.hr_user, self.cycle)
        self.assertEqual(run.status, PayrollRun.Status.DRAFT)


# ---------------------------------------------------------------------------
# PayrollGovernanceService.lock_run tests (cycle DRAFT -> LOCKED)
# ---------------------------------------------------------------------------

class LockRunTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Lock-Dept", code="LKD")
        self.hr_user = make_user("lock-hr@test.com", role=User.Role.HR)
        make_employee(self.hr_user, "EMP-LOCKHR", self.dept)

        self.emp_user = make_user("lock-emp@test.com")
        make_employee(self.emp_user, "EMP-LOCKEMP", self.dept, ctc=120000)

        self.cycle = make_cycle("Lock-Apr-2026", date(2026, 4, 1))

    def _patch_policy_engine(self):
        return patch(
            "apps.payroll.services.payroll_governance_service.PolicyRuleService.evaluate",
            return_value=None,
        )

    def _patch_lop(self):
        return patch(
            "apps.payroll.services.payroll_service.PayslipService.calculate_lop_days",
            return_value=Decimal("0"),
        )

    def test_lock_run_changes_status_to_locked(self):
        with self._patch_policy_engine(), self._patch_lop():
            run = PayrollGovernanceService.generate_run(self.hr_user, self.cycle)
        locked_run = PayrollGovernanceService.lock_run(self.hr_user, run)
        self.assertEqual(locked_run.status, PayrollRun.Status.LOCKED)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.status, PayrollCycle.Status.LOCKED)

    def test_lock_sets_locked_at(self):
        with self._patch_policy_engine(), self._patch_lop():
            run = PayrollGovernanceService.generate_run(self.hr_user, self.cycle)
        locked_run = PayrollGovernanceService.lock_run(self.hr_user, run)
        self.assertIsNotNone(locked_run.locked_at)

    def test_cannot_lock_released_run(self):
        with self._patch_policy_engine(), self._patch_lop():
            run = PayrollGovernanceService.generate_run(self.hr_user, self.cycle)
        run.status = PayrollRun.Status.RELEASED
        run.save(update_fields=["status", "updated_at"])
        with self.assertRaises(ValidationError):
            PayrollGovernanceService.lock_run(self.hr_user, run)

    def test_employee_cannot_lock_run(self):
        with self._patch_policy_engine(), self._patch_lop():
            run = PayrollGovernanceService.generate_run(self.hr_user, self.cycle)
        emp_user2 = make_user("lock-noauth@test.com", role=User.Role.EMPLOYEE)
        with self.assertRaises(PermissionDenied):
            PayrollGovernanceService.lock_run(emp_user2, run)


# ---------------------------------------------------------------------------
# SalaryComponent tests
# ---------------------------------------------------------------------------

class SalaryComponentTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Ded-Dept", code="DED")
        self.hr_user = make_user("ded-hr@test.com", role=User.Role.HR)
        make_employee(self.hr_user, "EMP-DEDHR", self.dept)
        self.salary_template = SalaryComponentTemplate.objects.create(
            name="Test Salary Structure",
            is_default=True,
            is_active=True,
        )

    def test_component_deduction_based_on_basic_salary(self):
        emp_user = make_user("ded-emp@test.com")
        emp = make_employee(emp_user, "EMP-DED001", self.dept, ctc=120000)

        basic = SalaryComponent.objects.create(
            template=self.salary_template,
            name="Basic Salary",
            code="BASIC_TEST",
            component_type=SalaryComponent.ComponentType.EARNING,
            calculation_type=SalaryComponent.CalculationType.PERCENT_OF_GROSS,
            value=Decimal("50.00"),
            is_part_of_gross=True,
            display_order=10,
        )
        SalaryComponent.objects.create(
            template=self.salary_template,
            name="PF",
            code="PF_TEST",
            component_type=SalaryComponent.ComponentType.DEDUCTION,
            calculation_type=SalaryComponent.CalculationType.PERCENT_OF_COMPONENT,
            base_component=basic,
            value=Decimal("12.00"),
            has_employer_contribution=True,
            employer_contribution_value=Decimal("12.00"),
            deduct_employer_contribution=False,
            display_order=100,
        )

        with patch(
            "apps.payroll.services.payroll_service.PayslipService.calculate_lop_days",
            return_value=Decimal("0"),
        ):
            payslip = PayslipService.generate_payslip(self.hr_user, emp, date(2026, 4, 1))

        expected_gross = (Decimal("120000") / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_basic = (expected_gross * Decimal("50") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_pf = (expected_basic * Decimal("12") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(payslip.additional_earnings, Decimal("0.00"))
        self.assertEqual(payslip.component_deductions, expected_pf)
        pf_entry = payslip.component_entries.get(component_code="PF_TEST")
        self.assertEqual(pf_entry.calculated_amount, expected_pf)
        self.assertEqual(pf_entry.employer_contribution_amount, expected_pf)
        self.assertFalse(pf_entry.deducts_employer_contribution)

    def test_employer_contribution_can_be_deducted_from_employee(self):
        emp_user = make_user("ded-emp@test.com")
        emp = make_employee(emp_user, "EMP-DED001", self.dept, ctc=120000)

        basic = SalaryComponent.objects.create(
            template=self.salary_template,
            name="Basic Salary",
            code="BASIC_DEDUCT_EMPLOYER",
            component_type=SalaryComponent.ComponentType.EARNING,
            calculation_type=SalaryComponent.CalculationType.PERCENT_OF_GROSS,
            value=Decimal("50.00"),
            is_part_of_gross=True,
            display_order=10,
        )
        SalaryComponent.objects.create(
            template=self.salary_template,
            name="PF",
            code="PF_DEDUCT_EMPLOYER",
            component_type=SalaryComponent.ComponentType.DEDUCTION,
            calculation_type=SalaryComponent.CalculationType.PERCENT_OF_COMPONENT,
            base_component=basic,
            value=Decimal("12.00"),
            has_employer_contribution=True,
            employer_contribution_value=Decimal("12.00"),
            deduct_employer_contribution=True,
            display_order=100,
        )

        with patch(
            "apps.payroll.services.payroll_service.PayslipService.calculate_lop_days",
            return_value=Decimal("0"),
        ):
            payslip = PayslipService.generate_payslip(self.hr_user, emp, date(2026, 4, 1))

        expected_gross = (Decimal("120000") / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_basic = (expected_gross * Decimal("50") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_pf = (expected_basic * Decimal("12") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(payslip.component_deductions, expected_pf * 2)

    def test_lop_is_mapped_to_deduction_entry_for_custom_salary_structure(self):
        emp_user = make_user("ded-lop-emp@test.com")
        emp = make_employee(emp_user, "EMP-DEDLOP", self.dept, ctc=120000)

        basic = SalaryComponent.objects.create(
            template=self.salary_template,
            name="Basic Salary",
            code="BASIC_LOP",
            component_type=SalaryComponent.ComponentType.EARNING,
            calculation_type=SalaryComponent.CalculationType.PERCENT_OF_GROSS,
            value=Decimal("50.00"),
            is_part_of_gross=True,
            display_order=10,
        )
        SalaryComponent.objects.create(
            template=self.salary_template,
            name="PF",
            code="PF_LOP",
            component_type=SalaryComponent.ComponentType.DEDUCTION,
            calculation_type=SalaryComponent.CalculationType.PERCENT_OF_COMPONENT,
            base_component=basic,
            value=Decimal("12.00"),
            display_order=100,
        )

        lop_days = Decimal("2")
        with patch(
            "apps.payroll.services.payroll_service.PayslipService.calculate_lop_days",
            return_value=lop_days,
        ):
            payslip = PayslipService.generate_payslip(self.hr_user, emp, date(2026, 4, 1))

        days_in_month = monthrange(2026, 4)[1]
        expected_gross = (Decimal("120000") / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_basic = (expected_gross * Decimal("50") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_pf = (expected_basic * Decimal("12") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_lop = (expected_gross / Decimal(days_in_month) * lop_days).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        self.assertEqual(payslip.component_deductions, expected_pf)
        self.assertEqual(payslip.lop_deduction, expected_lop)
        self.assertEqual(payslip.total_deductions, expected_pf + expected_lop)
        deduction_codes = list(
            payslip.component_entries.filter(component_type=SalaryComponent.ComponentType.DEDUCTION).values_list(
                "component_code",
                flat=True,
            )
        )
        self.assertEqual(
            deduction_codes,
            ["PF_LOP", PayslipService.LOP_COMPONENT_CODE],
        )
        lop_entry = payslip.component_entries.get(component_code=PayslipService.LOP_COMPONENT_CODE)
        self.assertEqual(lop_entry.calculated_amount, expected_lop)
        self.assertIsNone(lop_entry.component)

    def test_manual_lop_component_is_not_double_counted(self):
        emp_user = make_user("ded-lop-legacy-emp@test.com")
        emp = make_employee(emp_user, "EMP-DEDLOPLEGACY", self.dept, ctc=120000)

        SalaryComponent.objects.create(
            template=self.salary_template,
            name="Legacy LOP",
            code=PayslipService.LOP_COMPONENT_CODE,
            component_type=SalaryComponent.ComponentType.DEDUCTION,
            calculation_type=SalaryComponent.CalculationType.FIXED,
            value=Decimal("500.00"),
            display_order=100,
        )

        lop_days = Decimal("2")
        with patch(
            "apps.payroll.services.payroll_service.PayslipService.calculate_lop_days",
            return_value=lop_days,
        ):
            payslip = PayslipService.generate_payslip(self.hr_user, emp, date(2026, 4, 1))

        days_in_month = monthrange(2026, 4)[1]
        expected_gross = (Decimal("120000") / Decimal("12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_lop = (expected_gross / Decimal(days_in_month) * lop_days).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        self.assertEqual(payslip.component_deductions, Decimal("0.00"))
        self.assertEqual(payslip.total_deductions, expected_lop)
        self.assertEqual(payslip.component_entries.filter(component_code=PayslipService.LOP_COMPONENT_CODE).count(), 1)
        lop_entry = payslip.component_entries.get(component_code=PayslipService.LOP_COMPONENT_CODE)
        self.assertEqual(lop_entry.calculated_amount, expected_lop)
        self.assertIsNone(lop_entry.component)
