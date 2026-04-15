from rest_framework.routers import DefaultRouter

from .views import EmployeeHolidayAssignmentViewSet, HolidayCalendarViewSet, HolidayViewSet

router = DefaultRouter()
router.register("calendars", HolidayCalendarViewSet, basename="holiday-calendar")
router.register("days", HolidayViewSet, basename="holiday")
router.register("assignments", EmployeeHolidayAssignmentViewSet, basename="holiday-assignment")

urlpatterns = router.urls
