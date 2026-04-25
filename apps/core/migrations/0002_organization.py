import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=180, unique=True)),
                ("code", models.CharField(max_length=40, unique=True)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("is_default", models.BooleanField(db_index=True, default=False)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["is_active", "is_default"], name="core_org_active_default_idx"),
                ],
            },
        ),
    ]
