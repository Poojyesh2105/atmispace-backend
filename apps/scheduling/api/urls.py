from rest_framework.routers import DefaultRouter

from .views import ScheduleConflictViewSet, ShiftRosterEntryViewSet, ShiftRotationRuleViewSet

router = DefaultRouter()
router.register("rotation-rules", ShiftRotationRuleViewSet, basename="shift-rotation-rule")
router.register("roster", ShiftRosterEntryViewSet, basename="shift-roster-entry")
router.register("conflicts", ScheduleConflictViewSet, basename="schedule-conflict")

urlpatterns = router.urls

