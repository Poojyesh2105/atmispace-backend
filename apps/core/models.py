from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

class Organization(TimestampedModel):
    """Top-level tenant entity. One row = one customer organization."""

    class SubscriptionStatus(models.TextChoices):
        TRIAL = "TRIAL", "Trial"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        CANCELLED = "CANCELLED", "Cancelled"

    # Identity
    name = models.CharField(max_length=180)
    code = models.CharField(max_length=40)
    slug = models.SlugField(max_length=80, unique=True)

    # Routing / tenant resolution
    domain = models.CharField(
        max_length=253,
        blank=True,
        default="",
        help_text="Custom domain for this org, e.g. hr.acme.com",
    )
    subdomain = models.SlugField(
        max_length=80,
        blank=True,
        default="",
        help_text="Subdomain prefix, e.g. 'acme' → acme.atmispace.com",
    )

    # Branding / contact
    logo = models.URLField(blank=True, default="", help_text="Public URL of the org logo")
    primary_email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    address = models.TextField(blank=True, default="")
    tax_id_number = models.CharField(max_length=80, blank=True, default="")

    # Locale / currency
    timezone = models.CharField(
        max_length=60,
        blank=True,
        default="Asia/Kolkata",
        help_text="pytz timezone string, e.g. 'America/New_York'",
    )
    country = models.CharField(max_length=80, blank=True, default="India")
    currency = models.CharField(
        max_length=10,
        blank=True,
        default="INR",
        help_text="ISO 4217 currency code, e.g. INR, USD",
    )

    # Lifecycle
    is_active = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        help_text="The default org used for single-org mode and data back-fill",
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIAL,
        db_index=True,
    )

    # Flexible extra data
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("domain"),
                condition=~Q(domain=""),
                name="unique_org_domain_ci",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active", "is_default"]),
            models.Index(fields=["domain"]),
            models.Index(fields=["subdomain"]),
            models.Index(fields=["subscription_status"]),
        ]

    def __str__(self):
        return self.name

    @property
    def is_operational(self):
        return self.is_active and self.subscription_status in {
            self.SubscriptionStatus.TRIAL,
            self.SubscriptionStatus.ACTIVE,
        }


# ---------------------------------------------------------------------------
# Organization Membership
# ---------------------------------------------------------------------------

