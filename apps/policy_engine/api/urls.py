from rest_framework.routers import DefaultRouter

from .views import PolicyEvaluationLogViewSet, PolicyRuleViewSet

router = DefaultRouter()
router.register("rules", PolicyRuleViewSet, basename="policy-rule")
router.register("logs", PolicyEvaluationLogViewSet, basename="policy-evaluation-log")

urlpatterns = router.urls

