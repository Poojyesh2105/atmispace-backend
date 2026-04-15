from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import EarnedLeaveAdjustmentViewSet, LeaveBalanceViewSet, LeavePolicyView, LeaveRequestViewSet

router = DefaultRouter()
router.register("balances", LeaveBalanceViewSet, basename="leave-balance")
router.register("requests", LeaveRequestViewSet, basename="leave-request")
router.register("earned-adjustments", EarnedLeaveAdjustmentViewSet, basename="earned-leave-adjustment")

urlpatterns = [
    path("policy/", LeavePolicyView.as_view(), name="leave-policy"),
    *router.urls,
]
