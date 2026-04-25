"""
Org-context API endpoints
=========================
/api/v1/organizations/current/        GET  — current tenant details
/api/v1/organizations/current/        PATCH — update current org settings
/api/v1/organizations/mine/           GET  — orgs the authenticated user belongs to
/api/v1/organizations/switch/         POST — switch active org (returns new JWT context)
/api/v1/organizations/provision/      POST — SUPER_ADMIN: create a new org (full onboarding)
/api/v1/organizations/<pk>/deprovision/ POST — SUPER_ADMIN: cancel an org
"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.models import Organization, OrganizationMembership
from apps.core.permissions import IsSameOrganization, IsSuperAdmin
from apps.core.provisioning import OrganizationProvisioningService, ProvisioningError
from apps.core.models import OrganizationSettings
from apps.core.responses import success_response
from apps.core.role_utils import get_accessible_org_ids

from .serializers import (
    OrganizationDetailSerializer,
    OrganizationMembershipSerializer,
    OrganizationProvisioningSerializer,
    OrganizationSettingsSerializer,
    SwitchOrganizationSerializer,
)

logger = logging.getLogger("atmispace.platform")


class CurrentOrganizationView(APIView):
    """GET / PATCH the tenant org attached to the current request."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = getattr(request, "organization", None)
        if org is None:
            return success_response(data=None, message="No organization context resolved.")
        serializer = OrganizationDetailSerializer(org)
        return success_response(data=serializer.data)

    def patch(self, request):
        org = getattr(request, "organization", None)
        if org is None:
            return success_response(
                data=None,
                message="No organization context.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        # Only ADMIN / SUPER_ADMIN may update org settings
        from apps.core.role_utils import get_user_org_role, ELEVATED_ROLES
        role = get_user_org_role(request.user, org)
        if role not in ELEVATED_ROLES:
            return success_response(
                data=None,
                message="You do not have permission to update organization settings.",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = OrganizationDetailSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(
            "org.updated",
            extra={"org_id": org.pk, "updated_by": request.user.pk, "fields": list(request.data.keys())},
        )
        return success_response(data=serializer.data, message="Organization updated.")


class MyOrganizationsView(APIView):
    """
    GET  /api/v1/organizations/mine/
    Returns all orgs the authenticated user is a member of,
    including their role and which is primary.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # SUPER_ADMIN: return all active orgs (no membership needed)
        from apps.core.role_utils import is_super_admin
        if is_super_admin(user):
            orgs = Organization.objects.filter(is_active=True).order_by("name")
            data = OrganizationDetailSerializer(orgs, many=True).data
            return success_response(data=data)

        # Regular users: return their org memberships
        memberships = (
            OrganizationMembership.objects
            .filter(user=user, is_active=True)
            .select_related("organization")
            .order_by("-is_primary", "organization__name")
        )
        data = OrganizationMembershipSerializer(memberships, many=True).data
        return success_response(data=data)


class SwitchOrganizationView(APIView):
    """
    POST /api/v1/organizations/switch/
    Body: { "organization_id": <int> }

    Validates the user has access to the target org and returns
    updated user context. The frontend should update the
    X-Organization-ID header going forward.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SwitchOrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_org_id = serializer.validated_data["organization_id"]

        from apps.core.role_utils import is_super_admin
        user = request.user

        # SUPER_ADMIN can switch to any active org
        if is_super_admin(user):
            org = Organization.objects.filter(pk=target_org_id, is_active=True).first()
        else:
            # Regular user: must have an active membership
            accessible = get_accessible_org_ids(user)
            if accessible is not None and target_org_id not in accessible:
                return success_response(
                    data=None,
                    message="You do not have access to this organization.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )
            org = Organization.objects.filter(pk=target_org_id, is_active=True).first()

        if org is None:
            return success_response(
                data=None,
                message="Organization not found or inactive.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        logger.info(
            "org.switched",
            extra={"user_id": user.pk, "to_org_id": org.pk},
        )

        return success_response(
            data={
                "organization_id": org.pk,
                "organization_name": org.name,
                "message": f"Switched to {org.name}. Use X-Organization-ID: {org.pk} in future requests.",
            }
        )


class OrganizationProvisionView(APIView):
    """
    POST /api/v1/organizations/provision/
    SUPER_ADMIN only — full org onboarding.
    """

    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request):
        serializer = OrganizationProvisioningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = OrganizationProvisioningService.provision(
                name=data["name"],
                code=data["code"],
                domain=data["domain"],
                subdomain=data.get("subdomain", ""),
                primary_email=data.get("primary_email", ""),
                phone=data.get("phone", ""),
                address=data.get("address", ""),
                tax_id_number=data.get("tax_id_number", ""),
                timezone=data.get("timezone", "Asia/Kolkata"),
                country=data.get("country", "India"),
                currency=data.get("currency", "INR"),
                admin_email=data.get("admin_email", ""),
                provisioned_by=request.user,
            )
        except ProvisioningError as exc:
            return success_response(
                data=None,
                message=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        from apps.core.api.organizations.serializers import OrganizationDetailSerializer
        org_data = OrganizationDetailSerializer(result["organization"]).data
        return success_response(
            data={
                "organization": org_data,
                "flags_seeded": result["flags_seeded"],
                "admin_assigned": result["membership"] is not None,
            },
            message=f"Organization '{result['organization'].name}' provisioned successfully.",
            status_code=status.HTTP_201_CREATED,
        )


class OrganizationDeprovisionView(APIView):
    """
    POST /api/v1/organizations/<pk>/deprovision/
    SUPER_ADMIN only — soft-cancel an org.
    """

    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request, pk):
        org = Organization.objects.filter(pk=pk).first()
        if org is None:
            return success_response(
                data=None,
                message="Organization not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if org.is_default:
            return success_response(
                data=None,
                message="Cannot deprovision the default organization.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        OrganizationProvisioningService.deprovision(org, deprovisioned_by=request.user)
        return success_response(
            data={"organization_id": org.pk},
            message=f"Organization '{org.name}' has been deprovisioned.",
        )


class OrgSettingsView(APIView):
    """
    GET  /api/v1/organizations/current/settings/
    PATCH /api/v1/organizations/current/settings/
    Returns and updates per-org JSON config blobs.
    """
    permission_classes = [IsAuthenticated]

    def _get_settings(self, request):
        org = getattr(request, "organization", None)
        if org is None:
            return None, success_response(
                data=None,
                message="No organization context resolved.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return OrganizationSettings.for_org(org), None

    def get(self, request):
        settings, err = self._get_settings(request)
        if err:
            return err
        return success_response(data=OrganizationSettingsSerializer(settings).data)

    def patch(self, request):
        from apps.core.role_utils import ELEVATED_ROLES, get_user_org_role
        org = getattr(request, "organization", None)
        if org is None:
            return success_response(
                data=None, message="No organization context.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        role = get_user_org_role(request.user, org)
        if role not in ELEVATED_ROLES:
            return success_response(
                data=None, message="Admin or HR role required.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        settings = OrganizationSettings.for_org(org)
        serializer = OrganizationSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(
            "org.settings.updated",
            extra={"org_id": org.pk, "updated_by": request.user.pk,
                   "fields": list(request.data.keys())},
        )
        return success_response(data=serializer.data, message="Organization settings updated.")
