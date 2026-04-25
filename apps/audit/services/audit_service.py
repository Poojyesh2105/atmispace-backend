import json

from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict

from apps.audit.models import AuditLog


class AuditService:
    @staticmethod
    def _to_json_safe(value):
        if value is None:
            return {}
        return json.loads(json.dumps(value, cls=DjangoJSONEncoder))

    @staticmethod
    def snapshot(instance):
        if instance is None:
            return {}
        if hasattr(instance, "_meta"):
            return AuditService._to_json_safe(model_to_dict(instance))
        return AuditService._to_json_safe(instance)

    @staticmethod
    def log(actor, action, entity=None, before=None, after=None, entity_type=None, entity_id=None):
        resolved_type = entity_type or getattr(getattr(entity, "_meta", None), "label_lower", entity.__class__.__name__ if entity else "unknown")
        resolved_id = entity_id or getattr(entity, "pk", "")
        resolved_organization = getattr(entity, "organization", None) or getattr(actor, "organization", None)
        return AuditLog.objects.create(
            organization=resolved_organization,
            actor=actor,
            action=action,
            entity_type=resolved_type,
            entity_id=str(resolved_id),
            before=AuditService.snapshot(before),
            after=AuditService.snapshot(after),
        )
