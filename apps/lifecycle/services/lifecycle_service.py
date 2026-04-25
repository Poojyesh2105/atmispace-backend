from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User
from apps.audit.services.audit_service import AuditService
from apps.core.services import OrganizationService
from apps.lifecycle.models import EmployeeChangeRequest, EmployeeOnboarding, EmployeeOnboardingTask, OffboardingCase, OffboardingTask, OnboardingPlan, OnboardingTaskTemplate
from apps.notifications.services.notification_service import NotificationService
from apps.policy_engine.services.policy_rule_service import PolicyRuleService
from apps.workflow.models import Workflow
from apps.workflow.services.workflow_service import WorkflowService


class OnboardingPlanService:
    @staticmethod
    def create_plan(validated_data, actor):
        if organization := OrganizationService.resolve_for_actor(actor):
            validated_data.setdefault("organization", organization)
        plan = OnboardingPlan.objects.create(**validated_data)
        AuditService.log(actor=actor, action="lifecycle.onboarding_plan.created", entity=plan, after=plan)
        return plan

    @staticmethod
    def update_plan(instance, validated_data, actor):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="lifecycle.onboarding_plan.updated", entity=instance, before=before, after=instance)
        return instance


class OnboardingTaskTemplateService:
    @staticmethod
    def create_template(validated_data, actor):
        if organization := OrganizationService.resolve_for_actor(actor):
            validated_data.setdefault("organization", organization)
        template = OnboardingTaskTemplate.objects.create(**validated_data)
        AuditService.log(actor=actor, action="lifecycle.onboarding_template.created", entity=template, after=template)
        return template

    @staticmethod
    def update_template(instance, validated_data, actor):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="lifecycle.onboarding_template.updated", entity=instance, before=before, after=instance)
        return instance


class EmployeeOnboardingService:
    @staticmethod
    @transaction.atomic
    def create_onboarding(validated_data, actor):
        employee = validated_data["employee"]
        plan = validated_data.get("plan")
        organization = employee.organization or OrganizationService.resolve_for_actor(actor)
        onboarding = EmployeeOnboarding.objects.create(organization=organization, initiated_by=actor, **validated_data)

        if plan:
            for template in plan.task_templates.all().order_by("sequence", "id"):
                EmployeeOnboardingTask.objects.create(
                    organization=organization,
                    onboarding=onboarding,
                    template_task=template,
                    title=template.title,
                    description=template.description,
                    owner_role=template.owner_role,
                    task_type=template.task_type,
                    sequence=template.sequence,
                    due_date=onboarding.start_date + timedelta(days=template.due_offset_days),
                )

        onboarding.status = EmployeeOnboarding.Status.IN_PROGRESS
        onboarding.save(update_fields=["status", "updated_at"])
        NotificationService.create_notification(
            employee.user,
            NotificationService._resolve_type("ONBOARDING"),
            "Onboarding plan started",
            f"Your onboarding plan has started with due date {onboarding.due_date.isoformat()}.",
        )
        AuditService.log(actor=actor, action="lifecycle.employee_onboarding.created", entity=onboarding, after=onboarding)
        return onboarding

    @staticmethod
    def complete_task(user, task, notes=""):
        current_employee = getattr(user, "employee_profile", None)
        if user.role not in {User.Role.HR, User.Role.ADMIN} and task.owner_role != user.role and task.onboarding.employee_id != getattr(current_employee, "pk", None):
            raise exceptions.PermissionDenied("You cannot complete this onboarding task.")

        before = AuditService.snapshot(task)
        task.status = EmployeeOnboardingTask.Status.COMPLETED
        task.completed_by = user
        task.completed_at = timezone.now()
        task.notes = notes
        task.save(update_fields=["status", "completed_by", "completed_at", "notes", "updated_at"])
        onboarding = task.onboarding
        if onboarding.tasks.exclude(status__in=[EmployeeOnboardingTask.Status.COMPLETED, EmployeeOnboardingTask.Status.SKIPPED]).count() == 0:
            onboarding.status = EmployeeOnboarding.Status.COMPLETED
            onboarding.save(update_fields=["status", "updated_at"])
        AuditService.log(actor=user, action="lifecycle.employee_onboarding_task.completed", entity=task, before=before, after=task)
        return task


