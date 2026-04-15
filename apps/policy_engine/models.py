from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import TimestampedModel


class PolicyRule(TimestampedModel):
    class Module(models.TextChoices):
        LEAVE = "LEAVE", "Leave"
        ATTENDANCE = "ATTENDANCE", "Attendance"
        PAYROLL = "PAYROLL", "Payroll"
        COMPLIANCE = "COMPLIANCE", "Compliance"
        LIFECYCLE = "LIFECYCLE", "Lifecycle"

    class Operator(models.TextChoices):
        ALWAYS = "ALWAYS", "Always"
        EQUALS = "EQUALS", "Equals"
        NOT_EQUALS = "NOT_EQUALS", "Not Equals"
        GREATER_THAN_EQUAL = "GTE", "Greater Than Or Equal"
        LESS_THAN_EQUAL = "LTE", "Less Than Or Equal"
        IN = "IN", "In"
        CONTAINS = "CONTAINS", "Contains"

    class EffectType(models.TextChoices):
        WARN = "WARN", "Warn"
        BLOCK = "BLOCK", "Block"
        FLAG = "FLAG", "Flag"

    name = models.CharField(max_length=180)
    module = models.CharField(max_length=30, choices=Module.choices, db_index=True)
    description = models.TextField(blank=True)
    priority = models.PositiveIntegerField(default=100)
    condition_field = models.CharField(max_length=120, blank=True)
    condition_operator = models.CharField(max_length=20, choices=Operator.choices, default=Operator.ALWAYS)
    condition_value = models.JSONField(null=True, blank=True)
    effect_type = models.CharField(max_length=20, choices=EffectType.choices, default=EffectType.WARN)
    effect_message = models.CharField(max_length=240, blank=True)
    effect_payload = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["module", "priority", "name"]
        indexes = [
            models.Index(fields=["module", "is_active", "priority"]),
        ]

    def __str__(self):
        return f"{self.module} - {self.name}"


class PolicyEvaluationLog(TimestampedModel):
    rule = models.ForeignKey(
        PolicyRule,
        on_delete=models.SET_NULL,
        related_name="evaluation_logs",
        null=True,
        blank=True,
    )
    module = models.CharField(max_length=30, choices=PolicyRule.Module.choices, db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="policy_evaluation_logs",
        null=True,
        blank=True,
    )
    triggered = models.BooleanField(default=False, db_index=True)
    effect_type = models.CharField(max_length=20, choices=PolicyRule.EffectType.choices, blank=True)
    message = models.CharField(max_length=240, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["module", "triggered", "created_at"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.module} #{self.object_id} - {self.effect_type or 'NONE'}"

