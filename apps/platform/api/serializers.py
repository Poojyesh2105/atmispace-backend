from rest_framework import serializers
from django.utils.text import slugify
from urllib.parse import urlparse

from apps.core.models import FeatureFlag, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    is_operational = serializers.BooleanField(read_only=True)

    class Meta:
        model = Organization
        fields = [
            "id", "name", "code", "slug",
            "domain", "subdomain",
            "logo", "primary_email", "phone", "address",
            "tax_id_number",
            "timezone", "country", "currency",
            "is_active", "is_default", "is_operational",
            "subscription_status",
            "metadata",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_domain(self, value):
        normalized = value.strip().lower()
        if normalized.startswith(("http://", "https://")):
            normalized = urlparse(normalized).netloc
        normalized = normalized.split("/")[0].split(":")[0].strip(".")
        if self.instance is not None and normalized != (self.instance.domain or "").lower():
            raise serializers.ValidationError("Organization domain cannot be edited after creation.")
        if self.instance is None and not normalized:
            raise serializers.ValidationError("Domain is required.")
        queryset = Organization.objects.filter(domain__iexact=normalized)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if normalized and queryset.exists():
            raise serializers.ValidationError("This domain is already assigned to an organization.")
        return normalized

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and not attrs.get("domain"):
            raise serializers.ValidationError({"domain": "Domain is required."})
        return attrs

    def create(self, validated_data):
        if not validated_data.get("subdomain"):
            domain = validated_data.get("domain", "")
            validated_data["subdomain"] = slugify((domain.split(".")[0] if domain else validated_data.get("name", "")))[:80]
        return super().create(validated_data)


class FeatureFlagSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = FeatureFlag
        fields = [
            "id", "key", "label", "description",
            "is_enabled", "organization", "organization_name",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
