from collections import Counter
from datetime import timedelta

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.accounts.models import User
from apps.analytics.models import AnalyticsSnapshot
from apps.attendance.models import Attendance
from apps.attendance.services.attendance_service import AttendanceService
from apps.documents.models import EmployeeDocument
from apps.employees.models import Employee
from apps.leave_management.models import LeaveRequest
from apps.lifecycle.models import OffboardingCase
from apps.payroll.models import PayrollCycle, PayrollRun


class AnalyticsService:
    @staticmethod
    def _employee_queryset_for_user(user):
        queryset = Employee.objects.select_related("user", "manager", "secondary_manager")
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ADMIN, User.Role.ACCOUNTS}:
            return queryset.filter(is_active=True, user__is_active=True)
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(
                is_active=True,
                user__is_active=True,
            ).filter(
                Q(pk=employee.pk) | Q(manager=employee) | Q(secondary_manager=employee)
            )
        return queryset.none()

    @staticmethod
    def _employee_ids_for_user(user):
        return list(AnalyticsService._employee_queryset_for_user(user).values_list("pk", flat=True))

    @staticmethod
    def get_dashboard(user):
        employee_ids = AnalyticsService._employee_ids_for_user(user)
        today = timezone.localdate()
        month_start = today.replace(day=1)
        trailing_start = month_start - timedelta(days=150)

        employee_queryset = Employee.objects.filter(pk__in=employee_ids)
        active_headcount = employee_queryset.count()
        department_breakdown = list(
            employee_queryset.values(label=F("department__name")).annotate(value=Count("id")).order_by("-value", "label")
        )

        attrition_count = OffboardingCase.objects.filter(
            employee_id__in=employee_ids,
            actual_exit_date__gte=month_start,
            actual_exit_date__lte=today,
            status=OffboardingCase.Status.COMPLETED,
        ).count()

        leave_trend = list(
            LeaveRequest.objects.filter(
                employee_id__in=employee_ids,
                status=LeaveRequest.Status.APPROVED,
                start_date__gte=trailing_start,
            )
            .annotate(period=TruncMonth("start_date"))
            .values("period")
            .annotate(total=Sum("total_days"))
            .order_by("period")
        )
        leave_trend = [
            {
                "label": item["period"].strftime("%Y-%m") if item["period"] else "",
                "value": float(item["total"] or 0),
            }
            for item in leave_trend
        ]

        overtime_trend = []
        overtime_counter = Counter()
        for attendance in Attendance.objects.filter(
            employee_id__in=employee_ids,
            attendance_date__gte=trailing_start,
        ):
            expected_shift_minutes = AttendanceService.get_expected_shift_minutes(attendance.employee)
            overtime_minutes = max((attendance.total_work_minutes or 0) - expected_shift_minutes, 0)
            if overtime_minutes:
                month_key = attendance.attendance_date.strftime("%Y-%m")
                overtime_counter[month_key] += overtime_minutes
        for month_key, minutes in sorted(overtime_counter.items()):
            overtime_trend.append({"label": month_key, "value": round(minutes / 60, 2)})

        payroll_cycle = PayrollCycle.objects.order_by("-payroll_month", "-created_at").first()
        payroll_run = PayrollRun.objects.select_related("cycle").order_by("-created_at").first()
        payroll_readiness = {
            "latest_cycle": payroll_cycle.name if payroll_cycle else "",
            "cycle_status": payroll_cycle.status if payroll_cycle else "",
            "run_status": payroll_run.status if payroll_run else "",
            "total_employees": payroll_run.total_employees if payroll_run else 0,
        }

        document_expiry_rows = list(
            EmployeeDocument.objects.filter(
                employee_id__in=employee_ids,
                expiry_date__isnull=False,
                expiry_date__gte=today,
                expiry_date__lte=today + timedelta(days=45),
            )
            .select_related("employee__user", "document_type")
            .order_by("expiry_date")
            .values(
                "expiry_date",
                employee_name=F("employee__user__first_name"),
                employee_code=F("employee__employee_id"),
                document_type_name=F("document_type__name"),
            )
        )
        document_expiry = [
            {
                "employee_name": item["employee_name"],
                "employee_code": item["employee_code"],
                "document_type": item["document_type_name"],
                "expiry_date": item["expiry_date"],
            }
            for item in document_expiry_rows
        ]

        cards = [
            {"label": "Active headcount", "value": active_headcount, "helper": "Current visible workforce"},
            {"label": "Attrition this month", "value": attrition_count, "helper": "Completed exits in the current month"},
            {"label": "Departments covered", "value": len(department_breakdown), "helper": "Departments in current visibility scope"},
        ]
        if user.role in {User.Role.HR, User.Role.ADMIN, User.Role.ACCOUNTS}:
            cards.append(
                {
                    "label": "Payroll readiness",
                    "value": payroll_readiness["run_status"] or "N/A",
                    "helper": payroll_readiness["latest_cycle"] or "No payroll cycle",
                }
            )

        return {
            "cards": cards,
            "department_breakdown": department_breakdown,
            "leave_trend": leave_trend,
            "overtime_trend": overtime_trend,
            "payroll_readiness": payroll_readiness,
            "document_expiry": document_expiry,
        }

    @staticmethod
    def refresh_snapshots(snapshot_date=None):
        snapshot_date = snapshot_date or timezone.localdate()
        payload = AnalyticsService.get_dashboard(type("AnalyticsUser", (), {"role": User.Role.ADMIN, "employee_profile": None})())
        snapshots = []
        for metric_key, key in (
            (AnalyticsSnapshot.MetricKey.HEADCOUNT, "cards"),
            (AnalyticsSnapshot.MetricKey.LEAVE_TREND, "leave_trend"),
            (AnalyticsSnapshot.MetricKey.OVERTIME_TREND, "overtime_trend"),
            (AnalyticsSnapshot.MetricKey.PAYROLL_READINESS, "payroll_readiness"),
            (AnalyticsSnapshot.MetricKey.DOCUMENT_EXPIRY, "document_expiry"),
        ):
            snapshot, _ = AnalyticsSnapshot.objects.update_or_create(
                snapshot_date=snapshot_date,
                metric_key=metric_key,
                role_scope="ADMIN",
                defaults={"payload": payload.get(key, {})},
            )
            snapshots.append(snapshot)
        return snapshots
