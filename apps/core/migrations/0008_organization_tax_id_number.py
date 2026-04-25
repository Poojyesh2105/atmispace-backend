from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_update_org_domain_uniqueness"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="tax_id_number",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
    ]
