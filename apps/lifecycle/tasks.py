import logging

from celery import shared_task
from django.utils import timezone

from apps.lifecycle.models import EmployeeOnboardingTask, OffboardingTask
from apps.notifications.services.notification_service import NotificationService

task_logger = logging.getLogger("atmispace.tasks")


@shared_task
def send_lifecycle_task_reminders():
    """
    Org-aware: remind employees/managers of pending onboarding and offboarding
    tasks that are overdue, scoped per organization.
    """
    from apps.core.models import Organization

    today = timezone.localdate()
    total = 0

    for org in Organization.objects.filter(is_active=True):
        try:
            onboarding_tasks = (
                EmployeeOnboardingTask.objects
                .select_related("onboarding__employee__user", "onboarding__employee__organization")
                .filter(
                    status=EmployeeOnboardingTask.Status.PENDING,
                    due_date__lte=today,
                    onboarding__employee__organization=org,
                )
            )
            for task in onboarding_tasks:
                try:
                    NotificationService.create_notification(
                        task.onboarding.employee.user,
                        NotificationService._resolve_type("ONBOARDING"),
                        "Onboarding task due",
                        f"Task '{task.title}' is due on {task.due_date.isoformat()}.",
                    )
                    total += 1
                except Exception as exc:  # noqa: BLE001
                    task_logger.error("lifecycle.onboarding.notify_error",
                                      extra={"org_id": org.pk, "error": str(exc)}, exc_info=True)

            offboarding_tasks = (
                OffboardingTask.objects
                .select_related("offboarding_case__employee__user",
                                "offboarding_case__employee__organization")
                .filter(
                    status=OffboardingTask.Status.PENDING,
                    due_date__lte=today,
                    offboarding_case__employee__organization=org,
                )
            )
            for task in offboarding_tasks:
                try:
                    NotificationService.create_notification(
                        task.offboarding_case.employee.user,
                        NotificationService._resolve_type("OFFBOARDING"),
                        "Offboarding task due",
                        f"Task '{task.title}' is due on {task.due_date.isoformat()}.",
                    )
                    total += 1
                except Exception as exc:  # noqa: BLE001
                    task_logger.error("lifecycle.offboarding.notify_error",
                                      extra={"org_id": org.pk, "error": str(exc)}, exc_info=True)

        except Exception as exc:  # noqa: BLE001
            task_logger.error("lifecycle.reminders.org_error",
                              extra={"org_id": org.pk, "error": str(exc)}, exc_info=True)

    return {"reminders_sent": total}
