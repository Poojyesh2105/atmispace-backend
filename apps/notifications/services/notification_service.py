from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.attendance.models import Attendance
from apps.employees.models import Employee
from apps.notifications.models import Notification


class NotificationService:
    @staticmethod
    def _resolve_type(candidate):
        candidate = (candidate or "").upper()
        valid_types = {choice for choice, _label in Notification.Type.choices}
        return candidate if candidate in valid_types else Notification.Type.GENERIC

    @staticmethod
    def create_notification(user, notification_type, title, message, send_email=False):
        if not user:
            return None
        notification = Notification.objects.create(
            user=user,
            type=NotificationService._resolve_type(notification_type),
            title=title,
            message=message,
        )
        if send_email and user.email:
            send_mail(
                subject=title,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        return notification

    @staticmethod
    def notify_pending_approval(approval_instance):
        if not approval_instance.assigned_user:
            return None
        module_label = approval_instance.workflow_assignment.workflow.get_module_display()
        return NotificationService.create_notification(
            approval_instance.assigned_user,
            Notification.Type.WORKFLOW_PENDING,
            f"Pending approval: {module_label}",
            f"You have a pending {module_label.lower()} approval for step '{approval_instance.step.name}'.",
            send_email=True,
        )

    @staticmethod
    def notify_workflow_completed(assignment, approved, actor=None, comments=""):
        if not assignment.requested_by:
            return None

        module_label = assignment.workflow.get_module_display()
        outcome = "approved" if approved else "rejected"
        actor_name = actor.full_name if actor else "Workflow"
        detail = f" by {actor_name}." if actor_name else "."
        if comments:
            detail = f"{detail} Note: {comments}"

        notification_type = Notification.Type.LEAVE_APPROVED if approved else Notification.Type.LEAVE_REJECTED
        if assignment.module == "attendance_regularization":
            notification_type = Notification.Type.REGULARIZATION

        return NotificationService.create_notification(
            assignment.requested_by,
            notification_type,
            f"{module_label} {outcome.title()}",
            f"Your {module_label.lower()} request was {outcome}{detail}",
            send_email=True,
        )

    @staticmethod
    def notify_leave_applied(assignment):
        first_pending = assignment.approval_instances.filter(status="PENDING").select_related("assigned_user").first()
        if first_pending and first_pending.assigned_user:
            return NotificationService.create_notification(
                first_pending.assigned_user,
                Notification.Type.LEAVE_APPLIED,
                "New Leave Request",
                f"A leave request is waiting for your review from {assignment.requested_by.full_name if assignment.requested_by else 'an employee'}.",
                send_email=True,
            )
        return None

    @staticmethod
    def notify_regularization_applied(assignment):
        first_pending = assignment.approval_instances.filter(status="PENDING").select_related("assigned_user").first()
        if first_pending and first_pending.assigned_user:
            return NotificationService.create_notification(
                first_pending.assigned_user,
                Notification.Type.REGULARIZATION,
                "Attendance Regularization Pending",
                f"An attendance regularization request is waiting for your review from {assignment.requested_by.full_name if assignment.requested_by else 'an employee'}.",
                send_email=True,
            )
        return None

    @staticmethod
    def send_missing_attendance_notifications(target_date=None):
        target_date = target_date or timezone.localdate()
        employees = Employee.objects.select_related("user").filter(is_active=True, user__is_active=True)
        existing_attendance_employee_ids = set(
            Attendance.objects.filter(attendance_date=target_date).values_list("employee_id", flat=True)
        )

        notifications = []
        for employee in employees.exclude(pk__in=existing_attendance_employee_ids):
            notifications.append(
                NotificationService.create_notification(
                    employee.user,
                    Notification.Type.MISSING_ATTENDANCE,
                    "Attendance Missing",
                    f"No attendance record was found for {target_date.isoformat()}. Please submit your attendance or regularization request.",
                    send_email=True,
                )
            )
        return notifications
