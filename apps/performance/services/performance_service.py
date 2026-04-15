from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User
from apps.audit.services.audit_service import AuditService
from apps.notifications.services.notification_service import NotificationService
from apps.performance.models import PerformanceCycle, PerformanceGoal, PerformanceReview, RatingScale
from apps.workflow.models import Workflow
from apps.workflow.services.workflow_service import WorkflowService


class RatingScaleService:
    @staticmethod
    def create_scale(validated_data, actor):
        scale = RatingScale.objects.create(**validated_data)
        AuditService.log(actor=actor, action="performance.rating_scale.created", entity=scale, after=scale)
        return scale

    @staticmethod
    def update_scale(instance, validated_data, actor):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="performance.rating_scale.updated", entity=instance, before=before, after=instance)
        return instance


class PerformanceCycleService:
    @staticmethod
    def create_cycle(validated_data, actor):
        cycle = PerformanceCycle.objects.create(**validated_data)
        AuditService.log(actor=actor, action="performance.cycle.created", entity=cycle, after=cycle)
        return cycle

    @staticmethod
    def update_cycle(instance, validated_data, actor):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="performance.cycle.updated", entity=instance, before=before, after=instance)
        return instance


class PerformanceGoalService:
    @staticmethod
    def _can_manage_goal(user, employee):
        current_employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return True
        if current_employee and current_employee.pk == employee.pk:
            return True
        if user.role == User.Role.MANAGER and current_employee:
            return employee.manager_id == current_employee.pk or employee.secondary_manager_id == current_employee.pk
        return False

    @staticmethod
    def create_goal(validated_data, actor):
        employee = validated_data["employee"]
        if not PerformanceGoalService._can_manage_goal(actor, employee):
            raise exceptions.PermissionDenied("You cannot create goals for this employee.")
        goal = PerformanceGoal.objects.create(**validated_data)
        AuditService.log(actor=actor, action="performance.goal.created", entity=goal, after=goal)
        return goal

    @staticmethod
    def update_goal(instance, validated_data, actor):
        if not PerformanceGoalService._can_manage_goal(actor, instance.employee):
            raise exceptions.PermissionDenied("You cannot update goals for this employee.")
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="performance.goal.updated", entity=instance, before=before, after=instance)
        return instance


class PerformanceReviewService:
    @staticmethod
    def ensure_review(cycle, employee):
        review, _ = PerformanceReview.objects.get_or_create(
            cycle=cycle,
            employee=employee,
            defaults={"manager": employee.manager},
        )
        return review

    @staticmethod
    def _get_assignment(review):
        return WorkflowService.get_assignment_for_object(Workflow.Module.PERFORMANCE_REVIEW, review)

    @staticmethod
    @transaction.atomic
    def submit_self_review(user, review, validated_data):
        current_employee = getattr(user, "employee_profile", None)
        if not current_employee or review.employee_id != current_employee.pk:
            raise exceptions.PermissionDenied("You can only submit your own self review.")
        if review.status not in {PerformanceReview.Status.SELF_PENDING, PerformanceReview.Status.REJECTED}:
            raise exceptions.ValidationError({"status": "Self review has already been submitted."})

        before = AuditService.snapshot(review)
        review.self_summary = validated_data["self_summary"]
        review.self_rating = validated_data["self_rating"]
        review.manager = review.employee.manager
        review.status = PerformanceReview.Status.MANAGER_PENDING
        review.submitted_at = timezone.now()
        review.save()
        assignment = WorkflowService.start_workflow(
            Workflow.Module.PERFORMANCE_REVIEW,
            review,
            requested_by=user,
            context={"cycle_id": review.cycle_id, "employee_id": review.employee_id},
        )
        NotificationService.create_notification(
            user,
            NotificationService._resolve_type("PERFORMANCE_REVIEW"),
            "Performance review submitted",
            f"Your self review for {review.cycle.name} was submitted and moved to manager review.",
        )
        AuditService.log(
            actor=user,
            action="performance.review.self_submitted",
            entity=review,
            before=before,
            after={"status": review.status, "workflow_assignment_id": assignment.pk},
        )
        return review

    @staticmethod
    @transaction.atomic
    def submit_manager_review(user, review, validated_data):
        current_employee = getattr(user, "employee_profile", None)
        if user.role not in {User.Role.MANAGER, User.Role.HR, User.Role.ADMIN}:
            raise exceptions.PermissionDenied("You cannot review this performance submission.")
        if user.role == User.Role.MANAGER and current_employee and review.employee.manager_id != current_employee.pk and review.employee.secondary_manager_id != current_employee.pk:
            raise exceptions.PermissionDenied("This review is not assigned to your reporting chain.")

        assignment = PerformanceReviewService._get_assignment(review)
        approval = WorkflowService.get_pending_approval_for_assignment(assignment)
        if not approval:
            raise exceptions.ValidationError({"workflow": "No pending workflow step found for this review."})

        before = AuditService.snapshot(review)
        review.manager = current_employee or review.employee.manager
        review.manager_summary = validated_data["manager_summary"]
        review.manager_rating = validated_data["manager_rating"]
        review.manager_reviewed_at = timezone.now()
        review.status = PerformanceReview.Status.HR_PENDING
        review.save()
        WorkflowService.approve(user, approval, validated_data["manager_summary"])
        AuditService.log(actor=user, action="performance.review.manager_submitted", entity=review, before=before, after=review)
        return review

    @staticmethod
    @transaction.atomic
    def submit_hr_review(user, review, validated_data):
        if user.role not in {User.Role.HR, User.Role.ADMIN}:
            raise exceptions.PermissionDenied("Only HR or Admin can submit the final review.")

        assignment = PerformanceReviewService._get_assignment(review)
        approval = WorkflowService.get_pending_approval_for_assignment(assignment)
        if not approval:
            raise exceptions.ValidationError({"workflow": "No pending workflow step found for this review."})

        before = AuditService.snapshot(review)
        review.hr_summary = validated_data["hr_summary"]
        review.final_rating = validated_data["final_rating"]
        review.hr_reviewed_at = timezone.now()
        review.save()
        WorkflowService.approve(user, approval, validated_data["hr_summary"])
        AuditService.log(actor=user, action="performance.review.hr_submitted", entity=review, before=before, after=review)
        return review

    @staticmethod
    def finalize_workflow_approval(review, actor=None, approver_note=""):
        before = AuditService.snapshot(review)
        review.status = PerformanceReview.Status.COMPLETED
        if review.final_rating is None:
            review.final_rating = review.manager_rating or review.self_rating
        if review.hr_reviewed_at is None:
            review.hr_reviewed_at = timezone.now()
        review.save(update_fields=["status", "final_rating", "hr_reviewed_at", "updated_at"])
        NotificationService.create_notification(
            review.employee.user,
            NotificationService._resolve_type("PERFORMANCE_REVIEW"),
            "Performance review completed",
            f"Your performance review for {review.cycle.name} was finalized. {approver_note}".strip(),
        )
        AuditService.log(actor=actor, action="performance.review.approved", entity=review, before=before, after=review)

    @staticmethod
    def finalize_workflow_rejection(review, actor=None, approver_note=""):
        before = AuditService.snapshot(review)
        review.status = PerformanceReview.Status.REJECTED
        review.save(update_fields=["status", "updated_at"])
        NotificationService.create_notification(
            review.employee.user,
            NotificationService._resolve_type("PERFORMANCE_REVIEW"),
            "Performance review returned",
            f"Your performance review for {review.cycle.name} was returned for rework. {approver_note}".strip(),
        )
        AuditService.log(actor=actor, action="performance.review.rejected", entity=review, before=before, after=review)

