from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape

from django.db import transaction
from django.utils.dateformat import format as format_date
from django.utils.timezone import localtime
from rest_framework import exceptions

from apps.accounts.models import User
from apps.payroll.models import EmployeeSalaryComponentTemplate, PayslipTemplate, SalaryComponent, SalaryComponentTemplate


DEFAULT_PAYSLIP_EDITOR_CONFIG = {
    "organization_name": "Atmispace Labs",
    "logo_text": "A",
    "logo_url": "",
    "document_title": "Payslip",
    "subtitle": "Payslip For the Month",
    "address_line": "Update your registered office address in this line.",
    "payroll_note": "Salary is calculated from approved attendance, salary components, and payroll adjustments.",
    "footer_note": "This is a computer-generated payslip and does not require a physical signature.",
    "primary_color": "#123c46",
    "accent_color": "#f4b740",
    "paper_style": "standard",
}

DEFAULT_PAYSLIP_HEADER_HTML = """
<section class="payslip-header">
  <div class="brand-block">
    {{logo_image}}
    <div>
      <p class="organization-name">{{organization_name}}</p>
      <p class="organization-address">{{organization_address}}</p>
    </div>
  </div>
  <div class="document-meta">
    <p class="document-label">{{document_label}}</p>
    <p class="document-period">{{payroll_month}}</p>
  </div>
</section>
""".strip()

DEFAULT_PAYSLIP_BODY_HTML = """
<main class="payslip-body">
  <section class="summary-row">
    <div class="employee-summary">
      <h2>Employee Summary</h2>
      <div class="summary-line"><span>Employee Name</span><b>:</b><strong>{{employee_name}}</strong></div>
      <div class="summary-line"><span>Employee ID</span><b>:</b><strong>{{employee_id}}</strong></div>
      <div class="summary-line"><span>Pay Period</span><b>:</b><strong>{{payroll_month}}</strong></div>
      <div class="summary-line"><span>Pay Date</span><b>:</b><strong>{{pay_date}}</strong></div>
    </div>

    <div class="net-pay-card">
      <div class="net-pay-total">
        <strong>&#8377;{{net_pay}}</strong>
        <span>Total Net Pay</span>
      </div>
      <div class="net-pay-days">
        <div><span>Paid Days</span><b>:</b><strong>{{payable_days}}</strong></div>
        <div><span>LOP Days</span><b>:</b><strong>{{lop_days}}</strong></div>
      </div>
    </div>
  </section>

  <section class="salary-table">
    <table>
      <thead>
        <tr>
          <th>Earnings</th>
          <th class="amount-cell">Amount</th>
          <th>Deductions</th>
          <th class="amount-cell">Amount</th>
        </tr>
      </thead>
      <tbody>
        {{split_component_rows}}
        <tr class="totals-row">
          <td>Gross Earnings</td>
          <td class="amount-cell">&#8377;{{gross_earnings}}</td>
          <td>Total Deductions</td>
          <td class="amount-cell">&#8377;{{total_deductions}}</td>
        </tr>
      </tbody>
    </table>
  </section>

  <section class="net-payable-row">
    <div>
      <h2>Total Net Payable</h2>
      <p>Gross Earnings - Total Deductions</p>
    </div>
    <strong>&#8377;{{net_pay}}</strong>
  </section>

  <section class="amount-words">
    <span>Amount In Words:</span>
    <strong>{{amount_in_words}}</strong>
  </section>
</main>
""".strip()

DEFAULT_PAYSLIP_FOOTER_HTML = """
<footer class="payslip-footer">
  <span>{{footer_note}}</span>
</footer>
""".strip()

