from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.services.notification_service import NotificationService


class Command(BaseCommand):
    help = "Send in-app and email notifications to employees missing attendance for the target date."

    def handle(self, *args, **options):
        notifications = NotificationService.send_missing_attendance_notifications(timezone.localdate())
        self.stdout.write(self.style.SUCCESS(f"Created {len(notifications)} missing attendance notifications."))
