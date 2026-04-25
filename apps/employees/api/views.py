from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.permissions import IsAdminOrHR, IsManagerOrAbove
from apps.core.responses import success_response
from apps.employees.serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    OrganizationSettingsSerializer,
    ShiftTemplateSerializer,
)
from apps.employees.services.employee_service import (
    DepartmentService,
    EmployeeService,
    OrganizationSettingsService,
    ShiftTemplateService,
)


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DepartmentService.get_queryset(self.request.user)

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsAdminOrHR()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        department = DepartmentService.create_department(serializer.validated_data, actor=request.user)
        return success_response(
            data=self.get_serializer(department).data,
            message="Department created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        department = self.get_object()
        return success_response(data=self.get_serializer(department).data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        department = DepartmentService.update_department(instance, serializer.validated_data)
        return success_response(data=self.get_serializer(department).data, message="Department updated successfully.")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return success_response(message="Department deleted successfully.")


class OrganizationSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in {"PUT", "PATCH"}:
            return [IsAuthenticated(), IsManagerOrAbove()]
        return super().get_permissions()

    def get(self, request):
        settings = OrganizationSettingsService.get_settings(actor=request.user)
        return success_response(data=OrganizationSettingsSerializer(settings).data)

    def put(self, request):
        serializer = OrganizationSettingsSerializer(OrganizationSettingsService.get_settings(actor=request.user), data=request.data)
        serializer.is_valid(raise_exception=True)
        settings = OrganizationSettingsService.update_settings(serializer.validated_data, actor=request.user)
        return success_response(data=OrganizationSettingsSerializer(settings).data, message="Organization settings updated successfully.")

    def patch(self, request):
        serializer = OrganizationSettingsSerializer(OrganizationSettingsService.get_settings(actor=request.user), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        settings = OrganizationSettingsService.update_settings(serializer.validated_data, actor=request.user)
        return success_response(data=OrganizationSettingsSerializer(settings).data, message="Organization settings updated successfully.")


class ShiftTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = ShiftTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ShiftTemplateService.get_queryset(self.request.user)

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsManagerOrAbove()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = ShiftTemplateService.create_shift(serializer.validated_data, actor=request.user)
        return success_response(
            data=self.get_serializer(shift).data,
            message="Shift template created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def update(self, request, *args, **kwargs):
        shift = self.get_object()
        serializer = self.get_serializer(shift, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        shift = ShiftTemplateService.update_shift(shift, serializer.validated_data)
        return success_response(data=self.get_serializer(shift).data, message="Shift template updated successfully.")

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return success_response(message="Shift template deleted successfully.")


class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return EmployeeService.get_employee_queryset_for_user(self.request.user)

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsAdminOrHR()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = EmployeeService.create_employee(serializer.validated_data, actor=request.user)
        return success_response(
            data=self.get_serializer(employee).data,
            message="Employee created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        employee = self.get_object()
        return success_response(data=self.get_serializer(employee).data)

    def update(self, request, *args, **kwargs):
        employee = self.get_object()
        serializer = self.get_serializer(employee, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        updated_employee = EmployeeService.update_employee(employee, serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(updated_employee).data, message="Employee updated successfully.")

    def destroy(self, request, *args, **kwargs):
        employee = self.get_object()
        EmployeeService.delete_employee(employee, actor=request.user)
        return success_response(message="Employee deleted successfully.")
