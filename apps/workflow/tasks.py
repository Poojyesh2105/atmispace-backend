import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.services.notification_service import NotificationService
from apps.workflow.models import ApprovalInstance

task_logger = logging.getLogger("atmispace.tasks")


@shared_task
def alert_stuck_workflow_assignments(stale_hours: int = 48):
    """
    Org-aware: for each active org, alert HR/ADMIN about approval steps
    that have been pending longer than `stale_hours`.
    """
    from apps.core.models import Organization

    threshold = timezone.now() - timedelta(hours=stale_hours)
    total_reminders = 0

    for org in Organization.objects.filter(is_active=True):
        try:
            stale_approvals = (
                ApprovalInstance.objects
                .filter(
                    status=ApprovalInstance.Status.PENDING,
                    created_at__lte=threshold,
                    workflow_assignment__workflow__organization=org,
                )
                .select_related("workflow_assignment__workflow", "assigned_user", "step")
            )

            admins = list(
                User.objects.filter(
                    organization=org,
                    role__in=[User.Role.HR, User.Role.ADMIN],
                    is_active=True,
                )[:10]
            )

            org_reminders = 0
            for approval in stale_approvals:
                module_label = approval.workflow_assignment.workflow.get_module_display()
                message = (
                    f"Approval step '{approval.step.name}' for {module_label.lower()} "
                    f"has been pending since {approval.created_at.isoformat()}."
                )
                for admin in admins:
                    try:
                        NotificationService.create_notification(
                            admin,
                            NotificationService._resolve_type("WORKFLOW_PENDING"),
                            "Workflow approval appears stuck",
                            message,
                            send_email=False,
                        )
                        org_reminders += 1
                    except Exception as exc:  # noqa: BLE001
                        task_logger.error(
                            "workflow.reminder.notify_error",
                            extra={"org_id": org.pk, "error": str(exc)},
                            exc_info=True,
                        )

            total_reminders += org_reminders
            task_logger.info(
                "workflow.reminders.org_done",
                extra={
                    "event": "workflow.reminders.org_done",
                    "org_id": org.pk, "org_name": org.name,
                    "stale_count": stale_approvals.count(),
                    "reminders": org_reminders,
                },
            )
        except Exception as exc:  # noqa: BLE001
            task_logger.error(
                "workflow.reminders.org_error",
                extra={"org_id": org.pk, "error": str(exc)},
                exc_info=True,
            )

    return {"reminders_sent": total_reminders}
