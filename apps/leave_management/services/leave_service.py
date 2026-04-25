from decimal import Decimal
from datetime import date as _date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User
from apps.audit.services.audit_service import AuditService
from apps.core.services import OrganizationService
from apps.employees.selectors import EmployeeSelectors
from apps.holidays.services.holiday_service import HolidayService
from apps.leave_management.models import EarnedLeaveAdjustment, LeaveBalance, LeavePolicy, LeaveRequest
from apps.notifications.services.notification_service import NotificationService
from apps.workflow.models import ApprovalInstance, Workflow
from apps.workflow.services.workflow_service import WorkflowService


class LeavePolicyService:
    @staticmethod
    def get_policy(actor=None, organization=None):
        resolved_organization = OrganizationService.resolve_for_actor(actor, organization=organization)
        if resolved_organization:
            policy, _ = LeavePolicy.objects.get_or_create(organization=resolved_organization)
        else:
            policy, _ = LeavePolicy.objects.get_or_create(pk=1)
        return policy

    @staticmethod
    def update_policy(validated_data, actor=None, organization=None):
        policy = LeavePolicyService.get_policy(actor=actor, organization=organization)
        for attr, value in validated_data.items():
            setattr(policy, attr, value)
        if resolved_organization := OrganizationService.resolve_for_actor(actor, organization=organization):
            policy.organization = resolved_organization
        policy.save()
        return policy


class LeaveBalanceService:
    @staticmethod
    def get_queryset_for_user(user):
        queryset = LeaveBalance.objects.for_current_org(user).select_related("employee__user")
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
    def create_balance(validated_data):
        validated_data.setdefault("organization", getattr(validated_data.get("employee"), "organization", None))
        balance = LeaveBalance.objects.create(**validated_data)
        AuditService.log(actor=None, action="leave.balance.created", entity=balance, after=balance)
        return balance

    @staticmethod
    def update_balance(instance, validated_data):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=None, action="leave.balance.updated", entity=instance, before=before, after=instance)
        return instance