class OffboardingService:
    DEFAULT_TASKS = [
        {"title": "Manager knowledge handoff", "owner_role": User.Role.MANAGER, "offset_days": 2},
        {"title": "HR exit checklist", "owner_role": User.Role.HR, "offset_days": 4},
        {"title": "Accounts final settlement handoff", "owner_role": User.Role.ACCOUNTS, "offset_days": 5},
        {"title": "Admin access disablement", "owner_role": User.Role.ADMIN, "offset_days": 6},
    ]

    @staticmethod
    @transaction.atomic
    def create_case(validated_data, actor):
        employee = validated_data["employee"]
        organization = employee.organization or OrganizationService.resolve_for_actor(actor)
        offboarding_case = OffboardingCase.objects.create(
            organization=organization,
            initiated_by=actor,
            status=OffboardingCase.Status.PENDING_APPROVAL,
            **validated_data,
        )
        for index, task in enumerate(OffboardingService.DEFAULT_TASKS, start=1):
            OffboardingTask.objects.create(
                organization=organization,
                offboarding_case=offboarding_case,
                title=task["title"],
                owner_role=task["owner_role"],
                sequence=index,
                due_date=offboarding_case.notice_start_date + timedelta(days=task["offset_days"]),
            )
        PolicyRuleService.evaluate("LIFECYCLE", offboarding_case, actor=actor, persist=True)
        WorkflowService.start_workflow(
            Workflow.Module.LIFECYCLE_CASE,
            offboarding_case,
            requested_by=actor,
            context={"case_type": "offboarding", "employee_id": offboarding_case.employee_id},
        )
        NotificationService.create_notification(
            offboarding_case.employee.user,
            NotificationService._resolve_type("OFFBOARDING"),
            "Offboarding initiated",
            f"An offboarding case has been initiated for you with last working day {offboarding_case.last_working_day.isoformat()}.",
        )
        AuditService.log(actor=actor, action="lifecycle.offboarding_case.created", entity=offboarding_case, after=offboarding_case)
        return offboarding_case

    @staticmethod
    def complete_task(user, task, notes=""):
        before = AuditService.snapshot(task)
        task.status = OffboardingTask.Status.COMPLETED
        task.completed_by = user
        task.completed_at = timezone.now()
        task.notes = notes
        task.save(update_fields=["status", "completed_by", "completed_at", "notes", "updated_at"])
        offboarding_case = task.offboarding_case
        if offboarding_case.tasks.filter(status__in=[OffboardingTask.Status.PENDING, OffboardingTask.Status.IN_PROGRESS]).count() == 0:
            offboarding_case.status = OffboardingCase.Status.COMPLETED
            offboarding_case.actual_exit_date = offboarding_case.actual_exit_date or timezone.localdate()
            offboarding_case.save(update_fields=["status", "actual_exit_date", "updated_at"])
        AuditService.log(actor=user, action="lifecycle.offboarding_task.completed", entity=task, before=before, after=task)
        return task

    @staticmethod
    def finalize_workflow_approval(offboarding_case, actor=None, approver_note=""):
        before = AuditService.snapshot(offboarding_case)
        offboarding_case.status = OffboardingCase.Status.IN_PROGRESS
        offboarding_case.handoff_notes = approver_note or offboarding_case.handoff_notes
        offboarding_case.save(update_fields=["status", "handoff_notes", "updated_at"])
        NotificationService.create_notification(
            offboarding_case.employee.user,
            NotificationService._resolve_type("OFFBOARDING"),
            "Offboarding approved",
            f"Your offboarding case is now in progress. {approver_note}".strip(),
        )
        AuditService.log(actor=actor, action="lifecycle.offboarding_case.approved", entity=offboarding_case, before=before, after=offboarding_case)

    @staticmethod
    def finalize_workflow_rejection(offboarding_case, actor=None, approver_note=""):
        before = AuditService.snapshot(offboarding_case)
        offboarding_case.status = OffboardingCase.Status.REJECTED
        offboarding_case.handoff_notes = approver_note or offboarding_case.handoff_notes
        offboarding_case.save(update_fields=["status", "handoff_notes", "updated_at"])
        AuditService.log(actor=actor, action="lifecycle.offboarding_case.rejected", entity=offboarding_case, before=before, after=offboarding_case)