DEFAULT_PAYSLIP_CSS = """
body {
  margin: 0;
  background: #f7f8fb;
  color: #2f343d;
  font-family: Arial, sans-serif;
}

.payslip-header,
.payslip-body,
.payslip-footer {
  box-sizing: border-box;
  max-width: 1040px;
  margin: 0 auto;
  background: #ffffff;
}

.payslip-header {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 32px;
  padding: 30px 44px 14px;
  border-bottom: 2px solid #d8dde5;
}

.payslip-header:before {
  content: "";
  position: absolute;
  left: 44px;
  right: 44px;
  top: 0;
  height: 5px;
  border-radius: 0 0 999px 999px;
  background: linear-gradient(90deg, #123c46, #1aa39a 55%, #f4b740);
}

.brand-block {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: #123c46;
  color: #ffffff;
  font-size: 20px;
  font-weight: 700;
}

.brand-logo {
  width: 52px;
  height: 52px;
  object-fit: contain;
}

.organization-name {
  margin: 0;
  color: #2b2f36;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.organization-address {
  margin: 6px 0 0;
  color: #646b76;
  font-size: 15px;
  letter-spacing: 0.03em;
}

.document-meta {
  min-width: 220px;
  text-align: right;
}

.document-label {
  margin: 0;
  color: #646b76;
  font-size: 16px;
  font-weight: 600;
}

.document-period {
  margin: 6px 0 0;
  color: #123c46;
  font-size: 20px;
  font-weight: 700;
}

.payslip-body {
  padding: 20px 40px 20px;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  gap: 40px;
  margin-bottom: 50px;
}

.employee-summary {
  min-width: 440px;
}

.employee-summary h2,
.net-payable-row h2 {
  margin: 0 0 12px;
  color: #4b5563;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.summary-line {
  display: grid;
  grid-template-columns: 170px 18px 1fr;
  gap: 10px;
  margin-top: 13px;
  color: #5f6672;
  font-size: 16px;
}

.summary-line strong {
  color: #2f343d;
  font-weight: 700;
}

.net-pay-card {
  width: 330px;
  border: 1px solid #d8dde5;
  border-radius: 10px;
  background: #f1fbf8;
  overflow: hidden;
}

.net-pay-total {
  padding: 26px 28px 22px;
  border-bottom: 1px dashed #d8dde5;
  position: relative;
}

.net-pay-total:before {
  content: "";
  position: absolute;
  left: 24px;
  top: 24px;
  bottom: 26px;
  width: 4px;
  border-radius: 4px;
  background: #f4b740;
}

.net-pay-total strong {
  display: block;
  padding-left: 18px;
  color: #123c46;
  font-size: 31px;
  letter-spacing: 0.04em;
}

.net-pay-total span {
  display: block;
  padding-left: 18px;
  margin-top: 8px;
  color: #68707c;
  font-size: 15px;
}

.net-pay-days {
  padding: 18px 28px;
}

.net-pay-days div {
  display: grid;
  grid-template-columns: 120px 16px 1fr;
  gap: 8px;
  margin: 9px 0;
  color: #68707c;
  font-size: 16px;
}

.net-pay-days strong {
  color: #2f343d;
}

.salary-table {
  border: 1px solid #d8dde5;
  border-radius: 10px;
  overflow: hidden;
}

table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

th {
  color: #2f343d;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-align: left;
  text-transform: uppercase;
}

td,
th {
  padding: 14px 22px;
  border-bottom: 1px dashed #d8dde5;
  font-size: 15px;
}

td {
  color: #252a32;
  font-weight: 600;
}

.amount-cell {
  text-align: right;
  font-weight: 700;
}

.totals-row td {
  border-bottom: 0;
  background: #f7f8fb;
  font-weight: 700;
}

.net-payable-row {
  display: grid;
  grid-template-columns: 1fr 150px;
  align-items: center;
  margin-top: 38px;
  border: 1px solid #d8dde5;
  border-radius: 9px;
  overflow: hidden;
}

.net-payable-row div {
  padding: 14px 22px;
}

.net-payable-row h2 {
  margin-bottom: 5px;
  color: #123c46;
}

.net-payable-row p {
  margin: 0;
  color: #68707c;
  font-size: 14px;
}

.net-payable-row strong {
  align-self: stretch;
  display: grid;
  place-items: center;
  background: #f1fbf8;
  color: #123c46;
  font-size: 18px;
}

.amount-words {
  margin-top: 32px;
  padding: 0 0 18px;
  border-bottom: 2px solid #d8dde5;
  text-align: right;
  color: #5f6672;
  font-size: 15px;
}

.amount-words strong {
  color: #2f343d;
}

.payslip-footer {
  padding: 0 40px 28px;
  color: #68707c;
  font-size: 12px;
  text-align: center;
}
""".strip()

