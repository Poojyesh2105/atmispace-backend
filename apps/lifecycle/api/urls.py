from rest_framework.routers import DefaultRouter

from .views import (
    EmployeeChangeRequestViewSet,
    EmployeeOnboardingTaskViewSet,
    EmployeeOnboardingViewSet,
    OffboardingCaseViewSet,
    OffboardingTaskViewSet,
    OnboardingPlanViewSet,
    OnboardingTaskTemplateViewSet,
)

router = DefaultRouter()
router.register("onboarding-plans", OnboardingPlanViewSet, basename="onboarding-plan")
router.register("onboarding-task-templates", OnboardingTaskTemplateViewSet, basename="onboarding-task-template")
router.register("onboardings", EmployeeOnboardingViewSet, basename="employee-onboarding")
router.register("onboarding-tasks", EmployeeOnboardingTaskViewSet, basename="employee-onboarding-task")
router.register("offboarding-cases", OffboardingCaseViewSet, basename="offboarding-case")
router.register("offboarding-tasks", OffboardingTaskViewSet, basename="offboarding-task")
router.register("change-requests", EmployeeChangeRequestViewSet, basename="employee-change-request")

urlpatterns = router.urls

