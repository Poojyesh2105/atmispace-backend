from rest_framework.routers import DefaultRouter

from .views import AttendanceRegularizationViewSet, AttendanceViewSet

router = DefaultRouter()
router.register("regularizations", AttendanceRegularizationViewSet, basename="attendance-regularization")
router.register("", AttendanceViewSet, basename="attendance")

urlpatterns = router.urls
