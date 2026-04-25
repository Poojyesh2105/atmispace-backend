from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_organization"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("EMPLOYEE", "Employee"),
                    ("MANAGER", "Manager"),
                    ("HR", "HR"),
                    ("ACCOUNTS", "Accounts"),
                    ("ADMIN", "Admin"),
                    ("SUPER_ADMIN", "Super Admin"),
                ],
                default="EMPLOYEE",
                max_length=20,
            ),
        ),
    ]
