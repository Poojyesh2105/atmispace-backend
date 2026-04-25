from django.contrib import admin
from django.utils.html import format_html

from apps.core.models import FeatureFlag, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "domain", "is_active", "is_default", "created_at")
    list_filter = ("is_active", "is_default")
    search_fields = ("name", "code", "domain", "slug")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("name", "code", "slug", "domain")}),
        ("Status", {"fields": ("is_active", "is_default")}),
        ("Metadata", {"fields": ("metadata",), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    actions = ["activate_organizations", "deactivate_organizations"]

    @admin.action(description="Activate selected organizations")
    def activate_organizations(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} organization(s) activated.")

    @admin.action(description="Deactivate selected organizations")
    def deactivate_organizations(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} organization(s) deactivated.")


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "organization", "status_badge", "updated_at")
    list_filter = ("is_enabled", "organization")
    search_fields = ("key", "label", "description")
    ordering = ("key",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Flag Identity", {"fields": ("key", "label", "description")}),
        ("Scope & State", {"fields": ("organization", "is_enabled")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    actions = ["enable_flags", "disable_flags"]

    @admin.display(description="Status")
    def status_badge(self, obj):
        if obj.is_enabled:
            return format_html('<span style="color:green;font-weight:bold;">✔ Enabled</span>')
        return format_html('<span style="color:#aaa;">✘ Disabled</span>')

    @admin.action(description="Enable selected feature flags")
    def enable_flags(self, request, queryset):
        updated = queryset.update(is_enabled=True)
        self.message_user(request, f"{updated} flag(s) enabled.")

    @admin.action(description="Disable selected feature flags")
    def disable_flags(self, request, queryset):
        updated = queryset.update(is_enabled=False)
        self.message_user(request, f"{updated} flag(s) disabled.")
