from django.db import migrations


def enable_analytics_for_existing_orgs(apps, schema_editor):
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    Organization = apps.get_model("core", "Organization")
    OrganizationMembership = apps.get_model("core", "OrganizationMembership")
    User = apps.get_model("accounts", "User")

    FeatureFlag.objects.filter(key="enable_analytics").update(is_enabled=True)

    existing_org_ids = set(
        FeatureFlag.objects.filter(key="enable_analytics", organization__isnull=False)
        .values_list("organization_id", flat=True)
    )
    flags = [
        FeatureFlag(key="enable_analytics", organization=org, is_enabled=True, label="Enable Analytics")
        for org in Organization.objects.filter(is_active=True).exclude(pk__in=existing_org_ids)
    ]
    FeatureFlag.objects.bulk_create(flags)

    seen_user_ids = set()
    for membership in (
        OrganizationMembership.objects.filter(is_active=True)
        .order_by("user_id", "-is_primary", "id")
        .values("user_id", "organization_id", "role", "is_primary")
    ):
        user_id = membership["user_id"]
        if user_id in seen_user_ids:
            continue
        seen_user_ids.add(user_id)

        user = User.objects.filter(pk=user_id).first()
        if user is None or user.role == "SUPER_ADMIN":
            continue

        updates = {}
        if user.organization_id != membership["organization_id"]:
            updates["organization_id"] = membership["organization_id"]
        if membership["role"] == "ADMIN" and user.role != "ADMIN":
            updates["role"] = "ADMIN"
        if updates:
            User.objects.filter(pk=user_id).update(**updates)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_role_super_admin"),
        ("core", "0005_organizationsettings"),
    ]

    operations = [
        migrations.RunPython(enable_analytics_for_existing_orgs, noop_reverse),
    ]
