import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("workflow", "0003_alter_workflow_module_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflow",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="workflow_workflow_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="workflowstep",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="workflow_workflowstep_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="workflowassignment",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="workflow_workflowassignment_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="approvalinstance",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="workflow_approvalinstance_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="approvalaction",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="workflow_approvalaction_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="workflowassignment",
            index=models.Index(fields=["organization", "status", "module"], name="workflow_assign_org_status_idx"),
        ),
        migrations.AddIndex(
            model_name="approvalinstance",
            index=models.Index(fields=["organization", "status", "assigned_role"], name="workflow_approval_org_status_idx"),
        ),
    ]
