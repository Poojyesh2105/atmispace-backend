import logging

from celery import shared_task

from apps.notifications.services.notification_service import NotificationService
from apps.scheduling.models import ScheduleConflict

task_logger = logging.getLogger("atmispace.tasks")


@shared_task
def remind_unresolved_schedule_conflicts():
    """
    Org-aware: remind relevant users about unresolved schedule conflicts,
    scoped per organization.
    """
    from apps.core.models import Organization

    total = 0

    for org in Organization.objects.filter(is_active=True):
        try:
            conflicts = (
                ScheduleConflict.objects
                .filter(
                    is_resolved=False,
                    roster_entry__employee__organization=org,
                )
                .select_related("reported_by", "roster_entry__employee__user",
                                "roster_entry__employee__organization")
            )

            org_total = 0
            for conflict in conflicts:
                target_user = conflict.reported_by or conflict.roster_entry.employee.user
                if target_user:
                    try:
                        NotificationService.create_notification(
                            target_user,
                            NotificationService._resolve_type("GENERIC"),
                            "Unresolved schedule conflict",
                            conflict.message,
                        )
                        org_total += 1
                    except Exception as exc:  # noqa: BLE001
                        task_logger.error(
                            "scheduling.conflicts.notify_error",
                            extra={"org_id": org.pk, "conflict_id": conflict.pk, "error": str(exc)},
                            exc_info=True,
                        )

            total += org_total
            task_logger.info(
                "scheduling.conflicts.org_done",
                extra={"event": "scheduling.conflicts.org_done",
                       "org_id": org.pk, "reminders": org_total},
            )

        except Exception as exc:  # noqa: BLE001
            task_logger.error(
                "scheduling.conflicts.org_error",
                extra={"org_id": org.pk, "error": str(exc)},
                exc_info=True,
            )

    return {"reminders_sent": total}
