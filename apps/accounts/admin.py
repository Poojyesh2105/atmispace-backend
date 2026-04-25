from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = (
        "email", "first_name", "last_name", "role",
        "organization", "is_active", "is_staff", "date_joined",
    )
    list_filter = ("role", "is_active", "is_staff", "organization")
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = ("date_joined", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Role & Organization", {"fields": ("role", "organization")}),
        ("Permissions", {
            "fields": (
                "is_active", "is_staff", "is_superuser",
                "force_password_reset", "groups", "user_permissions",
            ),
        }),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email", "first_name", "last_name",
                    "role", "organization", "password1", "password2",
                ),
            },
        ),
    )

    actions = ["activate_users", "deactivate_users", "require_password_reset"]

    @admin.action(description="Activate selected users")
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} user(s) activated.")

    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request, queryset):
        updated = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f"{updated} user(s) deactivated.")

    @admin.action(description="Require password reset on next login")
    def require_password_reset(self, request, queryset):
        updated = queryset.update(force_password_reset=True)
        self.message_user(request, f"{updated} user(s) flagged for password reset.")
