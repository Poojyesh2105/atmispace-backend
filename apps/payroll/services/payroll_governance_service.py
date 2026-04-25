from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User
from apps.audit.services.audit_service import AuditService
from apps.core.services import OrganizationService
from apps.employees.models import Employee
from apps.notifications.services.notification_service import NotificationService
from apps.payroll.models import PayrollAdjustment, PayrollCycle, PayrollRun, SalaryRevision
from apps.payroll.services.payroll_service import PayslipService
from apps.policy_engine.services.policy_rule_service import PolicyRuleService
from apps.workflow.models import Workflow
from apps.workflow.services.workflow_service import WorkflowService


class PayrollGovernanceService:
    MANAGE_ROLES = {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}

    @staticmethod
    def _check_manage_permission(user):
        if not user or not getattr(user, "is_authenticated", False) or user.role not in PayrollGovernanceService.MANAGE_ROLES:
            raise exceptions.PermissionDenied("You are not allowed to manage payroll governance.")

    @staticmethod
    def create_cycle(validated_data, actor):
        PayrollGovernanceService._check_manage_permission(actor)
        organization = OrganizationService.resolve_for_actor(actor)
        if organization:
            validated_data.setdefault("organization", organization)
        cycle = PayrollCycle.objects.create(**validated_data)
        AuditService.log(actor=actor, action="payroll.cycle.created", entity=cycle, after=cycle)
        return cycle

    @staticmethod
    def update_cycle(instance, validated_data, actor):
        PayrollGovernanceService._check_manage_permission(actor)
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="payroll.cycle.updated", entity=instance, before=before, after=instance)
        return instance

    @staticmethod
    def create_adjustment(validated_data, actor):
        PayrollGovernanceService._check_manage_permission(actor)
        organization = OrganizationService.resolve_for_actor(actor)
        if organization:
            validated_data.setdefault("organization", organization)
        adjustment = PayrollAdjustment.objects.create(created_by=actor, **validated_data)
        AuditService.log(actor=actor, action="payroll.adjustment.created", entity=adjustment, after=adjustment)
        return adjustment

    @staticmethod
    def update_adjustment(instance, validated_data, actor):
        PayrollGovernanceService._check_manage_permission(actor)
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="payroll.adjustment.updated", entity=instance, before=before, after=instance)
        return instance

    @staticmethod
    def _calculate_adjustments(employee, cycle):
        earnings = Decimal("0.00")
        deductions = Decimal("0.00")
        for adjustment in PayrollAdjustment.objects.filter(cycle=cycle, employee=employee, status=PayrollAdjustment.Status.PENDING):
            if adjustment.adjustment_type == PayrollAdjustment.AdjustmentType.EARNING:
                earnings += adjustment.amount
            else:
                deductions += adjustment.amount
        return (
            earnings.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            deductions.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )

    @staticmethod
    @transaction.atomic
    def generate_run(actor, cycle):
        PayrollGovernanceService._check_manage_permission(actor)
        PolicyRuleService.evaluate("PAYROLL", cycle, actor=actor, persist=True)
        run, _ = PayrollRun.objects.get_or_create(cycle=cycle, defaults={"generated_by": actor})
        employees = Employee.objects.for_current_org(actor).filter(is_active=True, user__is_active=True).select_related("user")
        total_employees = 0
        skipped_employee_codes = []
        for employee in employees:
            if (employee.ctc_per_annum or Decimal("0")) <= 0:
                skipped_employee_codes.append(employee.employee_id)
                continue
            additional_earnings, adjustment_deductions = PayrollGovernanceService._calculate_adjustments(employee, cycle)
            PayslipService.generate_payslip(
                actor,
                employee=employee,
                payroll_month=cycle.payroll_month,
                notes=f"Generated from payroll cycle {cycle.name}",
                payroll_cycle=cycle,
                additional_earnings=additional_earnings,
                adjustment_deductions=adjustment_deductions,
            )
            PayrollAdjustment.objects.filter(cycle=cycle, employee=employee, status=PayrollAdjustment.Status.PENDING).update(
                status=PayrollAdjustment.Status.APPLIED
            )
            total_employees += 1

        run_note = f"Generated from payroll cycle {cycle.name}"
        if skipped_employee_codes:
            run_note = (
                f"{run_note}. Skipped {len(skipped_employee_codes)} employee(s) without configured CTC: "
                f"{', '.join(skipped_employee_codes)}."
            )
        run.organization = cycle.organization or OrganizationService.resolve_for_actor(actor)
        run.generated_by = actor
        run.total_employees = total_employees
        run.status = PayrollRun.Status.DRAFT
        run.notes = run_note
        run.save(update_fields=["organization", "generated_by", "total_employees", "status", "notes", "updated_at"])
        AuditService.log(
            actor=actor,
            action="payroll.run.generated",
            entity=run,
            after={
                "total_employees": total_employees,
                "cycle": cycle.name,
                "skipped_employee_codes": skipped_employee_codes,
            },
        )
        return run

    @staticmethod
    def lock_run(actor, run):
        PayrollGovernanceService._check_manage_permission(actor)
        if run.status == PayrollRun.Status.RELEASED:
            raise exceptions.ValidationError({"status": "Released payroll runs cannot be locked again."})
        before = AuditService.snapshot(run)
        run.status = PayrollRun.Status.LOCKED
        run.locked_at = timezone.now()
        run.save(update_fields=["status", "locked_at", "updated_at"])
        cycle = run.cycle
        cycle.status = PayrollCycle.Status.LOCKED
        cycle.save(update_fields=["status", "updated_at"])
        AuditService.log(actor=actor, action="payroll.run.locked", entity=run, before=before, after=run)
        return run

    @staticmethod
    def request_release(actor, run, notes=""):
        PayrollGovernanceService._check_manage_permission(actor)
        if run.status != PayrollRun.Status.LOCKED:
            raise exceptions.ValidationError({"status": "Payroll run must be locked before release approval."})
        before = AuditService.snapshot(run)
        WorkflowService.start_workflow(
            Workflow.Module.PAYROLL_RELEASE,
            run,
            requested_by=actor,
            context={"cycle_id": run.cycle_id},
        )
        run.status = PayrollRun.Status.RELEASE_PENDING
        run.notes = notes
        run.save(update_fields=["status", "notes", "updated_at"])
        run.cycle.status = PayrollCycle.Status.RELEASE_PENDING
        run.cycle.save(update_fields=["status", "updated_at"])
        AuditService.log(actor=actor, action="payroll.run.release_requested", entity=run, before=before, after=run)
        return run

    @staticmethod
    def finalize_release_approval(run, actor=None, approver_note=""):
        before = AuditService.snapshot(run)
        run.status = PayrollRun.Status.RELEASED
        run.released_at = timezone.now()
        run.released_by = actor
        run.notes = approver_note or run.notes
        run.save(update_fields=["status", "released_at", "released_by", "notes", "updated_at"])
        cycle = run.cycle
        cycle.status = PayrollCycle.Status.RELEASED
        cycle.save(update_fields=["status", "updated_at"])
        NotificationService.create_notification(
            run.generated_by,
            NotificationService._resolve_type("PAYROLL"),
            "Payroll run released",
            f"Payroll run for {run.cycle.name} was approved and released.",
        )
        AuditService.log(actor=actor, action="payroll.run.released", entity=run, before=before, after=run)

    @staticmethod
    def finalize_release_rejection(run, actor=None, approver_note=""):
        before = AuditService.snapshot(run)
        run.status = PayrollRun.Status.LOCKED
        run.notes = approver_note or run.notes
        run.save(update_fields=["status", "notes", "updated_at"])
        cycle = run.cycle
        cycle.status = PayrollCycle.Status.LOCKED
        cycle.save(update_fields=["status", "updated_at"])
        AuditService.log(actor=actor, action="payroll.run.release_rejected", entity=run, before=before, after=run)


class SalaryRevisionService:
    @staticmethod
    def apply_revision(actor, employee, new_ctc, effective_date, reason):
        status = SalaryRevision.Status.APPLIED if effective_date <= timezone.localdate() else SalaryRevision.Status.SCHEDULED
        revision = SalaryRevision.objects.create(
            organization=employee.organization or OrganizationService.resolve_for_actor(actor),
            employee=employee,
            previous_ctc=employee.ctc_per_annum,
            new_ctc=new_ctc,
            effective_date=effective_date,
            reason=reason,
            status=status,
            approved_by=actor,
        )
        if status == SalaryRevision.Status.APPLIED:
            employee.ctc_per_annum = new_ctc
            employee.save(update_fields=["ctc_per_annum", "updated_at"])
        AuditService.log(
            actor=actor,
            action="payroll.salary_revision.applied",
            entity=revision,
            after={"employee_id": employee.employee_id, "new_ctc": str(new_ctc), "effective_date": effective_date.isoformat()},
        )
        return revision
