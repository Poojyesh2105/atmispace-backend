import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("performance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ratingscale",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="performance_ratingscale_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="performancecycle",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="performance_performancecycle_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="performancegoal",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="performance_performancegoal_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="performancereview",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="performance_performancereview_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="performancecycle",
            index=models.Index(fields=["organization", "status", "start_date"], name="performance_cycle_org_idx"),
        ),
        migrations.AddIndex(
            model_name="performancegoal",
            index=models.Index(fields=["organization", "status", "cycle"], name="performance_goal_org_idx"),
        ),
        migrations.AddIndex(
            model_name="performancereview",
            index=models.Index(fields=["organization", "status", "cycle"], name="performance_review_org_idx"),
        ),
    ]
