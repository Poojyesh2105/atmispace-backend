from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import exceptions

from apps.attendance.models import Attendance, AttendanceRegularization
from apps.audit.services.audit_service import AuditService
from apps.notifications.services.notification_service import NotificationService
from apps.workflow.models import ApprovalInstance, Workflow
from apps.workflow.services.workflow_service import WorkflowService


class AttendanceRegularizationService:
    @staticmethod
    def get_queryset_for_user(user):
        queryset = AttendanceRegularization.objects.select_related("employee__user", "approver").all()
        employee = getattr(user, "employee_profile", None)

        if user.role in {"HR", "ADMIN"}:
            return queryset
        if user.role == "MANAGER" and employee:
            return queryset.filter(Q(employee=employee) | Q(employee__manager=employee) | Q(employee__secondary_manager=employee))
        if employee:
            return queryset.filter(employee=employee)
        return queryset.none()

    @staticmethod
    @transaction.atomic
    def apply_regularization(user, validated_data):
        employee = getattr(user, "employee_profile", None)
        if not employee:
            raise exceptions.PermissionDenied("Employee profile not found for the current user.")

        existing_pending = AttendanceRegularization.objects.filter(
            employee=employee,
            date=validated_data["date"],
            status=AttendanceRegularization.Status.PENDING,
        ).exists()
        if existing_pending:
            raise exceptions.ValidationError({"date": "A pending attendance regularization request already exists for this date."})

        regularization = AttendanceRegularization.objects.create(employee=employee, **validated_data)
        assignment = WorkflowService.start_workflow(
            Workflow.Module.ATTENDANCE_REGULARIZATION,
            regularization,
            requested_by=user,
            context={"date": regularization.date.isoformat()},
        )
        NotificationService.notify_regularization_applied(assignment)
        AuditService.log(actor=user, action="attendance.regularization.created", entity=regularization, after=regularization)
        return regularization

    @staticmethod
    @transaction.atomic
    def approve_regularization(user, regularization, approver_note=""):
        if regularization.status != AttendanceRegularization.Status.PENDING:
            raise exceptions.ValidationError({"status": "Only pending regularizations can be approved."})

        assignment = WorkflowService.get_assignment_for_object(Workflow.Module.ATTENDANCE_REGULARIZATION, regularization)
        if assignment:
            pending_approval = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING).first()
            if not pending_approval:
                raise exceptions.ValidationError({"workflow": "No pending workflow step is available for this request."})
            WorkflowService.approve(user, pending_approval, approver_note)
            regularization.refresh_from_db()
            return regularization

        AttendanceRegularizationService.finalize_workflow_approval(regularization, actor=user, approver_note=approver_note)
        return regularization

    @staticmethod
    @transaction.atomic
    def reject_regularization(user, regularization, approver_note=""):
        if regularization.status != AttendanceRegularization.Status.PENDING:
            raise exceptions.ValidationError({"status": "Only pending regularizations can be rejected."})

        assignment = WorkflowService.get_assignment_for_object(Workflow.Module.ATTENDANCE_REGULARIZATION, regularization)
        if assignment:
            pending_approval = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING).first()
            if not pending_approval:
                raise exceptions.ValidationError({"workflow": "No pending workflow step is available for this request."})
            WorkflowService.reject(user, pending_approval, approver_note)
            regularization.refresh_from_db()
            return regularization

        AttendanceRegularizationService.finalize_workflow_rejection(regularization, actor=user, approver_note=approver_note)
        return regularization

    @staticmethod
    @transaction.atomic
    def finalize_workflow_approval(regularization, actor=None, approver_note=""):
        if regularization.status == AttendanceRegularization.Status.APPROVED:
            return regularization

        attendance, _ = Attendance.objects.select_for_update().get_or_create(
            employee=regularization.employee,
            attendance_date=regularization.date,
            defaults={"status": Attendance.Status.PRESENT},
        )
        attendance_before = AuditService.snapshot(attendance)
        attendance.check_in = regularization.requested_check_in
        attendance.check_out = regularization.requested_check_out
        if regularization.date != timezone.localdate() or not attendance.current_session_check_in:
            attendance.current_session_check_in = None
            attendance.break_started_at = None
            attendance.current_session_break_minutes = 0
        attendance.total_work_minutes = max(
            int((regularization.requested_check_out - regularization.requested_check_in).total_seconds() // 60)
            - (attendance.break_minutes or 0),
            0,
        )
        attendance.status = Attendance.Status.PRESENT
        attendance.notes = regularization.reason
        attendance.save()

        before = AuditService.snapshot(regularization)
        regularization.status = AttendanceRegularization.Status.APPROVED
        regularization.approver = actor
        regularization.approver_note = approver_note
        regularization.reviewed_at = timezone.now()
        regularization.save()

        AuditService.log(actor=actor, action="attendance.updated", entity=attendance, before=attendance_before, after=attendance)
        AuditService.log(
            actor=actor,
            action="attendance.regularization.approved",
            entity=regularization,
            before=before,
            after=regularization,
        )
        return regularization

    @staticmethod
    @transaction.atomic
    def finalize_workflow_rejection(regularization, actor=None, approver_note=""):
        if regularization.status == AttendanceRegularization.Status.REJECTED:
            return regularization

        before = AuditService.snapshot(regularization)
        regularization.status = AttendanceRegularization.Status.REJECTED
        regularization.approver = actor
        regularization.approver_note = approver_note
        regularization.reviewed_at = timezone.now()
        regularization.save()
        AuditService.log(
            actor=actor,
            action="attendance.regularization.rejected",
            entity=regularization,
            before=before,
            after=regularization,
        )
        return regularization
