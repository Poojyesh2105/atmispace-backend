from django.urls import path

from .views import (
    CurrentOrganizationView,
    MyOrganizationsView,
    OrgSettingsView,
    OrganizationDeprovisionView,
    OrganizationProvisionView,
    SwitchOrganizationView,
)

urlpatterns = [
    # Current tenant context
    path("current/", CurrentOrganizationView.as_view(), name="org-current"),
    path("current/settings/", OrgSettingsView.as_view(), name="org-settings"),
    path("mine/", MyOrganizationsView.as_view(), name="org-mine"),
    path("switch/", SwitchOrganizationView.as_view(), name="org-switch"),

    # SUPER_ADMIN provisioning
    path("provision/", OrganizationProvisionView.as_view(), name="org-provision"),
    path("<int:pk>/deprovision/", OrganizationDeprovisionView.as_view(), name="org-deprovision"),
]
