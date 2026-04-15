from rest_framework import serializers

from apps.analytics.models import AnalyticsSnapshot


class AnalyticsSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsSnapshot
        fields = ("id", "snapshot_date", "metric_key", "role_scope", "payload", "created_at", "updated_at")
        read_only_fields = fields


class AnalyticsDashboardSerializer(serializers.Serializer):
    cards = serializers.ListField()
    leave_trend = serializers.ListField()
    overtime_trend = serializers.ListField()
    payroll_readiness = serializers.DictField()
    document_expiry = serializers.ListField()

