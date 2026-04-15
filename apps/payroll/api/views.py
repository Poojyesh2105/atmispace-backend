from rest_framework import decorators, exceptions, mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.responses import success_response
from apps.payroll.selectors.payroll_selectors import PayrollGovernanceSelectors
from apps.payroll.serializers import (
    DeductionRuleSerializer,
    PayrollAdjustmentSerializer,
    PayrollCycleSerializer,
    PayrollRunSerializer,
    PayslipGenerateSerializer,
    PayslipSerializer,
    SalaryRevisionSerializer,
)
from apps.payroll.services.payroll_governance_service import PayrollGovernanceService
from apps.payroll.services.payroll_service import PayslipService


class PayslipViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PayslipService.get_queryset_for_user(self.request.user)
        employee_id = self.request.query_params.get("employee")
        payroll_month = self.request.query_params.get("payroll_month")
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        if payroll_month:
            try:
                parsed_month = PayslipGenerateSerializer().fields["payroll_month"].to_internal_value(payroll_month)
                queryset = queryset.filter(payroll_month=PayslipService.normalize_payroll_month(parsed_month))
            except Exception as exc:
                raise exceptions.ValidationError({"payroll_month": "Use a valid payroll month date."}) from exc
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return PayslipGenerateSerializer
        return PayslipSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payslip = PayslipService.generate_payslip(
            request.user,
            serializer.validated_data["employee"],
            serializer.validated_data["payroll_month"],
            serializer.validated_data.get("notes", ""),
        )
        return success_response(
            data=PayslipSerializer(payslip).data,
            message="Payslip generated successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=PayslipSerializer(self.get_object()).data)


class DeductionRuleViewSet(viewsets.ModelViewSet):
    serializer_class = DeductionRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PayrollGovernanceSelectors.get_deduction_rule_queryset()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = PayrollGovernanceService.create_deduction_rule(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(rule).data, message="Deduction rule created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        rule = PayrollGovernanceService.update_deduction_rule(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(rule).data, message="Deduction rule updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class PayrollCycleViewSet(viewsets.ModelViewSet):
    serializer_class = PayrollCycleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PayrollGovernanceSelectors.get_cycle_queryset_for_user(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cycle = PayrollGovernanceService.create_cycle(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(cycle).data, message="Payroll cycle created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        cycle = PayrollGovernanceService.update_cycle(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(cycle).data, message="Payroll cycle updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=True, methods=["post"])
    def generate_run(self, request, pk=None):
        run = PayrollGovernanceService.generate_run(request.user, self.get_object())
        return success_response(data=PayrollRunSerializer(run).data, message="Payroll run generated.")


class PayrollRunViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PayrollRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PayrollGovernanceSelectors.get_run_queryset_for_user(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        run = PayrollGovernanceService.lock_run(request.user, self.get_object())
        return success_response(data=self.get_serializer(run).data, message="Payroll run locked.")

    @decorators.action(detail=True, methods=["post"])
    def request_release(self, request, pk=None):
        run = PayrollGovernanceService.request_release(request.user, self.get_object(), request.data.get("notes", ""))
        return success_response(data=self.get_serializer(run).data, message="Payroll release requested.")


class PayrollAdjustmentViewSet(viewsets.ModelViewSet):
    serializer_class = PayrollAdjustmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PayrollGovernanceSelectors.get_adjustment_queryset_for_user(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        adjustment = PayrollGovernanceService.create_adjustment(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(adjustment).data, message="Payroll adjustment created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        adjustment = PayrollGovernanceService.update_adjustment(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(adjustment).data, message="Payroll adjustment updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class SalaryRevisionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SalaryRevisionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PayrollGovernanceSelectors.get_revision_queryset_for_user(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)
