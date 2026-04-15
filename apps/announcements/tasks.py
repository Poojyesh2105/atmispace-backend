from celery import shared_task
from django.utils import timezone

from apps.announcements.models import Announcement
from apps.announcements.services.announcement_service import AnnouncementService
from apps.notifications.services.notification_service import NotificationService


@shared_task
def send_acknowledgement_reminders():
    now = timezone.now()
    reminders = 0
    announcements = Announcement.objects.filter(
        is_published=True,
        requires_acknowledgement=True,
        starts_at__lte=now,
    )
    for announcement in announcements:
        recipients = AnnouncementService._get_recipients(announcement)
        acknowledged_ids = set(announcement.acknowledgements.values_list("user_id", flat=True))
        for user in recipients.exclude(pk__in=acknowledged_ids):
            NotificationService.create_notification(
                user,
                NotificationService._resolve_type("ANNOUNCEMENT"),
                f"Acknowledge: {announcement.title}",
                "This announcement requires your acknowledgement.",
            )
            reminders += 1
    return reminders

