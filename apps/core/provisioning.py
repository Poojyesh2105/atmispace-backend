"""
OrganizationProvisioningService
===============================
Handles the full onboarding flow for a new tenant organization:
  1. Create the Organization record (with unique slug derived from name)
  2. Seed default FeatureFlags for the new org
  3. Create or look up the admin user, assign them via OrganizationMembership
  4. Return a structured result dict

All operations are wrapped in a single atomic transaction so a partial
failure leaves no orphaned data.
"""
import logging
import secrets
import string
from urllib.parse import urlparse

from django.db import transaction
from django.utils.text import slugify

from apps.core.models import FeatureFlag, Organization, OrganizationMembership

logger = logging.getLogger("atmispace.platform")


class ProvisioningError(Exception):
    """Raised when provisioning cannot complete (business rule violation)."""


class OrganizationProvisioningService:

    # Features that are enabled by default for every new org
    DEFAULT_ENABLED_FLAGS = [
        FeatureFlag.ENABLE_PAYROLL,
        FeatureFlag.ENABLE_LIFECYCLE,
        FeatureFlag.ENABLE_DOCUMENTS,
        FeatureFlag.ENABLE_SCHEDULING,
        FeatureFlag.ENABLE_ANALYTICS,
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    @transaction.atomic
    def provision(
        cls,
        *,
        name: str,
        code: str,
        domain: str,
        subdomain: str = "",
        primary_email: str = "",
        phone: str = "",
        address: str = "",
        tax_id_number: str = "",
        timezone: str = "Asia/Kolkata",
        country: str = "India",
        currency: str = "INR",
        admin_email: str = "",
        admin_first_name: str = "",
        admin_last_name: str = "",
        provisioned_by=None,
    ) -> dict:
        """
        Create a new tenant organization and run the full onboarding flow.

        If ``admin_email`` is provided and no matching User exists, a new
        User account is created with ``force_password_reset=True`` and a
        random temporary password (logged at WARNING level for ops handoff).

        Returns a dict:
          {
            "organization": <Organization instance>,
            "membership": <OrganizationMembership | None>,
            "flags_seeded": [list of flag keys],
            "admin_created": bool,
            "admin_temp_password": str | None,
          }
        """
        # Validate required fields
        if not name.strip():
            raise ProvisioningError("Organization name is required.")
        if not code.strip():
            raise ProvisioningError("Organization code is required.")
        domain = cls._normalize_domain(domain)
        if not domain:
            raise ProvisioningError("Organization domain is required.")
        if Organization.objects.filter(domain__iexact=domain).exists():
            raise ProvisioningError(f"Organization domain '{domain}' is already in use.")

        slug = cls._unique_slug(name)
        subdomain = subdomain or cls._derive_subdomain(domain, name)

        org = Organization.objects.create(
            name=name.strip(),
            code=code.upper(),
            slug=slug,
            domain=domain,
            subdomain=subdomain.lower().strip(),
            primary_email=primary_email.strip(),
            phone=phone,
            address=address,
            tax_id_number=tax_id_number.strip(),
            timezone=timezone or "Asia/Kolkata",
            country=country or "India",
            currency=(currency or "INR").upper(),
            is_active=True,
            subscription_status=Organization.SubscriptionStatus.TRIAL,
        )

        flags_seeded = cls._seed_feature_flags(org)

        admin_created = False
        admin_temp_password = None
        membership = None
        if admin_email:
            membership, admin_created, admin_temp_password = cls._provision_admin(
                org=org,
                admin_email=admin_email,
                first_name=admin_first_name,
                last_name=admin_last_name,
            )

        logger.info(
            "org.provisioned",
            extra={
                "event": "org.provisioned",
                "org_id": org.pk,
                "org_name": org.name,
                "admin_email": admin_email or None,
                "admin_created": admin_created,
                "provisioned_by": getattr(provisioned_by, "pk", None),
            },
        )

        return {
            "organization": org,
            "membership": membership,
            "flags_seeded": flags_seeded,
            "admin_created": admin_created,
            "admin_temp_password": admin_temp_password,
        }

    @classmethod
    @transaction.atomic
    def deprovision(cls, organization: Organization, deprovisioned_by=None):
        """
        Soft-delete an organization by marking it as CANCELLED + inactive.
        Hard-delete is intentionally NOT done here — requires a separate
        manual confirmation step.
        """
        organization.is_active = False
        organization.subscription_status = Organization.SubscriptionStatus.CANCELLED
        organization.save(update_fields=["is_active", "subscription_status", "updated_at"])

        # Deactivate all memberships
        OrganizationMembership.objects.filter(organization=organization).update(is_active=False)

        logger.warning(
            "org.deprovisioned",
            extra={
                "event": "org.deprovisioned",
                "org_id": organization.pk,
                "org_name": organization.name,
                "deprovisioned_by": getattr(deprovisioned_by, "pk", None),
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unique_slug(name: str) -> str:
        base = slugify(name)[:70]
        slug = base
        counter = 1
        while Organization.objects.filter(slug=slug).exists():
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        raw = (domain or "").strip().lower()
        if not raw:
            return ""
        parsed = urlparse(raw if "://" in raw else f"//{raw}")
        host = parsed.netloc or parsed.path
        return host.split("/")[0].split(":")[0].strip(".")

    @staticmethod
    def _derive_subdomain(domain: str, name: str) -> str:
        host = OrganizationProvisioningService._normalize_domain(domain)
        first_label = host.split(".")[0] if host else ""
        return slugify(first_label or name)[:80]

    @classmethod
    def _seed_feature_flags(cls, org: Organization) -> list:
        """Create per-org FeatureFlag overrides for all known flags."""
        seeded = []
        for key in FeatureFlag.ALL_KEYS:
            enabled = key in cls.DEFAULT_ENABLED_FLAGS
            FeatureFlag.objects.get_or_create(
                key=key,
                organization=org,
                defaults={
                    "is_enabled": enabled,
                    "label": key.replace("_", " ").title(),
                },
            )
            seeded.append(key)
        return seeded

    @staticmethod
    def _generate_temp_password(length: int = 16) -> str:
        """Generate a cryptographically random temporary password."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        # Guarantee at least one of each required character class
        password = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*"),
        ]
        password += [secrets.choice(alphabet) for _ in range(length - 4)]
        secrets.SystemRandom().shuffle(password)
        return "".join(password)

    @staticmethod
    def _provision_admin(
        org: Organization,
        admin_email: str,
        first_name: str = "",
        last_name: str = "",
    ):
        """
        Look up or create the admin user, then create an OrganizationMembership.

        Returns (membership, created: bool, temp_password: str | None).
        If the user already existed, temp_password is None.
        If the user was created, temp_password contains the generated password
        and the account has force_password_reset=True.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        admin_created = False
        temp_password = None

        try:
            user = User.objects.get(email=admin_email)
        except User.DoesNotExist:
            # Create a new org-scoped ADMIN user with a temp password
            temp_password = OrganizationProvisioningService._generate_temp_password()
            user = User.objects.create_user(
                email=admin_email,
                password=temp_password,
                first_name=first_name or admin_email.split("@")[0].capitalize(),
                last_name=last_name or "",
                role=User.Role.ADMIN,
                organization=org,
                is_active=True,
                force_password_reset=True,
            )
            admin_created = True
            logger.warning(
                "org.provision.admin_created",
                extra={
                    "admin_email": admin_email,
                    "org_id": org.pk,
                    # Do NOT log the password itself — only that one was generated
                    "temp_password_generated": True,
                },
            )

        if not admin_created and getattr(user, "role", None) != User.Role.SUPER_ADMIN:
            user_updates = []
            if getattr(user, "role", None) != User.Role.ADMIN:
                user.role = User.Role.ADMIN
                user_updates.append("role")
            if getattr(user, "organization_id", None) != org.pk:
                user.organization = org
                user_updates.append("organization")
            if not user.is_active:
                user.is_active = True
                user_updates.append("is_active")
            if user_updates:
                user.save(update_fields=[*user_updates, "updated_at"])

        membership, _ = OrganizationMembership.objects.get_or_create(
            user=user,
            organization=org,
            defaults={
                "role": OrganizationMembership.Role.ADMIN,
                "is_active": True,
                "is_primary": True,
            },
        )
        membership_updates = []
        if membership.role != OrganizationMembership.Role.ADMIN:
            membership.role = OrganizationMembership.Role.ADMIN
            membership_updates.append("role")
        if not membership.is_active:
            membership.is_active = True
            membership_updates.append("is_active")
        if not membership.is_primary:
            membership.is_primary = True
            membership_updates.append("is_primary")
        if membership_updates:
            membership.save(update_fields=[*membership_updates, "updated_at"])
        return membership, admin_created, temp_password