class EmployeeChangeRequestService:
    @staticmethod
    @transaction.atomic
    def create_change_request(validated_data, actor):
        employee = validated_data["employee"]
        change_request = EmployeeChangeRequest.objects.create(
            organization=employee.organization or OrganizationService.resolve_for_actor(actor),
            requested_by=actor,
            **validated_data,
        )
        PolicyRuleService.evaluate("LIFECYCLE", change_request, actor=actor, persist=True)
        WorkflowService.start_workflow(
            Workflow.Module.LIFECYCLE_CASE,
            change_request,
            requested_by=actor,
            context={"case_type": "employee_change", "change_type": change_request.change_type},
        )
        NotificationService.create_notification(
            change_request.employee.user,
            NotificationService._resolve_type("LIFECYCLE"),
            "Employee change request raised",
            f"A {change_request.get_change_type_display().lower()} request has been initiated for you.",
        )
        AuditService.log(actor=actor, action="lifecycle.employee_change_request.created", entity=change_request, after=change_request)
        return change_request

    @staticmethod
    def finalize_workflow_approval(change_request, actor=None, approver_note=""):
        before = AuditService.snapshot(change_request)
        employee = change_request.employee
        user = employee.user

        if change_request.proposed_designation:
            employee.designation = change_request.proposed_designation
        if change_request.proposed_department_role:
            employee.department_role = change_request.proposed_department_role
        if change_request.proposed_role:
            user.role = change_request.proposed_role
            user.save(update_fields=["role"])
        if change_request.proposed_ctc_per_annum is not None:
            from apps.payroll.services.payroll_governance_service import SalaryRevisionService

            SalaryRevisionService.apply_revision(
                actor=actor,
                employee=employee,
                new_ctc=change_request.proposed_ctc_per_annum,
                effective_date=change_request.proposed_effective_date,
                reason=change_request.justification,
            )

        employee.save(update_fields=["designation", "department_role", "updated_at"])
        change_request.status = EmployeeChangeRequest.Status.APPROVED
        change_request.approved_by = actor
        change_request.approved_at = timezone.now()
        change_request.notes = approver_note or change_request.notes
        change_request.save(update_fields=["status", "approved_by", "approved_at", "notes", "updated_at"])
        NotificationService.create_notification(
            change_request.employee.user,
            NotificationService._resolve_type("LIFECYCLE"),
            "Employee change request approved",
            f"Your {change_request.get_change_type_display().lower()} request was approved.",
        )
        AuditService.log(actor=actor, action="lifecycle.employee_change_request.approved", entity=change_request, before=before, after=change_request)

    @staticmethod
    def finalize_workflow_rejection(change_request, actor=None, approver_note=""):
        before = AuditService.snapshot(change_request)
        change_request.status = EmployeeChangeRequest.Status.REJECTED
        change_request.approved_by = actor
        change_request.approved_at = timezone.now()
        change_request.notes = approver_note or change_request.notes
        change_request.save(update_fields=["status", "approved_by", "approved_at", "notes", "updated_at"])
        NotificationService.create_notification(
            change_request.employee.user,
            NotificationService._resolve_type("LIFECYCLE"),
            "Employee change request rejected",
            f"Your {change_request.get_change_type_display().lower()} request was rejected.",
        )
        AuditService.log(actor=actor, action="lifecycle.employee_change_request.rejected", entity=change_request, before=before, after=change_request)
