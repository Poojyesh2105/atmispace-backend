from apps.analytics.models import AnalyticsSnapshot


class AnalyticsSelectors:
    @staticmethod
    def get_snapshot_queryset(user=None):
        return AnalyticsSnapshot.objects.for_current_org(user)
