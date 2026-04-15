from apps.analytics.models import AnalyticsSnapshot


class AnalyticsSelectors:
    @staticmethod
    def get_snapshot_queryset():
        return AnalyticsSnapshot.objects.all()

