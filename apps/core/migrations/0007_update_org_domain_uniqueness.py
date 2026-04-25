from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_enable_analytics_by_default"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organization",
            name="name",
            field=models.CharField(max_length=180),
        ),
        migrations.AlterField(
            model_name="organization",
            name="code",
            field=models.CharField(max_length=40),
        ),
        migrations.AddConstraint(
            model_name="organization",
            constraint=models.UniqueConstraint(
                Lower("domain"),
                condition=~Q(domain=""),
                name="unique_org_domain_ci",
            ),
        ),
    ]
