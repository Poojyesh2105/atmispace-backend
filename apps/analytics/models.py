from django.db import models

from apps.core.models import TimestampedModel


class AnalyticsSnapshot(TimestampedModel):
    class MetricKey(models.TextChoices):
        HEADCOUNT = "HEADCOUNT", "Headcount"
        ATTRITION = "ATTRITION", "Attrition"
        LEAVE_TREND = "LEAVE_TREND", "Leave Trend"
        OVERTIME_TREND = "OVERTIME_TREND", "Overtime Trend"
        PAYROLL_READINESS = "PAYROLL_READINESS", "Payroll Readiness"
        DOCUMENT_EXPIRY = "DOCUMENT_EXPIRY", "Document Expiry"

    snapshot_date = models.DateField(db_index=True)
    metric_key = models.CharField(max_length=40, choices=MetricKey.choices, db_index=True)
    role_scope = models.CharField(max_length=20, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-snapshot_date", "metric_key"]
        constraints = [
            models.UniqueConstraint(fields=["snapshot_date", "metric_key", "role_scope"], name="unique_analytics_snapshot_scope")
        ]
        indexes = [
            models.Index(fields=["metric_key", "snapshot_date"]),
        ]

    def __str__(self):
        scope = self.role_scope or "GLOBAL"
        return f"{self.metric_key} - {scope} - {self.snapshot_date.isoformat()}"

