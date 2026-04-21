from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.utils.dateformat import format as format_date
from django.utils.timezone import localtime

from apps.payroll.models import SalaryComponent
from apps.payroll.services.payroll_component_service import (
    DEFAULT_PAYSLIP_EDITOR_CONFIG,
    PayslipTemplateService,
)


class PayslipPdfService:
    PAGE_WIDTH = Decimal("595.28")
    PAGE_HEIGHT = Decimal("841.89")
    PAGE_MARGIN = Decimal("36")

    @staticmethod
    def render_pdf(payslip, html):
        try:
            from weasyprint import HTML

            return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
        except Exception:
            return PayslipPdfService._render_fallback_pdf(payslip)

    @staticmethod
    def _render_fallback_pdf(payslip):
        document = _SimplePdfDocument(PayslipPdfService.PAGE_WIDTH, PayslipPdfService.PAGE_HEIGHT)
        page = document.new_page()

        organization_name, organization_address = PayslipPdfService._get_organization_details()
        employee = payslip.employee
        employee_name = getattr(getattr(employee, "user", None), "full_name", "")
        employee_code = getattr(employee, "employee_id", "")
        payroll_month = payslip.payroll_month.strftime("%B %Y")
        pay_date = payslip.payroll_month.strftime("%d/%m/%Y")
        generated_at = format_date(localtime(payslip.generated_at), "d M Y, h:i A")

        left = PayslipPdfService.PAGE_MARGIN
        right = PayslipPdfService.PAGE_WIDTH - PayslipPdfService.PAGE_MARGIN

        page.fill_rect(0, 0, PayslipPdfService.PAGE_WIDTH, PayslipPdfService.PAGE_HEIGHT, (248, 250, 252))
        page.fill_rect(left, 28, right - left, 4, (18, 60, 70))
        page.text(left, 58, organization_name.upper(), size=17, font="bold", color=(35, 42, 52))
        page.text(left, 78, organization_address, size=9, color=(99, 108, 122))
        page.text(right, 58, "Payslip For the Month", size=10, font="bold", align="right", color=(99, 108, 122))
        page.text(right, 76, payroll_month, size=14, font="bold", align="right", color=(18, 60, 70))
        page.line(left, 96, right, 96, color=(207, 213, 224), width=1)

        page.text(left, 125, "EMPLOYEE SUMMARY", size=10, font="bold", color=(75, 85, 99))
        summary_rows = [
            ("Employee Name", employee_name),
            ("Employee ID", employee_code),
            ("Pay Period", payroll_month),
            ("Pay Date", pay_date),
            ("Generated", generated_at),
        ]
        y = Decimal("148")
        for label, value in summary_rows:
            page.text(left, y, label, size=10, color=(91, 99, 113))
            page.text(left + 112, y, ":", size=10, color=(91, 99, 113))
            page.text(left + 126, y, value, size=10, font="bold", color=(35, 42, 52))
            y += Decimal("20")

        card_x = Decimal("365")
        page.rounded_rect(card_x, 118, right - card_x, 124, stroke=(207, 213, 224), fill=(241, 251, 248))
        page.fill_rect(card_x + 18, 140, 3, 38, (244, 183, 64))
        page.text(card_x + 32, 150, f"INR {PayslipPdfService._money(payslip.net_pay)}", size=22, font="bold", color=(18, 60, 70))
        page.text(card_x + 32, 176, "Total Net Pay", size=10, color=(99, 108, 122))
        page.line(card_x + 16, 194, right - 16, 194, color=(207, 213, 224), width=0.75)
        page.text(card_x + 28, 216, "Paid Days", size=10, color=(99, 108, 122))
        page.text(card_x + 112, 216, str(payslip.payable_days), size=10, font="bold", color=(35, 42, 52))
        page.text(card_x + 28, 234, "LOP Days", size=10, color=(99, 108, 122))
        page.text(card_x + 112, 234, str(payslip.lop_days), size=10, font="bold", color=(35, 42, 52))

        earnings, deductions = PayslipPdfService._split_rows(payslip)
        table_top = Decimal("285")
        table_left = left
        table_width = right - left
        col_widths = [Decimal("185"), Decimal("84"), Decimal("185"), Decimal("84")]
        max_rows = max(len(earnings), len(deductions), 1)
        rows_on_first_page = min(max_rows, 16)
        table_height = Decimal("34") + Decimal(rows_on_first_page + 1) * Decimal("25")

        page.rounded_rect(table_left, table_top, table_width, table_height, stroke=(207, 213, 224), fill=(255, 255, 255))
        page.fill_rect(table_left, table_top, table_width, 34, (248, 250, 252))
        page.text(table_left + 12, table_top + 21, "EARNINGS", size=9, font="bold", color=(35, 42, 52))
        page.text(table_left + col_widths[0] + col_widths[1] - 12, table_top + 21, "AMOUNT", size=9, font="bold", align="right", color=(35, 42, 52))
        page.text(table_left + col_widths[0] + col_widths[1] + 12, table_top + 21, "DEDUCTIONS", size=9, font="bold", color=(35, 42, 52))
        page.text(right - 12, table_top + 21, "AMOUNT", size=9, font="bold", align="right", color=(35, 42, 52))
        page.line(table_left, table_top + 34, right, table_top + 34, color=(207, 213, 224), width=0.75)

        row_y = table_top + Decimal("56")
        for index in range(rows_on_first_page):
            earning_name, earning_amount = earnings[index] if index < len(earnings) else ("", None)
            deduction_name, deduction_amount = deductions[index] if index < len(deductions) else ("", None)
            page.text(table_left + 12, row_y, earning_name, size=9, color=(35, 42, 52))
            if earning_amount is not None:
                page.text(
                    table_left + col_widths[0] + col_widths[1] - 12,
                    row_y,
                    f"INR {PayslipPdfService._money(earning_amount)}",
                    size=9,
                    font="bold",
                    align="right",
                    color=(35, 42, 52),
                )
            page.text(table_left + col_widths[0] + col_widths[1] + 12, row_y, deduction_name, size=9, color=(35, 42, 52))
            if deduction_amount is not None:
                page.text(right - 12, row_y, f"INR {PayslipPdfService._money(deduction_amount)}", size=9, font="bold", align="right", color=(35, 42, 52))
            row_y += Decimal("25")

        total_y = table_top + Decimal("34") + Decimal(rows_on_first_page) * Decimal("25")
        page.fill_rect(table_left, total_y, table_width, 25, (248, 250, 252))
        page.text(table_left + 12, total_y + 17, "Gross Earnings", size=9, font="bold", color=(35, 42, 52))
        page.text(table_left + col_widths[0] + col_widths[1] - 12, total_y + 17, f"INR {PayslipPdfService._money(PayslipPdfService._gross_earnings(payslip))}", size=9, font="bold", align="right", color=(35, 42, 52))
        page.text(table_left + col_widths[0] + col_widths[1] + 12, total_y + 17, "Total Deductions", size=9, font="bold", color=(35, 42, 52))
        page.text(right - 12, total_y + 17, f"INR {PayslipPdfService._money(payslip.total_deductions)}", size=9, font="bold", align="right", color=(35, 42, 52))

        net_top = total_y + Decimal("58")
        page.rounded_rect(left, net_top, right - left, 46, stroke=(207, 213, 224), fill=(255, 255, 255))
        page.text(left + 14, net_top + 18, "TOTAL NET PAYABLE", size=10, font="bold", color=(35, 42, 52))
        page.text(left + 14, net_top + 34, "Gross Earnings - Total Deductions", size=9, color=(99, 108, 122))
        page.fill_rect(right - 150, net_top, 150, 46, (241, 251, 248))
        page.text(right - 18, net_top + 28, f"INR {PayslipPdfService._money(payslip.net_pay)}", size=13, font="bold", align="right", color=(18, 60, 70))

        footer_y = PayslipPdfService.PAGE_HEIGHT - 46
        page.line(left, footer_y - 14, right, footer_y - 14, color=(207, 213, 224), width=0.75)
        page.text((left + right) / 2, footer_y, "This is a computer-generated payslip.", size=8, align="center", color=(99, 108, 122))
        if max_rows > rows_on_first_page:
            page.text((left + right) / 2, footer_y - 16, "Additional component rows are included in the payroll totals.", size=8, align="center", color=(99, 108, 122))

        return document.render()

    @staticmethod
    def _decimal(value):
        try:
            return Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0.00")

    @staticmethod
    def _money(value):
        amount = PayslipPdfService._decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{amount:,.2f}"

    @staticmethod
    def _gross_earnings(payslip):
        return (PayslipPdfService._decimal(payslip.gross_monthly_salary) + PayslipPdfService._decimal(payslip.additional_earnings)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _get_organization_details():
        organization_name = DEFAULT_PAYSLIP_EDITOR_CONFIG["organization_name"]
        organization_address = DEFAULT_PAYSLIP_EDITOR_CONFIG["address_line"]
        try:
            template = PayslipTemplateService.get_default_template()
            editor_config = template.editor_config if template and isinstance(template.editor_config, dict) else {}
            organization_name = editor_config.get("organization_name") or organization_name
            organization_address = editor_config.get("address_line") or organization_address
        except Exception:
            pass
        return organization_name, organization_address

    @staticmethod
    def _split_rows(payslip):
        earnings = []
        deductions = []
        entries = list(payslip.component_entries.all().order_by("display_order", "component_name", "id"))
        for entry in entries:
            row = (entry.component_name, entry.calculated_amount)
            if entry.component_type == SalaryComponent.ComponentType.EARNING:
                earnings.append(row)
            else:
                deductions.append(row)

        gross_earnings = PayslipPdfService._gross_earnings(payslip)
        earning_total = sum((PayslipPdfService._decimal(amount) for _, amount in earnings), Decimal("0.00"))
        balance_earnings = (gross_earnings - earning_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if balance_earnings > 0:
            earnings.append(("Gross Salary" if not earnings else "Balance Gross Earnings", balance_earnings))

        adjustment_deductions = PayslipPdfService._decimal(payslip.adjustment_deductions)
        if adjustment_deductions > 0:
            deductions.append(("Payroll Adjustments", adjustment_deductions))

        deduction_total = sum((PayslipPdfService._decimal(amount) for _, amount in deductions), Decimal("0.00"))
        other_deductions = (PayslipPdfService._decimal(payslip.total_deductions) - deduction_total).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        if other_deductions > 0:
            deductions.append(("Other Deductions", other_deductions))

        return earnings, deductions


class _SimplePdfDocument:
    def __init__(self, width, height):
        self.width = float(width)
        self.height = float(height)
        self.pages = []

    def new_page(self):
        page = _SimplePdfPage(self.width, self.height)
        self.pages.append(page)
        return page

    def render(self):
        objects = []

        def add_object(body):
            objects.append(body)
            return len(objects)

        catalog_id = add_object("<< /Type /Catalog /Pages 2 0 R >>")
        pages_id = add_object("")
        font_regular_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        font_bold_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

        page_ids = []
        for page in self.pages:
            content = page.render_content()
            content_id = add_object(f"<< /Length {len(content.encode('latin-1'))} >>\nstream\n{content}\nendstream")
            page_id = add_object(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            )
            page_ids.append(page_id)

        objects[pages_id - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(page_ids)} >>"
        objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>"

        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for index, body in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1"))

        xref_position = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
        output.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_position}\n%%EOF\n".encode(
                "latin-1"
            )
        )
        return bytes(output)