DEFAULT_PAYSLIP_TEMPLATE_DATA = {
    "name": "Standard Payslip",
    "description": "Default no-code payslip layout for HR and Accounts teams.",
    "is_default": True,
    "is_active": True,
    "show_component_breakdown": True,
    "header_html": DEFAULT_PAYSLIP_HEADER_HTML,
    "body_html": DEFAULT_PAYSLIP_BODY_HTML,
    "footer_html": DEFAULT_PAYSLIP_FOOTER_HTML,
    "css_styles": DEFAULT_PAYSLIP_CSS,
    "editor_config": DEFAULT_PAYSLIP_EDITOR_CONFIG,
}

STANDARD_SALARY_COMPONENTS = [
    {
        "name": "Basic Salary",
        "code": "BASIC",
        "component_type": SalaryComponent.ComponentType.EARNING,
        "calculation_type": SalaryComponent.CalculationType.PERCENT_OF_GROSS,
        "value": "50.00",
        "display_order": 10,
        "is_active": True,
        "is_taxable": True,
        "is_part_of_gross": True,
        "description": "Standard basic salary component calculated as 50% of monthly gross salary.",
    },
    {
        "name": "Provident Fund",
        "code": "PF",
        "component_type": SalaryComponent.ComponentType.DEDUCTION,
        "calculation_type": SalaryComponent.CalculationType.PERCENT_OF_COMPONENT,
        "value": "12.00",
        "display_order": 100,
        "is_active": True,
        "is_taxable": False,
        "is_part_of_gross": False,
        "has_employer_contribution": True,
        "employer_contribution_value": "12.00",
        "deduct_employer_contribution": False,
        "description": "Employee PF calculated as 12% of Basic Salary. Employer PF is tracked separately unless configured as deductible.",
    },
]


