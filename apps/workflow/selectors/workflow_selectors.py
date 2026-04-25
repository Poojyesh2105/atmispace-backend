from django.db.models import Q

from apps.workflow.models import ApprovalInstance, Workflow, WorkflowAssignment


class WorkflowSelectors:
    @staticmethod
    def get_workflow_queryset(user=None):
        return Workflow.objects.for_current_org(user).prefetch_related("steps")

    @staticmethod
    def get_assignment_queryset_for_user(user):
        queryset = WorkflowAssignment.objects.for_current_org(user).select_related(
            "workflow",
            "requested_by",
            "content_type",
        ).prefetch_related(
            "approval_instances__step",
            "approval_instances__assigned_user",
            "approval_instances__actions__actor",
        )

        if user.role in {"HR", "ADMIN"}:
            return queryset
        return queryset.filter(Q(requested_by=user) | Q(approval_instances__assigned_user=user)).distinct()

    @staticmethod
    def get_approval_queryset_for_user(user):
        queryset = ApprovalInstance.objects.for_current_org(user).select_related(
            "workflow_assignment__workflow",
            "workflow_assignment__requested_by",
            "step",
            "assigned_user",
        ).prefetch_related("actions__actor")

        if user.role in {"HR", "ADMIN"}:
            return queryset
        return queryset.filter(Q(assigned_user=user) | Q(workflow_assignment__requested_by=user)).distinct()
