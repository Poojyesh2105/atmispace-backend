from rest_framework import serializers

from apps.core.models import Organization, OrganizationMembership, OrganizationSettings


class OrganizationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationSettings
        fields = [
            "attendance_config", "leave_config",
            "payroll_config", "feature_config", "branding_config",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class OrganizationBriefSerializer(serializers.ModelSerializer):
    """Compact representation — used in lists and switcher dropdown."""

    class Meta:
        model = Organization
        fields = [
            "id", "name", "code", "slug", "subdomain",
            "logo", "timezone", "country", "currency",
            "subscription_status", "is_active",
        ]


class OrganizationDetailSerializer(serializers.ModelSerializer):
    """Full detail — used for /current-organization/ and settings page."""
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
        read_only_fields = ["id", "domain", "slug", "is_default", "created_at", "updated_at"]


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    """Used in /my-organizations/ to show which orgs a user belongs to + their role."""
    organization = OrganizationBriefSerializer(read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = [
            "id", "organization", "role",
            "is_active", "is_primary", "joined_at",
        ]


class OrganizationProvisioningSerializer(serializers.Serializer):
    """Input validation for provisioning a new organization."""
    name = serializers.CharField(max_length=180)
    code = serializers.CharField(max_length=40)
    domain = serializers.CharField(max_length=253)
    subdomain = serializers.SlugField(max_length=80, required=False, allow_blank=True, default="")
    primary_email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    tax_id_number = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    timezone = serializers.CharField(max_length=60, required=False, default="Asia/Kolkata")
    country = serializers.CharField(max_length=80, required=False, default="India")
    currency = serializers.CharField(max_length=10, required=False, default="INR")
    # Optional: email of the user to assign as ADMIN for this org
    admin_email = serializers.EmailField(required=False, allow_blank=True, default="")

    def validate_code(self, value):
        return value.upper().strip()

    def validate_name(self, value):
        value = value.strip()
        return value

    def validate_domain(self, value):
        normalized = value.strip().lower()
        if normalized.startswith(("http://", "https://")):
            from urllib.parse import urlparse
            normalized = urlparse(normalized).netloc
        normalized = normalized.split("/")[0].split(":")[0].strip(".")
        if not normalized:
            raise serializers.ValidationError("Domain is required.")
        if Organization.objects.filter(domain__iexact=normalized).exists():
            raise serializers.ValidationError("This domain is already assigned to an organization.")
        return normalized

    def validate_subdomain(self, value):
        if value and Organization.objects.filter(subdomain=value).exists():
            raise serializers.ValidationError("This subdomain is already taken.")
        return value


class SwitchOrganizationSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()
