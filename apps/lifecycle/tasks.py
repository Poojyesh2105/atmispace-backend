from celery import shared_task
from django.utils import timezone

from apps.lifecycle.models import EmployeeOnboardingTask, OffboardingTask
from apps.notifications.services.notification_service import NotificationService


@shared_task
def send_lifecycle_task_reminders():
    today = timezone.localdate()
    reminder_count = 0

    for task in EmployeeOnboardingTask.objects.select_related("onboarding__employee__user").filter(status=EmployeeOnboardingTask.Status.PENDING, due_date__lte=today):
        NotificationService.create_notification(
            task.onboarding.employee.user,
            NotificationService._resolve_type("ONBOARDING"),
            "Onboarding task due",
            f"Task '{task.title}' is due on {task.due_date.isoformat()}.",
        )
        reminder_count += 1

    for task in OffboardingTask.objects.select_related("offboarding_case__employee__user").filter(status=OffboardingTask.Status.PENDING, due_date__lte=today):
        NotificationService.create_notification(
            task.offboarding_case.employee.user,
            NotificationService._resolve_type("OFFBOARDING"),
            "Offboarding task due",
            f"Task '{task.title}' is due on {task.due_date.isoformat()}.",
        )
        reminder_count += 1

    return reminder_count