class LeaveRequestService:
    @staticmethod
    def _get_workflow_visible_object_ids(user):
        return WorkflowService.get_assignment_queryset_for_user(user).filter(
            module=Workflow.Module.LEAVE_REQUEST
        ).values_list("object_id", flat=True)

    @staticmethod
    def calculate_total_days(validated_data, employee=None):
        if validated_data["duration_type"] == LeaveRequest.DurationType.HALF_DAY:
            return Decimal("0.5")

        total_days = (validated_data["end_date"] - validated_data["start_date"]).days + 1
        if employee:
            holiday_dates = HolidayService.get_holiday_dates_for_employee(
                employee,
                validated_data["start_date"],
                validated_data["end_date"],
            )
            total_days -= len(holiday_dates)

        if total_days <= 0:
            raise exceptions.ValidationError({"date_range": "Selected date range contains only holidays."})
        return Decimal(str(total_days))

    @staticmethod
    def _get_days_by_month(validated_data, employee):
        if validated_data["duration_type"] == LeaveRequest.DurationType.HALF_DAY:
            return {validated_data["start_date"].strftime("%Y-%m"): Decimal("0.5")}

        holiday_dates = set()
        if employee:
            holiday_dates = set(
                HolidayService.get_holiday_dates_for_employee(
                    employee,
                    validated_data["start_date"],
                    validated_data["end_date"],
                )
            )

        result = {}
        current_date = validated_data["start_date"]
        while current_date <= validated_data["end_date"]:
            if current_date not in holiday_dates:
                month_key = current_date.strftime("%Y-%m")
                result[month_key] = result.get(month_key, Decimal("0")) + Decimal("1.0")
            current_date += timedelta(days=1)
        return result

    @staticmethod
    def _validate_monthly_limit(employee, validated_data):
        leave_type = validated_data["leave_type"]
        policy = LeavePolicyService.get_policy(actor=employee.user if employee else None)
        monthly_limit = Decimal("0")
        if leave_type == LeaveBalance.LeaveType.SICK:
            monthly_limit = policy.monthly_sick_leave_limit
        elif leave_type == LeaveBalance.LeaveType.EARNED:
            monthly_limit = policy.monthly_earned_leave_limit

        if monthly_limit <= 0:
            return

        requested_days_by_month = LeaveRequestService._get_days_by_month(validated_data, employee)

        for month_key, requested_days in requested_days_by_month.items():
            year, month = month_key.split("-")
            year_int, month_int = int(year), int(month)
            # Compute the first and last day of this calendar month.
            month_start = _date(year_int, month_int, 1)
            if month_int == 12:
                next_month_start = _date(year_int + 1, 1, 1)
            else:
                next_month_start = _date(year_int, month_int + 1, 1)
            month_end = next_month_start - timedelta(days=1)

            # Fetch all existing requests for the same employee/leave_type that
            # fall within this calendar month — not just those overlapping the
            # new request's date range.
            existing_requests = LeaveRequest.objects.filter(
                employee=employee,
                leave_type=leave_type,
                status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
                start_date__lte=month_end,
                end_date__gte=month_start,
            )

            consumed_days = Decimal("0")
            for leave_request in existing_requests:
                overlap_start = max(leave_request.start_date, month_start)
                overlap_end = min(leave_request.end_date, month_end)
                if overlap_start > overlap_end:
                    continue
                slice_validated = {
                    "start_date": overlap_start,
                    "end_date": overlap_end,
                    "duration_type": leave_request.duration_type,
                }
                consumed_days += sum(LeaveRequestService._get_days_by_month(slice_validated, employee).values())

            if consumed_days + requested_days > monthly_limit:
                raise exceptions.ValidationError(
                    {
                        "leave_type": f"{leave_type.title()} leave exceeds the monthly limit of {monthly_limit} day(s) for {month_key}."
                    }
                )

    @staticmethod
    def _resolve_leave_deduction(leave_request: LeaveRequest, policy: LeavePolicy, balances):
        requested_type = leave_request.leave_type
        remaining_days = Decimal(str(leave_request.total_days))
        deductions = {
            requested_type: Decimal("0"),
            LeaveBalance.LeaveType.EARNED: Decimal("0"),
            LeaveBalance.LeaveType.LOP: Decimal("0"),
        }

        if requested_type != LeaveBalance.LeaveType.LOP:
            requested_balance = balances.get(requested_type)
            requested_available = max(Decimal(str(requested_balance.available_days if requested_balance else 0)), Decimal("0"))
            deductions[requested_type] = min(requested_available, remaining_days)
            remaining_days -= deductions[requested_type]
        else:
            deductions[LeaveBalance.LeaveType.LOP] = remaining_days
            remaining_days = Decimal("0")

        if remaining_days > 0 and requested_type != LeaveBalance.LeaveType.EARNED and policy.compensate_with_earned_leave:
            earned_balance = balances.get(LeaveBalance.LeaveType.EARNED)
            earned_available = max(Decimal(str(earned_balance.available_days if earned_balance else 0)), Decimal("0"))
            deductions[LeaveBalance.LeaveType.EARNED] = min(earned_available, remaining_days)
            remaining_days -= deductions[LeaveBalance.LeaveType.EARNED]

        if remaining_days > 0 and policy.excess_leave_becomes_lop:
            deductions[LeaveBalance.LeaveType.LOP] += remaining_days
            remaining_days = Decimal("0")

        if remaining_days > 0:
            raise exceptions.ValidationError({"leave_type": "Insufficient leave balance under the current leave policy."})

        return {key: value for key, value in deductions.items() if value > 0}

    @staticmethod
    def get_queryset_for_user(user):
        queryset = LeaveRequest.objects.for_current_org(user).select_related("employee__user", "approver")
        employee = getattr(user, "employee_profile", None)
        workflow_object_ids = LeaveRequestService._get_workflow_visible_object_ids(user)

        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset

        scope = Q(pk__in=workflow_object_ids)
        if employee:
            scope |= Q(employee=employee)
            if user.role == User.Role.MANAGER:
                scope |= Q(employee__manager=employee) | Q(employee__secondary_manager=employee)

        return queryset.filter(scope).distinct()

    @staticmethod
    def _get_approvable_queryset(user):
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return LeaveRequest.objects.for_current_org(user).select_related("employee__user", "approver")
        if user.role == User.Role.MANAGER and employee:
            return LeaveRequest.objects.for_current_org(user).select_related("employee__user", "approver").filter(
                Q(employee__manager=employee) | Q(employee__secondary_manager=employee)
            )
        return LeaveRequest.objects.none()

    @staticmethod
    @transaction.atomic
    def apply_leave(user, validated_data):
        employee = getattr(user, "employee_profile", None)
        if not employee:
            raise exceptions.PermissionDenied("Employee profile not found for the current user.")

        total_days = LeaveRequestService.calculate_total_days(validated_data, employee=employee)
        LeaveRequestService._validate_monthly_limit(employee, validated_data)
        policy = LeavePolicyService.get_policy(actor=user)
        if validated_data["leave_type"] != LeaveBalance.LeaveType.LOP:
            balance = LeaveBalance.objects.select_for_update().filter(
                employee=employee,
                leave_type=validated_data["leave_type"],
            ).first()
            if not balance:
                raise exceptions.ValidationError({"leave_type": "Leave balance has not been configured for this type."})
            if balance.available_days < total_days and not (
                policy.compensate_with_earned_leave or policy.excess_leave_becomes_lop
            ):
                raise exceptions.ValidationError({"leave_type": "Insufficient leave balance."})

        overlapping = LeaveRequest.objects.filter(
            employee=employee,
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            start_date__lte=validated_data["end_date"],
            end_date__gte=validated_data["start_date"],
        ).exists()
        if overlapping:
            raise exceptions.ValidationError({"date_range": "An overlapping leave request already exists."})

        leave_request = LeaveRequest.objects.create(
            employee=employee,
            organization=employee.organization or OrganizationService.resolve_for_actor(user),
            total_days=total_days,
            **validated_data,
        )
        assignment = WorkflowService.start_workflow(
            Workflow.Module.LEAVE_REQUEST,
            leave_request,
            requested_by=user,
            context={"leave_type": leave_request.leave_type, "total_days": str(leave_request.total_days)},
        )
        NotificationService.notify_leave_applied(assignment)
        AuditService.log(actor=user, action="leave.request.created", entity=leave_request, after=leave_request)
        return leave_request

    @staticmethod
    @transaction.atomic
    def approve_leave(user, leave_request: LeaveRequest, approver_note: str = ""):
        if leave_request.status != LeaveRequest.Status.PENDING:
            raise exceptions.ValidationError({"status": "Only pending leave requests can be approved."})
        assignment = WorkflowService.get_assignment_for_object(Workflow.Module.LEAVE_REQUEST, leave_request)
        if assignment:
            pending_approval = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING).first()
            if not pending_approval:
                raise exceptions.ValidationError({"workflow": "No pending workflow step is available for this leave request."})
            WorkflowService.approve(user, pending_approval, approver_note)
            leave_request.refresh_from_db()
            return leave_request

        allowed_qs = LeaveRequestService._get_approvable_queryset(user)
        if not allowed_qs.filter(pk=leave_request.pk).exists():
            raise exceptions.PermissionDenied("You are not allowed to approve this leave request.")
        LeaveRequestService.finalize_workflow_approval(leave_request, actor=user, approver_note=approver_note)
        return leave_request

    @staticmethod
    @transaction.atomic
    def reject_leave(user, leave_request: LeaveRequest, approver_note: str = ""):
        if leave_request.status != LeaveRequest.Status.PENDING:
            raise exceptions.ValidationError({"status": "Only pending leave requests can be rejected."})
        assignment = WorkflowService.get_assignment_for_object(Workflow.Module.LEAVE_REQUEST, leave_request)
        if assignment:
            pending_approval = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING).first()
            if not pending_approval:
                raise exceptions.ValidationError({"workflow": "No pending workflow step is available for this leave request."})
            WorkflowService.reject(user, pending_approval, approver_note)
            leave_request.refresh_from_db()
            return leave_request

        allowed_qs = LeaveRequestService._get_approvable_queryset(user)
        if not allowed_qs.filter(pk=leave_request.pk).exists():
            raise exceptions.PermissionDenied("You are not allowed to reject this leave request.")
        LeaveRequestService.finalize_workflow_rejection(leave_request, actor=user, approver_note=approver_note)
        return leave_request

    @staticmethod
    @transaction.atomic
    def finalize_workflow_approval(leave_request: LeaveRequest, actor=None, approver_note: str = ""):
        if leave_request.status == LeaveRequest.Status.APPROVED:
            return leave_request

        policy = LeavePolicyService.get_policy(actor=user)
        balances = {
            balance.leave_type: balance
            for balance in LeaveBalance.objects.select_for_update().filter(employee=leave_request.employee)
        }
        deductions = LeaveRequestService._resolve_leave_deduction(leave_request, policy, balances)
        for leave_type, days in deductions.items():
            balance = balances.get(leave_type)
            if not balance:
                balance = LeaveBalance.objects.create(
                    employee=leave_request.employee,
                    leave_type=leave_type,
                    allocated_days=Decimal("0"),
                    used_days=Decimal("0"),
                )
                balances[leave_type] = balance
            before_balance = AuditService.snapshot(balance)
            balance.used_days = balance.used_days + days
            balance.save()
            AuditService.log(actor=actor, action="leave.balance.updated", entity=balance, before=before_balance, after=balance)

        before = AuditService.snapshot(leave_request)
        leave_request.status = LeaveRequest.Status.APPROVED
        leave_request.lop_days_applied = deductions.get(LeaveBalance.LeaveType.LOP, Decimal("0"))
        leave_request.approver = actor
        breakdown = ", ".join(f"{days} day(s) from {leave_type}" for leave_type, days in deductions.items())
        leave_request.approver_note = approver_note or ""
        if breakdown:
            leave_request.approver_note = (
                f"{leave_request.approver_note} | Balance applied: {breakdown}".strip(" |")
            )
        leave_request.reviewed_at = timezone.now()
        leave_request.save()
        AuditService.log(actor=actor, action="leave.request.approved", entity=leave_request, before=before, after=leave_request)
        return leave_request

    @staticmethod
    @transaction.atomic
    def finalize_workflow_rejection(leave_request: LeaveRequest, actor=None, approver_note: str = ""):
        if leave_request.status == LeaveRequest.Status.REJECTED:
            return leave_request

        before = AuditService.snapshot(leave_request)
        leave_request.status = LeaveRequest.Status.REJECTED
        leave_request.approver = actor
        leave_request.approver_note = approver_note
        leave_request.reviewed_at = timezone.now()
        leave_request.save()
        AuditService.log(actor=actor, action="leave.request.rejected", entity=leave_request, before=before, after=leave_request)
        return leave_request


