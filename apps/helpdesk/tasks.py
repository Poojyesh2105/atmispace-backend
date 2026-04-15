from celery import shared_task
from django.utils import timezone

from apps.helpdesk.models import HelpdeskTicket
from apps.notifications.services.notification_service import NotificationService


@shared_task
def remind_pending_helpdesk_tickets():
    reminders = 0
    for ticket in HelpdeskTicket.objects.filter(status__in=[HelpdeskTicket.Status.OPEN, HelpdeskTicket.Status.IN_PROGRESS]).select_related("assigned_user"):
        if ticket.assigned_user:
            NotificationService.create_notification(
                ticket.assigned_user,
                NotificationService._resolve_type("HELPDESK"),
                f"Pending helpdesk ticket: {ticket.subject}",
                f"Ticket {ticket.id} is still pending as of {timezone.localdate().isoformat()}.",
            )
            reminders += 1
    return reminders

