from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AttendanceRegularizationViewSet,
    AttendanceViewSet,
    BiometricAttendanceEventViewSet,
    BiometricDeviceViewSet,
    BiometricIngestView,
    BioMaxBridgeIngestView,
)

router = DefaultRouter()
router.register("biometric-devices", BiometricDeviceViewSet, basename="biometric-device")
router.register("biometric-events", BiometricAttendanceEventViewSet, basename="biometric-attendance-event")
router.register("regularizations", AttendanceRegularizationViewSet, basename="attendance-regularization")
router.register("", AttendanceViewSet, basename="attendance")

urlpatterns = [
    path("biometric/ingest/", BiometricIngestView.as_view(), name="biometric-attendance-ingest"),
    path("biomax/bridge/ingest/", BioMaxBridgeIngestView.as_view(), name="biomax-bridge-ingest"),
    *router.urls,
]
