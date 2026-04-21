from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.attendance.services.geo_utils import GeoUtils
from apps.audit.services.audit_service import AuditService
from apps.employees.services.employee_service import OrganizationSettingsService


class AttendanceService:
    @staticmethod
    def get_expected_shift_minutes(employee):
        start_time = getattr(employee, "shift_start_time", None)
        end_time = getattr(employee, "shift_end_time", None)
        if not start_time or not end_time:
            return 0

        reference_date = timezone.localdate()
        start_dt = datetime.combine(reference_date, start_time)
        end_dt = datetime.combine(reference_date, end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        return int((end_dt - start_dt).total_seconds() // 60)

    @staticmethod
    def calculate_current_session_break_minutes(attendance, reference_time=None):
        break_minutes = attendance.current_session_break_minutes or 0
        if attendance.break_started_at and attendance.current_session_check_in:
            current_time = reference_time or timezone.now()
            break_minutes += max(int((current_time - attendance.break_started_at).total_seconds() // 60), 0)
        return break_minutes

    @staticmethod
    def calculate_break_minutes(attendance, reference_time=None):
        return (attendance.break_minutes or 0) + AttendanceService.calculate_current_session_break_minutes(
            attendance, reference_time=reference_time
        )

    @staticmethod
    def calculate_work_minutes(attendance, reference_time=None):
        total_minutes = attendance.total_work_minutes or 0
        if not attendance.current_session_check_in:
            return total_minutes
        if not attendance.check_in:
            return 0

        current_time = reference_time or timezone.now()
        session_minutes = max(int((current_time - attendance.current_session_check_in).total_seconds() // 60), 0)
        current_session_break_minutes = AttendanceService.calculate_current_session_break_minutes(
            attendance, reference_time=current_time
        )
        return max(total_minutes + session_minutes - current_session_break_minutes, 0)

    @staticmethod
    def get_queryset_for_user(user):
        queryset = Attendance.objects.select_related("employee__user", "employee__department").all()
        employee = getattr(user, "employee_profile", None)

        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def get_check_in_distance_meters(attendance):
        if attendance.check_in_latitude is None or attendance.check_in_longitude is None:
            return None
        settings = OrganizationSettingsService.get_settings()
        if settings.office_latitude is None or settings.office_longitude is None:
            return None
        return GeoUtils.calculate_distance(
            float(settings.office_latitude),
            float(settings.office_longitude),
            float(attendance.check_in_latitude),
            float(attendance.check_in_longitude),
        )

    @staticmethod
    def get_work_location(attendance):
        distance = AttendanceService.get_check_in_distance_meters(attendance)
        if attendance.check_in_latitude is None or attendance.check_in_longitude is None:
            return "UNVERIFIED"
        if distance is None:
            return "UNCONFIGURED"

        settings = OrganizationSettingsService.get_settings()
        accuracy = float(attendance.check_in_accuracy_meters or Decimal("0"))
        allowed_radius = float(settings.office_radius_meters or 0) + min(accuracy, 100)
        return "OFFICE" if distance <= allowed_radius else "REMOTE"

    @staticmethod
    def _resolve_status_from_location(status, latitude, longitude, accuracy_meters):
        if status == Attendance.Status.HALF_DAY:
            return status
        if latitude is None or longitude is None:
            return status or Attendance.Status.PRESENT

        settings = OrganizationSettingsService.get_settings()
        if settings.office_latitude is None or settings.office_longitude is None:
            return status or Attendance.Status.PRESENT

        distance = GeoUtils.calculate_distance(
            float(settings.office_latitude),
            float(settings.office_longitude),
            float(latitude),
            float(longitude),
        )
        accuracy = float(accuracy_meters or Decimal("0"))
        allowed_radius = float(settings.office_radius_meters or 0) + min(accuracy, 100)
        return Attendance.Status.PRESENT if distance <= allowed_radius else Attendance.Status.REMOTE

    @staticmethod
    @transaction.atomic
    def check_in(
        user,
        notes="",
        status="PRESENT",
        check_in_latitude=None,
        check_in_longitude=None,
        check_in_accuracy_meters=None,
    ):
        employee = getattr(user, "employee_profile", None)
        if not employee:
            raise exceptions.PermissionDenied("Employee profile not found for the current user.")

        today = timezone.localdate()
        current_time = timezone.now()
        resolved_status = AttendanceService._resolve_status_from_location(
            status,
            check_in_latitude,
            check_in_longitude,
            check_in_accuracy_meters,
        )
        attendance, created = Attendance.objects.select_for_update().get_or_create(
            employee=employee,
            attendance_date=today,
            defaults={
                "status": resolved_status,
                "notes": notes,
                "check_in": current_time,
                "current_session_check_in": current_time,
                "check_in_latitude": check_in_latitude,
                "check_in_longitude": check_in_longitude,
                "check_in_accuracy_meters": check_in_accuracy_meters,
            },
        )
        if not created and attendance.current_session_check_in:
            raise exceptions.ValidationError({"attendance": "You have already checked in today."})

        if not attendance.check_in:
            attendance.check_in = current_time
        attendance.current_session_check_in = current_time
        attendance.break_started_at = None
        attendance.current_session_break_minutes = 0
        if created:
            attendance.break_minutes = 0
            attendance.total_work_minutes = 0
        attendance.notes = notes or attendance.notes
        attendance.status = resolved_status
        if attendance.check_in_latitude is None and check_in_latitude is not None:
            attendance.check_in_latitude = check_in_latitude
            attendance.check_in_longitude = check_in_longitude
            attendance.check_in_accuracy_meters = check_in_accuracy_meters
        attendance.save()
        AuditService.log(actor=user, action="attendance.check_in", entity=attendance, after=attendance)
        return attendance

    @staticmethod
    @transaction.atomic
    def check_out(user, notes=""):
        employee = getattr(user, "employee_profile", None)
        if not employee:
            raise exceptions.PermissionDenied("Employee profile not found for the current user.")

        today = timezone.localdate()
        attendance = Attendance.objects.select_for_update().filter(employee=employee, attendance_date=today).first()
        if not attendance or not attendance.current_session_check_in:
            raise exceptions.ValidationError({"attendance": "Check-in is required before check-out."})

        current_time = timezone.now()
        if attendance.break_started_at:
            attendance.current_session_break_minutes = AttendanceService.calculate_current_session_break_minutes(
                attendance, reference_time=current_time
            )
            attendance.break_started_at = None

        session_minutes = max(int((current_time - attendance.current_session_check_in).total_seconds() // 60), 0)
        session_work_minutes = max(session_minutes - attendance.current_session_break_minutes, 0)

        attendance.check_out = current_time
        attendance.notes = notes or attendance.notes
        attendance.total_work_minutes = (attendance.total_work_minutes or 0) + session_work_minutes
        attendance.break_minutes = (attendance.break_minutes or 0) + (attendance.current_session_break_minutes or 0)
        attendance.current_session_check_in = None
        attendance.current_session_break_minutes = 0
        attendance.save()
        AuditService.log(actor=user, action="attendance.check_out", entity=attendance, after=attendance)
        return attendance

    @staticmethod
    @transaction.atomic
    def start_break(user, notes=""):
        employee = getattr(user, "employee_profile", None)
        if not employee:
            raise exceptions.PermissionDenied("Employee profile not found for the current user.")

        today = timezone.localdate()
        attendance = Attendance.objects.select_for_update().filter(employee=employee, attendance_date=today).first()
        if not attendance or not attendance.current_session_check_in:
            raise exceptions.ValidationError({"attendance": "Check-in is required before taking a break."})
        if attendance.break_started_at:
            raise exceptions.ValidationError({"attendance": "A break is already in progress."})

        attendance.break_started_at = timezone.now()
        attendance.notes = notes or attendance.notes
        attendance.save()
        AuditService.log(actor=user, action="attendance.break_started", entity=attendance, after=attendance)
        return attendance

    @staticmethod
    @transaction.atomic
    def end_break(user, notes=""):
        employee = getattr(user, "employee_profile", None)
        if not employee:
            raise exceptions.PermissionDenied("Employee profile not found for the current user.")

        today = timezone.localdate()
        attendance = Attendance.objects.select_for_update().filter(employee=employee, attendance_date=today).first()
        if not attendance or not attendance.current_session_check_in:
            raise exceptions.ValidationError({"attendance": "Check-in is required before ending a break."})
        if not attendance.break_started_at:
            raise exceptions.ValidationError({"attendance": "There is no active break to end."})

        attendance.current_session_break_minutes = AttendanceService.calculate_current_session_break_minutes(attendance)
        attendance.break_started_at = None
        attendance.notes = notes or attendance.notes
        attendance.save()
        AuditService.log(actor=user, action="attendance.break_ended", entity=attendance, after=attendance)
        return attendance
