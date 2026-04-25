import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("lifecycle", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="onboardingplan",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lifecycle_onboardingplan_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="onboardingtasktemplate",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lifecycle_onboardingtasktemplate_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="employeeonboarding",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lifecycle_employeeonboarding_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="employeeonboardingtask",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lifecycle_employeeonboardingtask_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="offboardingcase",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lifecycle_offboardingcase_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="offboardingtask",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lifecycle_offboardingtask_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="employeechangerequest",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lifecycle_employeechangerequest_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="employeeonboarding",
            index=models.Index(fields=["organization", "status", "start_date"], name="lifecycle_onboard_org_status_idx"),
        ),
        migrations.AddIndex(
            model_name="employeeonboardingtask",
            index=models.Index(fields=["organization", "status", "due_date"], name="lifecycle_onboard_task_org_idx"),
        ),
        migrations.AddIndex(
            model_name="offboardingcase",
            index=models.Index(fields=["organization", "status", "created_at"], name="lifecycle_offboard_org_idx"),
        ),
        migrations.AddIndex(
            model_name="offboardingtask",
            index=models.Index(fields=["organization", "status", "due_date"], name="lifecycle_offboard_task_org_idx"),
        ),
        migrations.AddIndex(
            model_name="employeechangerequest",
            index=models.Index(fields=["organization", "status", "change_type"], name="lifecycle_change_org_idx"),
        ),
    ]
