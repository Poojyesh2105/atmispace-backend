from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0007_remove_employee_monthly_fixed_deductions"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationsettings",
            name="office_latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text="Office GPS latitude for geo-fencing attendance",
                max_digits=9,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="organizationsettings",
            name="office_longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text="Office GPS longitude for geo-fencing attendance",
                max_digits=9,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="organizationsettings",
            name="office_radius_meters",
            field=models.PositiveIntegerField(
                default=200,
                help_text="Radius in metres within which check-in counts as PRESENT (on-site)",
            ),
        ),
    ]
