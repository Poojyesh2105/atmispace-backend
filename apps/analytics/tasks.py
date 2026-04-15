from celery import shared_task

from apps.analytics.services.analytics_service import AnalyticsService


@shared_task
def refresh_analytics_snapshots():
    snapshots = AnalyticsService.refresh_snapshots()
    return len(snapshots)

