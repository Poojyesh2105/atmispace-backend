import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("accounts", "0003_user_force_password_reset"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="accounts_user_records",
                to="core.organization",
            ),
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["organization", "role"], name="accounts_user_org_role_idx"),
        ),
    ]
