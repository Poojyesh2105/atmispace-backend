"""
Platform governance API — accessible only to SUPER_ADMIN users.
Provides:
  - Platform overview (user counts, payroll stats, approval queues)
  - System health (Celery queues, cache, database)
  - Feature flag management (CRUD)
  - Global audit log viewer
  - Organization management
"""
import logging
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView

from apps.audit.models import AuditLog
from apps.core.models import FeatureFlag, Organization
from apps.core.permissions import IsSuperAdmin
from apps.core.responses import success_response, error_response
from apps.core.throttling import PlatformBurstThrottle, PlatformSustainedThrottle

from .serializers import FeatureFlagSerializer, OrganizationSerializer


# Applied to every platform view via the mixin below
_PLATFORM_THROTTLES = [PlatformBurstThrottle, PlatformSustainedThrottle]

logger = logging.getLogger("atmispace.platform")
User = get_user_model()


# ---------------------------------------------------------------------------
# Platform Overview
# ---------------------------------------------------------------------------

class PlatformOverviewView(APIView):
    """
    GET /api/v1/platform/overview/
    Returns high-level platform statistics for the SUPER_ADMIN dashboard.
    """
    permission_classes = [IsSuperAdmin]
    throttle_classes = _PLATFORM_THROTTLES

    def get(self, request):
        cache_key = "platform:overview"
        cached = cache.get(cache_key)
        if cached:
            return success_response(cached)

        User_ = get_user_model()

        # Import here to avoid circular imports
        try:
            from apps.payroll.models import PayrollRun
            payroll_runs = PayrollRun.objects.count()
            recent_payroll = PayrollRun.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).count()
        except Exception:
            payroll_runs = 0
            recent_payroll = 0

        try:
            from apps.workflow.models import WorkflowAssignment
            pending_approvals = WorkflowAssignment.objects.filter(status="PENDING").count()
        except Exception:
            pending_approvals = 0

        try:
            from apps.employees.models import Employee
            active_employees = Employee.objects.filter(is_active=True).count()
        except Exception:
            active_employees = 0

        data = {
            "total_users": User_.objects.count(),
            "active_users": User_.objects.filter(is_active=True).count(),
            "total_organizations": Organization.objects.count(),
            "active_organizations": Organization.objects.filter(is_active=True).count(),
            "active_employees": active_employees,
            "payroll_runs_total": payroll_runs,
            "payroll_runs_last_30_days": recent_payroll,
            "pending_approvals": pending_approvals,
            "total_feature_flags": FeatureFlag.objects.count(),
            "enabled_feature_flags": FeatureFlag.objects.filter(is_enabled=True).count(),
            "generated_at": timezone.now().isoformat(),
        }
        cache.set(cache_key, data, timeout=60)
        logger.info("platform_overview_accessed", extra={"user_id": request.user.pk})
        return success_response(data)


# ---------------------------------------------------------------------------
# System Health
# ---------------------------------------------------------------------------

class SystemHealthView(APIView):
    """
    GET /api/v1/platform/health/
    Returns database, cache, and Celery queue health indicators.
    """
    permission_classes = [IsSuperAdmin]
    throttle_classes = _PLATFORM_THROTTLES

    def get(self, request):
        health = {}

        # Database check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health["database"] = {"status": "ok"}
        except Exception as exc:
            health["database"] = {"status": "error", "detail": str(exc)}

        # Cache check
        try:
            probe_key = "_health_probe_"
            cache.set(probe_key, "1", timeout=5)
            val = cache.get(probe_key)
            health["cache"] = {"status": "ok" if val == "1" else "degraded"}
        except Exception as exc:
            health["cache"] = {"status": "error", "detail": str(exc)}

        # Celery / Redis check
        try:
            from celery import current_app
            inspector = current_app.control.inspect(timeout=2)
            active = inspector.active()
            health["celery"] = {
                "status": "ok" if active is not None else "unreachable",
                "active_workers": len(active) if active else 0,
            }
        except Exception as exc:
            health["celery"] = {"status": "error", "detail": str(exc)}

        # Recent audit log volume as a proxy for activity
        try:
            recent_logs = AuditLog.objects.filter(
                timestamp__gte=timezone.now() - timezone.timedelta(hours=1)
            ).count()
            health["audit_activity"] = {"logs_last_hour": recent_logs, "status": "ok"}
        except Exception as exc:
            health["audit_activity"] = {"status": "error", "detail": str(exc)}

        overall = "ok" if all(v.get("status") == "ok" for v in health.values()) else "degraded"
        return success_response({"overall": overall, "checks": health})


