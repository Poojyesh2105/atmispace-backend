from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AnalyticsDashboardView, AnalyticsSnapshotViewSet

router = DefaultRouter()
router.register("snapshots", AnalyticsSnapshotViewSet, basename="analytics-snapshot")

urlpatterns = [
    path("dashboard/", AnalyticsDashboardView.as_view(), name="analytics-dashboard"),
    *router.urls,
]

