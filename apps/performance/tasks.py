from celery import shared_task
from django.utils import timezone

from apps.notifications.services.notification_service import NotificationService
from apps.performance.models import PerformanceReview


@shared_task
def send_pending_performance_review_reminders():
    today = timezone.localdate()
    reminders = []

    for review in PerformanceReview.objects.select_related("employee__user", "cycle").filter(
        status__in=[PerformanceReview.Status.SELF_PENDING, PerformanceReview.Status.MANAGER_PENDING, PerformanceReview.Status.HR_PENDING]
    ):
        due_date = review.cycle.self_review_due_date
        if review.status == PerformanceReview.Status.MANAGER_PENDING:
            due_date = review.cycle.manager_review_due_date
        elif review.status == PerformanceReview.Status.HR_PENDING:
            due_date = review.cycle.hr_review_due_date

        if due_date <= today:
            reminders.append(
                NotificationService.create_notification(
                    review.employee.user,
                    NotificationService._resolve_type("PERFORMANCE_REVIEW"),
                    "Performance review deadline",
                    f"The review '{review.cycle.name}' is due on {due_date.isoformat()} and still pending.",
                )
            )
    return len(reminders)

