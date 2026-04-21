from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.attendance.models import Attendance, AttendanceRegularization
from apps.attendance.services.attendance_service import AttendanceService
from apps.attendance.services.regularization_service import AttendanceRegularizationService
from apps.employees.models import Department, Employee


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


def make_employee(user, emp_id="EMP001", dept=None):
    return Employee.objects.create(
        user=user,
        employee_id=emp_id,
        designation="Dev",
        hire_date=date.today(),
        department=dept,
    )


def make_department(name="Engineering", code="ENG"):
    return Department.objects.create(name=name, code=code)


def authenticate_client(client, user):
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")


# ---------------------------------------------------------------------------
# AttendanceService: check_in tests
# ---------------------------------------------------------------------------

class CheckInServiceTestCase(TestCase):
    def setUp(self):
        self.dept = make_department("CI Dept", "CID")
        self.user = make_user("ci-emp@example.com")
        self.employee = make_employee(self.user, "CI-001", self.dept)

    def test_checkin_success_creates_attendance(self):
        attendance = AttendanceService.check_in(self.user)
        self.assertIsNotNone(attendance.pk)
        self.assertEqual(attendance.employee, self.employee)
        self.assertIsNotNone(attendance.check_in)
        self.assertIsNotNone(attendance.current_session_check_in)
        self.assertEqual(attendance.attendance_date, timezone.localdate())

    def test_checkin_default_status_is_present(self):
        attendance = AttendanceService.check_in(self.user)
        self.assertEqual(attendance.status, Attendance.Status.PRESENT)

    def test_checkin_with_custom_status(self):
        attendance = AttendanceService.check_in(self.user, status="REMOTE")
        self.assertEqual(attendance.status, Attendance.Status.REMOTE)

    def test_checkin_with_notes(self):
        attendance = AttendanceService.check_in(self.user, notes="Working from home")
        self.assertEqual(attendance.notes, "Working from home")

    def test_checkin_prevents_double_checkin(self):
        AttendanceService.check_in(self.user)
        from rest_framework import exceptions
        with self.assertRaises(exceptions.ValidationError):
            AttendanceService.check_in(self.user)

    def test_checkin_without_employee_profile_raises_permission_denied(self):
        bare_user = make_user("bare-ci@example.com")
        from rest_framework import exceptions
        with self.assertRaises(exceptions.PermissionDenied):
            AttendanceService.check_in(bare_user)

    def test_checkin_sets_break_fields_to_zero(self):
        attendance = AttendanceService.check_in(self.user)
        self.assertIsNone(attendance.break_started_at)
        self.assertEqual(attendance.current_session_break_minutes, 0)
        self.assertEqual(attendance.break_minutes, 0)


# ---------------------------------------------------------------------------
# AttendanceService: check_out tests
# ---------------------------------------------------------------------------

class CheckOutServiceTestCase(TestCase):
    def setUp(self):
        self.dept = make_department("CO Dept", "COD")
        self.user = make_user("co-emp@example.com")
        self.employee = make_employee(self.user, "CO-001", self.dept)

    def test_checkout_success_after_checkin(self):
        AttendanceService.check_in(self.user)
        attendance = AttendanceService.check_out(self.user)
        self.assertIsNotNone(attendance.check_out)
        self.assertIsNone(attendance.current_session_check_in)

    def test_checkout_without_checkin_raises_validation_error(self):
        from rest_framework import exceptions
        with self.assertRaises(exceptions.ValidationError):
            AttendanceService.check_out(self.user)

    def test_checkout_accumulates_work_minutes(self):
        now = timezone.now()
        checkin_time = now - timedelta(hours=2)
        with patch("apps.attendance.services.attendance_service.timezone") as mock_tz:
            mock_tz.now.return_value = checkin_time
            mock_tz.localdate.return_value = timezone.localdate()
            AttendanceService.check_in(self.user)

        with patch("apps.attendance.services.attendance_service.timezone") as mock_tz:
            mock_tz.now.return_value = now
            mock_tz.localdate.return_value = timezone.localdate()
            attendance = AttendanceService.check_out(self.user)

        self.assertGreater(attendance.total_work_minutes, 0)

    def test_checkout_without_employee_profile_raises_permission_denied(self):
        bare_user = make_user("bare-co@example.com")
        from rest_framework import exceptions
        with self.assertRaises(exceptions.PermissionDenied):
            AttendanceService.check_out(bare_user)

    def test_checkout_after_already_checked_out_raises_validation_error(self):
        AttendanceService.check_in(self.user)
        AttendanceService.check_out(self.user)
        from rest_framework import exceptions
        with self.assertRaises(exceptions.ValidationError):
            AttendanceService.check_out(self.user)


