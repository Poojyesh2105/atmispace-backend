from django.db import migrations


DEFAULT_PLANS = [
    {
        "name": "Starter",
        "code": "starter",
        "description": "Core HR for small teams getting started with employee records, attendance, leave, and documents.",
        "price_monthly": "4999.00",
        "price_yearly": "49990.00",
        "max_users": 50,
        "included_modules": ["enable_documents", "enable_scheduling"],
        "display_order": 10,
    },
    {
        "name": "Growth",
        "code": "growth",
        "description": "Expanded HR operations with payroll, lifecycle workflows, scheduling, and analytics for growing organizations.",
        "price_monthly": "14999.00",
        "price_yearly": "149990.00",
        "max_users": 250,
        "included_modules": ["enable_payroll", "enable_lifecycle", "enable_documents", "enable_scheduling", "enable_analytics"],
        "display_order": 20,
    },
    {
        "name": "Enterprise",
        "code": "enterprise",
        "description": "Full-suite plan for large organizations with advanced modules and unlimited users.",
        "price_monthly": "39999.00",
        "price_yearly": "399990.00",
        "max_users": 0,
        "included_modules": [
            "enable_payroll",
            "enable_performance",
            "enable_lifecycle",
            "enable_documents",
            "enable_scheduling",
            "enable_biometric",
            "enable_helpdesk",
            "enable_analytics",
        ],
        "display_order": 30,
    },
    {
        "name": "Lifetime",
        "code": "lifetime",
        "description": "One-time lifetime access plan with all current modules enabled and unlimited users.",
        "price_monthly": "0.00",
        "price_yearly": "0.00",
        "max_users": 0,
        "included_modules": [
            "enable_payroll",
            "enable_performance",
            "enable_lifecycle",
            "enable_documents",
            "enable_scheduling",
            "enable_biometric",
            "enable_helpdesk",
            "enable_analytics",
        ],
        "display_order": 40,
    },
]


def seed_default_subscription_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("platform", "SubscriptionPlan")

    for plan in DEFAULT_PLANS:
        SubscriptionPlan.objects.update_or_create(
            code=plan["code"],
            defaults={**plan, "is_active": True},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("platform", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_default_subscription_plans, noop_reverse),
    ]