class OrganizationMembership(TimestampedModel):
    """
    Links a User to an Organization with an org-scoped role.
    A user may belong to multiple organizations (future-ready).
    SUPER_ADMIN users are NOT required to have memberships — they are
    implicitly permitted across all orgs via the role on the User model.
    """

    class Role(models.TextChoices):
        EMPLOYEE = "EMPLOYEE", "Employee"
        MANAGER = "MANAGER", "Manager"
        HR = "HR", "HR"
        ACCOUNTS = "ACCOUNTS", "Accounts"
        ADMIN = "ADMIN", "Admin"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="org_memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    is_active = models.BooleanField(default=True, db_index=True)
    is_primary = models.BooleanField(
        default=True,
        help_text="The user's primary/default org when they belong to multiple orgs",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "organization__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="unique_user_org_membership",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "role", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user} @ {self.organization} [{self.role}]"


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

class FeatureFlag(TimestampedModel):
    """
    Platform-level feature toggles.
    Global flags (organization=None) set the default.
    Org-specific flags override the global default for that org.
    """

    # Well-known flag keys — use these constants everywhere in code
    ENABLE_PAYROLL = "enable_payroll"
    ENABLE_PERFORMANCE = "enable_performance"
    ENABLE_LIFECYCLE = "enable_lifecycle"
    ENABLE_DOCUMENTS = "enable_documents"
    ENABLE_SCHEDULING = "enable_scheduling"
    ENABLE_BIOMETRIC = "enable_biometric"
    ENABLE_HELPDESK = "enable_helpdesk"
    ENABLE_ANALYTICS = "enable_analytics"

    ALL_KEYS = [
        ENABLE_PAYROLL,
        ENABLE_PERFORMANCE,
        ENABLE_LIFECYCLE,
        ENABLE_DOCUMENTS,
        ENABLE_SCHEDULING,
        ENABLE_BIOMETRIC,
        ENABLE_HELPDESK,
        ENABLE_ANALYTICS,
    ]

    key = models.CharField(
        max_length=100,
        help_text="snake_case key, e.g. 'enable_payroll'",
    )
    label = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_enabled = models.BooleanField(default=False, db_index=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="feature_flags",
        help_text="None = global default; set to override for a specific org.",
    )

    class Meta:
        ordering = ["key"]
        constraints = [
            models.UniqueConstraint(
                fields=["key", "organization"],
                condition=Q(organization__isnull=False),
                name="unique_feature_flag_key_per_org",
            ),
            models.UniqueConstraint(
                fields=["key"],
                condition=Q(organization__isnull=True),
                name="unique_global_feature_flag_key",
            ),
        ]
        indexes = [
            models.Index(fields=["key", "is_enabled"]),
            models.Index(fields=["organization", "key"]),
        ]

    def __str__(self):
        scope = f"[{self.organization}]" if self.organization_id else "[global]"
        return f"{self.key} {scope} → {'ON' if self.is_enabled else 'OFF'}"

    @classmethod
    def is_enabled_for(cls, key: str, organization=None) -> bool:
        """
        Resolve flag state for a given org:
        1. Org-specific override if it exists
        2. Global default
        3. False (safe default)
        """
        if organization is not None:
            org_flag = cls.objects.filter(key=key, organization=organization).first()
            if org_flag is not None:
                return org_flag.is_enabled

        global_flag = cls.objects.filter(key=key, organization__isnull=True).first()
        return global_flag.is_enabled if global_flag is not None else False


# ---------------------------------------------------------------------------
# Tenant resolution helpers (used by middleware + services)
# ---------------------------------------------------------------------------

def resolve_current_organization(actor=None, organization=None):
    """Return the current org from explicit arg or from the actor's primary org."""
    if organization is not None:
        return organization
    if actor is not None:
        organization_id = getattr(actor, "organization_id", None)
        if organization_id:
            organization = getattr(actor, "organization", None)
            if organization is not None:
                return organization
            return Organization.objects.filter(pk=organization_id, is_active=True).first()
        try:
            membership = (
                actor.org_memberships.filter(is_active=True)
                .select_related("organization")
                .order_by("-is_primary", "id")
                .first()
            )
            if membership:
                return membership.organization
        except Exception:
            pass
    return None


def get_default_organization():
    """Return the default org (used for single-org / legacy data)."""
    return Organization.objects.filter(is_default=True, is_active=True).first()


# ---------------------------------------------------------------------------
# Org-Scoped QuerySet / Manager / Model
# ---------------------------------------------------------------------------

class OrganizationScopedQuerySet(models.QuerySet):
    def for_organization(self, organization, include_global=False):
        """
        Filter to records belonging to `organization`.
        include_global=True also returns records where organization IS NULL
        (shared/global records).
        """
        if organization is None:
            return self
        if include_global:
            return self.filter(Q(organization=organization) | Q(organization__isnull=True))
        return self.filter(organization=organization)

    # Convenience alias used widely across the codebase
    def for_org(self, organization, include_global=False):
        return self.for_organization(organization, include_global=include_global)

    def for_current_org(self, actor=None, organization=None, include_global=False):
        return self.for_organization(
            resolve_current_organization(actor=actor, organization=organization),
            include_global=include_global,
        )


class OrganizationScopedManager(models.Manager):
    def get_queryset(self):
        return OrganizationScopedQuerySet(self.model, using=self._db)

    def for_org(self, organization, include_global=False):
        return self.get_queryset().for_org(organization, include_global=include_global)

    def for_current_org(self, actor=None, organization=None, include_global=False):
        return self.get_queryset().for_current_org(
            actor=actor,
            organization=organization,
            include_global=include_global,
        )

    def for_organization(self, organization, include_global=False):
        return self.get_queryset().for_organization(organization, include_global=include_global)


class OrganizationScopedModel(TimestampedModel):
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_records",
    )

    objects = OrganizationScopedManager()

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Organization Settings (per-org configuration store)
# ---------------------------------------------------------------------------

class OrganizationSettings(TimestampedModel):
    """
    Per-organization configuration stored as JSON blobs.
    One row per organization, created on first access (get_or_create).

    Config shape (all keys optional — fall back to platform defaults):

    attendance_config  : { check_in_window_minutes, geo_fence_radius_m,
                           biometric_enabled, remote_check_in_allowed }
    leave_config       : { casual_days_per_year, sick_days_per_year,
                           earned_accrual_per_month, carry_forward_enabled }
    payroll_config     : { payroll_day, currency, pay_cycle, include_pf,
                           include_esi, overtime_eligible }
    feature_config     : { modules_enabled: [list of feature keys] }
    branding_config    : { primary_color, secondary_color, logo_url,
                           favicon_url, app_name }
    """

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="settings",
    )

    attendance_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Attendance policy configuration for this org.",
    )
    leave_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Leave policy defaults for this org.",
    )
    payroll_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Payroll processing configuration for this org.",
    )
    feature_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Module feature overrides for this org.",
    )
    branding_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Visual branding for this org (colors, logo, app name).",
    )

    class Meta:
        verbose_name = "Organization Settings"
        verbose_name_plural = "Organization Settings"

    def __str__(self):
        return f"Settings for {self.organization}"

    @classmethod
    def for_org(cls, organization):
        """Return (or create) settings for the given organization."""
        settings, _ = cls.objects.get_or_create(organization=organization)
        return settings
