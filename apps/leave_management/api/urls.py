from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import EarnedLeaveAdjustmentViewSet, LeaveBalanceViewSet, LeavePolicyView, LeaveRequestViewSet, ProcessCarryForwardView

router = DefaultRouter()
router.register("balances", LeaveBalanceViewSet, basename="leave-balance")
router.register("requests", LeaveRequestViewSet, basename="leave-request")
router.register("earned-adjustments", EarnedLeaveAdjustmentViewSet, basename="earned-leave-adjustment")

urlpatterns = [
    path("policy/", LeavePolicyView.as_view(), name="leave-policy"),
    path("process-carryforward/", ProcessCarryForwardView.as_view(), name="leave-process-carryforward"),
    *router.urls,
]
