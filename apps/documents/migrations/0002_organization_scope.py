import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_organization"),
        ("documents", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="documenttype",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="documents_documenttype_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="mandatorydocumentrule",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="documents_mandatorydocumentrule_records", to="core.organization"),
        ),
        migrations.AddField(
            model_name="employeedocument",
            name="organization",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="documents_employeedocument_records", to="core.organization"),
        ),
        migrations.AddIndex(
            model_name="mandatorydocumentrule",
            index=models.Index(fields=["organization", "is_active"], name="documents_rule_org_active_idx"),
        ),
        migrations.AddIndex(
            model_name="employeedocument",
            index=models.Index(fields=["organization", "status", "expiry_date"], name="documents_doc_org_expiry_idx"),
        ),
    ]
