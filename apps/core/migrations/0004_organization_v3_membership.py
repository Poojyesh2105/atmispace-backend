"""
V3 multi-tenant upgrade:
  1. Extend Organization with subdomain, logo, primary_email, phone, address,
     timezone, country, currency, subscription_status fields.
     NOTE: metadata and core_org_active_default_idx were already created in 0002.
  2. Create OrganizationMembership (user ↔ org many-to-many with role).
  3. Add performance indexes.

All AddField operations use ADD COLUMN IF NOT EXISTS so the migration is safe
to run even when some columns were already created by a prior partial run.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_organization_domain_featureflag"),
        ("accounts", "0005_user_role_super_admin"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------
        # 1.  Organization: add V3 fields (metadata already exists from 0002)
        #     Using SeparateDatabaseAndState so Django state is always correct
        #     and the SQL uses IF NOT EXISTS to survive partial prior runs.
        # ------------------------------------------------------------------
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="organization",
                    name="subdomain",
                    field=models.SlugField(
                        blank=True,
                        default="",
                        help_text="Subdomain prefix, e.g. 'acme' → acme.atmispace.com",
                        max_length=80,
                    ),
                ),
                migrations.AddField(
                    model_name="organization",
                    name="logo",
                    field=models.URLField(blank=True, default="",
                                         help_text="Public URL of the org logo"),
                ),
                migrations.AddField(
                    model_name="organization",
                    name="primary_email",
                    field=models.EmailField(blank=True, default=""),
                ),
                migrations.AddField(
                    model_name="organization",
                    name="phone",
                    field=models.CharField(blank=True, default="", max_length=30),
                ),
                migrations.AddField(
                    model_name="organization",
                    name="address",
                    field=models.TextField(blank=True, default=""),
                ),
                migrations.AddField(
                    model_name="organization",
                    name="timezone",
                    field=models.CharField(
                        blank=True,
                        default="Asia/Kolkata",
                        help_text="pytz timezone string, e.g. 'America/New_York'",
                        max_length=60,
                    ),
                ),
                migrations.AddField(
                    model_name="organization",
                    name="country",
                    field=models.CharField(blank=True, default="India", max_length=80),
                ),
                migrations.AddField(
                    model_name="organization",
                    name="currency",
                    field=models.CharField(
                        blank=True,
                        default="INR",
                        help_text="ISO 4217 currency code, e.g. INR, USD",
                        max_length=10,
                    ),
                ),
                migrations.AddField(
                    model_name="organization",
                    name="subscription_status",
                    field=models.CharField(
                        choices=[
                            ("TRIAL", "Trial"),
                            ("ACTIVE", "Active"),
                            ("SUSPENDED", "Suspended"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        db_index=True,
                        default="TRIAL",
                        max_length=20,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE core_organization
                            ADD COLUMN IF NOT EXISTS subdomain varchar(80) NOT NULL DEFAULT '',
                            ADD COLUMN IF NOT EXISTS logo varchar(200) NOT NULL DEFAULT '',
                            ADD COLUMN IF NOT EXISTS primary_email varchar(254) NOT NULL DEFAULT '',
                            ADD COLUMN IF NOT EXISTS phone varchar(30) NOT NULL DEFAULT '',
                            ADD COLUMN IF NOT EXISTS address text NOT NULL DEFAULT '',
                            ADD COLUMN IF NOT EXISTS timezone varchar(60) NOT NULL DEFAULT 'Asia/Kolkata',
                            ADD COLUMN IF NOT EXISTS country varchar(80) NOT NULL DEFAULT 'India',
                            ADD COLUMN IF NOT EXISTS currency varchar(10) NOT NULL DEFAULT 'INR',
                            ADD COLUMN IF NOT EXISTS subscription_status varchar(20) NOT NULL DEFAULT 'TRIAL';
                    """,
                    reverse_sql="""
                        ALTER TABLE core_organization
                            DROP COLUMN IF EXISTS subdomain,
                            DROP COLUMN IF EXISTS logo,
                            DROP COLUMN IF EXISTS primary_email,
                            DROP COLUMN IF EXISTS phone,
                            DROP COLUMN IF EXISTS address,
                            DROP COLUMN IF EXISTS timezone,
                            DROP COLUMN IF EXISTS country,
                            DROP COLUMN IF EXISTS currency,
                            DROP COLUMN IF EXISTS subscription_status;
                    """,
                ),
            ],
        ),

        # ------------------------------------------------------------------
        # 2.  Organization: new indexes (guard with IF NOT EXISTS)
        #     core_org_active_default_idx already exists from 0002 — skip it.
        # ------------------------------------------------------------------
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="organization",
                    index=models.Index(
                        fields=["subdomain"],
                        name="core_org_subdomain_idx",
                    ),
                ),
                migrations.AddIndex(
                    model_name="organization",
                    index=models.Index(
                        fields=["subscription_status"],
                        name="core_org_sub_status_idx",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE INDEX IF NOT EXISTS core_org_subdomain_idx
                            ON core_organization (subdomain);
                        CREATE INDEX IF NOT EXISTS core_org_sub_status_idx
                            ON core_organization (subscription_status);
                    """,
                    reverse_sql="""
                        DROP INDEX IF EXISTS core_org_subdomain_idx;
                        DROP INDEX IF EXISTS core_org_sub_status_idx;
                    """,
                ),
            ],
        ),

        # ------------------------------------------------------------------
        # 3.  OrganizationMembership model
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name="OrganizationMembership",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("EMPLOYEE", "Employee"),
                            ("MANAGER", "Manager"),
                            ("HR", "HR"),
                            ("ACCOUNTS", "Accounts"),
                            ("ADMIN", "Admin"),
                        ],
                        default="EMPLOYEE",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "is_primary",
                    models.BooleanField(
                        default=True,
                        help_text="The user's primary/default org when they belong to multiple orgs",
                    ),
                ),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="org_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="core.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["-is_primary", "organization__name"],
            },
        ),

        # ------------------------------------------------------------------
        # 4.  OrganizationMembership: constraints + indexes
        # ------------------------------------------------------------------
        migrations.AddConstraint(
            model_name="organizationmembership",
            constraint=models.UniqueConstraint(
                fields=["user", "organization"],
                name="unique_user_org_membership",
            ),
        ),
        migrations.AddIndex(
            model_name="organizationmembership",
            index=models.Index(
                fields=["organization", "role", "is_active"],
                name="org_membership_org_role_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="organizationmembership",
            index=models.Index(
                fields=["user", "is_active"],
                name="org_membership_user_active_idx",
            ),
        ),
    ]
