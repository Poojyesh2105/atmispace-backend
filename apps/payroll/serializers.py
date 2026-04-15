from rest_framework import serializers

from apps.employees.models import Employee
from apps.payroll.models import DeductionRule, PayrollAdjustment, PayrollCycle, PayrollRun, Payslip, SalaryRevision


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    generated_by_name = serializers.CharField(source="generated_by.full_name", read_only=True)
    payroll_cycle_name = serializers.CharField(source="payroll_cycle.name", read_only=True)

    class Meta:
        model = Payslip
        fields = (
            "id",
            "payroll_cycle",
            "payroll_cycle_name",
            "employee",
            "employee_code",
            "employee_name",
            "payroll_month",
            "gross_monthly_salary",
            "additional_earnings",
            "fixed_deductions",
            "rule_based_deductions",
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
        )
        read_only_fields = fields


class PayslipGenerateSerializer(serializers.Serializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.select_related("user"))
    payroll_month = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True)


class DeductionRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeductionRule
        fields = ("id", "name", "code", "description", "calculation_type", "value", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


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
