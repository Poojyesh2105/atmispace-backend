from rest_framework.routers import DefaultRouter

from .views import PerformanceCycleViewSet, PerformanceGoalViewSet, PerformanceReviewViewSet, RatingScaleViewSet

router = DefaultRouter()
router.register("rating-scales", RatingScaleViewSet, basename="performance-rating-scale")
router.register("cycles", PerformanceCycleViewSet, basename="performance-cycle")
router.register("goals", PerformanceGoalViewSet, basename="performance-goal")
router.register("reviews", PerformanceReviewViewSet, basename="performance-review")

urlpatterns = router.urls

