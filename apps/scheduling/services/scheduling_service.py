from datetime import timedelta

from django.db import transaction

from apps.audit.services.audit_service import AuditService
from apps.core.services import OrganizationService
from apps.holidays.services.holiday_service import HolidayService
from apps.lifecycle.models import OffboardingCase
from apps.notifications.services.notification_service import NotificationService
from apps.scheduling.models import ScheduleConflict, ShiftRosterEntry, ShiftRotationRule


class ShiftRotationRuleService:
    @staticmethod
    def create_rule(validated_data, actor):
        if organization := OrganizationService.resolve_for_actor(actor):
            validated_data.setdefault("organization", organization)
        rule = ShiftRotationRule.objects.create(**validated_data)
        AuditService.log(actor=actor, action="scheduling.rotation_rule.created", entity=rule, after=rule)
        return rule

    @staticmethod
    def update_rule(instance, validated_data, actor):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="scheduling.rotation_rule.updated", entity=instance, before=before, after=instance)
        return instance


class SchedulingService:
    @staticmethod
    def _record_conflict(entry, conflict_type, message, actor):
        entry.is_conflicted = True
        entry.save(update_fields=["is_conflicted", "updated_at"])
        return ScheduleConflict.objects.create(
            organization=entry.organization,
            roster_entry=entry,
            conflict_type=conflict_type,
            message=message,
            reported_by=actor,
        )

    @staticmethod
    def _apply_holiday_awareness(entry, actor):
        holiday_dates = HolidayService.get_holiday_dates_for_employee(entry.employee, entry.roster_date, entry.roster_date)
        if entry.roster_date in holiday_dates:
            entry.is_holiday = True
            entry.save(update_fields=["is_holiday", "updated_at"])
            SchedulingService._record_conflict(
                entry,
                ScheduleConflict.ConflictType.HOLIDAY,
                f"Roster date {entry.roster_date.isoformat()} is a holiday for this employee.",
                actor,
            )

    @staticmethod
    def _apply_offboarding_awareness(entry, actor):
        offboarding_case = (
            OffboardingCase.objects.filter(employee=entry.employee, status__in=[OffboardingCase.Status.IN_PROGRESS, OffboardingCase.Status.COMPLETED])
            .order_by("-created_at")
            .first()
        )
        if offboarding_case and entry.roster_date > offboarding_case.last_working_day:
            SchedulingService._record_conflict(
                entry,
                ScheduleConflict.ConflictType.OFFBOARDING,
                "Roster entry is after the employee's last working day.",
                actor,
            )

    @staticmethod
    @transaction.atomic
    def assign_shift(employee, roster_date, shift_template, actor, source=ShiftRosterEntry.Source.MANUAL, notes=""):
        entry, _ = ShiftRosterEntry.objects.update_or_create(
            employee=employee,
            roster_date=roster_date,
            defaults={
                "organization": employee.organization or OrganizationService.resolve_for_actor(actor),
                "shift_template": shift_template,
                "source": source,
                "notes": notes,
                "is_holiday": False,
                "is_conflicted": False,
            },
        )
        if not employee.is_active or not employee.user.is_active:
            SchedulingService._record_conflict(entry, ScheduleConflict.ConflictType.INACTIVE_EMPLOYEE, "Employee is inactive.", actor)
        SchedulingService._apply_holiday_awareness(entry, actor)
        SchedulingService._apply_offboarding_awareness(entry, actor)
        AuditService.log(actor=actor, action="scheduling.roster_entry.saved", entity=entry, after=entry)
        return entry

    @staticmethod
    def bulk_assign(employee_list, shift_template, start_date, end_date, actor):
        entries = []
        current_date = start_date
        while current_date <= end_date:
            for employee in employee_list:
                entries.append(
                    SchedulingService.assign_shift(employee, current_date, shift_template, actor, source=ShiftRosterEntry.Source.BULK)
                )
            current_date += timedelta(days=1)
        return entries

    @staticmethod
    def apply_rotation(rule, employee_list, start_date, end_date, actor):
        entries = []
        if not rule.rotation_pattern:
            return entries
        pattern = list(rule.rotation_pattern)
        current_date = start_date
        offset = 0
        while current_date <= end_date:
            shift_template_id = pattern[offset % len(pattern)]
            for employee in employee_list:
                entries.append(
                    SchedulingService.assign_shift(
                        employee,
                        current_date,
                        employee.shift_template.__class__.objects.get(pk=shift_template_id),
                        actor,
                        source=ShiftRosterEntry.Source.ROTATION,
                        notes=f"Applied from rotation rule {rule.name}",
                    )
                )
            current_date += timedelta(days=1)
            offset += 1
        NotificationService.create_notification(
            actor,
            NotificationService._resolve_type("GENERIC"),
            "Shift rotation applied",
            f"Rotation rule {rule.name} was applied successfully.",
        )
        return entries
