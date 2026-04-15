from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import viewsets

from apps.analytics.permissions import CanViewAnalytics
from apps.analytics.selectors.analytics_selectors import AnalyticsSelectors
from apps.analytics.serializers import AnalyticsSnapshotSerializer
from apps.analytics.services.analytics_service import AnalyticsService
from apps.core.responses import success_response


class AnalyticsDashboardView(APIView):
    permission_classes = [IsAuthenticated, CanViewAnalytics]

    def get(self, request):
        return success_response(data=AnalyticsService.get_dashboard(request.user))


class AnalyticsSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AnalyticsSnapshotSerializer
    permission_classes = [IsAuthenticated, CanViewAnalytics]

    def get_queryset(self):
        queryset = AnalyticsSelectors.get_snapshot_queryset()
        metric_key = self.request.query_params.get("metric_key")
        if metric_key:
            queryset = queryset.filter(metric_key=metric_key)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