class SalaryComponentService:
    MANAGE_ROLES = {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}
    DELETE_ROLES = {User.Role.ADMIN}

    @staticmethod
    def _check_manage_permission(user):
        if not user or not getattr(user, "is_authenticated", False) or user.role not in SalaryComponentService.MANAGE_ROLES:
            raise exceptions.PermissionDenied("You are not allowed to manage salary components.")

    @staticmethod
    def _check_delete_permission(user):
        if not user or not getattr(user, "is_authenticated", False) or user.role not in SalaryComponentService.DELETE_ROLES:
            raise exceptions.PermissionDenied("Only admins can delete salary components.")

    @staticmethod
    @transaction.atomic
    def ensure_standard_components():
        default_template = SalaryComponentService.get_default_template()
        if default_template.components.exists():
            return

        created_components = {}
        for component_data in STANDARD_SALARY_COMPONENTS:
            data = dict(component_data)
            code = data.pop("code")
            if code == "PF":
                data["base_component"] = created_components.get("BASIC")
            component = SalaryComponent.objects.create(template=default_template, code=code, **data)
            created_components[code] = component

    @staticmethod
    @transaction.atomic
    def get_default_template():
        default_template = SalaryComponentTemplate.objects.filter(is_default=True, is_active=True).first()
        if default_template:
            return default_template

        template, created = SalaryComponentTemplate.objects.get_or_create(
            name="Standard Salary Structure",
            defaults={
                "description": "Default salary component package used when no employee-specific package is assigned.",
                "is_default": True,
                "is_active": True,
            },
        )
        if created or not template.is_default:
            SalaryComponentTemplate.objects.exclude(pk=template.pk).update(is_default=False)
            template.is_default = True
            template.is_active = True
            template.save(update_fields=["is_default", "is_active", "updated_at"])
        return template

    @staticmethod
    def get_template_for_employee(employee):
        assignment = (
            EmployeeSalaryComponentTemplate.objects.select_related("template")
            .filter(employee=employee, template__is_active=True)
            .first()
        )
        if assignment:
            return assignment.template
        return SalaryComponentService.get_default_template()

    @staticmethod
    def _normalize_component_payload(validated_data, instance=None):
        if "template" not in validated_data and instance is None:
            validated_data["template"] = SalaryComponentService.get_default_template()
        component_type = validated_data.get("component_type", getattr(instance, "component_type", None))
        calculation_type = validated_data.get("calculation_type", getattr(instance, "calculation_type", None))
        has_employer_contribution = validated_data.get(
            "has_employer_contribution",
            getattr(instance, "has_employer_contribution", False),
        )

        if component_type == SalaryComponent.ComponentType.DEDUCTION:
            validated_data["is_part_of_gross"] = False
        if calculation_type != SalaryComponent.CalculationType.PERCENT_OF_COMPONENT:
            validated_data["base_component"] = None
        if not has_employer_contribution:
            validated_data["employer_contribution_value"] = 0
            validated_data["deduct_employer_contribution"] = False
        return validated_data

    @staticmethod
    def create_component(validated_data, actor):
        SalaryComponentService._check_manage_permission(actor)
        validated_data = SalaryComponentService._normalize_component_payload(validated_data)
        component = SalaryComponent.objects.create(**validated_data)
        return component

    @staticmethod
    def update_component(instance, validated_data, actor):
        SalaryComponentService._check_manage_permission(actor)
        validated_data = SalaryComponentService._normalize_component_payload(validated_data, instance=instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    def delete_component(instance, actor):
        SalaryComponentService._check_delete_permission(actor)
        instance.delete()

    @staticmethod
    @transaction.atomic
    def create_template(validated_data, actor):
        SalaryComponentService._check_manage_permission(actor)
        is_default = validated_data.get("is_default", False) or not SalaryComponentTemplate.objects.exists()
        validated_data["is_default"] = is_default
        if is_default:
            SalaryComponentTemplate.objects.filter(is_default=True).update(is_default=False)
        return SalaryComponentTemplate.objects.create(**validated_data)

    @staticmethod
    @transaction.atomic
    def update_template(instance, validated_data, actor):
        SalaryComponentService._check_manage_permission(actor)
        is_default = validated_data.get("is_default", instance.is_default)
        if is_default and not instance.is_default:
            SalaryComponentTemplate.objects.filter(is_default=True).update(is_default=False)
        if instance.is_default and not is_default:
            has_other_default = SalaryComponentTemplate.objects.exclude(pk=instance.pk).filter(
                is_default=True,
                is_active=True,
            ).exists()
            if not has_other_default:
                validated_data["is_default"] = True
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    def delete_template(instance, actor):
        SalaryComponentService._check_delete_permission(actor)
        if instance.is_default:
            raise exceptions.ValidationError({"template": "Default salary component template cannot be deleted."})
        if instance.employee_assignments.exists():
            raise exceptions.ValidationError({"template": "Template is assigned to employees and cannot be deleted."})
        instance.delete()

    @staticmethod
    @transaction.atomic
    def assign_template_to_employee(employee, template, actor, notes=""):
        SalaryComponentService._check_manage_permission(actor)
        if not template.is_active:
            raise exceptions.ValidationError({"template": "Select an active salary component template."})
        assignment, _ = EmployeeSalaryComponentTemplate.objects.update_or_create(
            employee=employee,
            defaults={
                "template": template,
                "assigned_by": actor,
                "notes": notes,
            },
        )
        return assignment


class PayslipTemplateService:
    MANAGE_ROLES = {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}
    DELETE_ROLES = {User.Role.ADMIN}

    @staticmethod
    def _check_manage_permission(user):
        if not user or not getattr(user, "is_authenticated", False) or user.role not in PayslipTemplateService.MANAGE_ROLES:
            raise exceptions.PermissionDenied("You are not allowed to manage payslip templates.")

    @staticmethod
    def _check_delete_permission(user):
        if not user or not getattr(user, "is_authenticated", False) or user.role not in PayslipTemplateService.DELETE_ROLES:
            raise exceptions.PermissionDenied("Only admins can delete payslip templates.")

    @staticmethod
    @transaction.atomic
    def create_template(validated_data, actor):
        PayslipTemplateService._check_manage_permission(actor)
        is_default = validated_data.get("is_default", False) or not PayslipTemplate.objects.exists()
        validated_data["is_default"] = is_default
        if is_default:
            PayslipTemplate.objects.filter(is_default=True).update(is_default=False)
        template = PayslipTemplate.objects.create(**validated_data)
        return template

    @staticmethod
    @transaction.atomic
    def update_template(instance, validated_data, actor):
        PayslipTemplateService._check_manage_permission(actor)
        is_default = validated_data.get("is_default", instance.is_default)
        if is_default and not instance.is_default:
            PayslipTemplate.objects.filter(is_default=True).update(is_default=False)
        if instance.is_default and not is_default:
            has_other_default = PayslipTemplate.objects.exclude(pk=instance.pk).filter(is_default=True, is_active=True).exists()
            if not has_other_default:
                validated_data["is_default"] = True
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @staticmethod
    @transaction.atomic
    def delete_template(instance, actor):
        PayslipTemplateService._check_delete_permission(actor)
        was_default = instance.is_default
        instance.delete()
        if was_default:
            replacement = PayslipTemplate.objects.filter(is_active=True).first()
            if replacement:
                replacement.is_default = True
                replacement.save(update_fields=["is_default", "updated_at"])

    @staticmethod
    def _refresh_legacy_default_template(template):
        legacy_body_markers = ("intro-strip", "info-grid", "summary-grid", "component-section")
        editor_config = template.editor_config if isinstance(template.editor_config, dict) else {}
        uses_stock_theme = editor_config.get("primary_color") in {"#111827", "#0f766e", None} or "#86d37f" in (
            template.css_styles or ""
        )
        uses_legacy_layout = any(marker in (template.body_html or "") for marker in legacy_body_markers)
        if template.name != DEFAULT_PAYSLIP_TEMPLATE_DATA["name"] or not (uses_legacy_layout or uses_stock_theme):
            return template

        refreshed_editor_config = dict(DEFAULT_PAYSLIP_EDITOR_CONFIG)
        for key in ("organization_name", "logo_text", "logo_url", "address_line", "footer_note"):
            if editor_config.get(key):
                refreshed_editor_config[key] = editor_config[key]

        template.header_html = DEFAULT_PAYSLIP_HEADER_HTML
        template.body_html = DEFAULT_PAYSLIP_BODY_HTML
        template.footer_html = DEFAULT_PAYSLIP_FOOTER_HTML
        template.css_styles = DEFAULT_PAYSLIP_CSS
        template.editor_config = refreshed_editor_config
        template.show_component_breakdown = True
        template.save(
            update_fields=[
                "header_html",
                "body_html",
                "footer_html",
                "css_styles",
                "editor_config",
                "show_component_breakdown",
                "updated_at",
            ]
        )
        return template

    @staticmethod
    @transaction.atomic
    def ensure_default_template():
        default_template = PayslipTemplate.objects.filter(is_default=True, is_active=True).first()
        if default_template:
            return PayslipTemplateService._refresh_legacy_default_template(default_template)
        if PayslipTemplate.objects.exists():
            return None

        template = PayslipTemplate.objects.create(**DEFAULT_PAYSLIP_TEMPLATE_DATA)
        return template

    @staticmethod
    def get_default_template():
        default_template = PayslipTemplate.objects.filter(is_default=True, is_active=True).first()
        if default_template:
            return PayslipTemplateService._refresh_legacy_default_template(default_template)
        return PayslipTemplateService.ensure_default_template()

    @staticmethod
    def render_payslip(payslip, template=None):
        """
        Render a payslip as HTML using the given template (or default/built-in if None).
        Returns an HTML string.
        """
        payroll_month_str = payslip.payroll_month.strftime("%B %Y")
        employee = payslip.employee
        generated_at = format_date(localtime(payslip.generated_at), "d M Y, h:i A")
        pay_date = payslip.payroll_month.strftime("%d/%m/%Y")

        def safe(value):
            return escape("" if value is None else str(value), quote=True)

        def decimal_value(value):
            try:
                return Decimal(str(value or 0))
            except (InvalidOperation, TypeError, ValueError):
                return Decimal("0.00")

        def money(value):
            amount = decimal_value(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return f"{amount:,.2f}"

        def number_to_words_under_1000(number):
            ones = [
                "",
                "One",
                "Two",
                "Three",
                "Four",
                "Five",
                "Six",
                "Seven",
                "Eight",
                "Nine",
                "Ten",
                "Eleven",
                "Twelve",
                "Thirteen",
                "Fourteen",
                "Fifteen",
                "Sixteen",
                "Seventeen",
                "Eighteen",
                "Nineteen",
            ]
            tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

            number = int(number)
            if number < 20:
                return ones[number]
            if number < 100:
                ten, remainder = divmod(number, 10)
                return tens[ten] if remainder == 0 else f"{tens[ten]}-{ones[remainder]}"
            hundred, remainder = divmod(number, 100)
            words = [f"{ones[hundred]} Hundred"]
            if remainder:
                words.append(number_to_words_under_1000(remainder))
            return " ".join(words)

        def amount_to_words(value):
            amount = decimal_value(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            absolute_amount = abs(amount)
            rupees = int(absolute_amount)
            paise = int(((absolute_amount - Decimal(rupees)) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            if paise == 100:
                rupees += 1
                paise = 0

            remaining = rupees
            parts = []
            for divisor, label in (
                (10000000, "Crore"),
                (100000, "Lakh"),
                (1000, "Thousand"),
                (1, ""),
            ):
                chunk, remaining = divmod(remaining, divisor)
                if chunk:
                    words = number_to_words_under_1000(chunk)
                    parts.append(f"{words} {label}".strip())

            rupee_words = " ".join(parts) if parts else "Zero"
            prefix = "Negative Indian Rupee" if amount < 0 else "Indian Rupee"
            if paise:
                return f"{prefix} {rupee_words} and {number_to_words_under_1000(paise)} Paise Only"
            return f"{prefix} {rupee_words} Only"

        employee_name = ""
        try:
            employee_name = employee.user.full_name
        except Exception:
            pass

        employee_id = getattr(employee, "employee_id", "")
        designation = getattr(employee, "designation", "") or ""
        department_name = getattr(getattr(employee, "department", None), "name", "") or ""
        settings_organization_name = "Organization"
        try:
            from apps.employees.services.employee_service import OrganizationSettingsService

            settings_organization_name = OrganizationSettingsService.get_settings().organization_name
        except Exception:
            pass

        editor_config = dict(DEFAULT_PAYSLIP_EDITOR_CONFIG)
        if template is not None and isinstance(template.editor_config, dict):
            editor_config.update({key: value for key, value in template.editor_config.items() if value is not None})

        organization_name = editor_config.get("organization_name") or settings_organization_name
        organization_address = editor_config.get("address_line") or DEFAULT_PAYSLIP_EDITOR_CONFIG["address_line"]
        document_label = editor_config.get("subtitle") or DEFAULT_PAYSLIP_EDITOR_CONFIG["subtitle"]
        footer_note = editor_config.get("footer_note") or DEFAULT_PAYSLIP_EDITOR_CONFIG["footer_note"]
        logo_text = (editor_config.get("logo_text") or organization_name[:1] or "A")[:3].upper()
        logo_url = (editor_config.get("logo_url") or "").strip()
        logo_image = (
            f'<img class="brand-logo" src="{safe(logo_url)}" alt="{safe(organization_name)} logo" />'
            if logo_url
            else f'<div class="brand-mark">{safe(logo_text)}</div>'
        )

        # Build component rows HTML
        component_rows_html = ""
        split_component_rows_html = ""
        earning_rows = []
        deduction_rows = []
        has_lop_component_entry = False
        entries = list(payslip.component_entries.all().order_by("display_order", "component_name", "id"))
        if entries:
            rows = []
            for entry in entries:
                row_type = "Earning" if entry.component_type == SalaryComponent.ComponentType.EARNING else "Deduction"
                component_name = safe(entry.component_name)
                if (
                    entry.component_type == SalaryComponent.ComponentType.DEDUCTION
                    and str(entry.component_code).upper() == "LOP"
                ):
                    has_lop_component_entry = True
                if entry.employer_contribution_amount:
                    employer_status = "deducted" if entry.deducts_employer_contribution else "not deducted"
                    component_name = (
                        f"{component_name}<br><small>Employer contribution: "
                        f"{safe(money(entry.employer_contribution_amount))} ({employer_status})</small>"
                    )
                rows.append(
                    f"<tr><td>{component_name}</td><td>{safe(row_type)}</td>"
                    f"<td class='amount-cell' style='text-align:right'>{safe(money(entry.calculated_amount))}</td></tr>"
                )
                if entry.component_type == SalaryComponent.ComponentType.EARNING:
                    earning_rows.append((component_name, entry.calculated_amount))
                else:
                    deduction_rows.append((component_name, entry.calculated_amount))
            component_rows_html = "\n".join(rows)

        gross_earnings = (decimal_value(payslip.gross_monthly_salary) + decimal_value(payslip.additional_earnings)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        earning_rows_total = sum((decimal_value(amount) for _, amount in earning_rows), Decimal("0.00"))
        balance_earnings = (gross_earnings - earning_rows_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if balance_earnings > 0:
            earning_rows.append(("Gross Salary" if not earning_rows else "Balance Gross Earnings", balance_earnings))

        lop_deduction = decimal_value(payslip.lop_deduction)
        if lop_deduction > 0 and not has_lop_component_entry:
            deduction_rows.append(("LOP Deduction", lop_deduction))

        adjustment_deductions = decimal_value(payslip.adjustment_deductions)
        if adjustment_deductions > 0:
            deduction_rows.append(("Payroll Adjustments", adjustment_deductions))

        deduction_rows_total = sum((decimal_value(amount) for _, amount in deduction_rows), Decimal("0.00"))
        other_deductions = (decimal_value(payslip.total_deductions) - deduction_rows_total).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        if other_deductions > 0:
            deduction_rows.append(("Other Deductions", other_deductions))

        split_row_count = max(len(earning_rows), len(deduction_rows))
        if split_row_count:
            split_rows = []
            for index in range(split_row_count):
                earning_name, earning_amount = earning_rows[index] if index < len(earning_rows) else ("", None)
                deduction_name, deduction_amount = deduction_rows[index] if index < len(deduction_rows) else ("", None)
                split_rows.append(
                    "<tr>"
                    f"<td>{earning_name}</td>"
                    f"<td class='amount-cell'>{'&#8377;' + safe(money(earning_amount)) if earning_amount is not None else ''}</td>"
                    f"<td>{deduction_name}</td>"
                    f"<td class='amount-cell'>{'&#8377;' + safe(money(deduction_amount)) if deduction_amount is not None else ''}</td>"
                    "</tr>"
                )
            split_component_rows_html = "\n".join(split_rows)

        replacements = {
            "{{organization_name}}": safe(organization_name),
            "{{organization_address}}": safe(organization_address),
            "{{document_label}}": safe(document_label),
            "{{logo_image}}": logo_image,
            "{{footer_note}}": safe(footer_note),
            "{{employee_name}}": safe(employee_name),
            "{{employee_id}}": safe(employee_id),
            "{{designation}}": safe(designation),
            "{{department_name}}": safe(department_name),
            "{{payroll_month}}": safe(payroll_month_str),
            "{{pay_date}}": safe(pay_date),
            "{{generated_at}}": safe(generated_at),
            "{{gross_salary}}": safe(money(payslip.gross_monthly_salary)),
            "{{gross_earnings}}": safe(money(gross_earnings)),
            "{{additional_earnings}}": safe(money(payslip.additional_earnings)),
            "{{net_pay}}": safe(money(payslip.net_pay)),
            "{{total_deductions}}": safe(money(payslip.total_deductions)),
            "{{component_deductions}}": safe(money(payslip.component_deductions)),
            "{{adjustment_deductions}}": safe(money(payslip.adjustment_deductions)),
            "{{fixed_deductions}}": safe("0.00"),
            "{{rule_based_deductions}}": safe(money(payslip.component_deductions)),
            "{{lop_days}}": safe(payslip.lop_days),
            "{{lop_deduction}}": safe(money(payslip.lop_deduction)),
            "{{payable_days}}": safe(payslip.payable_days),
            "{{days_in_month}}": safe(payslip.days_in_month),
            "{{notes}}": safe(payslip.notes),
            "{{component_rows}}": component_rows_html if template is None or template.show_component_breakdown else "",
            "{{split_component_rows}}": split_component_rows_html if template is None or template.show_component_breakdown else "",
            "{{amount_in_words}}": safe(amount_to_words(payslip.net_pay)),
        }

        def render_fragment(fragment):
            rendered = fragment or ""
            for placeholder, value in replacements.items():
                rendered = rendered.replace(placeholder, value)
            return rendered

        if template is None:
            # Built-in fallback template
            show_breakdown = bool(entries)
            breakdown_section = ""
            if show_breakdown:
                breakdown_section = f"""
                <h3>Component Breakdown</h3>
                <table border="1" cellpadding="5" cellspacing="0" style="width:100%;border-collapse:collapse">
                  <thead>
                    <tr><th>Component</th><th>Type</th><th>Amount</th></tr>
                  </thead>
                  <tbody>
                    {component_rows_html}
                  </tbody>
                </table>
                """
            html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Payslip - {payroll_month_str}</title>
<style>body{{font-family:Arial,sans-serif;padding:20px}} table{{width:100%}}</style>
</head>
<body>
  <h1>Payslip</h1>
  <hr>
  <table>
    <tr><td><strong>Employee Name:</strong></td><td>{safe(employee_name)}</td>
        <td><strong>Employee ID:</strong></td><td>{safe(employee_id)}</td></tr>
    <tr><td><strong>Designation:</strong></td><td>{safe(designation)}</td>
        <td><strong>Payroll Month:</strong></td><td>{safe(payroll_month_str)}</td></tr>
  </table>
  <hr>
  <table>
    <tr><td><strong>Gross Salary:</strong></td><td>{safe(money(payslip.gross_monthly_salary))}</td></tr>
    <tr><td><strong>Total Deductions:</strong></td><td>{safe(money(payslip.total_deductions))}</td></tr>
    <tr><td><strong>LOP Days:</strong></td><td>{safe(payslip.lop_days)}</td></tr>
    <tr><td><strong>Net Pay:</strong></td><td>{safe(money(payslip.net_pay))}</td></tr>
  </table>
  {breakdown_section}
</body>
</html>"""
            return html

        # Use the provided template
        header = render_fragment(template.header_html)
        body = render_fragment(template.body_html)
        footer = render_fragment(template.footer_html)

        css_block = f"<style>{template.css_styles}</style>" if template.css_styles else ""
        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Payslip - {payroll_month_str}</title>
{css_block}
</head>
<body>
{header}
{body}
{footer}
</body>
</html>"""
        return html
