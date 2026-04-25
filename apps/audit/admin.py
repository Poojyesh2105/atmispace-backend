from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "action", "entity_type", "entity_id", "actor", "organization")
    list_filter = ("action", "entity_type", "organization")
    search_fields = ("action", "entity_type", "entity_id", "actor__email")
    ordering = ("-timestamp",)
    readonly_fields = (
        "actor", "action", "entity_type", "entity_id",
        "before", "after", "timestamp", "organization",
    )
    date_hierarchy = "timestamp"

    # Audit logs are read-only — no one should edit them
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.role == "SUPER_ADMIN"