# ---------------------------------------------------------------------------
# AttendanceService: start_break / end_break tests
# ---------------------------------------------------------------------------

class BreakServiceTestCase(TestCase):
    def setUp(self):
        self.dept = make_department("BR Dept", "BRD")
        self.user = make_user("br-emp@example.com")
        self.employee = make_employee(self.user, "BR-001", self.dept)

    def test_start_break_success(self):
        AttendanceService.check_in(self.user)
        attendance = AttendanceService.start_break(self.user)
        self.assertIsNotNone(attendance.break_started_at)

    def test_start_break_without_checkin_raises(self):
        from rest_framework import exceptions
        with self.assertRaises(exceptions.ValidationError):
            AttendanceService.start_break(self.user)

    def test_start_break_double_break_raises(self):
        AttendanceService.check_in(self.user)
        AttendanceService.start_break(self.user)
        from rest_framework import exceptions
        with self.assertRaises(exceptions.ValidationError):
            AttendanceService.start_break(self.user)

    def test_end_break_success(self):
        AttendanceService.check_in(self.user)
        AttendanceService.start_break(self.user)
        attendance = AttendanceService.end_break(self.user)
        self.assertIsNone(attendance.break_started_at)

    def test_end_break_without_active_break_raises(self):
        AttendanceService.check_in(self.user)
        from rest_framework import exceptions
        with self.assertRaises(exceptions.ValidationError):
            AttendanceService.end_break(self.user)

    def test_end_break_without_checkin_raises(self):
        from rest_framework import exceptions
        with self.assertRaises(exceptions.ValidationError):
            AttendanceService.end_break(self.user)

    def test_start_break_without_employee_profile_raises(self):
        bare_user = make_user("bare-br@example.com")
        from rest_framework import exceptions
        with self.assertRaises(exceptions.PermissionDenied):
            AttendanceService.start_break(bare_user)

    def test_end_break_without_employee_profile_raises(self):
        bare_user = make_user("bare-ebr@example.com")
        from rest_framework import exceptions
        with self.assertRaises(exceptions.PermissionDenied):
            AttendanceService.end_break(bare_user)

    def test_break_accumulates_break_minutes(self):
        now = timezone.now()
        checkin_time = now - timedelta(hours=3)
        break_start = now - timedelta(hours=1)

        with patch("apps.attendance.services.attendance_service.timezone") as mock_tz:
            mock_tz.now.return_value = checkin_time
            mock_tz.localdate.return_value = timezone.localdate()
            AttendanceService.check_in(self.user)

        with patch("apps.attendance.services.attendance_service.timezone") as mock_tz:
            mock_tz.now.return_value = break_start
            mock_tz.localdate.return_value = timezone.localdate()
            AttendanceService.start_break(self.user)

        with patch("apps.attendance.services.attendance_service.timezone") as mock_tz:
            mock_tz.now.return_value = now
            mock_tz.localdate.return_value = timezone.localdate()
            attendance = AttendanceService.end_break(self.user)

        self.assertGreater(attendance.current_session_break_minutes, 0)


