from decimal import Decimal

from rest_framework import serializers

from apps.leave_management.models import EarnedLeaveAdjustment, LeaveBalance, LeavePolicy, LeaveRequest
from apps.workflow.models import Workflow
from apps.workflow.services.workflow_service import WorkflowService


class LeaveBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    available_days = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)

    class Meta:
        model = LeaveBalance
        fields = (
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "leave_type",
            "allocated_days",
            "used_days",
            "available_days",
        )
        read_only_fields = ("id", "employee_code", "employee_name", "available_days")


class LeavePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeavePolicy
        fields = (
            "id",
            "casual_days_onboarding",
            "sick_days_onboarding",
            "earned_days_onboarding",
            "monthly_sick_leave_limit",
            "monthly_earned_leave_limit",
            "compensate_with_earned_leave",
            "excess_leave_becomes_lop",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    approver_name = serializers.CharField(source="approver.full_name", read_only=True)
    workflow = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = (
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "leave_type",
            "duration_type",
            "start_date",
            "end_date",
            "reason",
            "status",
            "total_days",
            "lop_days_applied",
            "approver",
            "approver_name",
            "approver_note",
            "reviewed_at",
            "workflow",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "status",
            "total_days",
            "lop_days_applied",
            "approver",
            "approver_name",
            "reviewed_at",
            "created_at",
            "updated_at",
        )

    def _get_workflow_assignment(self, obj):
        assignment = self.context.get("workflow_assignment")
        if assignment and assignment.object_id == obj.pk:
            return assignment

        assignment_map = self.context.get("workflow_assignment_map")
        if assignment_map is not None:
            return assignment_map.get(obj.pk)

        return WorkflowService.get_assignment_for_object(Workflow.Module.LEAVE_REQUEST, obj)

    def get_workflow(self, obj):
        assignment = self._get_workflow_assignment(obj)
        if not assignment:
            return None

        pending_approval = WorkflowService.get_pending_approval_for_assignment(assignment)
        current_step_name = None
        if assignment.current_step_sequence is not None:
            for approval in assignment.approval_instances.all():
                if approval.sequence == assignment.current_step_sequence:
                    current_step_name = approval.step.name
                    break

        request = self.context.get("request")
        return {
            "assignment_id": assignment.id,
            "workflow_name": assignment.workflow.name,
            "status": assignment.status,
            "current_step_sequence": assignment.current_step_sequence,
            "current_step_name": current_step_name,
            "pending_approval_id": getattr(pending_approval, "id", None),
            "pending_step_name": getattr(getattr(pending_approval, "step", None), "name", None),
            "pending_with": getattr(pending_approval, "assigned_user_id", None),
            "pending_with_name": getattr(getattr(pending_approval, "assigned_user", None), "full_name", None),
            "pending_assigned_role": getattr(pending_approval, "assigned_role", ""),
            "can_act": WorkflowService.can_user_act_on_approval(getattr(request, "user", None), pending_approval),
        }


class LeaveApplySerializer(serializers.Serializer):
    leave_type = serializers.ChoiceField(choices=LeaveBalance.LeaveType.choices)
    duration_type = serializers.ChoiceField(
        choices=LeaveRequest.DurationType.choices,
        default=LeaveRequest.DurationType.FULL_DAY,
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField()

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "End date must be on or after start date."})
        if attrs["duration_type"] == LeaveRequest.DurationType.HALF_DAY and attrs["start_date"] != attrs["end_date"]:
            raise serializers.ValidationError({"duration_type": "Half-day leave can only be applied for a single date."})
        return attrs

    def get_total_days(self):
        validated = getattr(self, "validated_data", {})
        if not validated:
            return Decimal("0.0")
        if validated["duration_type"] == LeaveRequest.DurationType.HALF_DAY:
            return Decimal("0.5")
        total_days = (validated["end_date"] - validated["start_date"]).days + 1
        return Decimal(str(total_days))


class LeaveDecisionSerializer(serializers.Serializer):
    approver_note = serializers.CharField(required=False, allow_blank=True)


class EarnedLeaveAdjustmentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.full_name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_id", read_only=True)
    approver_name = serializers.CharField(source="approver.full_name", read_only=True)

    class Meta:
        model = EarnedLeaveAdjustment
        fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "work_date",
            "days",
            "reason",
            "status",
            "approver",
            "approver_name",
            "approver_note",
            "reviewed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "employee",
            "employee_name",
            "employee_code",
            "status",
            "approver",
            "approver_name",
            "reviewed_at",
            "created_at",
            "updated_at",
        )


class EarnedLeaveAdjustmentApplySerializer(serializers.Serializer):
    work_date = serializers.DateField()
    days = serializers.DecimalField(max_digits=5, decimal_places=1, min_value=Decimal("0.5"))
    reason = serializers.CharField(required=False, allow_blank=True)