class EarnedLeaveAdjustmentService:
    @staticmethod
    def get_queryset_for_user(user):
        queryset = EarnedLeaveAdjustment.objects.select_related("employee__user", "approver")
        employee = getattr(user, "employee_profile", None)

        if user.role in {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if user.role == User.Role.MANAGER and employee:
            return queryset.filter(Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    def _get_approvable_queryset(user):
        employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return EarnedLeaveAdjustment.objects.select_related("employee__user", "approver")
        if user.role == User.Role.MANAGER and employee:
            return EarnedLeaveAdjustment.objects.select_related("employee__user", "approver").filter(
                Q(employee__manager=employee) | Q(employee__secondary_manager=employee)
            )
        return EarnedLeaveAdjustment.objects.none()

    @staticmethod
    @transaction.atomic
    def apply_adjustment(user, validated_data):
        employee = getattr(user, "employee_profile", None)
        if not employee:
            raise exceptions.PermissionDenied("Employee profile not found for the current user.")

        work_date = validated_data["work_date"]
        if work_date > timezone.localdate():
            raise exceptions.ValidationError({"work_date": "Earned leave adjustment can only be requested for past or current dates."})
        is_weekend = work_date.weekday() >= 5
        is_holiday = work_date in set(HolidayService.get_holiday_dates_for_employee(employee, work_date, work_date))
        if not (is_weekend or is_holiday):
            raise exceptions.ValidationError({"work_date": "Earned leave can only be requested for weekends or holidays."})

        duplicate = EarnedLeaveAdjustment.objects.filter(
            employee=employee,
            work_date=work_date,
            status__in=[EarnedLeaveAdjustment.Status.PENDING, EarnedLeaveAdjustment.Status.APPROVED],
        ).exists()
        if duplicate:
            raise exceptions.ValidationError({"work_date": "An earned leave adjustment already exists for this work date."})

        adjustment = EarnedLeaveAdjustment.objects.create(
            employee=employee,
            organization=employee.organization or OrganizationService.resolve_for_actor(user),
            **validated_data,
        )
        AuditService.log(actor=user, action="leave.earned_adjustment.created", entity=adjustment, after=adjustment)
        return adjustment

    @staticmethod
    @transaction.atomic
    def approve_adjustment(user, adjustment, approver_note=""):
        if adjustment.status != EarnedLeaveAdjustment.Status.PENDING:
            raise exceptions.ValidationError({"status": "Only pending earned leave adjustments can be approved."})

        if not EarnedLeaveAdjustmentService._get_approvable_queryset(user).filter(pk=adjustment.pk).exists():
            raise exceptions.PermissionDenied("You are not allowed to approve this earned leave adjustment.")

        earned_balance = LeaveBalance.objects.select_for_update().get(
            employee=adjustment.employee,
            leave_type=LeaveBalance.LeaveType.EARNED,
        )
        before_balance = AuditService.snapshot(earned_balance)
        earned_balance.allocated_days = earned_balance.allocated_days + adjustment.days
        earned_balance.save()
        AuditService.log(actor=user, action="leave.balance.updated", entity=earned_balance, before=before_balance, after=earned_balance)

        before = AuditService.snapshot(adjustment)
        adjustment.status = EarnedLeaveAdjustment.Status.APPROVED
        adjustment.approver = user
        adjustment.approver_note = approver_note
        adjustment.reviewed_at = timezone.now()
        adjustment.save()
        AuditService.log(actor=user, action="leave.earned_adjustment.approved", entity=adjustment, before=before, after=adjustment)
        return adjustment

    @staticmethod
    @transaction.atomic
    def reject_adjustment(user, adjustment, approver_note=""):
        if adjustment.status != EarnedLeaveAdjustment.Status.PENDING:
            raise exceptions.ValidationError({"status": "Only pending earned leave adjustments can be rejected."})

        if not EarnedLeaveAdjustmentService._get_approvable_queryset(user).filter(pk=adjustment.pk).exists():
            raise exceptions.PermissionDenied("You are not allowed to reject this earned leave adjustment.")

        before = AuditService.snapshot(adjustment)
        adjustment.status = EarnedLeaveAdjustment.Status.REJECTED
        adjustment.approver = user
        adjustment.approver_note = approver_note
        adjustment.reviewed_at = timezone.now()
        adjustment.save()
        AuditService.log(actor=user, action="leave.earned_adjustment.rejected", entity=adjustment, before=before, after=adjustment)
        return adjustment
