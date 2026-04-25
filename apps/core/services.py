from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Sum, Q
from django.utils import timezone

from apps.core.models import Organization
from apps.employees.selectors import EmployeeSelectors
from apps.leave_management.models import LeaveBalance, LeaveRequest
from apps.workflow.services.workflow_service import WorkflowService


class OrganizationService:
    @staticmethod
    def get_default_organization():
        
        return Organization.objects.filter(is_active=True, is_default=True).order_by("id").first()

    @staticmethod
    def resolve_for_actor(actor=None, organization=None):
        if organization is not None:
            return organization
        if actor is not None and getattr(actor, "organization_id", None):
            return actor.organization
        return OrganizationService.get_default_organization()


class DashboardService:
    
    @staticmethod
    def _get_scope(user):
        from apps.attendance.services.attendance_service import AttendanceService
        employee = getattr(user, "employee_profile", None)
        employee_qs = EmployeeSelectors.base_employee_queryset(user)
        leave_qs = LeaveRequest.objects.for_current_org(user).select_related("employee__user", "approver")
        attendance_qs = AttendanceService.get_queryset_for_user(user)

        if user.role == "EMPLOYEE" and employee:
            return (
                employee_qs.filter(pk=employee.pk),
                leave_qs.filter(employee=employee),
                attendance_qs.filter(employee=employee),
            )
        if user.role == "MANAGER" and employee:
            team_ids = EmployeeSelectors.get_team_member_ids(employee)
            return (
                employee_qs.filter(Q(pk=employee.pk) | Q(pk__in=team_ids)),
                leave_qs.filter(Q(employee=employee) | Q(employee_id__in=team_ids)),
                attendance_qs.filter(Q(employee=employee) | Q(employee_id__in=team_ids)),
            )
        return employee_qs, leave_qs, attendance_qs

    @staticmethod
    def _get_today_attendance_summary(attendance_qs, today):
        from apps.attendance.services.attendance_service import AttendanceService
        today_qs = attendance_qs.filter(attendance_date=today)
        present_today = today_qs.exclude(check_in__isnull=True).count()
        total_work_minutes = sum(AttendanceService.calculate_work_minutes(attendance) for attendance in today_qs)
        average_hours = round((total_work_minutes / 60) / present_today, 2) if present_today else 0
        return {
            "present_today": present_today,
            "average_hours_today": average_hours,
            "checked_in_count": today_qs.filter(current_session_check_in__isnull=False).count(),
            "on_break_count": today_qs.filter(break_started_at__isnull=False).count(),
        }

    @staticmethod
    def _get_team_on_leave(leave_qs, today):
        return list(
            leave_qs.filter(status=LeaveRequest.Status.APPROVED, start_date__lte=today, end_date__gte=today)
            .values("employee__user__first_name", "employee__user__last_name", "employee__employee_id", "leave_type", "total_days")
            .order_by("employee__employee_id")
        )

    @staticmethod
    def _get_leave_balance_summary(employee_qs):
        return list(
            LeaveBalance.objects.filter(employee__in=employee_qs)
            .values("leave_type")
            .annotate(
                allocated_days=Sum("allocated_days"),
                used_days=Sum("used_days"),
            )
            .order_by("leave_type")
        )

    @staticmethod
    def get_summary(user):
        cache_key = f"dashboard:summary:{getattr(user, 'organization_id', 'global')}:{user.role}:{user.pk}"

        def build_summary():
            from apps.attendance.services.attendance_service import AttendanceService
            today = timezone.localdate()
            employee_qs, base_leave_qs, attendance_qs = DashboardService._get_scope(user)
            base_attendance_qs = attendance_qs.filter(attendance_date=today)
            pending_leaves = base_leave_qs.filter(status="PENDING").count()
            approved_leaves = base_leave_qs.filter(status="APPROVED").count()
            present_today = base_attendance_qs.exclude(check_in__isnull=True).count()
            department_breakdown = list(
                employee_qs.values("department__name").annotate(total=Count("id")).order_by("department__name")
            )
            total_work_minutes = sum(AttendanceService.calculate_work_minutes(attendance) for attendance in base_attendance_qs)
            total_hours = total_work_minutes / 60

            return {
                "employee_count": employee_qs.count(),
                "pending_leaves": pending_leaves,
                "approved_leaves": approved_leaves,
                "present_today": present_today,
                "average_hours_today": round(total_hours / present_today, 2) if present_today else 0,
                "departments": department_breakdown,
            }

        return cache.get_or_set(cache_key, build_summary, timeout=settings.DASHBOARD_CACHE_TTL_SECONDS)

    @staticmethod
    def get_employee_dashboard(user):
        from apps.attendance.services.attendance_service import AttendanceService
        employee = getattr(user, "employee_profile", None)
        today = timezone.localdate()
        employee_qs, leave_qs, attendance_qs = DashboardService._get_scope(user)
        today_attendance = attendance_qs.filter(attendance_date=today).first()
        leave_balances = list(
            LeaveBalance.objects.filter(employee=employee).values("leave_type", "allocated_days", "used_days")
        ) if employee else []
        return {
            "today_attendance": {
                "status": getattr(today_attendance, "status", "ABSENT"),
                "is_checked_in": bool(getattr(today_attendance, "current_session_check_in", None)),
                "is_on_break": bool(getattr(today_attendance, "break_started_at", None)),
                "worked_minutes": AttendanceService.calculate_work_minutes(today_attendance) if today_attendance else 0,
                "expected_shift_minutes": AttendanceService.get_expected_shift_minutes(employee) if employee else 0,
            },
            "pending_approvals": WorkflowService.list_pending_approvals_for_user(user).count(),
            "team_on_leave": [],
            "leave_balance_summary": leave_balances,
            "attendance_summary": DashboardService._get_today_attendance_summary(attendance_qs, today),
        }

    @staticmethod
    def get_manager_dashboard(user):
        today = timezone.localdate()
        employee_qs, leave_qs, attendance_qs = DashboardService._get_scope(user)
        return {
            "today_attendance": DashboardService._get_today_attendance_summary(attendance_qs, today),
            "pending_approvals": WorkflowService.list_pending_approvals_for_user(user).count(),
            "team_on_leave": DashboardService._get_team_on_leave(leave_qs, today),
            "leave_balance_summary": DashboardService._get_leave_balance_summary(employee_qs),
            "team_availability": {
                "total": employee_qs.count(),
                "on_leave": leave_qs.filter(status=LeaveRequest.Status.APPROVED, start_date__lte=today, end_date__gte=today).count(),
                "checked_in": attendance_qs.filter(attendance_date=today, current_session_check_in__isnull=False).count(),
            },
        }

    @staticmethod
    def get_hr_dashboard(user):
        today = timezone.localdate()
        employee_qs, leave_qs, attendance_qs = DashboardService._get_scope(user)
        department_breakdown = list(
            employee_qs.values("department__name").annotate(total=Count("id")).order_by("department__name")
        )
        return {
            "today_attendance": DashboardService._get_today_attendance_summary(attendance_qs, today),
            "pending_approvals": WorkflowService.list_pending_approvals_for_user(user).count(),
            "team_on_leave": DashboardService._get_team_on_leave(leave_qs, today),
            "leave_balance_summary": DashboardService._get_leave_balance_summary(employee_qs),
            "team_availability": {
                "total": employee_qs.count(),
                "on_leave": leave_qs.filter(status=LeaveRequest.Status.APPROVED, start_date__lte=today, end_date__gte=today).count(),
                "checked_in": attendance_qs.filter(attendance_date=today, current_session_check_in__isnull=False).count(),
            },
            "departments": department_breakdown,
        }
