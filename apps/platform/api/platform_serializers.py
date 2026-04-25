"""
Serializers for the new SaaS platform models.
"""
from rest_framework import serializers

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


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id", "name", "code", "description",
            "price_monthly", "price_yearly",
            "max_users", "included_modules",
            "is_active", "display_order",
            "subscriber_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "subscriber_count"]

    def get_subscriber_count(self, obj):
        return obj.subscriptions.filter(
            status__in=["ACTIVE", "TRIAL"]
        ).count()


class OrganizationSubscriptionSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True, default="")
    is_trial_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = OrganizationSubscription
        fields = [
            "id", "organization", "organization_name",
            "plan", "plan_name",
            "billing_cycle", "status",
            "start_date", "end_date",
            "trial_end_date", "next_billing_date",
            "mrr", "is_trial_expired",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "organization", "organization_name",
            "subscription", "invoice_number",
            "amount", "tax_amount", "total_amount",
            "status", "due_date", "paid_at", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PaymentSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "organization", "organization_name",
            "invoice", "amount", "provider",
            "provider_reference", "status", "paid_at",
            "metadata", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OrganizationOnboardingSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(
        source="organization.name", read_only=True, default=""
    )
    provisioned_by_email = serializers.CharField(
        source="provisioned_by.email", read_only=True, default=""
    )

    class Meta:
        model = OrganizationOnboarding
        fields = [
            "id", "organization", "organization_name",
            "status", "current_step", "step_data",
            "error_message", "provisioned_by", "provisioned_by_email",
            "completed_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UsageEventSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = UsageEvent
        fields = [
            "id", "organization", "organization_name",
            "user", "module", "action",
            "metadata", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PlatformSupportTicketSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True, default=""
    )
    assigned_to_name = serializers.CharField(
        source="assigned_to.full_name", read_only=True, default=""
    )
    is_sla_breached = serializers.BooleanField(read_only=True)

    class Meta:
        model = PlatformSupportTicket
        fields = [
            "id", "organization", "organization_name",
            "created_by", "created_by_name",
            "assigned_to", "assigned_to_name",
            "subject", "description", "priority", "status",
            "internal_notes", "sla_due_at", "resolved_at",
            "is_sla_breached",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SecurityEventSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(
        source="organization.name", read_only=True, default=""
    )
    user_email = serializers.CharField(
        source="user.email", read_only=True, default=""
    )

    class Meta:
        model = SecurityEvent
        fields = [
            "id", "organization", "organization_name",
            "user", "user_email",
            "event_type", "severity",
            "ip_address", "user_agent", "path",
            "metadata", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class FailedJobSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(
        source="organization.name", read_only=True, default=""
    )
    resolved_by_email = serializers.CharField(
        source="resolved_by.email", read_only=True, default=""
    )

    class Meta:
        model = FailedJob
        fields = [
            "id", "organization", "organization_name",
            "task_name", "task_id",
            "args", "kwargs",
            "error_message", "traceback",
            "status", "retry_count", "last_retry_at",
            "resolved_at", "resolved_by", "resolved_by_email",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "task_id", "created_at", "updated_at",
            "retry_count", "last_retry_at",
        ]