# ---------------------------------------------------------------------------
# AttendanceService: calculate_work_minutes / calculate_break_minutes
# ---------------------------------------------------------------------------

class CalculateMinutesTestCase(TestCase):
    def setUp(self):
        self.dept = make_department("Calc Dept", "CAL")
        self.user = make_user("calc-emp@example.com")
        self.employee = make_employee(self.user, "CALC-001", self.dept)

    def test_calculate_work_minutes_returns_zero_when_not_checked_in(self):
        attendance = Attendance.objects.create(
            employee=self.employee,
            attendance_date=date.today(),
            total_work_minutes=0,
        )
        self.assertEqual(AttendanceService.calculate_work_minutes(attendance), 0)

    def test_calculate_work_minutes_with_active_session(self):
        now = timezone.now()
        session_start = now - timedelta(hours=2)
        attendance = Attendance.objects.create(
            employee=self.employee,
            attendance_date=date.today(),
            check_in=session_start,
            current_session_check_in=session_start,
            total_work_minutes=0,
        )
        work_minutes = AttendanceService.calculate_work_minutes(attendance, reference_time=now)
        self.assertAlmostEqual(work_minutes, 120, delta=2)

    def test_calculate_work_minutes_excludes_break_time(self):
        now = timezone.now()
        session_start = now - timedelta(hours=3)
        break_start = now - timedelta(hours=1)
        attendance = Attendance.objects.create(
            employee=self.employee,
            attendance_date=date.today(),
            check_in=session_start,
            current_session_check_in=session_start,
            break_started_at=break_start,
            total_work_minutes=0,
            current_session_break_minutes=0,
        )
        work_minutes = AttendanceService.calculate_work_minutes(attendance, reference_time=now)
        # 3 hours session - 1 hour break = 2 hours = ~120 minutes
        self.assertAlmostEqual(work_minutes, 120, delta=2)

    def test_calculate_break_minutes_accumulates_past_and_live(self):
        now = timezone.now()
        break_start = now - timedelta(minutes=30)
        attendance = Attendance.objects.create(
            employee=self.employee,
            attendance_date=date.today(),
            check_in=now - timedelta(hours=2),
            current_session_check_in=now - timedelta(hours=2),
            break_started_at=break_start,
            break_minutes=10,
            current_session_break_minutes=5,
        )
        total_break = AttendanceService.calculate_break_minutes(attendance, reference_time=now)
        # 10 (past) + 5 (current session accumulated) + ~30 (live) = ~45
        self.assertAlmostEqual(total_break, 45, delta=3)

    def test_calculate_break_minutes_no_break_returns_accumulated(self):
        attendance = Attendance.objects.create(
            employee=self.employee,
            attendance_date=date.today(),
            break_minutes=20,
            current_session_break_minutes=0,
        )
        total_break = AttendanceService.calculate_break_minutes(attendance)
        self.assertEqual(total_break, 20)

    def test_calculate_work_minutes_with_prior_sessions(self):
        now = timezone.now()
        session_start = now - timedelta(hours=1)
        attendance = Attendance.objects.create(
            employee=self.employee,
            attendance_date=date.today(),
            check_in=now - timedelta(hours=3),
            current_session_check_in=session_start,
            total_work_minutes=60,  # 1 hour from previous session
        )
        work_minutes = AttendanceService.calculate_work_minutes(attendance, reference_time=now)
        # Prior 60 minutes + current ~60 minutes = ~120
        self.assertAlmostEqual(work_minutes, 120, delta=2)


# ---------------------------------------------------------------------------
# Multi-session: check-in → check-out → check-in (overtime)
# ---------------------------------------------------------------------------