# ---------------------------------------------------------------------------
# Feature Flag Management
# ---------------------------------------------------------------------------

class FeatureFlagListCreateView(CreateAPIView, ListAPIView):
    """
    GET  /api/v1/platform/feature-flags/   — list all flags
    POST /api/v1/platform/feature-flags/   — create new flag
    """
    permission_classes = [IsSuperAdmin]
    throttle_classes = _PLATFORM_THROTTLES
    serializer_class = FeatureFlagSerializer

    def get_queryset(self):
        qs = FeatureFlag.objects.select_related("organization").order_by("key")
        org_id = self.request.query_params.get("organization")
        if org_id:
            qs = qs.filter(organization_id=org_id)
        enabled = self.request.query_params.get("is_enabled")
        if enabled is not None:
            qs = qs.filter(is_enabled=enabled.lower() == "true")
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        serializer = self.get_serializer(qs, many=True)
        return success_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flag = serializer.save()
        logger.info(
            "feature_flag_created",
            extra={"user_id": request.user.pk, "flag_key": flag.key},
        )
        return success_response(serializer.data, status_code=status.HTTP_201_CREATED)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class FeatureFlagDetailView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/platform/feature-flags/<id>/
    PATCH  /api/v1/platform/feature-flags/<id>/
    DELETE /api/v1/platform/feature-flags/<id>/
    """
    permission_classes = [IsSuperAdmin]
    throttle_classes = _PLATFORM_THROTTLES
    serializer_class = FeatureFlagSerializer
    queryset = FeatureFlag.objects.select_related("organization")

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        flag = serializer.save()
        # Invalidate platform overview cache when flags change
        cache.delete("platform:overview")
        logger.info(
            "feature_flag_updated",
            extra={"user_id": request.user.pk, "flag_key": flag.key, "is_enabled": flag.is_enabled},
        )
        return success_response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        key = instance.key
        instance.delete()
        cache.delete("platform:overview")
        logger.info("feature_flag_deleted", extra={"user_id": request.user.pk, "flag_key": key})
        return success_response({"detail": "Feature flag deleted."}, status_code=status.HTTP_200_OK)


class FeatureFlagToggleView(APIView):
    """
    POST /api/v1/platform/feature-flags/<id>/toggle/
    Quickly flip is_enabled on a flag.
    """
    permission_classes = [IsSuperAdmin]
    throttle_classes = _PLATFORM_THROTTLES

    def post(self, request, pk):
        try:
            flag = FeatureFlag.objects.get(pk=pk)
        except FeatureFlag.DoesNotExist:
            return error_response("Feature flag not found.", status_code=status.HTTP_404_NOT_FOUND)
        flag.is_enabled = not flag.is_enabled
        flag.save(update_fields=["is_enabled", "updated_at"])
        cache.delete("platform:overview")
        logger.info(
            "feature_flag_toggled",
            extra={"user_id": request.user.pk, "flag_key": flag.key, "is_enabled": flag.is_enabled},
        )
        return success_response({
            "key": flag.key,
            "is_enabled": flag.is_enabled,
            "detail": f"Flag '{flag.key}' is now {'enabled' if flag.is_enabled else 'disabled'}.",
        })


# ---------------------------------------------------------------------------
# Global Audit Logs
# ---------------------------------------------------------------------------

class GlobalAuditLogView(ListAPIView):
    """
    GET /api/v1/platform/audit-logs/
    Returns platform-wide audit logs with filtering by module, user, action.
    """
    permission_classes = [IsSuperAdmin]
    throttle_classes = _PLATFORM_THROTTLES

    def list(self, request):
        qs = AuditLog.objects.select_related(
            "actor",
            "actor__organization",
            "organization",
        ).order_by("-timestamp")

        # Filtering
        entity_type = request.query_params.get("module")
        if entity_type:
            qs = qs.filter(entity_type__icontains=entity_type)
        action = request.query_params.get("action")
        if action:
            qs = qs.filter(action__icontains=action)
        user_id = request.query_params.get("user_id")
        if user_id:
            qs = qs.filter(actor_id=user_id)
        org_id = request.query_params.get("organization")
        if org_id:
            qs = qs.filter(organization_id=org_id)
        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)

        # Pagination
        from apps.core.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)

        def _organization_id(log):
            if log.organization_id:
                return log.organization_id
            return getattr(log.actor, "organization_id", None) if log.actor else None

        def _organization_name(log):
            if log.organization:
                return log.organization.name
            actor_org = getattr(log.actor, "organization", None) if log.actor else None
            return actor_org.name if actor_org else None

        data = [
            {
                "id": log.id,
                "action": log.action,
                "module": log.entity_type,
                "entity_id": log.entity_id,
                "actor_id": log.actor_id,
                "actor_email": log.actor.email if log.actor else None,
                "actor_name": log.actor.full_name if log.actor else None,
                "organization_id": _organization_id(log),
                "organization_name": _organization_name(log),
                "before": log.before,
                "after": log.after,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in page
        ]
        return paginator.get_paginated_response(data)


# ---------------------------------------------------------------------------
# Organization Management
# ---------------------------------------------------------------------------

class OrganizationListCreateView(APIView):
    """
    GET  /api/v1/platform/organizations/
    POST /api/v1/platform/organizations/
    """
    permission_classes = [IsSuperAdmin]
    throttle_classes = _PLATFORM_THROTTLES

    def get(self, request):
        qs = Organization.objects.all()
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")
        serializer = OrganizationSerializer(qs, many=True)
        return success_response(serializer.data)

    def post(self, request):
        serializer = OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = serializer.save()
        logger.info("organization_created", extra={"user_id": request.user.pk, "org_id": org.pk, "name": org.name})
        return success_response(serializer.data, status_code=status.HTTP_201_CREATED)


class OrganizationDetailView(APIView):
    """
    GET   /api/v1/platform/organizations/<id>/
    PATCH /api/v1/platform/organizations/<id>/
    """
    permission_classes = [IsSuperAdmin]
    throttle_classes = _PLATFORM_THROTTLES

    def _get_org(self, pk):
        try:
            return Organization.objects.get(pk=pk)
        except Organization.DoesNotExist:
            return None

    def get(self, request, pk):
        org = self._get_org(pk)
        if not org:
            return error_response("Organization not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = OrganizationSerializer(org)
        return success_response(serializer.data)

    def patch(self, request, pk):
        org = self._get_org(pk)
        if not org:
            return error_response("Organization not found.", status_code=status.HTTP_404_NOT_FOUND)
        serializer = OrganizationSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info("organization_updated", extra={"user_id": request.user.pk, "org_id": org.pk})
        return success_response(serializer.data)


# ---------------------------------------------------------------------------
# Cross-org Aggregate Reports (SUPER_ADMIN)
# ---------------------------------------------------------------------------

class PlatformReportsView(APIView):
    """
    GET /api/v1/platform/reports/
    Returns cross-organization aggregate statistics for the SUPER_ADMIN.
    Supports ?org_id= to drill into a single organization.
    """
    permission_classes = [IsSuperAdmin]
    throttle_classes = _PLATFORM_THROTTLES

    def get(self, request):
        from django.db.models import Count
        from apps.employees.models import Employee
        from apps.leave_management.models import LeaveRequest
        from apps.payroll.models import PayrollRun
        from apps.workflow.models import ApprovalInstance

        cache_key = "platform:reports"
        org_id = request.query_params.get("org_id")
        if org_id:
            cache_key = f"platform:reports:org:{org_id}"

        cached = cache.get(cache_key)
        if cached:
            return success_response(cached)

        try:
            orgs_qs = Organization.objects.filter(is_active=True)
            if org_id:
                orgs_qs = orgs_qs.filter(pk=org_id)

            # Platform-wide summary
            org_ids = list(orgs_qs.values_list("pk", flat=True))

            total_employees = Employee.objects.filter(
                organization_id__in=org_ids, is_active=True
            ).count()

            leave_requests_month = LeaveRequest.objects.filter(
                employee__organization_id__in=org_ids,
                created_at__gte=timezone.now() - timezone.timedelta(days=30),
            ).count()

            pending_approvals = ApprovalInstance.objects.filter(
                organization_id__in=org_ids,
                status=ApprovalInstance.Status.PENDING,
            ).count()

            payroll_runs_month = PayrollRun.objects.filter(
                organization_id__in=org_ids,
                created_at__gte=timezone.now() - timezone.timedelta(days=30),
            ).count()

            # Per-org breakdown
            per_org = []
            for org in orgs_qs.order_by("name"):
                emp_count = Employee.objects.filter(
                    organization=org, is_active=True
                ).count()
                user_count = User.objects.filter(
                    organization=org, is_active=True
                ).count()
                active_flags = FeatureFlag.objects.filter(
                    organization=org, is_enabled=True
                ).count()
                org_leave = LeaveRequest.objects.filter(
                    employee__organization=org,
                    status=LeaveRequest.Status.PENDING,
                ).count()
                org_approvals = ApprovalInstance.objects.filter(
                    organization=org,
                    status=ApprovalInstance.Status.PENDING,
                ).count()
                per_org.append({
                    "id": org.pk,
                    "name": org.name,
                    "code": org.code,
                    "subscription_status": getattr(org, "subscription_status", ""),
                    "active_employees": emp_count,
                    "active_users": user_count,
                    "enabled_feature_flags": active_flags,
                    "pending_leave_requests": org_leave,
                    "pending_approvals": org_approvals,
                })

            data = {
                "summary": {
                    "total_active_organizations": len(org_ids),
                    "total_active_employees": total_employees,
                    "leave_requests_last_30d": leave_requests_month,
                    "payroll_runs_last_30d": payroll_runs_month,
                    "pending_approvals": pending_approvals,
                },
                "organizations": per_org,
                "generated_at": timezone.now().isoformat(),
            }
            cache.set(cache_key, data, timeout=120)
            logger.info(
                "platform_reports_accessed",
                extra={"user_id": request.user.pk, "org_id_filter": org_id},
            )
            return success_response(data)

        except Exception as exc:
            logger.error("platform_reports_error", extra={"error": str(exc)}, exc_info=True)
            return error_response(
                "Failed to generate platform reports.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# User Management (global)
# ---------------------------------------------------------------------------

class GlobalUserListView(ListAPIView):
    """
    GET /api/v1/platform/users/
    Lists all users across all organizations.
    """
    permission_classes = [IsSuperAdmin]
    throttle_classes = _PLATFORM_THROTTLES

    def list(self, request):
        from django.contrib.auth import get_user_model
        User_ = get_user_model()
        qs = User_.objects.select_related("organization").prefetch_related(
            "org_memberships__organization"
        ).order_by("email")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(email__icontains=search)
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        org_id = request.query_params.get("organization")
        if org_id:
            qs = qs.filter(organization_id=org_id)

        from apps.core.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)

        def _primary_membership(user):
            memberships = sorted(
                [membership for membership in user.org_memberships.all() if membership.is_active],
                key=lambda membership: (not membership.is_primary, membership.id),
            )
            return memberships[0] if memberships else None

        def _primary_membership_org_id(user):
            membership = _primary_membership(user)
            return membership.organization_id if membership else None

        def _primary_membership_org_name(user):
            membership = _primary_membership(user)
            return membership.organization.name if membership and membership.organization else None

        data = [
            {
                "id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "organization_id": u.organization_id or _primary_membership_org_id(u),
                "organization_name": u.organization.name if u.organization else _primary_membership_org_name(u),
                "date_joined": u.date_joined.isoformat(),
            }
            for u in page
        ]
        return paginator.get_paginated_response(data)
