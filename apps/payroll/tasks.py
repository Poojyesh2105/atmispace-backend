import logging

from celery import shared_task

from apps.notifications.services.notification_service import NotificationService
from apps.payroll.models import PayrollRun

task_logger = logging.getLogger("atmispace.tasks")


@shared_task
def remind_pending_payroll_release():
    """
    Org-aware: sends a reminder to the payroll approver for every RELEASE_PENDING
    run, tagged with the organization so notifications land in the right tenant.
    """
    reminders = 0
    runs = (
        PayrollRun.objects
        .filter(status=PayrollRun.Status.RELEASE_PENDING)
        .select_related("generated_by", "cycle", "organization")
    )
    for run in runs:
        if not run.generated_by:
            continue
        try:
            NotificationService.create_notification(
                run.generated_by,
                NotificationService._resolve_type("PAYROLL"),
                f"Payroll release pending: {run.cycle.name}",
                "Your payroll run is still waiting for release approval.",
            )
            reminders += 1
            task_logger.info(
                "payroll.reminder.sent",
                extra={
                    "event": "payroll.reminder.sent",
                    "org_id": getattr(run, "organization_id", None),
                    "run_id": run.pk,
                    "cycle": run.cycle.name,
                    "user_id": run.generated_by.pk,
                },
            )
        except Exception as exc:  # noqa: BLE001
            task_logger.error(
                "payroll.reminder.error",
                extra={"event": "payroll.reminder.error", "run_id": run.pk, "error": str(exc)},
                exc_info=True,
            )
    return {"reminders_sent": reminders}
