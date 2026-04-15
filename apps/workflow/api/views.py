from rest_framework import decorators, status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsWorkflowAdmin
from apps.core.responses import success_response
from apps.workflow.models import ApprovalInstance, Workflow, WorkflowAssignment
from apps.workflow.serializers import (
    ApprovalDecisionSerializer,
    ApprovalInstanceSerializer,
    WorkflowAssignmentSerializer,
    WorkflowAttachSerializer,
    WorkflowSerializer,
)
from apps.workflow.services.workflow_service import WorkflowService


class WorkflowViewSet(viewsets.ModelViewSet):
    serializer_class = WorkflowSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WorkflowService.get_workflow_queryset()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "attach"}:
            return [IsAuthenticated(), IsWorkflowAdmin()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workflow = WorkflowService.create_workflow(
            {key: value for key, value in serializer.validated_data.items() if key != "steps"},
            serializer.validated_data.get("steps", []),
        )
        return success_response(data=self.get_serializer(workflow).data, message="Workflow created successfully.", status_code=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        workflow = self.get_object()
        serializer = self.get_serializer(workflow, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        workflow = WorkflowService.update_workflow(
            workflow,
            {key: value for key, value in serializer.validated_data.items() if key != "steps"},
            serializer.validated_data.get("steps"),
        )
        return success_response(data=self.get_serializer(workflow).data, message="Workflow updated successfully.")

    @decorators.action(detail=True, methods=["post"])
    def attach(self, request, pk=None):
        serializer = WorkflowAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workflow = WorkflowService.attach_workflow(
            self.get_object(),
            serializer.validated_data["module"],
            serializer.validated_data.get("priority"),
        )
        return success_response(data=self.get_serializer(workflow).data, message="Workflow attached successfully.")


class WorkflowAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WorkflowAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = WorkflowService.get_assignment_queryset_for_user(self.request.user)
        module = self.request.query_params.get("module")
        object_id = self.request.query_params.get("object_id")
        if module:
            queryset = queryset.filter(module=module)
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        assignment = self.get_object()
        return success_response(data=self.get_serializer(assignment, context={"request": request}).data)


class ApprovalInstanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ApprovalInstanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = WorkflowService.get_approval_queryset_for_user(self.request.user)
        status_filter = self.request.query_params.get("status")
        module = self.request.query_params.get("module")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        elif self.action == "list":
            queryset = queryset.filter(status=ApprovalInstance.Status.PENDING)
        if module:
            queryset = queryset.filter(workflow_assignment__module=module)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        return success_response(data=self.get_serializer(queryset, many=True, context={"request": request}).data)

    def retrieve(self, request, *args, **kwargs):
        approval = self.get_object()
        return success_response(data=self.get_serializer(approval, context={"request": request}).data)

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approval = WorkflowService.approve(request.user, self.get_object(), serializer.validated_data.get("comments", ""))
        return success_response(data=self.get_serializer(approval, context={"request": request}).data, message="Approval recorded.")

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approval = WorkflowService.reject(request.user, self.get_object(), serializer.validated_data.get("comments", ""))
        return success_response(data=self.get_serializer(approval, context={"request": request}).data, message="Rejection recorded.")

    @decorators.action(detail=True, methods=["post"])
    def comment(self, request, pk=None):
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approval = WorkflowService.comment(request.user, self.get_object(), serializer.validated_data.get("comments", ""))
        return success_response(data=self.get_serializer(approval, context={"request": request}).data, message="Comment recorded.")
