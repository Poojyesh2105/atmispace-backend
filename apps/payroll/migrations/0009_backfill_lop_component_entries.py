from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


LOP_COMPONENT_CODE = "LOP"
LOP_COMPONENT_NAME = "Loss of Pay"
LOP_COMPONENT_DISPLAY_ORDER = 9000


def backfill_lop_component_entries(apps, schema_editor):
    payslip_model = apps.get_model("payroll", "Payslip")
    component_entry_model = apps.get_model("payroll", "PayslipComponentEntry")

    for payslip in payslip_model.objects.all().iterator():
        has_lop_entry = component_entry_model.objects.filter(
            payslip=payslip,
            component_code=LOP_COMPONENT_CODE,
        ).exists()
        if has_lop_entry:
            continue

        component_entry_model.objects.create(
            payslip=payslip,
            component=None,
            component_name=LOP_COMPONENT_NAME,
            component_code=LOP_COMPONENT_CODE,
            component_type="DEDUCTION",
            calculated_amount=Decimal(str(payslip.lop_deduction or 0)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            ),
            employer_contribution_amount=Decimal("0.00"),
            deducts_employer_contribution=False,
            display_order=LOP_COMPONENT_DISPLAY_ORDER,
        )


def remove_backfilled_lop_component_entries(apps, schema_editor):
    component_entry_model = apps.get_model("payroll", "PayslipComponentEntry")
    component_entry_model.objects.filter(
        component__isnull=True,
        component_name=LOP_COMPONENT_NAME,
        component_code=LOP_COMPONENT_CODE,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0008_salary_component_templates"),
    ]

    operations = [
        migrations.RunPython(backfill_lop_component_entries, remove_backfilled_lop_component_entries),
    ]
