from django.urls import path
from . import views, platform_views

urlpatterns = [
    # ── Existing platform endpoints ──────────────────────────────────────────
    # Platform overview
    path("overview/", views.PlatformOverviewView.as_view(), name="platform-overview"),

    # System health
    path("health/", views.SystemHealthView.as_view(), name="platform-health"),

    # Feature flags
    path("feature-flags/", views.FeatureFlagListCreateView.as_view(), name="platform-feature-flags"),
    path("feature-flags/<int:pk>/", views.FeatureFlagDetailView.as_view(), name="platform-feature-flag-detail"),
    path("feature-flags/<int:pk>/toggle/", views.FeatureFlagToggleView.as_view(), name="platform-feature-flag-toggle"),

    # Global audit logs
    path("audit-logs/", views.GlobalAuditLogView.as_view(), name="platform-audit-logs"),

    # Organizations
    path("organizations/", views.OrganizationListCreateView.as_view(), name="platform-organizations"),
    path("organizations/<int:pk>/", views.OrganizationDetailView.as_view(), name="platform-organization-detail"),

    # Global users
    path("users/", views.GlobalUserListView.as_view(), name="platform-users"),

    # Cross-org aggregate reports
    path("reports/", views.PlatformReportsView.as_view(), name="platform-reports"),

    # ── SaaS billing / subscription endpoints ────────────────────────────────
    path("plans/", platform_views.SubscriptionPlanListCreateView.as_view(), name="platform-plans"),
    path("plans/<int:pk>/", platform_views.SubscriptionPlanDetailView.as_view(), name="platform-plan-detail"),

    path("subscriptions/", platform_views.OrgSubscriptionListView.as_view(), name="platform-subscriptions"),
    path("subscriptions/<int:org_pk>/", platform_views.OrgSubscriptionDetailView.as_view(), name="platform-subscription-detail"),

    path("invoices/", platform_views.InvoiceListView.as_view(), name="platform-invoices"),
    path("payments/", platform_views.PaymentListView.as_view(), name="platform-payments"),

    path("revenue/", platform_views.RevenueSummaryView.as_view(), name="platform-revenue"),

    # ── Onboarding stepper ────────────────────────────────────────────────────
    path("onboarding/", platform_views.OnboardingListCreateView.as_view(), name="platform-onboarding"),
    path("onboarding/<int:pk>/", platform_views.OnboardingDetailView.as_view(), name="platform-onboarding-detail"),
    path("onboarding/<int:pk>/provision/", platform_views.OnboardingProvisionView.as_view(), name="platform-onboarding-provision"),

    # ── Usage analytics ───────────────────────────────────────────────────────
    path("usage/", platform_views.UsageEventListView.as_view(), name="platform-usage"),
    path("usage/summary/", platform_views.UsageSummaryView.as_view(), name="platform-usage-summary"),

    # ── Support tickets ───────────────────────────────────────────────────────
    path("support/", platform_views.SupportTicketListCreateView.as_view(), name="platform-support"),
    path("support/<int:pk>/", platform_views.SupportTicketDetailView.as_view(), name="platform-support-detail"),

    # ── Security events ───────────────────────────────────────────────────────
    path("security-events/", platform_views.SecurityEventListView.as_view(), name="platform-security-events"),

    # ── Failed jobs ───────────────────────────────────────────────────────────
    path("failed-jobs/", platform_views.FailedJobListView.as_view(), name="platform-failed-jobs"),
    path("failed-jobs/<int:pk>/retry/", platform_views.FailedJobRetryView.as_view(), name="platform-failed-job-retry"),
    path("failed-jobs/<int:pk>/ignore/", platform_views.FailedJobIgnoreView.as_view(), name="platform-failed-job-ignore"),
]
