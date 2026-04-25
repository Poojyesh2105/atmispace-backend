import logging

from celery import shared_task
from django.utils import timezone

from apps.notifications.services.notification_service import NotificationService
from apps.performance.models import PerformanceReview

task_logger = logging.getLogger("atmispace.tasks")


@shared_task
def send_pending_performance_review_reminders():
    """
    Org-aware: remind employees/managers of pending performance reviews
    that are overdue, scoped per organization.
    """
    from apps.core.models import Organization

    today = timezone.localdate()
    total = 0

    for org in Organization.objects.filter(is_active=True):
        try:
            pending_reviews = (
                PerformanceReview.objects
                .select_related("employee__user", "cycle", "employee__organization")
                .filter(
                    status__in=[
                        PerformanceReview.Status.SELF_PENDING,
                        PerformanceReview.Status.MANAGER_PENDING,
                        PerformanceReview.Status.HR_PENDING,
                    ],
                    employee__organization=org,
                )
            )

            org_total = 0
            for review in pending_reviews:
                due_date = review.cycle.self_review_due_date
                if review.status == PerformanceReview.Status.MANAGER_PENDING:
                    due_date = review.cycle.manager_review_due_date
                elif review.status == PerformanceReview.Status.HR_PENDING:
                    due_date = review.cycle.hr_review_due_date

                if due_date and due_date <= today:
                    try:
                        NotificationService.create_notification(
                            review.employee.user,
                            NotificationService._resolve_type("PERFORMANCE_REVIEW"),
                            "Performance review deadline",
                            f"The review '{review.cycle.name}' is due on {due_date.isoformat()} and still pending.",
                        )
                        org_total += 1
                    except Exception as exc:  # noqa: BLE001
                        task_logger.error(
                            "performance.reminders.notify_error",
                            extra={"org_id": org.pk, "review_id": review.pk, "error": str(exc)},
                            exc_info=True,
                        )

            total += org_total
            task_logger.info(
                "performance.reminders.org_done",
                extra={"event": "performance.reminders.org_done",
                       "org_id": org.pk, "reminders": org_total},
            )

        except Exception as exc:  # noqa: BLE001
            task_logger.error(
                "performance.reminders.org_error",
                extra={"org_id": org.pk, "error": str(exc)},
                exc_info=True,
            )

    return {"reminders_sent": total}
