from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_organization"),
    ]

    operations = [
        # Add domain field to Organization
        migrations.AddField(
            model_name="organization",
            name="domain",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Primary email domain for this organization (e.g. acme.com)",
                max_length=253,
            ),
        ),
        migrations.AddIndex(
            model_name="organization",
            index=models.Index(fields=["domain"], name="core_org_domain_idx"),
        ),
        # Create FeatureFlag model
        migrations.CreateModel(
            name="FeatureFlag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(
                    max_length=100,
                    help_text="Unique snake_case key identifying the feature (e.g. 'enable_payroll')",
                )),
                ("label", models.CharField(blank=True, default="", max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                ("is_enabled", models.BooleanField(db_index=True, default=False)),
                ("organization", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="feature_flags",
                    to="core.organization",
                    help_text="Null = global flag applies to all orgs; set to scope to a single org.",
                )),
            ],
            options={
                "ordering": ["key"],
            },
        ),
        migrations.AddConstraint(
            model_name="featureflag",
            constraint=models.UniqueConstraint(
                condition=models.Q(organization__isnull=False),
                fields=["key", "organization"],
                name="unique_feature_flag_key_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="featureflag",
            constraint=models.UniqueConstraint(
                condition=models.Q(organization__isnull=True),
                fields=["key"],
                name="unique_global_feature_flag_key",
            ),
        ),
        migrations.AddIndex(
            model_name="featureflag",
            index=models.Index(fields=["key", "is_enabled"], name="core_ff_key_enabled_idx"),
        ),
    ]
