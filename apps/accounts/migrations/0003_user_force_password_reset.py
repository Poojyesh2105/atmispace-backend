from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_user_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="force_password_reset",
            field=models.BooleanField(default=False),
        ),
    ]
