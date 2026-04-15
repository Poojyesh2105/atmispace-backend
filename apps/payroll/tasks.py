from celery import shared_task

from apps.notifications.services.notification_service import NotificationService
from apps.payroll.models import PayrollRun


@shared_task
def remind_pending_payroll_release():
    reminders = 0
    runs = PayrollRun.objects.filter(status=PayrollRun.Status.RELEASE_PENDING).select_related("generated_by", "cycle")
    for run in runs:
        if run.generated_by:
            NotificationService.create_notification(
                run.generated_by,
                NotificationService._resolve_type("PAYROLL"),
                f"Payroll release pending: {run.cycle.name}",
                "Your payroll run is still waiting for release approval.",
            )
            reminders += 1
    return reminders
