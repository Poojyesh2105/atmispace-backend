from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import DepartmentViewSet, EmployeeViewSet, OrganizationSettingsView, ShiftTemplateViewSet

router = DefaultRouter()
router.register("departments", DepartmentViewSet, basename="department")
router.register("shifts", ShiftTemplateViewSet, basename="shift-template")
router.register("", EmployeeViewSet, basename="employee")

urlpatterns = [
    path("organization-settings/", OrganizationSettingsView.as_view(), name="organization-settings"),
    *router.urls,
]
