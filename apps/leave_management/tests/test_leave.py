"""
Tests for leave_management services:
- LeaveRequestService
- EarnedLeaveAdjustmentService
- LeaveBalance model property
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.leave_management.models import (
    EarnedLeaveAdjustment,
    LeaveBalance,
    LeavePolicy,
    LeaveRequest,
)
from apps.leave_management.services.leave_service import (
    EarnedLeaveAdjustmentService,
    LeavePolicyService,
    LeaveRequestService,
)


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


def make_employee(user, emp_id, dept=None, manager=None):
    return Employee.objects.create(
        user=user,
        employee_id=emp_id,
        designation="Dev",
        hire_date=date.today(),
        department=dept,
        manager=manager,
    )


def make_balance(employee, leave_type, allocated=10, used=0):
    return LeaveBalance.objects.create(
        employee=employee,
        leave_type=leave_type,
        allocated_days=Decimal(str(allocated)),
        used_days=Decimal(str(used)),
    )


def make_leave_data(
    leave_type,
    start_date,
    end_date,
    duration_type=LeaveRequest.DurationType.FULL_DAY,
    reason="Test leave",
):
    return {
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "duration_type": duration_type,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# LeaveBalance model property tests
# ---------------------------------------------------------------------------

class LeaveBalancePropertyTest(TestCase):
    def setUp(self):
        dept = Department.objects.create(name="Eng", code="ENG")
        user = make_user("bal@test.com")
        self.employee = make_employee(user, "EMP-BAL", dept)

    def test_available_days_normal(self):
        balance = make_balance(self.employee, LeaveBalance.LeaveType.CASUAL, allocated=12, used=3)
        self.assertEqual(balance.available_days, Decimal("9"))

    def test_available_days_zero(self):
        balance = make_balance(self.employee, LeaveBalance.LeaveType.SICK, allocated=6, used=6)
        self.assertEqual(balance.available_days, Decimal("0"))

    def test_available_days_negative_allowed(self):
        """
        LOP or over-approval can result in used > allocated; available_days
        should be able to return a negative value — it is intentionally not clamped.
        """
        balance = make_balance(self.employee, LeaveBalance.LeaveType.CASUAL, allocated=5, used=7)
        self.assertEqual(balance.available_days, Decimal("-2"))

    def test_unique_constraint_employee_leave_type(self):
        make_balance(self.employee, LeaveBalance.LeaveType.EARNED, allocated=15)
        with self.assertRaises(Exception):
            LeaveBalance.objects.create(
                employee=self.employee,
                leave_type=LeaveBalance.LeaveType.EARNED,
                allocated_days=Decimal("10"),
                used_days=Decimal("0"),
            )


# ---------------------------------------------------------------------------
# calculate_total_days tests (no DB needed, but uses mock for holidays)
# ---------------------------------------------------------------------------

class CalculateTotalDaysTest(TestCase):
    def setUp(self):
        dept = Department.objects.create(name="Ops", code="OPS")
        user = make_user("days@test.com")
        self.employee = make_employee(user, "EMP-DAYS", dept)

    def _data(self, start, end, duration=LeaveRequest.DurationType.FULL_DAY):
        return {"start_date": start, "end_date": end, "duration_type": duration, "leave_type": LeaveBalance.LeaveType.CASUAL}

    @patch("apps.leave_management.services.leave_service.HolidayService.get_holiday_dates_for_employee", return_value=set())
    def test_single_day_full_day(self, _mock):
        d = date(2026, 4, 1)
        result = LeaveRequestService.calculate_total_days(self._data(d, d), employee=self.employee)
        self.assertEqual(result, Decimal("1"))

    @patch("apps.leave_management.services.leave_service.HolidayService.get_holiday_dates_for_employee", return_value=set())
    def test_multi_day_full_day(self, _mock):
        result = LeaveRequestService.calculate_total_days(
            self._data(date(2026, 4, 1), date(2026, 4, 5)), employee=self.employee
        )
        self.assertEqual(result, Decimal("5"))

    def test_half_day_returns_point_five(self):
        d = date(2026, 4, 1)
        result = LeaveRequestService.calculate_total_days(
            self._data(d, d, duration=LeaveRequest.DurationType.HALF_DAY)
        )
        self.assertEqual(result, Decimal("0.5"))

    @patch("apps.leave_management.services.leave_service.HolidayService.get_holiday_dates_for_employee")
    def test_holiday_deducted_from_day_count(self, mock_holidays):
        holiday_date = date(2026, 4, 3)
        mock_holidays.return_value = {holiday_date}
        result = LeaveRequestService.calculate_total_days(
            self._data(date(2026, 4, 1), date(2026, 4, 5)), employee=self.employee
        )
        # 5 calendar days - 1 holiday = 4 working days
        self.assertEqual(result, Decimal("4"))

    @patch("apps.leave_management.services.leave_service.HolidayService.get_holiday_dates_for_employee")
    def test_all_holidays_raises_validation_error(self, mock_holidays):
        d = date(2026, 4, 1)
        mock_holidays.return_value = {d}
        with self.assertRaises(ValidationError):
            LeaveRequestService.calculate_total_days(self._data(d, d), employee=self.employee)


# ---------------------------------------------------------------------------
# apply_leave tests
# ---------------------------------------------------------------------------

class ApplyLeaveTest(TestCase):
    def setUp(self):
        dept = Department.objects.create(name="Dev", code="DEV")
        self.user = make_user("emp@test.com")
        manager_user = make_user("mgr@test.com", role=User.Role.MANAGER)
        self.manager_emp = make_employee(manager_user, "EMP-MGR", dept)
        self.employee = make_employee(self.user, "EMP-001", dept, manager=self.manager_emp)
        # ensure a policy row exists
        LeavePolicyService.get_policy()

    def _patch_holidays(self, holiday_dates=None):
        """Return a context manager that patches HolidayService."""
        return patch(
            "apps.leave_management.services.leave_service.HolidayService.get_holiday_dates_for_employee",
            return_value=holiday_dates or set(),
        )

    # --- casual leave ---
    def test_apply_casual_leave_success(self):
        make_balance(self.employee, LeaveBalance.LeaveType.CASUAL, allocated=10)
        data = make_leave_data(
            LeaveBalance.LeaveType.CASUAL,
            date(2026, 5, 5),
            date(2026, 5, 7),
        )
        with self._patch_holidays():
            leave = LeaveRequestService.apply_leave(self.user, data)
        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)
        self.assertEqual(leave.total_days, Decimal("3"))
        self.assertEqual(leave.employee, self.employee)

    # --- sick leave ---
    def test_apply_sick_leave_success(self):
        make_balance(self.employee, LeaveBalance.LeaveType.SICK, allocated=6)
        data = make_leave_data(
            LeaveBalance.LeaveType.SICK,
            date(2026, 5, 10),
            date(2026, 5, 11),
        )
        with self._patch_holidays():
            leave = LeaveRequestService.apply_leave(self.user, data)
        self.assertEqual(leave.total_days, Decimal("2"))

    # --- earned leave ---
    def test_apply_earned_leave_success(self):
        make_balance(self.employee, LeaveBalance.LeaveType.EARNED, allocated=15)
        data = make_leave_data(
            LeaveBalance.LeaveType.EARNED,
            date(2026, 5, 18),
            date(2026, 5, 20),
        )
        with self._patch_holidays():
            leave = LeaveRequestService.apply_leave(self.user, data)
        self.assertEqual(leave.total_days, Decimal("3"))

    # --- LOP leave ---
    def test_apply_lop_leave_success_no_balance_needed(self):
        # No LeaveBalance row for LOP — should succeed
        data = make_leave_data(
            LeaveBalance.LeaveType.LOP,
            date(2026, 5, 25),
            date(2026, 5, 25),
        )
        with self._patch_holidays():
            leave = LeaveRequestService.apply_leave(self.user, data)
        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)
        self.assertEqual(leave.leave_type, LeaveBalance.LeaveType.LOP)

    # --- insufficient balance when policy prevents fallback ---
    def test_insufficient_balance_raises_error(self):
        policy = LeavePolicyService.get_policy()
        policy.compensate_with_earned_leave = False
        policy.excess_leave_becomes_lop = False
        policy.save()

        make_balance(self.employee, LeaveBalance.LeaveType.CASUAL, allocated=1, used=0)
        data = make_leave_data(
            LeaveBalance.LeaveType.CASUAL,
            date(2026, 6, 1),
            date(2026, 6, 5),
        )
        with self._patch_holidays():
            with self.assertRaises(ValidationError):
                LeaveRequestService.apply_leave(self.user, data)

    # --- half-day leave ---
    def test_half_day_leave_total_days_is_point_five(self):
        make_balance(self.employee, LeaveBalance.LeaveType.CASUAL, allocated=10)
        data = make_leave_data(
            LeaveBalance.LeaveType.CASUAL,
            date(2026, 6, 10),
            date(2026, 6, 10),
            duration_type=LeaveRequest.DurationType.HALF_DAY,
        )
        with self._patch_holidays():
            leave = LeaveRequestService.apply_leave(self.user, data)
        self.assertEqual(leave.total_days, Decimal("0.5"))

    # --- no employee profile ---
    def test_no_employee_profile_raises_permission_denied(self):
        orphan_user = make_user("orphan@test.com")
        data = make_leave_data(
            LeaveBalance.LeaveType.CASUAL,
            date(2026, 7, 1),
            date(2026, 7, 1),
        )
        with self.assertRaises(PermissionDenied):
            LeaveRequestService.apply_leave(orphan_user, data)

    # --- overlapping leave ---
    def test_overlapping_leave_raises_error(self):
        make_balance(self.employee, LeaveBalance.LeaveType.CASUAL, allocated=10)
        data = make_leave_data(
            LeaveBalance.LeaveType.CASUAL,
            date(2026, 7, 5),
            date(2026, 7, 7),
        )
        with self._patch_holidays():
            LeaveRequestService.apply_leave(self.user, data)
            with self.assertRaises(ValidationError):
                LeaveRequestService.apply_leave(self.user, data)


# ---------------------------------------------------------------------------
# Monthly limit enforcement tests
# ---------------------------------------------------------------------------

class MonthlyLimitTest(TestCase):
    def setUp(self):
        dept = Department.objects.create(name="Finance", code="FIN")
        self.user = make_user("limit@test.com")
        manager_user = make_user("limitmgr@test.com", role=User.Role.MANAGER)
        self.manager_emp = make_employee(manager_user, "EMP-LIMITMGR", dept)
        self.employee = make_employee(self.user, "EMP-LIMIT", dept, manager=self.manager_emp)
        self.policy = LeavePolicyService.get_policy()
        self.policy.monthly_sick_leave_limit = Decimal("2")
        self.policy.monthly_earned_leave_limit = Decimal("3")
        self.policy.save()
        make_balance(self.employee, LeaveBalance.LeaveType.SICK, allocated=10)
        make_balance(self.employee, LeaveBalance.LeaveType.EARNED, allocated=15)

    def _patch_holidays(self):
        return patch(
            "apps.leave_management.services.leave_service.HolidayService.get_holiday_dates_for_employee",
            return_value=set(),
        )

    def test_sick_leave_within_monthly_limit_succeeds(self):
        data = make_leave_data(
            LeaveBalance.LeaveType.SICK,
            date(2026, 8, 3),
            date(2026, 8, 4),  # 2 days = limit
        )
        with self._patch_holidays():
            leave = LeaveRequestService.apply_leave(self.user, data)
        self.assertIsNotNone(leave.pk)

    def test_sick_leave_exceeding_monthly_limit_raises_error(self):
        data = make_leave_data(
            LeaveBalance.LeaveType.SICK,
            date(2026, 8, 3),
            date(2026, 8, 6),  # 4 days > 2 day limit
        )
        with self._patch_holidays():
            with self.assertRaises(ValidationError):
                LeaveRequestService.apply_leave(self.user, data)

    def test_earned_leave_exceeding_monthly_limit_raises_error(self):
        data = make_leave_data(
            LeaveBalance.LeaveType.EARNED,
            date(2026, 9, 1),
            date(2026, 9, 5),  # 5 days > 3 day limit
        )
        with self._patch_holidays():
            with self.assertRaises(ValidationError):
                LeaveRequestService.apply_leave(self.user, data)


# ---------------------------------------------------------------------------
# Approve / reject leave tests
# ---------------------------------------------------------------------------

class ApproveRejectLeaveTest(TestCase):
    def setUp(self):
        dept = Department.objects.create(name="HR-dept", code="HRD")
        self.hr_user = make_user("hr@test.com", role=User.Role.HR)
        self.hr_emp = make_employee(self.hr_user, "EMP-HR", dept)

        self.emp_user = make_user("emp2@test.com")
        self.employee = make_employee(self.emp_user, "EMP-002", dept)
        LeavePolicyService.get_policy()

    def _make_pending_leave(self, leave_type=LeaveBalance.LeaveType.CASUAL, days=2):
        start = date(2026, 10, 5)
        end = start + timedelta(days=days - 1)
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=leave_type,
            duration_type=LeaveRequest.DurationType.FULL_DAY,
            start_date=start,
            end_date=end,
            reason="Test",
            status=LeaveRequest.Status.PENDING,
            total_days=Decimal(str(days)),
        )
        return leave

    def test_approve_leave_updates_status(self):
        make_balance(self.employee, LeaveBalance.LeaveType.CASUAL, allocated=10)
        leave = self._make_pending_leave()
        LeaveRequestService.finalize_workflow_approval(leave, actor=self.hr_user)
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.APPROVED)
        self.assertEqual(leave.approver, self.hr_user)

    def test_approve_leave_deducts_balance(self):
        balance = make_balance(self.employee, LeaveBalance.LeaveType.CASUAL, allocated=10, used=0)
        leave = self._make_pending_leave(days=3)
        LeaveRequestService.finalize_workflow_approval(leave, actor=self.hr_user)
        balance.refresh_from_db()
        self.assertEqual(balance.used_days, Decimal("3"))

    def test_reject_leave_updates_status(self):
        leave = self._make_pending_leave()
        LeaveRequestService.finalize_workflow_rejection(leave, actor=self.hr_user, approver_note="No reason")
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.REJECTED)
        self.assertEqual(leave.approver, self.hr_user)
        self.assertEqual(leave.approver_note, "No reason")

    def test_reject_leave_does_not_deduct_balance(self):
        balance = make_balance(self.employee, LeaveBalance.LeaveType.CASUAL, allocated=10, used=0)
        leave = self._make_pending_leave(days=3)
        LeaveRequestService.finalize_workflow_rejection(leave, actor=self.hr_user)
        balance.refresh_from_db()
        self.assertEqual(balance.used_days, Decimal("0"))

    def test_approve_already_approved_is_idempotent(self):
        make_balance(self.employee, LeaveBalance.LeaveType.CASUAL, allocated=10)
        leave = self._make_pending_leave()
        LeaveRequestService.finalize_workflow_approval(leave, actor=self.hr_user)
        # Calling again should not raise or double-deduct
        result = LeaveRequestService.finalize_workflow_approval(leave, actor=self.hr_user)
        self.assertEqual(result.status, LeaveRequest.Status.APPROVED)


# ---------------------------------------------------------------------------
# LOP leave tests
# ---------------------------------------------------------------------------

class LopLeaveTest(TestCase):
    def setUp(self):
        dept = Department.objects.create(name="LOP-dept", code="LOPD")
        self.hr_user = make_user("hrLop@test.com", role=User.Role.HR)
        make_employee(self.hr_user, "EMP-HRLO", dept)
        self.emp_user = make_user("empLop@test.com")
        self.employee = make_employee(self.emp_user, "EMP-LOP", dept)
        LeavePolicyService.get_policy()

    def test_approve_lop_leave_sets_lop_days_applied(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=LeaveBalance.LeaveType.LOP,
            duration_type=LeaveRequest.DurationType.FULL_DAY,
            start_date=date(2026, 11, 3),
            end_date=date(2026, 11, 5),
            reason="Extra LOP",
            status=LeaveRequest.Status.PENDING,
            total_days=Decimal("3"),
        )
        LeaveRequestService.finalize_workflow_approval(leave, actor=self.hr_user)
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.APPROVED)
        self.assertEqual(leave.lop_days_applied, Decimal("3"))


# ---------------------------------------------------------------------------
# EarnedLeaveAdjustment tests
# ---------------------------------------------------------------------------

class EarnedLeaveAdjustmentTest(TestCase):
    def setUp(self):
        dept = Department.objects.create(name="ELA-dept", code="ELAD")
        self.hr_user = make_user("hrEla@test.com", role=User.Role.HR)
        self.hr_emp = make_employee(self.hr_user, "EMP-HRELA", dept)

        self.emp_user = make_user("empEla@test.com")
        self.employee = make_employee(self.emp_user, "EMP-ELA", dept)
        # Earned balance required by approve_adjustment
        self.earned_balance = make_balance(self.employee, LeaveBalance.LeaveType.EARNED, allocated=5, used=0)

    def _make_adjustment(self, work_date=None, days=1):
        if work_date is None:
            # default to last Saturday
            today = date.today()
            days_since_saturday = (today.weekday() - 5) % 7
            work_date = today - timedelta(days=days_since_saturday or 7)

        return EarnedLeaveAdjustment.objects.create(
            employee=self.employee,
            work_date=work_date,
            days=Decimal(str(days)),
            reason="Worked on weekend",
            status=EarnedLeaveAdjustment.Status.PENDING,
        )

    def test_apply_adjustment_creates_pending_record(self):
        """apply_adjustment must be for a weekend or holiday; patch to allow it."""
        last_saturday = date.today() - timedelta(days=(date.today().weekday() - 5) % 7 or 7)
        with patch(
            "apps.leave_management.services.leave_service.HolidayService.get_holiday_dates_for_employee",
            return_value=set(),
        ):
            adj = EarnedLeaveAdjustmentService.apply_adjustment(
                self.emp_user,
                {"work_date": last_saturday, "days": Decimal("1"), "reason": "Worked"},
            )
        self.assertEqual(adj.status, EarnedLeaveAdjustment.Status.PENDING)
        self.assertEqual(adj.employee, self.employee)

    def test_approve_adjustment_credits_earned_balance(self):
        adj = self._make_adjustment(days=2)
        initial_allocated = self.earned_balance.allocated_days
        EarnedLeaveAdjustmentService.approve_adjustment(self.hr_user, adj, approver_note="Good work")
        adj.refresh_from_db()
        self.earned_balance.refresh_from_db()
        self.assertEqual(adj.status, EarnedLeaveAdjustment.Status.APPROVED)
        self.assertEqual(self.earned_balance.allocated_days, initial_allocated + Decimal("2"))

    def test_reject_adjustment_does_not_credit_balance(self):
        adj = self._make_adjustment(days=1)
        initial_allocated = self.earned_balance.allocated_days
        EarnedLeaveAdjustmentService.reject_adjustment(self.hr_user, adj, approver_note="Rejected")
        adj.refresh_from_db()
        self.earned_balance.refresh_from_db()
        self.assertEqual(adj.status, EarnedLeaveAdjustment.Status.REJECTED)
        self.assertEqual(self.earned_balance.allocated_days, initial_allocated)

    def test_approve_non_pending_adjustment_raises_error(self):
        adj = self._make_adjustment()
        adj.status = EarnedLeaveAdjustment.Status.APPROVED
        adj.save()
        with self.assertRaises(ValidationError):
            EarnedLeaveAdjustmentService.approve_adjustment(self.hr_user, adj)

    def test_reject_non_pending_adjustment_raises_error(self):
        adj = self._make_adjustment()
        adj.status = EarnedLeaveAdjustment.Status.REJECTED
        adj.save()
        with self.assertRaises(ValidationError):
            EarnedLeaveAdjustmentService.reject_adjustment(self.hr_user, adj)

    def test_employee_cannot_approve_own_adjustment(self):
        adj = self._make_adjustment()
        with self.assertRaises(PermissionDenied):
            EarnedLeaveAdjustmentService.approve_adjustment(self.emp_user, adj)
