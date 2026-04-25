import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("policy_engine", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="policyrule",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="policy_engine_policyrule_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="policyevaluationlog",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="policy_engine_policyevaluationlog_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="policyrule",
            index=models.Index(fields=["organization", "module", "is_active"], name="policy_rule_org_module_idx"),
        ),
        migrations.AddIndex(
            model_name="policyevaluationlog",
            index=models.Index(fields=["organization", "module", "triggered"], name="policy_log_org_module_idx"),
        ),
    ]
