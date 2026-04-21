from rest_framework import serializers

from apps.employees.models import Employee
from apps.payroll.models import (
    EmployeeSalaryComponentTemplate,
    PayrollAdjustment,
    PayrollCycle,
    PayrollRun,
    Payslip,
    PayslipComponentEntry,
    PayslipTemplate,
    SalaryComponent,
    SalaryComponentTemplate,
    SalaryRevision,
)


class PayslipComponentEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PayslipComponentEntry
        fields = (
            "id",
            "component",
            "component_name",
            "component_code",
            "component_type",
            "calculated_amount",
            "employer_contribution_amount",
            "deducts_employer_contribution",
            "display_order",
        )
        read_only_fields = fields


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    generated_by_name = serializers.CharField(source="generated_by.full_name", read_only=True)
    payroll_cycle_name = serializers.CharField(source="payroll_cycle.name", read_only=True)
    salary_component_template_name = serializers.CharField(read_only=True)
    component_entries = PayslipComponentEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Payslip
        fields = (
            "id",
            "payroll_cycle",
            "payroll_cycle_name",
            "salary_component_template",
            "salary_component_template_name",
            "employee",
            "employee_code",
            "employee_name",
            "payroll_month",
            "gross_monthly_salary",
            "additional_earnings",
            "component_deductions",
            "adjustment_deductions",
            "lop_days",
            "lop_deduction",
            "total_deductions",
            "net_pay",
            "days_in_month",
            "payable_days",
            "generated_by",
            "generated_by_name",
            "notes",
            "generated_at",
            "created_at",
            "updated_at",
            "component_entries",
        )
        read_only_fields = fields


class PayslipGenerateSerializer(serializers.Serializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.select_related("user"))
    payroll_month = serializers.DateField()
    salary_component_template = serializers.PrimaryKeyRelatedField(
        queryset=SalaryComponentTemplate.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class PayrollCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollCycle
        fields = ("id", "name", "payroll_month", "start_date", "end_date", "status", "notes", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class PayrollRunSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(source="generated_by.full_name", read_only=True)
    released_by_name = serializers.CharField(source="released_by.full_name", read_only=True)
    cycle_name = serializers.CharField(source="cycle.name", read_only=True)

    class Meta:
        model = PayrollRun
        fields = (
            "id",
            "cycle",
            "cycle_name",
            "generated_by",
            "generated_by_name",
            "released_by",
            "released_by_name",
            "total_employees",
            "status",
            "locked_at",
            "released_at",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PayrollAdjustmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    cycle_name = serializers.CharField(source="cycle.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = PayrollAdjustment
        fields = (
            "id",
            "cycle",
            "cycle_name",
            "employee",
            "employee_name",
            "employee_code",
            "adjustment_type",
            "amount",
            "reason",
            "status",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "cycle_name", "employee_name", "employee_code", "created_by_name", "created_at", "updated_at")


class SalaryRevisionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.full_name", read_only=True)

    class Meta:
        model = SalaryRevision
        fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "previous_ctc",
            "new_ctc",
            "effective_date",
            "reason",
            "status",
            "approved_by",
            "approved_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SalaryComponentSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    base_component_name = serializers.CharField(source="base_component.name", read_only=True)

    class Meta:
        model = SalaryComponent
        fields = (
            "id",
            "template",
            "template_name",
            "name",
            "code",
            "component_type",
            "calculation_type",
            "base_component",
            "base_component_name",
            "value",
            "display_order",
            "is_active",
            "is_taxable",
            "is_part_of_gross",
            "has_employer_contribution",
            "employer_contribution_value",
            "deduct_employer_contribution",
            "description",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "template_name", "base_component_name", "created_at", "updated_at")

    def validate(self, attrs):
        code = attrs.get("code", getattr(self.instance, "code", ""))
        if str(code).upper() == "LOP":
            raise serializers.ValidationError({"code": "LOP is reserved for the system-generated Loss of Pay deduction."})
        calculation_type = attrs.get("calculation_type", getattr(self.instance, "calculation_type", None))
        base_component = attrs.get("base_component", getattr(self.instance, "base_component", None))
        template = attrs.get("template", getattr(self.instance, "template", None))
        if calculation_type == SalaryComponent.CalculationType.PERCENT_OF_COMPONENT and not base_component:
            raise serializers.ValidationError({"base_component": "Select the salary component this percentage is based on."})
        if self.instance and base_component and base_component.pk == self.instance.pk:
            raise serializers.ValidationError({"base_component": "A component cannot be based on itself."})
        if base_component and template and base_component.template_id != template.pk:
            raise serializers.ValidationError({"base_component": "Base component must belong to the same salary template."})
        return attrs


class SalaryComponentTemplateSerializer(serializers.ModelSerializer):
    component_count = serializers.SerializerMethodField()
    assigned_employee_count = serializers.SerializerMethodField()

    class Meta:
        model = SalaryComponentTemplate
        fields = (
            "id",
            "name",
            "description",
            "is_default",
            "is_active",
            "component_count",
            "assigned_employee_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "component_count", "assigned_employee_count", "created_at", "updated_at")

    def get_component_count(self, obj):
        return obj.components.count()

    def get_assigned_employee_count(self, obj):
        return obj.employee_assignments.count()


class EmployeeSalaryComponentTemplateSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)
    assigned_by_name = serializers.CharField(source="assigned_by.full_name", read_only=True)

    class Meta:
        model = EmployeeSalaryComponentTemplate
        fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "template",
            "template_name",
            "assigned_by",
            "assigned_by_name",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "employee_name",
            "employee_code",
            "template_name",
            "assigned_by",
            "assigned_by_name",
            "created_at",
            "updated_at",
        )


class PayslipTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayslipTemplate
        fields = (
            "id",
            "name",
            "description",
            "is_default",
            "is_active",
            "header_html",
            "body_html",
            "footer_html",
            "css_styles",
            "editor_config",
            "show_component_breakdown",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
