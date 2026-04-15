from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from rest_framework import exceptions

from apps.audit.services.audit_service import AuditService
from apps.policy_engine.models import PolicyEvaluationLog, PolicyRule


class PolicyRuleService:
    @staticmethod
    def create_rule(validated_data, actor):
        rule = PolicyRule.objects.create(**validated_data)
        AuditService.log(actor=actor, action="policy.rule.created", entity=rule, after=rule)
        return rule

    @staticmethod
    def update_rule(instance, validated_data, actor):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="policy.rule.updated", entity=instance, before=before, after=instance)
        return instance

    @staticmethod
    def _get_value(obj, field_path):
        value = obj
        for part in field_path.split("."):
            value = getattr(value, part, None)
            if value is None:
                break
        return value

    @staticmethod
    def _matches_condition(obj, rule):
        if rule.condition_operator == PolicyRule.Operator.ALWAYS or not rule.condition_field:
            return True

        actual = PolicyRuleService._get_value(obj, rule.condition_field)
        if actual is None:
            return False

        expected = rule.condition_value
        if rule.condition_operator == PolicyRule.Operator.EQUALS:
            return str(actual) == str(expected)
        if rule.condition_operator == PolicyRule.Operator.NOT_EQUALS:
            return str(actual) != str(expected)
        if rule.condition_operator == PolicyRule.Operator.CONTAINS:
            return str(expected).lower() in str(actual).lower()
        if rule.condition_operator == PolicyRule.Operator.IN:
            values = expected if isinstance(expected, list) else [item.strip() for item in str(expected).split(",")]
            return str(actual) in {str(item) for item in values}

        try:
            actual_value = Decimal(str(actual))
            expected_value = Decimal(str(expected))
        except Exception:
            return False

        if rule.condition_operator == PolicyRule.Operator.GREATER_THAN_EQUAL:
            return actual_value >= expected_value
        if rule.condition_operator == PolicyRule.Operator.LESS_THAN_EQUAL:
            return actual_value <= expected_value
        return False

    @staticmethod
    def evaluate(module, target_obj, actor=None, persist=False, raise_on_block=True):
        rules = PolicyRule.objects.filter(module=module, is_active=True).order_by("priority", "id")
        content_type = ContentType.objects.get_for_model(target_obj.__class__)
        results = []
        block_messages = []

        for rule in rules:
            triggered = PolicyRuleService._matches_condition(target_obj, rule)
            message = rule.effect_message or f"Policy rule {rule.name} was evaluated."
            result = {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "triggered": triggered,
                "effect_type": rule.effect_type,
                "message": message,
                "effect_payload": rule.effect_payload,
            }
            results.append(result)

            if persist:
                PolicyEvaluationLog.objects.create(
                    rule=rule,
                    module=module,
                    content_type=content_type,
                    object_id=target_obj.pk,
                    actor=actor,
                    triggered=triggered,
                    effect_type=rule.effect_type if triggered else "",
                    message=message if triggered else "",
                    metadata={"effect_payload": rule.effect_payload},
                )

            if triggered and rule.effect_type == PolicyRule.EffectType.BLOCK:
                block_messages.append(message)

        if block_messages and raise_on_block:
            raise exceptions.ValidationError({"policy_rules": block_messages})

        return results

