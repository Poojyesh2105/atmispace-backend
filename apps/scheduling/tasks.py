from celery import shared_task

from apps.notifications.services.notification_service import NotificationService
from apps.scheduling.models import ScheduleConflict


@shared_task
def remind_unresolved_schedule_conflicts():
    reminders = 0
    conflicts = ScheduleConflict.objects.filter(is_resolved=False).select_related("reported_by", "roster_entry__employee__user")
    for conflict in conflicts:
        target_user = conflict.reported_by or conflict.roster_entry.employee.user
        if target_user:
            NotificationService.create_notification(
                target_user,
                NotificationService._resolve_type("GENERIC"),
                "Unresolved schedule conflict",
                conflict.message,
            )
            reminders += 1
    return reminders

