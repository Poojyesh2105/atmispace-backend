from rest_framework.routers import DefaultRouter

from .views import ApprovalInstanceViewSet, WorkflowAssignmentViewSet, WorkflowViewSet

router = DefaultRouter()
router.register("workflows", WorkflowViewSet, basename="workflow")
router.register("assignments", WorkflowAssignmentViewSet, basename="workflow-assignment")
router.register("approvals", ApprovalInstanceViewSet, basename="approval-instance")

urlpatterns = router.urls
