from rest_framework import decorators, status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.responses import success_response
from apps.lifecycle.permissions import IsLifecycleAdmin
from apps.lifecycle.selectors.lifecycle_selectors import LifecycleSelectors
from apps.lifecycle.serializers import (
    EmployeeChangeRequestSerializer,
    EmployeeOnboardingSerializer,
    EmployeeOnboardingTaskSerializer,
    OffboardingCaseSerializer,
    OffboardingTaskSerializer,
    OnboardingPlanSerializer,
    OnboardingTaskTemplateSerializer,
    TaskCompletionSerializer,
)
from apps.lifecycle.services.lifecycle_service import (
    EmployeeChangeRequestService,
    EmployeeOnboardingService,
    OffboardingService,
    OnboardingPlanService,
    OnboardingTaskTemplateService,
)


class OnboardingPlanViewSet(viewsets.ModelViewSet):
    serializer_class = OnboardingPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LifecycleSelectors.get_onboarding_plan_queryset(self.request.user)

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsLifecycleAdmin()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = OnboardingPlanService.create_plan(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(plan).data, message="Onboarding plan created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        plan = OnboardingPlanService.update_plan(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(plan).data, message="Onboarding plan updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class OnboardingTaskTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = OnboardingTaskTemplateSerializer
    permission_classes = [IsAuthenticated, IsLifecycleAdmin]

    def get_queryset(self):
        queryset = LifecycleSelectors.get_onboarding_task_template_queryset(self.request.user)
        plan_id = self.request.query_params.get("plan")
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = OnboardingTaskTemplateService.create_template(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(template).data, message="Onboarding task template created.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        template = OnboardingTaskTemplateService.update_template(self.get_object(), serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(template).data, message="Onboarding task template updated.")

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class EmployeeOnboardingViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeOnboardingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LifecycleSelectors.get_employee_onboarding_queryset_for_user(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        onboarding = EmployeeOnboardingService.create_onboarding(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(onboarding).data, message="Employee onboarding created.", status_code=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class EmployeeOnboardingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EmployeeOnboardingTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LifecycleSelectors.get_employee_onboarding_task_queryset_for_user(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        serializer = TaskCompletionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = EmployeeOnboardingService.complete_task(request.user, self.get_object(), serializer.validated_data.get("notes", ""))
        return success_response(data=self.get_serializer(task).data, message="Onboarding task completed.")


class OffboardingCaseViewSet(viewsets.ModelViewSet):
    serializer_class = OffboardingCaseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LifecycleSelectors.get_offboarding_queryset_for_user(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        offboarding_case = OffboardingService.create_case(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(offboarding_case).data, message="Offboarding case created.", status_code=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)


class OffboardingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OffboardingTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LifecycleSelectors.get_offboarding_task_queryset_for_user(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        serializer = TaskCompletionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = OffboardingService.complete_task(request.user, self.get_object(), serializer.validated_data.get("notes", ""))
        return success_response(data=self.get_serializer(task).data, message="Offboarding task completed.")


class EmployeeChangeRequestViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeChangeRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LifecycleSelectors.get_change_request_queryset_for_user(self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_request = EmployeeChangeRequestService.create_change_request(serializer.validated_data, actor=request.user)
        return success_response(data=self.get_serializer(change_request).data, message="Employee change request created.", status_code=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)
