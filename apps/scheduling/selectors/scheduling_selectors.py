from django.db.models import Q

from apps.accounts.models import User
from apps.scheduling.models import ScheduleConflict, ShiftRosterEntry, ShiftRotationRule


class SchedulingSelectors:
    @staticmethod
    def get_rotation_rule_queryset():
        return ShiftRotationRule.objects.select_related("department").all()

    @staticmethod
    def get_roster_queryset_for_user(user):
        queryset = ShiftRosterEntry.objects.select_related("employee__user", "employee__manager", "shift_template")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.MANAGER, User.Role.HR, User.Role.ADMIN}:
            if user.role == User.Role.MANAGER and employee:
                return queryset.filter(Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee))
            return queryset
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def get_conflict_queryset_for_user(user):
        queryset = ScheduleConflict.objects.select_related("roster_entry__employee__user", "reported_by")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.MANAGER, User.Role.HR, User.Role.ADMIN}:
            if user.role == User.Role.MANAGER and employee:
                return queryset.filter(
                    Q(roster_entry__employee=employee)
                    | Q(roster_entry__employee__manager=employee)
                    | Q(roster_entry__employee__secondary_manager=employee)
                )
            return queryset
        if employee:
            return queryset.filter(roster_entry__employee=employee)
        return queryset.none()