class MultiSessionTestCase(TestCase):
    def setUp(self):
        self.dept = make_department("MS Dept", "MSD")
        self.user = make_user("ms-emp@example.com")
        self.employee = make_employee(self.user, "MS-001", self.dept)

    def test_checkin_checkout_checkin_overtime_session(self):
        now = timezone.now()

        # First session: 09:00 - 13:00 = 4 hours
        ci1_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        co1_time = now.replace(hour=13, minute=0, second=0, microsecond=0)
        if co1_time <= ci1_time:
            co1_time = ci1_time + timedelta(hours=4)

        with patch("apps.attendance.services.attendance_service.timezone") as mock_tz:
            mock_tz.now.return_value = ci1_time
            mock_tz.localdate.return_value = timezone.localdate()
            AttendanceService.check_in(self.user)

        with patch("apps.attendance.services.attendance_service.timezone") as mock_tz:
            mock_tz.now.return_value = co1_time
            mock_tz.localdate.return_value = timezone.localdate()
            att_after_co1 = AttendanceService.check_out(self.user)

        self.assertGreater(att_after_co1.total_work_minutes, 0)
        first_session_minutes = att_after_co1.total_work_minutes

        # Second session: check in again (overtime)
        ci2_time = co1_time + timedelta(hours=1)
        with patch("apps.attendance.services.attendance_service.timezone") as mock_tz:
            mock_tz.now.return_value = ci2_time
            mock_tz.localdate.return_value = timezone.localdate()
            att_ci2 = AttendanceService.check_in(self.user)

        self.assertIsNotNone(att_ci2.current_session_check_in)
        # Total work minutes should still hold what was accumulated
        self.assertEqual(att_ci2.total_work_minutes, first_session_minutes)

        # Check out from second session
        co2_time = ci2_time + timedelta(hours=2)
        with patch("apps.attendance.services.attendance_service.timezone") as mock_tz:
            mock_tz.now.return_value = co2_time
            mock_tz.localdate.return_value = timezone.localdate()
            att_co2 = AttendanceService.check_out(self.user)

        # Total work minutes should be greater than first session alone
        self.assertGreater(att_co2.total_work_minutes, first_session_minutes)


# ---------------------------------------------------------------------------
# AttendanceService: get_queryset_for_user tests
# ---------------------------------------------------------------------------

class AttendanceQuerysetForUserTestCase(TestCase):
    def setUp(self):
        self.dept = make_department("QS Dept", "QSD")

        self.hr_user = make_user("qs-hr@example.com", role=User.Role.HR)
        self.admin_user = make_user("qs-admin@example.com", role=User.Role.ADMIN)
        self.accounts_user = make_user("qs-accts@example.com", role=User.Role.ACCOUNTS)
        self.manager_user = make_user("qs-mgr@example.com", role=User.Role.MANAGER)
        self.employee_user = make_user("qs-emp@example.com", role=User.Role.EMPLOYEE)
        self.other_employee_user = make_user("qs-other@example.com", role=User.Role.EMPLOYEE)

        self.hr_emp = make_employee(self.hr_user, "QS-HR", self.dept)
        self.admin_emp = make_employee(self.admin_user, "QS-ADM", self.dept)
        self.accounts_emp = make_employee(self.accounts_user, "QS-ACCT", self.dept)
        self.manager_emp = make_employee(self.manager_user, "QS-MGR", self.dept)
        self.emp = make_employee(self.employee_user, "QS-EMP", self.dept)
        self.other_emp = make_employee(self.other_employee_user, "QS-OTH", self.dept)

        # Create attendance records
        today = date.today()
        Attendance.objects.create(employee=self.emp, attendance_date=today, status="PRESENT")
        Attendance.objects.create(employee=self.other_emp, attendance_date=today, status="PRESENT")

    def test_hr_sees_all_attendance(self):
        qs = AttendanceService.get_queryset_for_user(self.hr_user)
        self.assertGreaterEqual(qs.count(), 2)

    def test_admin_sees_all_attendance(self):
        qs = AttendanceService.get_queryset_for_user(self.admin_user)
        self.assertGreaterEqual(qs.count(), 2)

    def test_accounts_sees_all_attendance(self):
        qs = AttendanceService.get_queryset_for_user(self.accounts_user)
        self.assertGreaterEqual(qs.count(), 2)

    def test_employee_sees_only_own_attendance(self):
        qs = AttendanceService.get_queryset_for_user(self.employee_user)
        employee_ids = list(qs.values_list("employee_id", flat=True))
        for eid in employee_ids:
            self.assertEqual(eid, self.emp.pk)

    def test_manager_sees_own_and_team_attendance(self):
        # Assign emp to manager
        self.emp.manager = self.manager_emp
        self.emp.save()
        qs = AttendanceService.get_queryset_for_user(self.manager_user)
        # Should include manager's own attendance (none yet) and their team
        employee_ids_in_qs = set(qs.values_list("employee_id", flat=True))
        self.assertIn(self.emp.pk, employee_ids_in_qs)

    def test_user_without_employee_profile_sees_nothing(self):
        bare_user = make_user("bare-qs@example.com")
        qs = AttendanceService.get_queryset_for_user(bare_user)
        self.assertEqual(qs.count(), 0)


