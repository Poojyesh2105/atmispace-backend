from __future__ import annotations

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User
from apps.audit.services.audit_service import AuditService
from apps.core.models import resolve_current_organization
from apps.notifications.services.notification_service import NotificationService
from apps.workflow.models import ApprovalAction, ApprovalInstance, Workflow, WorkflowAssignment, WorkflowStep
from apps.workflow.selectors import WorkflowSelectors


class WorkflowService:
    @staticmethod
    def is_admin_override(user):
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and user.role in {User.Role.ADMIN, User.Role.SUPER_ADMIN}
        )

    @staticmethod
    def can_manage_pending_approval(user, approval_instance):
        if not user or not getattr(user, "is_authenticated", False) or not approval_instance:
            return False
        if approval_instance.status != ApprovalInstance.Status.PENDING:
            return False
        return approval_instance.assigned_user_id == user.pk or WorkflowService.is_admin_override(user)

    @staticmethod
    def get_workflow_queryset(user=None):
        return WorkflowSelectors.get_workflow_queryset(user)

    @staticmethod
    def get_assignment_queryset_for_user(user):
        return WorkflowSelectors.get_assignment_queryset_for_user(user)

    @staticmethod
    def get_approval_queryset_for_user(user):
        return WorkflowSelectors.get_approval_queryset_for_user(user)

    @staticmethod
    def create_workflow(validated_data, steps_data, actor=None):
        organization = resolve_current_organization(actor=actor)
        if organization:
            validated_data.setdefault("organization", organization)
        workflow = Workflow.objects.create(**validated_data)
        for step_data in sorted(steps_data, key=lambda item: item["sequence"]):
            if organization:
                step_data = {"organization": organization, **step_data}
            WorkflowStep.objects.create(workflow=workflow, **step_data)
        return workflow

    @staticmethod
    @transaction.atomic
    def update_workflow(instance, validated_data, steps_data=None):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if steps_data is not None:
            instance.steps.all().delete()
            for step_data in sorted(steps_data, key=lambda item: item["sequence"]):
                if instance.organization_id and "organization" not in step_data:
                    step_data = {"organization": instance.organization, **step_data}
                WorkflowStep.objects.create(workflow=instance, **step_data)
        return instance

    @staticmethod
    def attach_workflow(instance, module, priority=None):
        instance.module = module
        if priority is not None:
            instance.priority = priority
        instance.save(update_fields=["module", "priority", "updated_at"] if priority is not None else ["module", "updated_at"])
        return instance

    @staticmethod
    def get_assignment_for_object(module, obj):
        content_type = ContentType.objects.get_for_model(obj.__class__)
        return (
            WorkflowAssignment.objects.for_current_org(
                organization=getattr(obj, "organization", None),
            )
            .select_related("workflow", "requested_by")
            .prefetch_related("approval_instances__step", "approval_instances__assigned_user", "approval_instances__actions__actor")
            .filter(module=module, content_type=content_type, object_id=obj.pk)
            .order_by("-created_at", "-id")
            .first()
        )

    @staticmethod
    def get_assignment_map_for_objects(module, objects):
        objects = [obj for obj in objects if getattr(obj, "pk", None)]
        if not objects:
            return {}

        content_type = ContentType.objects.get_for_model(objects[0].__class__)
        organization = getattr(objects[0], "organization", None)
        assignments = (
            WorkflowAssignment.objects.for_current_org(organization=organization)
            .select_related("workflow", "requested_by")
            .prefetch_related("approval_instances__step", "approval_instances__assigned_user", "approval_instances__actions__actor")
            .filter(module=module, content_type=content_type, object_id__in=[obj.pk for obj in objects])
            .order_by("object_id", "-created_at", "-id")
        )

        assignment_map = {}
        for assignment in assignments:
            assignment_map.setdefault(assignment.object_id, assignment)
        return assignment_map

    @staticmethod
    def get_pending_approval_for_assignment(assignment):
        if not assignment:
            return None

        for approval in assignment.approval_instances.all():
            if approval.status == ApprovalInstance.Status.PENDING:
                return approval
        return None

    @staticmethod
    def can_user_act_on_approval(user, approval_instance):
        return WorkflowService.can_manage_pending_approval(user, approval_instance)

    @staticmethod
    @transaction.atomic
    def _ensure_default_workflow_shape(workflow, module):
        if (
            module != Workflow.Module.LEAVE_REQUEST
            or workflow.name != "Default Leave Approval"
            or workflow.description != "Auto-generated default workflow for backward compatibility."
        ):
            return workflow

        has_secondary_step = workflow.steps.filter(assignment_type=WorkflowStep.AssignmentType.SECONDARY_MANAGER).exists()
        if has_secondary_step:
            return workflow

        hr_step = workflow.steps.filter(assignment_type=WorkflowStep.AssignmentType.ROLE, role=User.Role.HR).order_by("sequence", "id").first()
        if hr_step:
            hr_step.sequence = 3
            hr_step.save(update_fields=["sequence", "updated_at"])

        WorkflowStep.objects.create(
            workflow=workflow,
            organization=workflow.organization,
            name="Secondary Manager Review",
            sequence=2,
            assignment_type=WorkflowStep.AssignmentType.SECONDARY_MANAGER,
        )
        return workflow

    @staticmethod
    def _get_default_workflow(module, organization=None):
        workflow = (
            Workflow.objects.for_current_org(organization=organization)
            .filter(module=module, is_active=True)
            .order_by("-organization_id", "priority", "id")
            .first()
        )
        if workflow:
            return WorkflowService._ensure_default_workflow_shape(workflow, module)

        default_configs = {
            Workflow.Module.LEAVE_REQUEST: {
                "name": "Default Leave Approval",
                "steps": [
                    {
                        "name": "Primary Manager Review",
                        "sequence": 1,
                        "assignment_type": WorkflowStep.AssignmentType.PRIMARY_MANAGER,
                    },
                    {
                        "name": "HR Review",
                        "sequence": 2,
                        "assignment_type": WorkflowStep.AssignmentType.ROLE,
                        "role": User.Role.HR,
                    },
                ],
            },
            Workflow.Module.ATTENDANCE_REGULARIZATION: {
                "name": "Default Attendance Regularization",
                "steps": [
                    {
                        "name": "Primary Manager Review",
                        "sequence": 1,
                        "assignment_type": WorkflowStep.AssignmentType.PRIMARY_MANAGER,
                    }
                ],
            },
            Workflow.Module.PERFORMANCE_REVIEW: {
                "name": "Default Performance Review Workflow",
                "steps": [
                    {
                        "name": "Primary Manager Review",
                        "sequence": 1,
                        "assignment_type": WorkflowStep.AssignmentType.PRIMARY_MANAGER,
                    },
                    {
                        "name": "HR Final Review",
                        "sequence": 2,
                        "assignment_type": WorkflowStep.AssignmentType.ROLE,
                        "role": User.Role.HR,
                    },
                ],
            },
            Workflow.Module.LIFECYCLE_CASE: {
                "name": "Default Lifecycle Approval",
                "steps": [
                    {
                        "name": "Primary Manager Review",
                        "sequence": 1,
                        "assignment_type": WorkflowStep.AssignmentType.PRIMARY_MANAGER,
                    },
                    {
                        "name": "HR Review",
                        "sequence": 2,
                        "assignment_type": WorkflowStep.AssignmentType.ROLE,
                        "role": User.Role.HR,
                    },
                    {
                        "name": "Admin Approval",
                        "sequence": 3,
                        "assignment_type": WorkflowStep.AssignmentType.ROLE,
                        "role": User.Role.ADMIN,
                    },
                ],
            },
            Workflow.Module.PAYROLL_RELEASE: {
                "name": "Default Payroll Release",
                "steps": [
                    {
                        "name": "Admin Release Approval",
                        "sequence": 1,
                        "assignment_type": WorkflowStep.AssignmentType.ROLE,
                        "role": User.Role.ADMIN,
                    }
                ],
            },
        }

        config = default_configs.get(module)
        if not config:
            raise exceptions.ValidationError({"workflow": f"No active workflow configured for module '{module}'."})

        workflow = Workflow.objects.create(
            organization=organization,
            name=config["name"],
            module=module,
            description="Auto-generated default workflow for backward compatibility.",
            priority=1000,
            is_active=True,
        )
        for step in config["steps"]:
            WorkflowStep.objects.create(workflow=workflow, organization=workflow.organization, **step)
        return WorkflowService._ensure_default_workflow_shape(workflow, module)

    @staticmethod
    def _get_value(obj, field_path):
        value = obj
        for part in field_path.split("."):
            value = getattr(value, part, None)
            if value is None:
                break
        return value

    @staticmethod
    def _matches_condition(obj, field_name, operator, expected):
        if not field_name or operator == Workflow.ConditionOperator.ALWAYS:
            return True

        actual = WorkflowService._get_value(obj, field_name)
        if actual is None:
            return False

        if operator == Workflow.ConditionOperator.EQUALS:
            return str(actual) == str(expected)
        if operator == Workflow.ConditionOperator.NOT_EQUALS:
            return str(actual) != str(expected)
        if operator == Workflow.ConditionOperator.IN:
            values = expected if isinstance(expected, list) else [item.strip() for item in str(expected).split(",")]
            return str(actual) in {str(item) for item in values}

        try:
            actual_value = Decimal(str(actual))
            expected_value = Decimal(str(expected))
        except Exception:
            actual_value = str(actual)
            expected_value = str(expected)

        if operator == Workflow.ConditionOperator.GREATER_THAN_EQUAL:
            return actual_value >= expected_value
        if operator == Workflow.ConditionOperator.LESS_THAN_EQUAL:
            return actual_value <= expected_value
        return False

    @staticmethod
    def _resolve_step_user(step, target_obj):
        requester = getattr(target_obj, "employee", None)

        if step.assignment_type == WorkflowStep.AssignmentType.PRIMARY_MANAGER:
            return getattr(getattr(requester, "manager", None), "user", None), User.Role.MANAGER
        if step.assignment_type == WorkflowStep.AssignmentType.SECONDARY_MANAGER:
            secondary_manager = getattr(requester, "secondary_manager", None)
            return getattr(secondary_manager, "user", None), getattr(getattr(secondary_manager, "user", None), "role", "")
        if step.assignment_type == WorkflowStep.AssignmentType.USER:
            return step.user, getattr(step.user, "role", "")
        if step.assignment_type == WorkflowStep.AssignmentType.ROLE:
            assignee_qs = User.objects.filter(role=step.role, is_active=True)
            workflow_org = getattr(step.workflow, "organization", None)
            if workflow_org:
                assignee_qs = assignee_qs.for_current_org(organization=workflow_org, include_global=False)
            assignee = assignee_qs.order_by("date_joined", "id").first()
            return assignee, step.role
        return None, ""

    @staticmethod
    def _resolve_assignment_organization(target_obj, requested_by):
        return getattr(target_obj, "organization", None) or resolve_current_organization(actor=requested_by)

    @staticmethod
    @transaction.atomic
    def start_workflow(module, target_obj, requested_by, context=None):
        existing_assignment = WorkflowService.get_assignment_for_object(module, target_obj)
        if existing_assignment and existing_assignment.status == WorkflowAssignment.Status.PENDING:
            return existing_assignment

        assignment_organization = WorkflowService._resolve_assignment_organization(target_obj, requested_by)
        workflow = WorkflowService._get_default_workflow(module, organization=assignment_organization)
        matching_workflow = None
        for candidate in Workflow.objects.for_current_org(
            organization=assignment_organization,
            include_global=True,
        ).filter(module=module, is_active=True).order_by("priority", "id"):
            if WorkflowService._matches_condition(
                target_obj, candidate.condition_field, candidate.condition_operator, candidate.condition_value
            ):
                matching_workflow = candidate
                break

        workflow = matching_workflow or workflow
        assignment = WorkflowAssignment.objects.create(
            organization=assignment_organization,
            workflow=workflow,
            module=module,
            requested_by=requested_by,
            content_type=ContentType.objects.get_for_model(target_obj.__class__),
            object_id=target_obj.pk,
            context=context or {},
        )

        for step in workflow.steps.filter(is_active=True).order_by("sequence", "id"):
            if not WorkflowService._matches_condition(
                target_obj, step.condition_field, step.condition_operator, step.condition_value
            ):
                approval = ApprovalInstance.objects.create(
                    organization=assignment_organization,
                    workflow_assignment=assignment,
                    step=step,
                    sequence=step.sequence,
                    status=ApprovalInstance.Status.SKIPPED,
                    comments="Skipped due to workflow condition.",
                )
                ApprovalAction.objects.create(
                    organization=assignment_organization,
                    approval_instance=approval,
                    action=ApprovalAction.Action.SYSTEM,
                    comments="Step skipped due to condition mismatch.",
                )
                continue

            assigned_user, assigned_role = WorkflowService._resolve_step_user(step, target_obj)
            status = ApprovalInstance.Status.QUEUED if assigned_user else ApprovalInstance.Status.SKIPPED
            comments = "" if assigned_user else "Skipped because no assignee could be resolved."
            approval = ApprovalInstance.objects.create(
                organization=assignment_organization,
                workflow_assignment=assignment,
                step=step,
                sequence=step.sequence,
                assigned_user=assigned_user,
                assigned_role=assigned_role or "",
                status=status,
                comments=comments,
            )
            if not assigned_user:
                ApprovalAction.objects.create(
                    organization=assignment_organization,
                    approval_instance=approval,
                    action=ApprovalAction.Action.SYSTEM,
                    comments=comments or "System skipped unresolved workflow step.",
                )

        first_pending = (
            assignment.approval_instances.filter(status=ApprovalInstance.Status.QUEUED)
            .order_by("sequence", "id")
            .first()
        )
        if first_pending:
            first_pending.status = ApprovalInstance.Status.PENDING
            first_pending.save(update_fields=["status", "updated_at"])
            assignment.current_step_sequence = first_pending.sequence
            assignment.save(update_fields=["current_step_sequence", "updated_at"])
            NotificationService.notify_pending_approval(first_pending)
        else:
            assignment.status = WorkflowAssignment.Status.APPROVED
            assignment.completed_at = timezone.now()
            assignment.save(update_fields=["status", "completed_at", "updated_at"])
            WorkflowService._handle_assignment_completed(assignment, actor=requested_by, comment="Auto-approved: no active approvers.")

        AuditService.log(
            actor=requested_by,
            action="workflow.started",
            entity=assignment,
            after={
                "module": assignment.module,
                "workflow": workflow.name,
                "status": assignment.status,
                "target_object_id": assignment.object_id,
            },
        )
        return assignment

    @staticmethod
    def list_pending_approvals_for_user(user):
        return WorkflowService.get_approval_queryset_for_user(user).filter(status=ApprovalInstance.Status.PENDING)

    @staticmethod
    def get_approval_chain(assignment):
        return assignment.approval_instances.select_related("step", "assigned_user").prefetch_related("actions__actor").order_by("sequence", "id")

    @staticmethod
    def comment(user, approval_instance, comments=""):
        if not WorkflowService.can_manage_pending_approval(user, approval_instance):
            raise exceptions.PermissionDenied("This approval step is not assigned to you.")

        ApprovalAction.objects.create(
            organization=approval_instance.organization,
            approval_instance=approval_instance,
            actor=user,
            action=ApprovalAction.Action.COMMENTED,
            comments=comments,
        )
        return approval_instance

    @staticmethod
    @transaction.atomic
    def approve(user, approval_instance, comments=""):
        if approval_instance.status != ApprovalInstance.Status.PENDING:
            raise exceptions.ValidationError({"approval": "Only pending approvals can be approved."})
        if not WorkflowService.can_manage_pending_approval(user, approval_instance):
            raise exceptions.PermissionDenied("This approval step is not assigned to you.")

        approval_instance.status = ApprovalInstance.Status.APPROVED
        approval_instance.acted_at = timezone.now()
        approval_instance.comments = comments
        approval_instance.save(update_fields=["status", "acted_at", "comments", "updated_at"])
        ApprovalAction.objects.create(
            organization=approval_instance.organization,
            approval_instance=approval_instance,
            actor=user,
            action=ApprovalAction.Action.APPROVED,
            comments=comments,
        )

        assignment = approval_instance.workflow_assignment
        next_instance = assignment.approval_instances.filter(
            status=ApprovalInstance.Status.QUEUED,
            sequence__gt=approval_instance.sequence,
        ).order_by("sequence", "id").first()

        if next_instance:
            next_instance.status = ApprovalInstance.Status.PENDING
            next_instance.save(update_fields=["status", "updated_at"])
            assignment.current_step_sequence = next_instance.sequence
            assignment.save(update_fields=["current_step_sequence", "updated_at"])
            NotificationService.notify_pending_approval(next_instance)
        else:
            assignment.status = WorkflowAssignment.Status.APPROVED
            assignment.current_step_sequence = approval_instance.sequence
            assignment.completed_at = timezone.now()
            assignment.save(update_fields=["status", "current_step_sequence", "completed_at", "updated_at"])
            WorkflowService._handle_assignment_completed(assignment, actor=user, comment=comments)
        return approval_instance

    @staticmethod
    @transaction.atomic
    def reject(user, approval_instance, comments=""):
        if approval_instance.status != ApprovalInstance.Status.PENDING:
            raise exceptions.ValidationError({"approval": "Only pending approvals can be rejected."})
        if not WorkflowService.can_manage_pending_approval(user, approval_instance):
            raise exceptions.PermissionDenied("This approval step is not assigned to you.")

        approval_instance.status = ApprovalInstance.Status.REJECTED
        approval_instance.acted_at = timezone.now()
        approval_instance.comments = comments
        approval_instance.save(update_fields=["status", "acted_at", "comments", "updated_at"])
        ApprovalAction.objects.create(
            organization=approval_instance.organization,
            approval_instance=approval_instance,
            actor=user,
            action=ApprovalAction.Action.REJECTED,
            comments=comments,
        )

        assignment = approval_instance.workflow_assignment
        assignment.status = WorkflowAssignment.Status.REJECTED
        assignment.current_step_sequence = approval_instance.sequence
        assignment.completed_at = timezone.now()
        assignment.save(update_fields=["status", "current_step_sequence", "completed_at", "updated_at"])
        WorkflowService._handle_assignment_rejected(assignment, actor=user, comment=comments)
        return approval_instance

    @staticmethod
    def _handle_assignment_completed(assignment, actor=None, comment=""):
        target_obj = assignment.content_object
        if assignment.module == Workflow.Module.LEAVE_REQUEST:
            from apps.leave_management.services.leave_service import LeaveRequestService

            LeaveRequestService.finalize_workflow_approval(target_obj, actor=actor, approver_note=comment)
        elif assignment.module == Workflow.Module.ATTENDANCE_REGULARIZATION:
            from apps.attendance.services.regularization_service import AttendanceRegularizationService

            AttendanceRegularizationService.finalize_workflow_approval(target_obj, actor=actor, approver_note=comment)
        elif assignment.module == Workflow.Module.PERFORMANCE_REVIEW:
            from apps.performance.services.performance_service import PerformanceReviewService

            PerformanceReviewService.finalize_workflow_approval(target_obj, actor=actor, approver_note=comment)
        elif assignment.module == Workflow.Module.LIFECYCLE_CASE:
            from apps.lifecycle.models import EmployeeChangeRequest, OffboardingCase
            from apps.lifecycle.services.lifecycle_service import EmployeeChangeRequestService, OffboardingService

            if isinstance(target_obj, OffboardingCase):
                OffboardingService.finalize_workflow_approval(target_obj, actor=actor, approver_note=comment)
            elif isinstance(target_obj, EmployeeChangeRequest):
                EmployeeChangeRequestService.finalize_workflow_approval(target_obj, actor=actor, approver_note=comment)
        elif assignment.module == Workflow.Module.PAYROLL_RELEASE:
            from apps.payroll.services.payroll_governance_service import PayrollGovernanceService

            PayrollGovernanceService.finalize_release_approval(target_obj, actor=actor, approver_note=comment)

        NotificationService.notify_workflow_completed(assignment, approved=True, actor=actor, comments=comment)
        AuditService.log(
            actor=actor,
            action="workflow.approved",
            entity=assignment,
            after={"status": assignment.status, "module": assignment.module},
        )

    @staticmethod
    def _handle_assignment_rejected(assignment, actor=None, comment=""):
        target_obj = assignment.content_object
        if assignment.module == Workflow.Module.LEAVE_REQUEST:
            from apps.leave_management.services.leave_service import LeaveRequestService

            LeaveRequestService.finalize_workflow_rejection(target_obj, actor=actor, approver_note=comment)
        elif assignment.module == Workflow.Module.ATTENDANCE_REGULARIZATION:
            from apps.attendance.services.regularization_service import AttendanceRegularizationService

            AttendanceRegularizationService.finalize_workflow_rejection(target_obj, actor=actor, approver_note=comment)
        elif assignment.module == Workflow.Module.PERFORMANCE_REVIEW:
            from apps.performance.services.performance_service import PerformanceReviewService

            PerformanceReviewService.finalize_workflow_rejection(target_obj, actor=actor, approver_note=comment)
        elif assignment.module == Workflow.Module.LIFECYCLE_CASE:
            from apps.lifecycle.models import EmployeeChangeRequest, OffboardingCase
            from apps.lifecycle.services.lifecycle_service import EmployeeChangeRequestService, OffboardingService

            if isinstance(target_obj, OffboardingCase):
                OffboardingService.finalize_workflow_rejection(target_obj, actor=actor, approver_note=comment)
            elif isinstance(target_obj, EmployeeChangeRequest):
                EmployeeChangeRequestService.finalize_workflow_rejection(target_obj, actor=actor, approver_note=comment)
        elif assignment.module == Workflow.Module.PAYROLL_RELEASE:
            from apps.payroll.services.payroll_governance_service import PayrollGovernanceService

            PayrollGovernanceService.finalize_release_rejection(target_obj, actor=actor, approver_note=comment)

        NotificationService.notify_workflow_completed(assignment, approved=False, actor=actor, comments=comment)
        AuditService.log(
            actor=actor,
            action="workflow.rejected",
            entity=assignment,
            after={"status": assignment.status, "module": assignment.module},
        )
