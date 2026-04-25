"""
SaaS Platform API views — all require IsSuperAdmin.

Endpoints:
  Subscription Plans       GET/POST /platform/plans/
                           GET/PATCH/DELETE /platform/plans/<pk>/
  Org Subscriptions        GET /platform/subscriptions/
                           GET/PATCH /platform/subscriptions/<org_pk>/
  Invoices                 GET /platform/invoices/
  Payments                 GET /platform/payments/
  Revenue Summary          GET /platform/revenue/
  Onboarding               GET/POST /platform/onboarding/
                           GET/PATCH /platform/onboarding/<pk>/
                           POST /platform/onboarding/<pk>/provision/
  Usage Events             GET /platform/usage/
                           GET /platform/usage/summary/
  Support Tickets          GET/POST /platform/support/
                           GET/PATCH /platform/support/<pk>/
  Security Events          GET /platform/security-events/
  Failed Jobs              GET /platform/failed-jobs/
                           POST /platform/failed-jobs/<pk>/retry/
                           POST /platform/failed-jobs/<pk>/ignore/
"""
import logging
from datetime import timedelta

from django.db.models import Count, FloatField, Sum, Value
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import Organization
from apps.core.permissions import IsSuperAdmin
from apps.core.provisioning import OrganizationProvisioningService, ProvisioningError
from apps.core.responses import success_response, error_response
from apps.core.pagination import StandardResultsSetPagination
from apps.platform.models import (
    FailedJob,
    Invoice,
    OrganizationOnboarding,
    OrganizationSubscription,
    Payment,
    PlatformSupportTicket,
    SecurityEvent,
    SubscriptionPlan,
    UsageEvent,
)
from .platform_serializers import (
    FailedJobSerializer,
    InvoiceSerializer,
    OrganizationOnboardingSerializer,
    OrganizationSubscriptionSerializer,
    PaymentSerializer,
    PlatformSupportTicketSerializer,
    SecurityEventSerializer,
    SubscriptionPlanSerializer,
    UsageEventSerializer,
)

logger = logging.getLogger("atmispace.platform")


# ── Helper ────────────────────────────────────────────────────────────────────

def _paginate(request, qs, serializer_class):
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(qs, request)
    data = serializer_class(page, many=True).data
    return paginator.get_paginated_response(data)


# ── Subscription Plans ────────────────────────────────────────────────────────

class SubscriptionPlanListCreateView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = SubscriptionPlan.objects.prefetch_related("subscriptions")
        if request.query_params.get("active_only"):
            qs = qs.filter(is_active=True)
        return success_response(
            SubscriptionPlanSerializer(qs, many=True).data
        )

    def post(self, request):
        ser = SubscriptionPlanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        plan = ser.save()
        logger.info("plan.created", extra={"plan_id": plan.pk, "by": request.user.pk})
        return success_response(ser.data, status_code=status.HTTP_201_CREATED)


class SubscriptionPlanDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def _get(self, pk):
        try:
            return SubscriptionPlan.objects.get(pk=pk)
        except SubscriptionPlan.DoesNotExist:
            return None

    def get(self, request, pk):
        plan = self._get(pk)
        if not plan:
            return error_response("Plan not found.", status_code=404)
        return success_response(SubscriptionPlanSerializer(plan).data)

    def patch(self, request, pk):
        plan = self._get(pk)
        if not plan:
            return error_response("Plan not found.", status_code=404)
        ser = SubscriptionPlanSerializer(plan, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return success_response(ser.data)

    def delete(self, request, pk):
        plan = self._get(pk)
        if not plan:
            return error_response("Plan not found.", status_code=404)
        if plan.subscriptions.filter(status__in=["ACTIVE", "TRIAL"]).exists():
            return error_response(
                "Cannot delete a plan with active subscribers.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        plan.delete()
        return success_response({"detail": "Plan deleted."})


# ── Org Subscriptions ─────────────────────────────────────────────────────────

class OrgSubscriptionListView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = OrganizationSubscription.objects.select_related(
            "organization", "plan"
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return _paginate(request, qs, OrganizationSubscriptionSerializer)


class OrgSubscriptionDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request, org_pk):
        try:
            sub = OrganizationSubscription.objects.select_related(
                "organization", "plan"
            ).get(organization_id=org_pk)
        except OrganizationSubscription.DoesNotExist:
            return error_response("Subscription not found.", status_code=404)
        return success_response(OrganizationSubscriptionSerializer(sub).data)

    def patch(self, request, org_pk):
        try:
            sub = OrganizationSubscription.objects.get(organization_id=org_pk)
        except OrganizationSubscription.DoesNotExist:
            # Auto-create if missing
            try:
                org = Organization.objects.get(pk=org_pk)
            except Organization.DoesNotExist:
                return error_response("Organization not found.", status_code=404)
            sub = OrganizationSubscription(organization=org)
        ser = OrganizationSubscriptionSerializer(sub, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return success_response(ser.data)


# ── Invoices ──────────────────────────────────────────────────────────────────

class InvoiceListView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = Invoice.objects.select_related("organization", "subscription")
        org_id = request.query_params.get("organization")
        if org_id:
            qs = qs.filter(organization_id=org_id)
        invoice_status = request.query_params.get("status")
        if invoice_status:
            qs = qs.filter(status=invoice_status)
        return _paginate(request, qs, InvoiceSerializer)


# ── Payments ──────────────────────────────────────────────────────────────────

class PaymentListView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = Payment.objects.select_related("organization", "invoice")
        org_id = request.query_params.get("organization")
        if org_id:
            qs = qs.filter(organization_id=org_id)
        return _paginate(request, qs, PaymentSerializer)


# ── Revenue Summary ───────────────────────────────────────────────────────────

class RevenueSummaryView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        subs = OrganizationSubscription.objects.select_related("plan", "organization")

        active_subs = subs.filter(status="ACTIVE")
        trial_subs = subs.filter(status="TRIAL")

        # MRR: sum of active subscriptions monthly amount
        mrr = active_subs.aggregate(total=Sum("mrr"))["total"] or 0
        arr = float(mrr) * 12

        paid_count = active_subs.count()
        trial_count = trial_subs.count()

        # Revenue this month (paid invoices)
        revenue_month = Invoice.objects.filter(
            status="PAID",
            paid_at__gte=month_start,
        ).aggregate(total=Sum("total_amount"))["total"] or 0

        # Failed payments this month
        failed_payments = Payment.objects.filter(
            status="FAILED",
            created_at__gte=month_start,
        ).count()

        # Outstanding invoices
        outstanding = Invoice.objects.filter(
            status__in=["OPEN", "OVERDUE"]
        ).aggregate(total=Sum("total_amount"))["total"] or 0

        # Churned (cancelled this month)
        churned = subs.filter(
            status="CANCELLED",
            updated_at__gte=month_start,
        ).count()

        # Revenue by plan
        # Aggregate MRR and subscriber count per plan in the DB — no Python loop
        by_plan_qs = (
            active_subs
            .values(plan_name=Coalesce("plan__name", Value("No Plan")))
            .annotate(
                count=Count("id"),
                mrr=Sum(Cast("mrr", output_field=FloatField())),
            )
            .order_by("-mrr")
        )
        by_plan = [
            {"plan": row["plan_name"], "mrr": row["mrr"] or 0.0, "count": row["count"]}
            for row in by_plan_qs
        ]

        data = {
            "mrr": float(mrr),
            "arr": float(arr),
            "paid_organizations": paid_count,
            "trial_organizations": trial_count,
            "revenue_this_month": float(revenue_month),
            "failed_payments_this_month": failed_payments,
            "outstanding_invoices_amount": float(outstanding),
            "churned_organizations_this_month": churned,
            "revenue_by_plan": by_plan,
            "generated_at": now.isoformat(),
        }
        return success_response(data)


# ── Organization Onboarding ───────────────────────────────────────────────────

class OnboardingListCreateView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = OrganizationOnboarding.objects.select_related(
            "organization", "provisioned_by"
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return _paginate(request, qs, OrganizationOnboardingSerializer)

    def post(self, request):
        """Create a new onboarding draft (step 1 data)."""
        onboarding = OrganizationOnboarding.objects.create(
            provisioned_by=request.user,
            status=OrganizationOnboarding.Status.PENDING,
            current_step=2,
            step_data=request.data,
        )
        logger.info("onboarding.created", extra={"onboarding_id": onboarding.pk, "by": request.user.pk})
        return success_response(
            OrganizationOnboardingSerializer(onboarding).data,
            status_code=status.HTTP_201_CREATED,
        )


class OnboardingDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def _get(self, pk):
        try:
            return OrganizationOnboarding.objects.select_related(
                "organization", "provisioned_by"
            ).get(pk=pk)
        except OrganizationOnboarding.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return error_response("Onboarding record not found.", status_code=404)
        return success_response(OrganizationOnboardingSerializer(obj).data)

    def patch(self, request, pk):
        """Update step data as the SUPER_ADMIN navigates through the stepper."""
        obj = self._get(pk)
        if not obj:
            return error_response("Onboarding record not found.", status_code=404)
        if obj.status == OrganizationOnboarding.Status.COMPLETED:
            return error_response("Cannot edit a completed onboarding.", status_code=400)

        # Merge step data
        step_data = {**obj.step_data, **request.data.get("step_data", {})}
        obj.step_data = step_data
        if "current_step" in request.data:
            obj.current_step = request.data["current_step"]
        obj.status = OrganizationOnboarding.Status.IN_PROGRESS
        obj.save(update_fields=["step_data", "current_step", "status", "updated_at"])
        return success_response(OrganizationOnboardingSerializer(obj).data)

    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return error_response("Onboarding record not found.", status_code=404)
        if obj.status == OrganizationOnboarding.Status.COMPLETED:
            return error_response("Completed onboarding records cannot be deleted.", status_code=400)

        obj.delete()
        logger.info("onboarding.deleted", extra={"onboarding_id": pk, "by": request.user.pk})
        return success_response({"id": pk}, message="Onboarding record deleted.")


class OnboardingProvisionView(APIView):
    """POST /platform/onboarding/<pk>/provision/ — execute the full provisioning."""
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        try:
            obj = OrganizationOnboarding.objects.get(pk=pk)
        except OrganizationOnboarding.DoesNotExist:
            return error_response("Onboarding record not found.", status_code=404)

        if obj.status == OrganizationOnboarding.Status.COMPLETED:
            return error_response("Already provisioned.", status_code=400)

        obj.status = OrganizationOnboarding.Status.IN_PROGRESS
        obj.save(update_fields=["status", "updated_at"])

        step_data = obj.step_data
        try:
            result = OrganizationProvisioningService.provision(
                name=step_data.get("name", ""),
                code=step_data.get("code", ""),
                domain=step_data.get("domain", ""),
                subdomain=step_data.get("subdomain", ""),
                primary_email=step_data.get("primary_email", ""),
                address=step_data.get("address", ""),
                tax_id_number=step_data.get("tax_id_number", ""),
                timezone=step_data.get("timezone", "Asia/Kolkata"),
                country=step_data.get("country", "India"),
                currency=step_data.get("currency", "INR"),
                admin_email=step_data.get("admin_email", ""),
                admin_first_name=step_data.get("admin_first_name", ""),
                admin_last_name=step_data.get("admin_last_name", ""),
                provisioned_by=request.user,
            )
            org = result["organization"]
            obj.organization = org
            obj.status = OrganizationOnboarding.Status.COMPLETED
            obj.completed_at = timezone.now()
            obj.error_message = ""
            obj.save(update_fields=["organization", "status", "completed_at", "error_message", "updated_at"])

            # Auto-create subscription in TRIAL
            OrganizationSubscription.objects.get_or_create(
                organization=org,
                defaults={
                    "status": (
                        OrganizationSubscription.Status.ACTIVE
                        if step_data.get("plan_code", "").upper() == "LIFETIME"
                        else OrganizationSubscription.Status.TRIAL
                    ),
                    "trial_end_date": timezone.localdate() + timedelta(days=30),
                    "plan": (
                        SubscriptionPlan.objects.filter(code=step_data.get("plan_code", "").lower(), is_active=True).first()
                        or SubscriptionPlan.objects.filter(is_active=True).order_by("display_order", "price_monthly").first()
                    ),
                    "billing_cycle": (
                        OrganizationSubscription.BillingCycle.YEARLY
                        if step_data.get("billing_cycle", "MONTHLY").upper() == "YEARLY"
                        or step_data.get("plan_code", "").upper() == "LIFETIME"
                        else OrganizationSubscription.BillingCycle.MONTHLY
                    ),
                },
            )

            logger.info(
                "onboarding.provisioned",
                extra={"org_id": org.pk, "by": request.user.pk},
            )
            response_payload = {
                "organization_id": org.pk,
                "organization_name": org.name,
                "admin_email": step_data.get("admin_email", ""),
                "admin_created": result.get("admin_created", False),
                "detail": "Organization provisioned successfully.",
            }
            # Only surface temp password in this single response — never stored
            if result.get("admin_created") and result.get("admin_temp_password"):
                response_payload["admin_temp_password"] = result["admin_temp_password"]
                response_payload["detail"] = (
                    "Organization provisioned. Admin account created — "
                    "share the temporary password securely. It will not be shown again."
                )
            return success_response(response_payload)

        except ProvisioningError as exc:
            obj.status = OrganizationOnboarding.Status.FAILED
            obj.error_message = str(exc)
            obj.save(update_fields=["status", "error_message", "updated_at"])
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            obj.status = OrganizationOnboarding.Status.FAILED
            obj.error_message = str(exc)
            obj.save(update_fields=["status", "error_message", "updated_at"])
            logger.error("onboarding.provision_error", extra={"pk": pk, "error": str(exc)}, exc_info=True)
            return error_response(
                "Provisioning failed. See platform logs.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ── Usage Analytics ───────────────────────────────────────────────────────────

class UsageEventListView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = UsageEvent.objects.select_related("organization", "user")
        org_id = request.query_params.get("organization")
        if org_id:
            qs = qs.filter(organization_id=org_id)
        module = request.query_params.get("module")
        if module:
            qs = qs.filter(module=module)
        days = int(request.query_params.get("days", 30))
        since = timezone.now() - timedelta(days=days)
        qs = qs.filter(created_at__gte=since)
        return _paginate(request, qs, UsageEventSerializer)


class UsageSummaryView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        since = timezone.now() - timedelta(days=days)
        qs = UsageEvent.objects.filter(created_at__gte=since)

        by_module = list(
            qs.values("module").annotate(count=Count("id")).order_by("-count")
        )
        by_org = list(
            qs.values("organization_id")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        )
        # Re-fetch org names
        org_ids = [r["organization_id"] for r in by_org]
        org_names = dict(
            Organization.objects.filter(pk__in=org_ids).values_list("id", "name")
        )
        for r in by_org:
            r["organization_name"] = org_names.get(r["organization_id"], "")

        return success_response({
            "period_days": days,
            "total_events": qs.count(),
            "by_module": by_module,
            "by_organization": by_org,
        })


# ── Platform Support Tickets ──────────────────────────────────────────────────

class SupportTicketListCreateView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = PlatformSupportTicket.objects.select_related(
            "organization", "created_by", "assigned_to"
        )
        org_id = request.query_params.get("organization")
        if org_id:
            qs = qs.filter(organization_id=org_id)
        ticket_status = request.query_params.get("status")
        if ticket_status:
            qs = qs.filter(status=ticket_status)
        priority = request.query_params.get("priority")
        if priority:
            qs = qs.filter(priority=priority)
        return _paginate(request, qs, PlatformSupportTicketSerializer)

    def post(self, request):
        ser = PlatformSupportTicketSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ticket = ser.save(created_by=request.user)
        return success_response(
            PlatformSupportTicketSerializer(ticket).data,
            status_code=status.HTTP_201_CREATED,
        )


class SupportTicketDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def _get(self, pk):
        try:
            return PlatformSupportTicket.objects.select_related(
                "organization", "created_by", "assigned_to"
            ).get(pk=pk)
        except PlatformSupportTicket.DoesNotExist:
            return None

    def get(self, request, pk):
        ticket = self._get(pk)
        if not ticket:
            return error_response("Ticket not found.", status_code=404)
        return success_response(PlatformSupportTicketSerializer(ticket).data)

    def patch(self, request, pk):
        ticket = self._get(pk)
        if not ticket:
            return error_response("Ticket not found.", status_code=404)
        ser = PlatformSupportTicketSerializer(ticket, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        # Auto-set resolved_at
        if request.data.get("status") in ("RESOLVED", "CLOSED") and not ticket.resolved_at:
            ser.save(resolved_at=timezone.now())
        else:
            ser.save()
        return success_response(ser.data)


# ── Security Events ───────────────────────────────────────────────────────────

class SecurityEventListView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = SecurityEvent.objects.select_related("organization", "user")
        event_type = request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)
        severity = request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity)
        org_id = request.query_params.get("organization")
        if org_id:
            qs = qs.filter(organization_id=org_id)
        days = int(request.query_params.get("days", 7))
        since = timezone.now() - timedelta(days=days)
        qs = qs.filter(created_at__gte=since)
        return _paginate(request, qs, SecurityEventSerializer)


# ── Failed Jobs ───────────────────────────────────────────────────────────────

class FailedJobListView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = FailedJob.objects.select_related("organization", "resolved_by")
        job_status = request.query_params.get("status", "FAILED")
        if job_status:
            qs = qs.filter(status=job_status)
        org_id = request.query_params.get("organization")
        if org_id:
            qs = qs.filter(organization_id=org_id)
        return _paginate(request, qs, FailedJobSerializer)


class FailedJobRetryView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        try:
            job = FailedJob.objects.get(pk=pk)
        except FailedJob.DoesNotExist:
            return error_response("Job not found.", status_code=404)

        if job.status == FailedJob.Status.RESOLVED:
            return error_response("Job is already resolved.", status_code=400)

        try:
            from celery import current_app
            current_app.send_task(job.task_name, args=job.args, kwargs=job.kwargs)
            job.retry_count += 1
            job.last_retry_at = timezone.now()
            job.status = FailedJob.Status.RETRYING
            job.save(update_fields=["retry_count", "last_retry_at", "status", "updated_at"])
            logger.info(
                "failed_job.retried",
                extra={"job_id": job.pk, "task": job.task_name, "by": request.user.pk},
            )
            return success_response({"detail": f"Task '{job.task_name}' queued for retry."})
        except Exception as exc:  # noqa: BLE001
            return error_response(f"Retry failed: {exc}", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FailedJobIgnoreView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        try:
            job = FailedJob.objects.get(pk=pk)
        except FailedJob.DoesNotExist:
            return error_response("Job not found.", status_code=404)
        job.status = FailedJob.Status.IGNORED
        job.resolved_at = timezone.now()
        job.resolved_by = request.user
        job.save(update_fields=["status", "resolved_at", "resolved_by", "updated_at"])
        return success_response({"detail": "Job marked as ignored."})