# ---------------------------------------------------------------------------
# Attendance API endpoint tests
# ---------------------------------------------------------------------------

class AttendanceAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dept = make_department("API-ATT Dept", "AATD")
        self.user = make_user("api-att@example.com")
        self.employee = make_employee(self.user, "API-ATT-001", self.dept)

        self.checkin_url = reverse("attendance-check-in")
        self.checkout_url = reverse("attendance-check-out")
        self.start_break_url = reverse("attendance-start-break")
        self.end_break_url = reverse("attendance-end-break")

    def test_checkin_api_success(self):
        authenticate_client(self.client, self.user)
        resp = self.client.post(self.checkin_url, {}, format="json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])

    def test_checkin_api_unauthenticated_returns_401(self):
        resp = self.client.post(self.checkin_url, {}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_checkout_api_success(self):
        authenticate_client(self.client, self.user)
        self.client.post(self.checkin_url, {}, format="json")
        resp = self.client.post(self.checkout_url, {}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_checkout_api_without_checkin_returns_400(self):
        authenticate_client(self.client, self.user)
        resp = self.client.post(self.checkout_url, {}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_start_break_api_success(self):
        authenticate_client(self.client, self.user)
        self.client.post(self.checkin_url, {}, format="json")
        resp = self.client.post(self.start_break_url, {}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_end_break_api_success(self):
        authenticate_client(self.client, self.user)
        self.client.post(self.checkin_url, {}, format="json")
        self.client.post(self.start_break_url, {}, format="json")
        resp = self.client.post(self.end_break_url, {}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_double_checkin_api_returns_400(self):
        authenticate_client(self.client, self.user)
        self.client.post(self.checkin_url, {}, format="json")
        resp = self.client.post(self.checkin_url, {}, format="json")
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# AttendanceRegularization tests
# ---------------------------------------------------------------------------

class AttendanceRegularizationServiceTestCase(TestCase):
    def setUp(self):
        self.dept = make_department("Reg Dept", "REGD")
        self.hr_user = make_user("reg-hr@example.com", role=User.Role.HR)
        self.employee_user = make_user("reg-emp@example.com", role=User.Role.EMPLOYEE)

        self.hr_emp = make_employee(self.hr_user, "REG-HR", self.dept)
        self.emp = make_employee(self.employee_user, "REG-EMP", self.dept)

        self.reg_date = date.today() - timedelta(days=1)
        self.requested_check_in = timezone.now() - timedelta(days=1, hours=2)
        self.requested_check_out = timezone.now() - timedelta(days=1)

    def _apply_regularization(self, user=None, target_date=None):
        user = user or self.employee_user
        target_date = target_date or self.reg_date
        validated_data = {
            "date": target_date,
            "requested_check_in": self.requested_check_in,
            "requested_check_out": self.requested_check_out,
            "reason": "Forgot to clock in",
        }
        with patch("apps.attendance.services.regularization_service.WorkflowService") as mock_ws, \
             patch("apps.attendance.services.regularization_service.NotificationService") as mock_ns:
            mock_ws.start_workflow.return_value = MagicMock()
            mock_ns.notify_regularization_applied.return_value = None
            return AttendanceRegularizationService.apply_regularization(user, validated_data)

    def test_apply_regularization_success(self):
        reg = self._apply_regularization()
        self.assertIsNotNone(reg.pk)
        self.assertEqual(reg.employee, self.emp)
        self.assertEqual(reg.status, AttendanceRegularization.Status.PENDING)

    def test_apply_regularization_creates_db_record(self):
        self._apply_regularization()
        self.assertTrue(AttendanceRegularization.objects.filter(
            employee=self.emp,
            date=self.reg_date,
            status=AttendanceRegularization.Status.PENDING,
        ).exists())

    def test_apply_regularization_duplicate_pending_raises(self):
        self._apply_regularization()
        from rest_framework import exceptions
        with self.assertRaises(exceptions.ValidationError):
            self._apply_regularization()

    def test_apply_regularization_without_employee_profile_raises(self):
        bare_user = make_user("bare-reg@example.com")
        from rest_framework import exceptions
        with self.assertRaises(exceptions.PermissionDenied):
            self._apply_regularization(user=bare_user)

    def test_approve_regularization_marks_approved(self):
        reg = self._apply_regularization()
        with patch("apps.attendance.services.regularization_service.WorkflowService") as mock_ws:
            mock_ws.get_assignment_for_object.return_value = None
            result = AttendanceRegularizationService.approve_regularization(
                self.hr_user, reg, approver_note="Approved"
            )
        result.refresh_from_db()
        self.assertEqual(result.status, AttendanceRegularization.Status.APPROVED)
        self.assertEqual(result.approver, self.hr_user)
        self.assertEqual(result.approver_note, "Approved")

    def test_approve_regularization_creates_attendance_record(self):
        reg = self._apply_regularization()
        with patch("apps.attendance.services.regularization_service.WorkflowService") as mock_ws:
            mock_ws.get_assignment_for_object.return_value = None
            AttendanceRegularizationService.approve_regularization(self.hr_user, reg)
        attendance = Attendance.objects.filter(employee=self.emp, attendance_date=self.reg_date).first()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.check_in, self.requested_check_in)
        self.assertEqual(attendance.check_out, self.requested_check_out)

    def test_approve_non_pending_regularization_raises(self):
        reg = self._apply_regularization()
        with patch("apps.attendance.services.regularization_service.WorkflowService") as mock_ws:
            mock_ws.get_assignment_for_object.return_value = None
            AttendanceRegularizationService.approve_regularization(self.hr_user, reg)

        reg.refresh_from_db()
        from rest_framework import exceptions
        with self.assertRaises(exceptions.ValidationError):
            with patch("apps.attendance.services.regularization_service.WorkflowService") as mock_ws:
                mock_ws.get_assignment_for_object.return_value = None
                AttendanceRegularizationService.approve_regularization(self.hr_user, reg)

    def test_reject_regularization_marks_rejected(self):
        reg = self._apply_regularization()
        with patch("apps.attendance.services.regularization_service.WorkflowService") as mock_ws:
            mock_ws.get_assignment_for_object.return_value = None
            result = AttendanceRegularizationService.reject_regularization(
                self.hr_user, reg, approver_note="Not valid"
            )
        result.refresh_from_db()
        self.assertEqual(result.status, AttendanceRegularization.Status.REJECTED)
        self.assertEqual(result.approver_note, "Not valid")

    def test_reject_non_pending_regularization_raises(self):
        reg = self._apply_regularization()
        with patch("apps.attendance.services.regularization_service.WorkflowService") as mock_ws:
            mock_ws.get_assignment_for_object.return_value = None
            AttendanceRegularizationService.reject_regularization(self.hr_user, reg)

        reg.refresh_from_db()
        from rest_framework import exceptions
        with self.assertRaises(exceptions.ValidationError):
            with patch("apps.attendance.services.regularization_service.WorkflowService") as mock_ws:
                mock_ws.get_assignment_for_object.return_value = None
                AttendanceRegularizationService.reject_regularization(self.hr_user, reg)

    def test_approve_regularization_sets_reviewed_at(self):
        reg = self._apply_regularization()
        with patch("apps.attendance.services.regularization_service.WorkflowService") as mock_ws:
            mock_ws.get_assignment_for_object.return_value = None
            AttendanceRegularizationService.approve_regularization(self.hr_user, reg)
        reg.refresh_from_db()
        self.assertIsNotNone(reg.reviewed_at)


# ---------------------------------------------------------------------------
# AttendanceRegularizationService: get_queryset_for_user tests
# ---------------------------------------------------------------------------

class RegularizationQuerysetForUserTestCase(TestCase):
    def setUp(self):
        self.dept = make_department("RQ Dept", "RQD")
        self.hr_user = make_user("rq-hr@example.com", role=User.Role.HR)
        self.admin_user = make_user("rq-admin@example.com", role=User.Role.ADMIN)
        self.manager_user = make_user("rq-mgr@example.com", role=User.Role.MANAGER)
        self.employee_user = make_user("rq-emp@example.com", role=User.Role.EMPLOYEE)
        self.other_employee_user = make_user("rq-other@example.com", role=User.Role.EMPLOYEE)

        self.hr_emp = make_employee(self.hr_user, "RQ-HR", self.dept)
        self.admin_emp = make_employee(self.admin_user, "RQ-ADM", self.dept)
        self.manager_emp = make_employee(self.manager_user, "RQ-MGR", self.dept)
        self.emp = make_employee(self.employee_user, "RQ-EMP", self.dept)
        self.other_emp = make_employee(self.other_employee_user, "RQ-OTH", self.dept)

        now = timezone.now()
        reg_date = date.today() - timedelta(days=1)
        self.reg_emp = AttendanceRegularization.objects.create(
            employee=self.emp,
            date=reg_date,
            requested_check_in=now - timedelta(days=1, hours=2),
            requested_check_out=now - timedelta(days=1),
            reason="Test",
            status=AttendanceRegularization.Status.PENDING,
        )
        self.reg_other = AttendanceRegularization.objects.create(
            employee=self.other_emp,
            date=reg_date,
            requested_check_in=now - timedelta(days=1, hours=2),
            requested_check_out=now - timedelta(days=1),
            reason="Test other",
            status=AttendanceRegularization.Status.PENDING,
        )

    def test_hr_sees_all_regularizations(self):
        qs = AttendanceRegularizationService.get_queryset_for_user(self.hr_user)
        self.assertGreaterEqual(qs.count(), 2)

    def test_admin_sees_all_regularizations(self):
        qs = AttendanceRegularizationService.get_queryset_for_user(self.admin_user)
        self.assertGreaterEqual(qs.count(), 2)

    def test_employee_sees_only_own_regularizations(self):
        qs = AttendanceRegularizationService.get_queryset_for_user(self.employee_user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().pk, self.reg_emp.pk)

    def test_manager_sees_own_and_team_regularizations(self):
        self.emp.manager = self.manager_emp
        self.emp.save()
        qs = AttendanceRegularizationService.get_queryset_for_user(self.manager_user)
        reg_ids = set(qs.values_list("id", flat=True))
        self.assertIn(self.reg_emp.pk, reg_ids)

    def test_user_without_employee_profile_sees_nothing(self):
        bare_user = make_user("bare-rq@example.com")
        qs = AttendanceRegularizationService.get_queryset_for_user(bare_user)
        self.assertEqual(qs.count(), 0)
