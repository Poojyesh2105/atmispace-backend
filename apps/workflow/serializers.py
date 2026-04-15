from apps.accounts.models import User
from rest_framework import serializers

from apps.workflow.models import ApprovalAction, ApprovalInstance, Workflow, WorkflowAssignment, WorkflowStep
from apps.workflow.services.workflow_service import WorkflowService


class ConditionValidationMixin:
    def validate_condition(self, attrs):
        operator = attrs.get("condition_operator", Workflow.ConditionOperator.ALWAYS)
        field_name = attrs.get("condition_field", "")
        value = attrs.get("condition_value", None)

        if operator == Workflow.ConditionOperator.ALWAYS:
            return attrs
        if not field_name:
            raise serializers.ValidationError({"condition_field": "Condition field is required when a conditional operator is used."})
        if value in (None, ""):
            raise serializers.ValidationError({"condition_value": "Condition value is required when a conditional operator is used."})
        return attrs


class WorkflowStepSerializer(ConditionValidationMixin, serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=User.Role.choices, required=False, allow_blank=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False, allow_null=True)

    class Meta:
        model = WorkflowStep
        fields = (
            "id",
            "name",
            "sequence",
            "assignment_type",
            "role",
            "user",
            "is_active",
            "condition_field",
            "condition_operator",
            "condition_value",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        attrs = self.validate_condition(attrs)
        assignment_type = attrs.get("assignment_type", getattr(self.instance, "assignment_type", None))
        role = attrs.get("role", getattr(self.instance, "role", ""))
        user = attrs.get("user", getattr(self.instance, "user", None))

        if assignment_type == WorkflowStep.AssignmentType.ROLE:
            if not role:
                raise serializers.ValidationError({"role": "Role is required when assignment type is ROLE."})
            attrs["user"] = None
        elif assignment_type == WorkflowStep.AssignmentType.USER:
            if not user:
                raise serializers.ValidationError({"user": "User is required when assignment type is USER."})
            attrs["role"] = ""
        else:
            attrs["role"] = ""
            attrs["user"] = None

        return attrs


class WorkflowSerializer(ConditionValidationMixin, serializers.ModelSerializer):
    steps = WorkflowStepSerializer(many=True)

    class Meta:
        model = Workflow
        fields = (
            "id",
            "name",
            "module",
            "description",
            "is_active",
            "priority",
            "condition_field",
            "condition_operator",
            "condition_value",
            "steps",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_steps(self, steps):
        if not steps:
            raise serializers.ValidationError("At least one workflow step is required.")

        sequences = [step["sequence"] for step in steps]
        if len(sequences) != len(set(sequences)):
            raise serializers.ValidationError("Workflow step sequence numbers must be unique.")

        expected = list(range(1, len(sequences) + 1))
        if sorted(sequences) != expected:
            raise serializers.ValidationError("Workflow step sequences must be contiguous and start at 1.")

        return steps

    def validate(self, attrs):
        return self.validate_condition(attrs)


class WorkflowAttachSerializer(serializers.Serializer):
    module = serializers.ChoiceField(choices=Workflow.Module.choices)
    priority = serializers.IntegerField(required=False, min_value=1)


class ApprovalActionSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True)

    class Meta:
        model = ApprovalAction
        fields = ("id", "actor", "actor_name", "action", "comments", "metadata", "created_at")
        read_only_fields = fields


class ApprovalInstanceSerializer(serializers.ModelSerializer):
    step_name = serializers.CharField(source="step.name", read_only=True)
    assigned_user_name = serializers.CharField(source="assigned_user.full_name", read_only=True)
    module = serializers.CharField(source="workflow_assignment.module", read_only=True)
    workflow_name = serializers.CharField(source="workflow_assignment.workflow.name", read_only=True)
    requested_by_name = serializers.CharField(source="workflow_assignment.requested_by.full_name", read_only=True)
    object_id = serializers.IntegerField(source="workflow_assignment.object_id", read_only=True)
    can_act = serializers.SerializerMethodField()
    actions = ApprovalActionSerializer(many=True, read_only=True)

    class Meta:
        model = ApprovalInstance
        fields = (
            "id",
            "workflow_assignment",
            "workflow_name",
            "module",
            "object_id",
            "step_name",
            "sequence",
            "assigned_user",
            "assigned_user_name",
            "assigned_role",
            "requested_by_name",
            "status",
            "acted_at",
            "comments",
            "can_act",
            "actions",
            "created_at",
        )
        read_only_fields = fields

    def get_can_act(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return WorkflowService.can_user_act_on_approval(request.user, obj)


class WorkflowAssignmentSerializer(serializers.ModelSerializer):
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.full_name", read_only=True)
    content_type_label = serializers.CharField(source="content_type.model", read_only=True)
    approval_instances = ApprovalInstanceSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowAssignment
        fields = (
            "id",
            "workflow",
            "workflow_name",
            "module",
            "requested_by",
            "requested_by_name",
            "content_type_label",
            "object_id",
            "status",
            "current_step_sequence",
            "context",
            "completed_at",
            "approval_instances",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ApprovalDecisionSerializer(serializers.Serializer):
    comments = serializers.CharField(required=False, allow_blank=True)
