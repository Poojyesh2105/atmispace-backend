from django.db.models import Q

from apps.accounts.models import User
from apps.attendance.models import Attendance, AttendanceRegularization, BiometricAttendanceEvent, BiometricDevice
from apps.employees.selectors import EmployeeSelectors


class AttendanceSelectors:
    @staticmethod
    def get_attendance_queryset_for_user(user):
        queryset = Attendance.objects.for_current_org(user).select_related("employee__user", "employee__department")
        employee = getattr(user, "employee_profile", None)

        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            team_ids = EmployeeSelectors.get_team_member_ids(employee)
            return queryset.filter(Q(employee=employee) | Q(employee_id__in=team_ids))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def get_regularization_queryset_for_user(user):
        queryset = AttendanceRegularization.objects.for_current_org(user).select_related("employee__user", "approver")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            team_ids = EmployeeSelectors.get_team_member_ids(employee)
            return queryset.filter(Q(employee=employee) | Q(employee_id__in=team_ids))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def get_biometric_device_queryset(user=None):
        return BiometricDevice.objects.for_current_org(user)

    @staticmethod
    def get_biometric_event_queryset_for_user(user):
        queryset = BiometricAttendanceEvent.objects.for_current_org(user).select_related("device", "employee__user", "attendance")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            team_ids = EmployeeSelectors.get_team_member_ids(employee)
            return queryset.filter(Q(employee=employee) | Q(employee_id__in=team_ids))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()
