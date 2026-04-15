from rest_framework import serializers

from apps.policy_engine.models import PolicyEvaluationLog, PolicyRule


class PolicyRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyRule
        fields = (
            "id",
            "name",
            "module",
            "description",
            "priority",
            "condition_field",
            "condition_operator",
            "condition_value",
            "effect_type",
            "effect_message",
            "effect_payload",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        operator = attrs.get("condition_operator", getattr(self.instance, "condition_operator", PolicyRule.Operator.ALWAYS))
        field_name = attrs.get("condition_field", getattr(self.instance, "condition_field", ""))
        value = attrs.get("condition_value", getattr(self.instance, "condition_value", None))

        if operator != PolicyRule.Operator.ALWAYS and not field_name:
            raise serializers.ValidationError({"condition_field": "Condition field is required for conditional rules."})
        if operator != PolicyRule.Operator.ALWAYS and value in (None, ""):
            raise serializers.ValidationError({"condition_value": "Condition value is required for conditional rules."})
        return attrs


class PolicyEvaluationLogSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)
    actor_name = serializers.CharField(source="actor.full_name", read_only=True)
    content_type_label = serializers.CharField(source="content_type.model", read_only=True)

    class Meta:
        model = PolicyEvaluationLog
        fields = (
            "id",
            "rule",
            "rule_name",
            "module",
            "content_type_label",
            "object_id",
            "actor",
            "actor_name",
            "triggered",
            "effect_type",
            "message",
            "metadata",
            "created_at",
        )
        read_only_fields = fields

