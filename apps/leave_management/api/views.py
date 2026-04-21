from rest_framework import decorators, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminOrHR, IsManagerOrAbove
from apps.core.responses import success_response
from apps.leave_management.serializers import (
    EarnedLeaveAdjustmentApplySerializer,
    EarnedLeaveAdjustmentSerializer,
    LeaveApplySerializer,
    LeaveBalanceSerializer,
    LeaveCarryForwardLogSerializer,
    LeavePolicySerializer,
    LeaveDecisionSerializer,
    LeaveRequestSerializer,
    ProcessCarryForwardSerializer,
)
from apps.leave_management.services.carry_forward_service import LeaveCarryForwardService
from apps.leave_management.services.leave_service import (
    EarnedLeaveAdjustmentService,
    LeaveBalanceService,
    LeavePolicyService,
    LeaveRequestService,
)
from apps.workflow.models import Workflow
from apps.workflow.serializers import WorkflowAssignmentSerializer
from apps.workflow.services.workflow_service import WorkflowService


class LeaveBalanceViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return LeaveBalanceService.get_queryset_for_user(self.request.user)

    def get_permissions(self):
        if self.action in {"update", "partial_update"}:
            return [IsAuthenticated(), IsManagerOrAbove()]
        if self.action in {"create", "destroy"}:
            return [IsAuthenticated(), IsAdminOrHR()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        balance = LeaveBalanceService.create_balance(serializer.validated_data)
        return success_response(
            data=self.get_serializer(balance).data,
            message="Leave balance created successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        balance = self.get_object()
        return success_response(data=self.get_serializer(balance).data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        balance = LeaveBalanceService.update_balance(instance, serializer.validated_data)
        return success_response(data=self.get_serializer(balance).data, message="Leave balance updated successfully.")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return success_response(message="Leave balance deleted successfully.")


class LeaveRequestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = LeaveRequestService.get_queryset_for_user(self.request.user)
        status_filter = self.request.query_params.get("status")
        employee_id = self.request.query_params.get("employee")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if employee_id and self.request.user.role in {"HR", "ACCOUNTS", "ADMIN", "MANAGER"}:
            queryset = queryset.filter(employee_id=employee_id)
        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(end_date__lte=date_to)
        return queryset

    def _get_serializer_context_with_workflow(self, leave_requests=None, leave_request=None):
        context = self.get_serializer_context()
        if leave_request is not None:
            context["workflow_assignment"] = WorkflowService.get_assignment_for_object(Workflow.Module.LEAVE_REQUEST, leave_request)
        elif leave_requests is not None:
            context["workflow_assignment_map"] = WorkflowService.get_assignment_map_for_objects(
                Workflow.Module.LEAVE_REQUEST,
                leave_requests,
            )
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(
                page,
                many=True,
                context=self._get_serializer_context_with_workflow(leave_requests=page),
            )
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(
            queryset,
            many=True,
            context=self._get_serializer_context_with_workflow(leave_requests=queryset),
        )
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return success_response(
            data=self.get_serializer(
                instance,
                context=self._get_serializer_context_with_workflow(leave_request=instance),
            ).data
        )

    @decorators.action(detail=False, methods=["post"], url_path="apply")
    def apply(self, request):
        serializer = LeaveApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave_request = LeaveRequestService.apply_leave(request.user, serializer.validated_data)
        return success_response(
            data=self.get_serializer(
                leave_request,
                context=self._get_serializer_context_with_workflow(leave_request=leave_request),
            ).data,
            message="Leave request submitted successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    @decorators.action(detail=True, methods=["get"], url_path="workflow")
    def workflow(self, request, pk=None):
        leave_request = self.get_object()
        assignment = WorkflowService.get_assignment_for_object(Workflow.Module.LEAVE_REQUEST, leave_request)
        if not assignment:
            return success_response(data={})
        return success_response(data=WorkflowAssignmentSerializer(assignment, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"], url_path="approve", permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        serializer = LeaveDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave_request = self.get_object()
        leave_request = LeaveRequestService.approve_leave(
            request.user,
            leave_request,
            approver_note=serializer.validated_data.get("approver_note", ""),
        )
        return success_response(
            data=self.get_serializer(
                leave_request,
                context=self._get_serializer_context_with_workflow(leave_request=leave_request),
            ).data,
            message="Leave request approved.",
        )

    @decorators.action(detail=True, methods=["post"], url_path="reject", permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        serializer = LeaveDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave_request = self.get_object()
        leave_request = LeaveRequestService.reject_leave(
            request.user,
            leave_request,
            approver_note=serializer.validated_data.get("approver_note", ""),
        )
        return success_response(
            data=self.get_serializer(
                leave_request,
                context=self._get_serializer_context_with_workflow(leave_request=leave_request),
            ).data,
            message="Leave request rejected.",
        )


class LeavePolicyView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in {"PUT", "PATCH"}:
            return [IsAuthenticated(), IsManagerOrAbove()]
        return super().get_permissions()

    def get(self, request):
        return success_response(data=LeavePolicySerializer(LeavePolicyService.get_policy()).data)

    def put(self, request):
        serializer = LeavePolicySerializer(LeavePolicyService.get_policy(), data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = LeavePolicyService.update_policy(serializer.validated_data)
        return success_response(data=LeavePolicySerializer(policy).data, message="Leave policy updated successfully.")

    def patch(self, request):
        serializer = LeavePolicySerializer(LeavePolicyService.get_policy(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        policy = LeavePolicyService.update_policy(serializer.validated_data)
        return success_response(data=LeavePolicySerializer(policy).data, message="Leave policy updated successfully.")


class EarnedLeaveAdjustmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EarnedLeaveAdjustmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = EarnedLeaveAdjustmentService.get_queryset_for_user(self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    @decorators.action(detail=False, methods=["post"], url_path="apply")
    def apply(self, request):
        serializer = EarnedLeaveAdjustmentApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        adjustment = EarnedLeaveAdjustmentService.apply_adjustment(request.user, serializer.validated_data)
        return success_response(
            data=self.get_serializer(adjustment).data,
            message="Earned leave adjustment submitted successfully.",
            status_code=status.HTTP_201_CREATED,
        )

    @decorators.action(detail=True, methods=["post"], url_path="approve", permission_classes=[IsAuthenticated, IsManagerOrAbove])
    def approve(self, request, pk=None):
        serializer = LeaveDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        adjustment = EarnedLeaveAdjustmentService.approve_adjustment(
            request.user,
            self.get_object(),
            approver_note=serializer.validated_data.get("approver_note", ""),
        )
        return success_response(data=self.get_serializer(adjustment).data, message="Earned leave adjustment approved.")

    @decorators.action(detail=True, methods=["post"], url_path="reject", permission_classes=[IsAuthenticated, IsManagerOrAbove])
    def reject(self, request, pk=None):
        serializer = LeaveDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        adjustment = EarnedLeaveAdjustmentService.reject_adjustment(
            request.user,
            self.get_object(),
            approver_note=serializer.validated_data.get("approver_note", ""),
        )
        return success_response(data=self.get_serializer(adjustment).data, message="Earned leave adjustment rejected.")


class ProcessCarryForwardView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrHR]

    def post(self, request):
        from datetime import date

        serializer = ProcessCarryForwardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_month = serializer.validated_data.get("month") or date.today().replace(day=1)
        count = LeaveCarryForwardService.process_carry_forward(target_month)
        return success_response(
            data={"employees_processed": count, "target_month": target_month.strftime("%Y-%m")},
            message=f"Leave carry forward processed for {count} employee(s).",
        )
