"""
Serializer mixins for multi-tenant safety.

OrgScopedSerializerMixin
------------------------
Drop this into any ModelSerializer whose model has an `organization` FK to get:

  1. Auto-stamp   — `organization` is silently set from `request.organization`
                    on create; the client never needs to send it.
  2. Injection guard — if a client sends `organization` or `organization_id`
                       in the payload, it is stripped (create) or validated
                       against the resolved tenant (update / partial update).
  3. Read-only org_id field — `organization_id` is exposed as a read-only
                               integer in the serialized output so the client
                               can confirm which org owns the record.

Usage:

    class LeaveRequestSerializer(OrgScopedSerializerMixin,
                                  serializers.ModelSerializer):
        class Meta:
            model = LeaveRequest
            fields = "__all__"
"""

from rest_framework import serializers


class OrgScopedSerializerMixin:
    """
    Mixin that enforces organization scoping on DRF ModelSerializers.

    Requirements:
    - The view must set `request.organization` (done by TenantMiddleware).
    - The model must have an `organization` FK field.
    """

    # Expose org id as read-only in output
    organization_id = serializers.IntegerField(read_only=True)

    # ── Validation ────────────────────────────────────────────────────────

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self._get_request()

        # Strip any client-supplied organization reference — we always resolve
        # it from the request context, never trust the payload.
        attrs.pop("organization", None)

        # Extra safety: if someone passes organization_id as a writable field
        # on a non-standard serializer, strip it too.
        attrs.pop("organization_id", None)

        return attrs

    # ── Create ────────────────────────────────────────────────────────────

    def create(self, validated_data):
        org = self._resolve_org()
        if org is not None:
            validated_data["organization"] = org
        return super().create(validated_data)

    # ── Update ────────────────────────────────────────────────────────────

    def update(self, instance, validated_data):
        # Prevent silently moving a record to a different org via PATCH
        org = self._resolve_org()
        if org is not None and hasattr(instance, "organization_id"):
            if instance.organization_id != org.pk:
                raise serializers.ValidationError(
                    "You cannot move this record to a different organization."
                )
        return super().update(instance, validated_data)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_request(self):
        return self.context.get("request")

    def _resolve_org(self):
        request = self._get_request()
        if request is None:
            return None
        return getattr(request, "organization", None)
