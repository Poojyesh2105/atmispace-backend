import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("audit", "0001_initial"),
        ("core", "0005_organizationsettings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── SubscriptionPlan ──────────────────────────────────────────────
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120, unique=True)),
                ("code", models.SlugField(max_length=60, unique=True)),
                ("description", models.TextField(blank=True, default="")),
                ("price_monthly", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("price_yearly", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("max_users", models.PositiveIntegerField(default=0)),
                ("included_modules", models.JSONField(default=list)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"ordering": ["display_order", "price_monthly"]},
        ),
        # ── OrganizationSubscription ──────────────────────────────────────
        migrations.CreateModel(
            name="OrganizationSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("billing_cycle", models.CharField(choices=[("MONTHLY", "Monthly"), ("YEARLY", "Yearly")], default="MONTHLY", max_length=10)),
                ("status", models.CharField(choices=[("TRIAL", "Trial"), ("ACTIVE", "Active"), ("PAST_DUE", "Past Due"), ("SUSPENDED", "Suspended"), ("CANCELLED", "Cancelled")], db_index=True, default="TRIAL", max_length=20)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("trial_end_date", models.DateField(blank=True, null=True)),
                ("next_billing_date", models.DateField(blank=True, null=True)),
                ("mrr", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("organization", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to="core.organization")),
                ("plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="platform.subscriptionplan")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # ── Invoice ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_number", models.CharField(max_length=80, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("tax_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("OPEN", "Open"), ("PAID", "Paid"), ("VOID", "Void"), ("OVERDUE", "Overdue")], db_index=True, default="DRAFT", max_length=20)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invoices", to="core.organization")),
                ("subscription", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="invoices", to="platform.organizationsubscription")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # ── Payment ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("provider", models.CharField(default="manual", max_length=60)),
                ("provider_reference", models.CharField(blank=True, default="", max_length=200)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("SUCCESS", "Success"), ("FAILED", "Failed"), ("REFUNDED", "Refunded")], db_index=True, default="PENDING", max_length=20)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="core.organization")),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payments", to="platform.invoice")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # ── OrganizationOnboarding ────────────────────────────────────────
        migrations.CreateModel(
            name="OrganizationOnboarding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("IN_PROGRESS", "In Progress"), ("COMPLETED", "Completed"), ("FAILED", "Failed"), ("ROLLED_BACK", "Rolled Back")], db_index=True, default="PENDING", max_length=20)),
                ("current_step", models.PositiveSmallIntegerField(default=1)),
                ("step_data", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True, default="")),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="onboarding", to="core.organization")),
                ("provisioned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="provisioned_onboardings", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        # ── UsageEvent ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="UsageEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module", models.CharField(db_index=True, max_length=60)),
                ("action", models.CharField(db_index=True, max_length=120)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("organization", models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name="usage_events", to="core.organization")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="usageevent",
            index=models.Index(fields=["organization", "module", "created_at"], name="platform_usage_org_mod_idx"),
        ),
        migrations.AddIndex(
            model_name="usageevent",
            index=models.Index(fields=["organization", "created_at"], name="platform_usage_org_date_idx"),
        ),
        # ── PlatformSupportTicket ─────────────────────────────────────────
        migrations.CreateModel(
            name="PlatformSupportTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subject", models.CharField(max_length=300)),
                ("description", models.TextField()),
                ("priority", models.CharField(choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical")], db_index=True, default="MEDIUM", max_length=20)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("IN_PROGRESS", "In Progress"), ("WAITING", "Waiting on Customer"), ("RESOLVED", "Resolved"), ("CLOSED", "Closed")], db_index=True, default="OPEN", max_length=20)),
                ("internal_notes", models.TextField(blank=True, default="")),
                ("sla_due_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="support_tickets", to="core.organization")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_support_tickets", to=settings.AUTH_USER_MODEL)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_support_tickets", to=settings.AUTH_USER_MODEL)),
                ("related_audit_log", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="support_tickets", to="audit.auditlog")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="platformsupportticket",
            index=models.Index(fields=["organization", "status"], name="platform_support_org_status_idx"),
        ),
        migrations.AddIndex(
            model_name="platformsupportticket",
            index=models.Index(fields=["status", "priority"], name="platform_support_status_pri_idx"),
        ),
        # ── SecurityEvent ─────────────────────────────────────────────────
        migrations.CreateModel(
            name="SecurityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("FAILED_LOGIN", "Failed Login"), ("UNAUTHORIZED_ACCESS", "Unauthorized Access"), ("PERMISSION_DENIED", "Permission Denied"), ("SUSPICIOUS_TOKEN", "Suspicious Token"), ("ORG_CONTEXT_MISMATCH", "Org Context Mismatch"), ("RATE_LIMITED", "Rate Limited"), ("PASSWORD_CHANGED", "Password Changed"), ("ACCOUNT_LOCKED", "Account Locked"), ("SUPER_ADMIN_ACTION", "Super Admin Action")], db_index=True, max_length=40)),
                ("severity", models.CharField(choices=[("INFO", "Info"), ("WARNING", "Warning"), ("HIGH", "High"), ("CRITICAL", "Critical")], db_index=True, default="INFO", max_length=20)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("path", models.CharField(blank=True, default="", max_length=500)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("organization", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="security_events", to="core.organization")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="security_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="securityevent",
            index=models.Index(fields=["event_type", "created_at"], name="platform_sec_type_date_idx"),
        ),
        migrations.AddIndex(
            model_name="securityevent",
            index=models.Index(fields=["severity", "created_at"], name="platform_sec_sev_date_idx"),
        ),
        migrations.AddIndex(
            model_name="securityevent",
            index=models.Index(fields=["organization", "event_type"], name="platform_sec_org_type_idx"),
        ),
        # ── FailedJob ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name="FailedJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("task_name", models.CharField(db_index=True, max_length=300)),
                ("task_id", models.CharField(max_length=200, unique=True)),
                ("args", models.JSONField(blank=True, default=list)),
                ("kwargs", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True, default="")),
                ("traceback", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("FAILED", "Failed"), ("RETRYING", "Retrying"), ("RESOLVED", "Resolved"), ("IGNORED", "Ignored")], db_index=True, default="FAILED", max_length=20)),
                ("retry_count", models.PositiveSmallIntegerField(default=0)),
                ("last_retry_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="failed_jobs", to="core.organization")),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resolved_jobs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="failedjob",
            index=models.Index(fields=["status", "created_at"], name="platform_job_status_date_idx"),
        ),
        migrations.AddIndex(
            model_name="failedjob",
            index=models.Index(fields=["organization", "status"], name="platform_job_org_status_idx"),
        ),
    ]
