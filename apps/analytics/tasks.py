import logging

from celery import shared_task

from apps.analytics.services.analytics_service import AnalyticsService

task_logger = logging.getLogger("atmispace.tasks")


@shared_task
def refresh_analytics_snapshots():
    """
    Org-aware: refresh analytics snapshots for every active organization.
    """
    from apps.core.models import Organization

    total = 0
    for org in Organization.objects.filter(is_active=True):
        try:
            snapshots = AnalyticsService.refresh_snapshots(organization=org)
            total += len(snapshots)
            task_logger.info(
                "analytics.snapshots.org_done",
                extra={"event": "analytics.snapshots.org_done",
                       "org_id": org.pk, "count": len(snapshots)},
            )
        except Exception as exc:  # noqa: BLE001
            task_logger.error(
                "analytics.snapshots.org_error",
                extra={"event": "analytics.snapshots.org_error",
                       "org_id": org.pk, "error": str(exc)},
                exc_info=True,
            )
    return {"snapshots_refreshed": total}
