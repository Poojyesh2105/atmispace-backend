import logging
from datetime import date

from celery import shared_task

task_logger = logging.getLogger("atmispace.tasks")


@shared_task
def process_monthly_leave_carry_forward():
    """
    Monthly task (runs on the 1st of each month).
    Org-aware: iterates over every active organization and processes carry
    forward independently per org so that each org's own leave policy is
    respected.
    """
    from apps.core.models import Organization
    from apps.leave_management.services.carry_forward_service import LeaveCarryForwardService

    today = date.today()
    target_month = today.replace(day=1)

    orgs = Organization.objects.filter(is_active=True)
    total = 0
    results = []

    for org in orgs:
        try:
            count = LeaveCarryForwardService.process_carry_forward(
                target_month,
                organization=org,
            )
            total += count
            results.append({"org": org.name, "processed": count})
            task_logger.info(
                "leave.carry_forward.org_done",
                extra={
                    "event": "leave.carry_forward.org_done",
                    "org_id": org.pk,
                    "org_name": org.name,
                    "count": count,
                    "month": target_month.strftime("%Y-%m"),
                },
            )
        except Exception as exc:  # noqa: BLE001
            task_logger.error(
                "leave.carry_forward.org_error",
                extra={
                    "event": "leave.carry_forward.org_error",
                    "org_id": org.pk,
                    "org_name": org.name,
                    "error": str(exc),
                },
                exc_info=True,
            )

    return {
        "month": target_month.strftime("%Y-%m"),
        "total_employees_processed": total,
        "orgs": results,
    }
