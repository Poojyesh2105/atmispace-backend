from django.http import HttpResponse
from rest_framework import decorators, exceptions, mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsAdminOrHR
from apps.core.responses import success_response
from apps.payroll.models import EmployeeSalaryComponentTemplate, Payslip, PayslipTemplate, SalaryComponent, SalaryComponentTemplate
from apps.payroll.selectors.payroll_selectors import PayrollGovernanceSelectors
from apps.payroll.serializers import (
    PayrollAdjustmentSerializer,
    PayrollCycleSerializer,
    PayrollRunSerializer,
    PayslipGenerateSerializer,
    PayslipSerializer,
    PayslipTemplateSerializer,
    EmployeeSalaryComponentTemplateSerializer,
    SalaryComponentSerializer,
    SalaryComponentTemplateSerializer,
    SalaryRevisionSerializer,
)
from apps.payroll.services.payroll_component_service import PayslipTemplateService, SalaryComponentService
from apps.payroll.services.payroll_governance_service import PayrollGovernanceService
from apps.payroll.services.payslip_pdf_service import PayslipPdfService
from apps.payroll.services.payroll_service import PayslipService


class PayslipViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            PayslipService.get_queryset_for_user(self.request.user)
            .select_related("employee__user", "employee__department", "generated_by", "payroll_cycle")
            .prefetch_related("component_entries")
        )
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
            salary_component_template=serializer.validated_data.get("salary_component_template"),
        )
        return success_response(
            data=PayslipSerializer(payslip).data,
            message="Payslip generated successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=PayslipSerializer(self.get_object()).data)

    def _render_payslip_html(self, request, payslip):
        # Permission: employee can only render their own; HR/ADMIN/ACCOUNTS can render any
        user = request.user
        if user.role not in PayslipService.VIEW_ROLES:
            employee = getattr(user, "employee_profile", None)
            if not employee or employee.pk != payslip.employee_id:
                raise exceptions.PermissionDenied("You can only render your own payslip.")

        template = None
        template_id = request.query_params.get("template_id")
        if template_id:
            try:
                template = PayslipTemplate.objects.get(pk=template_id)
            except PayslipTemplate.DoesNotExist:
                raise exceptions.NotFound("Template not found.")
        else:
            template = PayslipTemplateService.get_default_template()

        try:
            html = PayslipTemplateService.render_payslip(payslip, template)
        except Exception as exc:
            if template is None:
                raise exceptions.ValidationError({"template": "Unable to render this payslip."}) from exc
            html = PayslipTemplateService.render_payslip(payslip, None)
        return html

    @staticmethod
    def _download_filename(payslip):
        employee_code = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in str(payslip.employee.employee_id)
        )
        month = payslip.payroll_month.strftime("%Y-%m")
        return f"payslip_{employee_code}_{month}.pdf"

    @decorators.action(detail=True, methods=["get"])
    def render(self, request, pk=None):
        payslip = self.get_object()
        html = self._render_payslip_html(request, payslip)
        return success_response(data={"html": html})

    @decorators.action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        payslip = self.get_object()
        html = self._render_payslip_html(request, payslip)
        pdf = PayslipPdfService.render_pdf(payslip, html)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{self._download_filename(payslip)}"'
        response["X-Content-Type-Options"] = "nosniff"
        return response


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


class _IsAdminHROrAccounts(IsAdminOrHR):
    """Extended permission: HR, ADMIN, or ACCOUNTS can manage components/templates."""
    allowed_roles = {"HR", "ADMIN", "ACCOUNTS"}


class _IsAdminOnly(_IsAdminHROrAccounts):
    allowed_roles = {"ADMIN"}


class SalaryComponentViewSet(viewsets.ModelViewSet):
    serializer_class = SalaryComponentSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [_IsAdminOnly()]
        if self.action in ("create", "update", "partial_update"):
            return [_IsAdminHROrAccounts()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = SalaryComponent.objects.select_related("template", "base_component").order_by(
            "template__name",
            "display_order",
            "name",
            "id",
        )
        template_id = self.request.query_params.get("template")
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        return queryset

    def list(self, request, *args, **kwargs):
        SalaryComponentService.ensure_standard_components()
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        component = SalaryComponentService.create_component(serializer.validated_data, actor=request.user)
        return success_response(
            data=self.get_serializer(component).data,
            message="Salary component created.",
            status_code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        component = SalaryComponentService.update_component(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(component).data, message="Salary component updated.")

    def destroy(self, request, *args, **kwargs):
        SalaryComponentService.delete_component(self.get_object(), actor=request.user)
        return success_response(message="Salary component deleted.")


class SalaryComponentTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = SalaryComponentTemplateSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [_IsAdminOnly()]
        if self.action in ("create", "update", "partial_update"):
            return [_IsAdminHROrAccounts()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return SalaryComponentTemplate.objects.all().order_by("-is_default", "name")

    def list(self, request, *args, **kwargs):
        SalaryComponentService.ensure_standard_components()
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return success_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = SalaryComponentService.create_template(serializer.validated_data, actor=request.user)
        return success_response(
            data=self.get_serializer(template).data,
            message="Salary component template created.",
            status_code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        template = SalaryComponentService.update_template(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(template).data, message="Salary component template updated.")

    def destroy(self, request, *args, **kwargs):
        SalaryComponentService.delete_template(self.get_object(), actor=request.user)
        return success_response(message="Salary component template deleted.")


class EmployeeSalaryComponentTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeSalaryComponentTemplateSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [_IsAdminHROrAccounts()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = EmployeeSalaryComponentTemplate.objects.select_related(
            "employee__user",
            "template",
            "assigned_by",
        ).order_by("employee__employee_id")
        user = self.request.user
        if user.role not in {"HR", "ACCOUNTS", "ADMIN"}:
            employee = getattr(user, "employee_profile", None)
            return queryset.filter(employee=employee) if employee else queryset.none()
        employee_id = self.request.query_params.get("employee")
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        return queryset

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return success_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = SalaryComponentService.assign_template_to_employee(
            serializer.validated_data["employee"],
            serializer.validated_data["template"],
            request.user,
            serializer.validated_data.get("notes", ""),
        )
        return success_response(
            data=self.get_serializer(assignment).data,
            message="Salary component template assigned.",
            status_code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        employee = serializer.validated_data.get("employee", self.get_object().employee)
        template = serializer.validated_data.get("template", self.get_object().template)
        notes = serializer.validated_data.get("notes", self.get_object().notes)
        assignment = SalaryComponentService.assign_template_to_employee(employee, template, request.user, notes)
        return success_response(data=self.get_serializer(assignment).data, message="Salary component template assignment updated.")


class PayslipTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = PayslipTemplateSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [_IsAdminOnly()]
        if self.action in ("create", "update", "partial_update"):
            return [_IsAdminHROrAccounts()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return PayslipTemplate.objects.all()

    def list(self, request, *args, **kwargs):
        PayslipTemplateService.ensure_default_template()
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = PayslipTemplateService.create_template(serializer.validated_data, actor=request.user)
        return success_response(
            data=self.get_serializer(template).data,
            message="Payslip template created.",
            status_code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        template = PayslipTemplateService.update_template(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(template).data, message="Payslip template updated.")

    def destroy(self, request, *args, **kwargs):
        PayslipTemplateService.delete_template(self.get_object(), actor=request.user)
        return success_response(message="Payslip template deleted.")