class _SimplePdfPage:
    def __init__(self, width, height):
        self.width = float(width)
        self.height = float(height)
        self.operations = []

    def render_content(self):
        return "\n".join(self.operations)

    def text(self, x, y, text, size=10, font="regular", align="left", color=(0, 0, 0)):
        value = self._sanitize_text(text)
        font_ref = "/F2" if font == "bold" else "/F1"
        width = self._text_width(value, size)
        x = float(x)
        if align == "right":
            x -= width
        elif align == "center":
            x -= width / 2
        y = self.height - float(y)
        self.operations.append(
            f"{self._color(color, 'rg')} BT {font_ref} {float(size):.2f} Tf {x:.2f} {y:.2f} Td ({self._escape(value)}) Tj ET"
        )

    def line(self, x1, y1, x2, y2, color=(0, 0, 0), width=1):
        self.operations.append(
            f"q {self._color(color, 'RG')} {float(width):.2f} w {float(x1):.2f} {self.height - float(y1):.2f} m "
            f"{float(x2):.2f} {self.height - float(y2):.2f} l S Q"
        )

    def fill_rect(self, x, y, width, height, fill):
        self.operations.append(
            f"q {self._color(fill, 'rg')} {float(x):.2f} {self.height - float(y) - float(height):.2f} "
            f"{float(width):.2f} {float(height):.2f} re f Q"
        )

    def rounded_rect(self, x, y, width, height, stroke=(0, 0, 0), fill=None):
        fill_op = f"{self._color(fill, 'rg')} " if fill else ""
        paint = "B" if fill else "S"
        self.operations.append(
            f"q {fill_op}{self._color(stroke, 'RG')} {float(x):.2f} {self.height - float(y) - float(height):.2f} "
            f"{float(width):.2f} {float(height):.2f} re {paint} Q"
        )

    @staticmethod
    def _sanitize_text(value):
        return str(value or "").encode("latin-1", "replace").decode("latin-1")

    @staticmethod
    def _escape(value):
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    @staticmethod
    def _text_width(value, size):
        return len(value) * float(size) * 0.52

    @staticmethod
    def _color(color, operator):
        red, green, blue = color
        return f"{red / 255:.3f} {green / 255:.3f} {blue / 255:.3f} {operator}"
