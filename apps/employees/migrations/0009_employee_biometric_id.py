from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0008_organizationsettings_office_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="biometric_id",
            field=models.CharField(blank=True, max_length=80, null=True, unique=True),
        ),
    ]
