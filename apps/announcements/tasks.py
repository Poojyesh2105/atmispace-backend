import logging

from celery import shared_task
from django.utils import timezone

from apps.announcements.models import Announcement
from apps.announcements.services.announcement_service import AnnouncementService
from apps.notifications.services.notification_service import NotificationService

task_logger = logging.getLogger("atmispace.tasks")


@shared_task
def send_acknowledgement_reminders():
    """
    Org-aware: remind employees to acknowledge published announcements that
    require acknowledgement, scoped per organization.
    """
    from apps.core.models import Organization

    now = timezone.now()
    total = 0

    for org in Organization.objects.filter(is_active=True):
        try:
            announcements = Announcement.objects.filter(
                is_published=True,
                requires_acknowledgement=True,
                starts_at__lte=now,
                organization=org,
            )

            org_total = 0
            for announcement in announcements:
                try:
                    recipients = AnnouncementService._get_recipients(announcement)
                    acknowledged_ids = set(
                        announcement.acknowledgements.values_list("user_id", flat=True)
                    )
                    for user in recipients.exclude(pk__in=acknowledged_ids):
                        try:
                            NotificationService.create_notification(
                                user,
                                NotificationService._resolve_type("ANNOUNCEMENT"),
                                f"Acknowledge: {announcement.title}",
                                "This announcement requires your acknowledgement.",
                            )
                            org_total += 1
                        except Exception as exc:  # noqa: BLE001
                            task_logger.error(
                                "announcements.ack.notify_error",
                                extra={"org_id": org.pk, "announcement_id": announcement.pk,
                                       "user_id": user.pk, "error": str(exc)},
                                exc_info=True,
                            )
                except Exception as exc:  # noqa: BLE001
                    task_logger.error(
                        "announcements.ack.announcement_error",
                        extra={"org_id": org.pk, "announcement_id": announcement.pk, "error": str(exc)},
                        exc_info=True,
                    )

            total += org_total
            task_logger.info(
                "announcements.ack.org_done",
                extra={"event": "announcements.ack.org_done",
                       "org_id": org.pk, "reminders": org_total},
            )

        except Exception as exc:  # noqa: BLE001
            task_logger.error(
                "announcements.ack.org_error",
                extra={"org_id": org.pk, "error": str(exc)},
                exc_info=True,
            )

    return {"reminders_sent": total}
