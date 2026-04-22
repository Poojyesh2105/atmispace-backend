from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework import exceptions

from apps.attendance.models import Attendance, BiometricAttendanceEvent, BiometricDevice
from apps.attendance.services.attendance_service import AttendanceService
from apps.audit.services.audit_service import AuditService
from apps.employees.models import Employee


class BiometricAttendanceService:
    EVENT_ALIASES = {
        "AUTO": BiometricAttendanceEvent.EventType.AUTO,
        "PUNCH": BiometricAttendanceEvent.EventType.AUTO,
        "CHECK_IN": BiometricAttendanceEvent.EventType.CHECK_IN,
        "CHECKIN": BiometricAttendanceEvent.EventType.CHECK_IN,
        "CLOCK_IN": BiometricAttendanceEvent.EventType.CHECK_IN,
        "IN": BiometricAttendanceEvent.EventType.CHECK_IN,
        "CHECK_OUT": BiometricAttendanceEvent.EventType.CHECK_OUT,
        "CHECKOUT": BiometricAttendanceEvent.EventType.CHECK_OUT,
        "CLOCK_OUT": BiometricAttendanceEvent.EventType.CHECK_OUT,
        "OUT": BiometricAttendanceEvent.EventType.CHECK_OUT,
        "BREAK_START": BiometricAttendanceEvent.EventType.BREAK_START,
        "BREAK_IN": BiometricAttendanceEvent.EventType.BREAK_START,
        "LUNCH_OUT": BiometricAttendanceEvent.EventType.BREAK_START,
        "BREAK_OUT": BiometricAttendanceEvent.EventType.BREAK_END,
        "BREAK_END": BiometricAttendanceEvent.EventType.BREAK_END,
        "LUNCH_IN": BiometricAttendanceEvent.EventType.BREAK_END,
    }

    @classmethod
    def normalize_event_type(cls, value):
        normalized = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        event_type = cls.EVENT_ALIASES.get(normalized)
        if not event_type:
            raise exceptions.ValidationError({"event_type": "Unsupported biometric event type."})
        return event_type

    @staticmethod
    def authenticate_device(device_code, secret_key):
        device = BiometricDevice.objects.filter(device_code=device_code, is_active=True).first()
        if not device or not constant_time_compare(device.secret_key, secret_key):
            raise exceptions.AuthenticationFailed("Invalid biometric device credentials.")

        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at", "updated_at"])
        return device

    @staticmethod
    def _local_attendance_date(occurred_at):
        return timezone.localtime(occurred_at).date()

    @staticmethod
    def _get_existing_event(device, device_user_id, event_type, occurred_at):
        return (
            BiometricAttendanceEvent.objects.select_for_update()
            .filter(
                device=device,
                device_user_id=device_user_id,
                event_type=event_type,
                occurred_at=occurred_at,
            )
            .first()
        )

    @classmethod
    @transaction.atomic
    def ingest_event(cls, validated_data):
        device = cls.authenticate_device(validated_data["device_code"], validated_data["secret_key"])
        device_user_id = validated_data["biometric_id"].strip()
        event_type = cls.normalize_event_type(validated_data["event_type"])
        occurred_at = validated_data["occurred_at"]
        if timezone.is_naive(occurred_at):
            occurred_at = timezone.make_aware(occurred_at, timezone.get_current_timezone())

        external_event_id = validated_data.get("external_event_id") or None
        raw_payload = validated_data.get("raw_payload") or {}

        if external_event_id:
            event, created = BiometricAttendanceEvent.objects.select_for_update().get_or_create(
                device=device,
                external_event_id=external_event_id,
                defaults={
                    "device_user_id": device_user_id,
                    "event_type": event_type,
                    "occurred_at": occurred_at,
                    "raw_payload": raw_payload,
                },
            )
            if not created:
                return event
        else:
            event = cls._get_existing_event(device, device_user_id, event_type, occurred_at)
            if event:
                return event
            event = BiometricAttendanceEvent.objects.create(
                device=device,
                device_user_id=device_user_id,
                event_type=event_type,
                occurred_at=occurred_at,
                raw_payload=raw_payload,
            )

        employee = Employee.objects.filter(biometric_id__iexact=device_user_id, is_active=True).first()
        if not employee:
            event.status = BiometricAttendanceEvent.Status.FAILED
            event.message = "No active employee is mapped to this biometric ID."
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "message", "processed_at", "updated_at"])
            return event

        attendance, event_status, message = cls.apply_attendance_event(employee, event_type, occurred_at)
        event.employee = employee
        event.attendance = attendance
        event.status = event_status
        event.message = message
        event.processed_at = timezone.now()
        event.save(update_fields=["employee", "attendance", "status", "message", "processed_at", "updated_at"])
        return event

    @classmethod
    @transaction.atomic
    def apply_attendance_event(cls, employee, event_type, occurred_at):
        attendance_date = cls._local_attendance_date(occurred_at)
        attendance = (
            Attendance.objects.select_for_update()
            .filter(employee=employee, attendance_date=attendance_date)
            .first()
        )

        resolved_event_type = event_type
        if event_type == BiometricAttendanceEvent.EventType.AUTO:
            resolved_event_type = cls._resolve_auto_event_type(attendance)

        if resolved_event_type == BiometricAttendanceEvent.EventType.CHECK_IN:
            return cls._apply_check_in(employee, attendance, attendance_date, occurred_at, event_type)
        if resolved_event_type == BiometricAttendanceEvent.EventType.CHECK_OUT:
            return cls._apply_check_out(attendance, occurred_at, event_type)
        if resolved_event_type == BiometricAttendanceEvent.EventType.BREAK_START:
            return cls._apply_break_start(attendance, occurred_at)
        return cls._apply_break_end(attendance, occurred_at)

    @staticmethod
    def _resolve_auto_event_type(attendance):
        if not attendance or not attendance.current_session_check_in:
            return BiometricAttendanceEvent.EventType.CHECK_IN
        if attendance.break_started_at:
            return BiometricAttendanceEvent.EventType.BREAK_END
        return BiometricAttendanceEvent.EventType.CHECK_OUT

    @staticmethod
    def _message(action, original_event_type):
        if original_event_type == BiometricAttendanceEvent.EventType.AUTO:
            return f"Auto punch processed as {action}."
        return f"Biometric {action} processed."

    @classmethod
    def _apply_check_in(cls, employee, attendance, attendance_date, occurred_at, original_event_type):
        if attendance and attendance.current_session_check_in:
            return (
                attendance,
                BiometricAttendanceEvent.Status.IGNORED,
                "Employee already has an active attendance session.",
            )

        created = False
        if not attendance:
            attendance = Attendance.objects.create(
                employee=employee,
                attendance_date=attendance_date,
                status=Attendance.Status.PRESENT,
                source=Attendance.Source.BIOMETRIC,
                check_in=occurred_at,
                current_session_check_in=occurred_at,
            )
            created = True

        before = {} if created else AuditService.snapshot(attendance)
        if not attendance.check_in or occurred_at < attendance.check_in:
            attendance.check_in = occurred_at
        attendance.current_session_check_in = occurred_at
        attendance.break_started_at = None
        attendance.current_session_break_minutes = 0
        attendance.status = Attendance.Status.PRESENT
        attendance.source = Attendance.Source.BIOMETRIC
        attendance.notes = attendance.notes or "Recorded from biometric device."
        attendance.save()
        AuditService.log(actor=None, action="attendance.biometric_check_in", entity=attendance, before=before, after=attendance)
        return (
            attendance,
            BiometricAttendanceEvent.Status.PROCESSED,
            cls._message("check-in", original_event_type),
        )

    @classmethod
    def _apply_check_out(cls, attendance, occurred_at, original_event_type):
        if not attendance or not attendance.current_session_check_in:
            return (
                attendance,
                BiometricAttendanceEvent.Status.IGNORED,
                "Check-out ignored because no active attendance session exists.",
            )

        before = AuditService.snapshot(attendance)
        if attendance.break_started_at:
            attendance.current_session_break_minutes = AttendanceService.calculate_current_session_break_minutes(
                attendance,
                reference_time=occurred_at,
            )
            attendance.break_started_at = None

        session_minutes = max(int((occurred_at - attendance.current_session_check_in).total_seconds() // 60), 0)
        session_work_minutes = max(session_minutes - (attendance.current_session_break_minutes or 0), 0)
        if not attendance.check_out or occurred_at > attendance.check_out:
            attendance.check_out = occurred_at
        attendance.total_work_minutes = (attendance.total_work_minutes or 0) + session_work_minutes
        attendance.break_minutes = (attendance.break_minutes or 0) + (attendance.current_session_break_minutes or 0)
        attendance.current_session_check_in = None
        attendance.current_session_break_minutes = 0
        attendance.source = Attendance.Source.BIOMETRIC
        attendance.save()
        AuditService.log(actor=None, action="attendance.biometric_check_out", entity=attendance, before=before, after=attendance)
        return (
            attendance,
            BiometricAttendanceEvent.Status.PROCESSED,
            cls._message("check-out", original_event_type),
        )

    @staticmethod
    def _apply_break_start(attendance, occurred_at):
        if not attendance or not attendance.current_session_check_in:
            return (
                attendance,
                BiometricAttendanceEvent.Status.IGNORED,
                "Break start ignored because no active attendance session exists.",
            )
        if attendance.break_started_at:
            return (
                attendance,
                BiometricAttendanceEvent.Status.IGNORED,
                "Break start ignored because a break is already active.",
            )
        if occurred_at < attendance.current_session_check_in:
            return (
                attendance,
                BiometricAttendanceEvent.Status.IGNORED,
                "Break start ignored because it is earlier than check-in.",
            )

        before = AuditService.snapshot(attendance)
        attendance.break_started_at = occurred_at
        attendance.break_count = (attendance.break_count or 0) + 1
        attendance.source = Attendance.Source.BIOMETRIC
        attendance.save()
        AuditService.log(actor=None, action="attendance.biometric_break_started", entity=attendance, before=before, after=attendance)
        return attendance, BiometricAttendanceEvent.Status.PROCESSED, "Biometric break start processed."

    @staticmethod
    def _apply_break_end(attendance, occurred_at):
        if not attendance or not attendance.current_session_check_in:
            return (
                attendance,
                BiometricAttendanceEvent.Status.IGNORED,
                "Break end ignored because no active attendance session exists.",
            )
        if not attendance.break_started_at:
            return (
                attendance,
                BiometricAttendanceEvent.Status.IGNORED,
                "Break end ignored because no active break exists.",
            )
        if occurred_at < attendance.break_started_at:
            return (
                attendance,
                BiometricAttendanceEvent.Status.IGNORED,
                "Break end ignored because it is earlier than the break start.",
            )

        before = AuditService.snapshot(attendance)
        attendance.current_session_break_minutes = AttendanceService.calculate_current_session_break_minutes(
            attendance,
            reference_time=occurred_at,
        )
        attendance.break_started_at = None
        attendance.source = Attendance.Source.BIOMETRIC
        attendance.save()
        AuditService.log(actor=None, action="attendance.biometric_break_ended", entity=attendance, before=before, after=attendance)
        return attendance, BiometricAttendanceEvent.Status.PROCESSED, "Biometric break end processed."
