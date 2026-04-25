import logging

from celery import shared_task
from django.utils import timezone

from apps.helpdesk.models import HelpdeskTicket
from apps.notifications.services.notification_service import NotificationService

task_logger = logging.getLogger("atmispace.tasks")


@shared_task
def remind_pending_helpdesk_tickets():
    """
    Org-aware: remind assignees about open/in-progress helpdesk tickets,
    scoped per organization.
    """
    from apps.core.models import Organization

    today = timezone.localdate()
    total = 0

    for org in Organization.objects.filter(is_active=True):
        try:
            tickets = (
                HelpdeskTicket.objects
                .filter(
                    status__in=[HelpdeskTicket.Status.OPEN, HelpdeskTicket.Status.IN_PROGRESS],
                    organization=org,
                )
                .select_related("assigned_user", "organization")
            )

            org_total = 0
            for ticket in tickets:
                if ticket.assigned_user:
                    try:
                        NotificationService.create_notification(
                            ticket.assigned_user,
                            NotificationService._resolve_type("HELPDESK"),
                            f"Pending helpdesk ticket: {ticket.subject}",
                            f"Ticket {ticket.id} is still pending as of {today.isoformat()}.",
                        )
                        org_total += 1
                    except Exception as exc:  # noqa: BLE001
                        task_logger.error(
                            "helpdesk.reminders.notify_error",
                            extra={"org_id": org.pk, "ticket_id": ticket.pk, "error": str(exc)},
                            exc_info=True,
                        )

            total += org_total
            task_logger.info(
                "helpdesk.reminders.org_done",
                extra={"event": "helpdesk.reminders.org_done",
                       "org_id": org.pk, "reminders": org_total},
            )

        except Exception as exc:  # noqa: BLE001
            task_logger.error(
                "helpdesk.reminders.org_error",
                extra={"org_id": org.pk, "error": str(exc)},
                exc_info=True,
            )

    return {"reminders_sent": total}
