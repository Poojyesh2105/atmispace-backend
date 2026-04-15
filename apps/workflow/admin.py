from django.contrib import admin

from apps.workflow.models import ApprovalAction, ApprovalInstance, Workflow, WorkflowAssignment, WorkflowStep


class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStep
    extra = 0
    ordering = ("sequence", "id")


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ("name", "module", "priority", "is_active", "updated_at")
    list_filter = ("module", "is_active")
    search_fields = ("name", "description", "module")
    inlines = [WorkflowStepInline]


class ApprovalInstanceInline(admin.TabularInline):
    model = ApprovalInstance
    extra = 0
    readonly_fields = ("step", "sequence", "assigned_user", "assigned_role", "status", "acted_at", "created_at")
    can_delete = False


@admin.register(WorkflowAssignment)
class WorkflowAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "module", "workflow", "requested_by", "status", "current_step_sequence", "completed_at")
    list_filter = ("module", "status", "workflow")
    search_fields = ("workflow__name", "requested_by__email", "object_id")
    readonly_fields = ("content_type", "object_id", "completed_at", "created_at", "updated_at")
    inlines = [ApprovalInstanceInline]


class ApprovalActionInline(admin.TabularInline):
    model = ApprovalAction
    extra = 0
    readonly_fields = ("actor", "action", "comments", "metadata", "created_at")
    can_delete = False


@admin.register(ApprovalInstance)
class ApprovalInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "workflow_assignment", "sequence", "step", "assigned_user", "status", "acted_at")
    list_filter = ("status", "step__assignment_type")
    search_fields = ("workflow_assignment__workflow__name", "assigned_user__email", "step__name")
    readonly_fields = ("workflow_assignment", "step", "sequence", "assigned_user", "assigned_role", "acted_at", "created_at", "updated_at")
    inlines = [ApprovalActionInline]


@admin.register(ApprovalAction)
class ApprovalActionAdmin(admin.ModelAdmin):
    list_display = ("id", "approval_instance", "actor", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("approval_instance__workflow_assignment__workflow__name", "actor__email", "comments")
    readonly_fields = ("approval_instance", "actor", "action", "comments", "metadata", "created_at", "updated_at")
