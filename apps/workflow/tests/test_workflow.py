"""
Tests for workflow services:
- WorkflowService: create, assign, step transitions, can_act, role-based, primary manager
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core.models import Organization
from apps.employees.models import Department, Employee
from apps.leave_management.models import LeaveBalance, LeavePolicy, LeaveRequest
from apps.workflow.models import (
    ApprovalInstance,
    Workflow,
    WorkflowAssignment,
    WorkflowStep,
)
from apps.workflow.services.workflow_service import WorkflowService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email, role=User.Role.EMPLOYEE, password="Test@1234", organization=None):
    return User.objects.create_user(
        email=email,
        password=password,
        first_name="Test",
        last_name="User",
        role=role,
        organization=organization,
    )


def make_employee(user, emp_id, dept=None, manager=None, secondary_manager=None, organization=None):
    return Employee.objects.create(
        user=user,
        employee_id=emp_id,
        designation="Dev",
        hire_date=date.today(),
        department=dept,
        manager=manager,
        secondary_manager=secondary_manager,
        organization=organization or getattr(user, "organization", None),
    )


def make_leave_request(employee, status=LeaveRequest.Status.PENDING, total_days=1):
    return LeaveRequest.objects.create(
        employee=employee,
        leave_type=LeaveBalance.LeaveType.CASUAL,
        duration_type=LeaveRequest.DurationType.FULL_DAY,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        reason="Test",
        status=status,
        total_days=Decimal(str(total_days)),
    )


# ---------------------------------------------------------------------------
# WorkflowService.create_workflow tests
# ---------------------------------------------------------------------------

class WorkflowCreateTest(TestCase):
    def test_create_workflow_with_steps(self):
        wf_data = {
            "name": "Test Leave WF",
            "module": Workflow.Module.LEAVE_REQUEST,
            "description": "Workflow for tests",
            "is_active": True,
            "priority": 10,
            "condition_operator": Workflow.ConditionOperator.ALWAYS,
        }
        steps_data = [
            {
                "name": "Manager Review",
                "sequence": 1,
                "assignment_type": WorkflowStep.AssignmentType.PRIMARY_MANAGER,
            },
            {
                "name": "HR Review",
                "sequence": 2,
                "assignment_type": WorkflowStep.AssignmentType.ROLE,
                "role": User.Role.HR,
            },
        ]
        workflow = WorkflowService.create_workflow(wf_data, steps_data)
        self.assertEqual(workflow.name, "Test Leave WF")
        self.assertEqual(workflow.steps.count(), 2)
        sequences = list(workflow.steps.values_list("sequence", flat=True))
        self.assertEqual(sequences, [1, 2])

    def test_steps_sorted_by_sequence_on_create(self):
        wf_data = {
            "name": "Sequence WF",
            "module": Workflow.Module.ATTENDANCE_REGULARIZATION,
            "is_active": True,
            "priority": 50,
            "condition_operator": Workflow.ConditionOperator.ALWAYS,
        }
        # Pass steps in reverse order; service should sort them
        steps_data = [
            {"name": "Step B", "sequence": 2, "assignment_type": WorkflowStep.AssignmentType.PRIMARY_MANAGER},
            {"name": "Step A", "sequence": 1, "assignment_type": WorkflowStep.AssignmentType.PRIMARY_MANAGER},
        ]
        workflow = WorkflowService.create_workflow(wf_data, steps_data)
        step_names = list(workflow.steps.order_by("sequence").values_list("name", flat=True))
        self.assertEqual(step_names, ["Step A", "Step B"])


# ---------------------------------------------------------------------------
# start_workflow / assignment tests
# ---------------------------------------------------------------------------

class WorkflowAssignmentTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="WF-Dept", code="WFD")

        self.hr_user = make_user("wf-hr@test.com", role=User.Role.HR)
        self.hr_emp = make_employee(self.hr_user, "EMP-WFHR", self.dept)

        self.manager_user = make_user("wf-mgr@test.com", role=User.Role.MANAGER)
        self.manager_emp = make_employee(self.manager_user, "EMP-WFMGR", self.dept)

        self.emp_user = make_user("wf-emp@test.com")
        self.employee = make_employee(self.emp_user, "EMP-WF001", self.dept, manager=self.manager_emp)

        # Ensure policy exists
        LeavePolicy.objects.get_or_create(pk=1)

    def _patch_notifications(self):
        return patch("apps.workflow.services.workflow_service.NotificationService.notify_pending_approval")

    def _patch_leave_finalize(self):
        return patch(
            "apps.leave_management.services.leave_service.LeaveRequestService.finalize_workflow_approval"
        )

    def test_start_workflow_creates_assignment(self):
        leave = make_leave_request(self.employee)
        with self._patch_notifications():
            assignment = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST,
                leave,
                requested_by=self.emp_user,
            )
        self.assertIsNotNone(assignment.pk)
        self.assertEqual(assignment.module, Workflow.Module.LEAVE_REQUEST)
        self.assertEqual(assignment.object_id, leave.pk)

    def test_start_workflow_first_step_becomes_pending(self):
        leave = make_leave_request(self.employee)
        with self._patch_notifications():
            assignment = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST,
                leave,
                requested_by=self.emp_user,
            )
        pending_instances = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING)
        # There should be exactly one PENDING step at the start
        self.assertEqual(pending_instances.count(), 1)
        pending = pending_instances.first()
        self.assertEqual(pending.sequence, assignment.current_step_sequence)

    def test_start_workflow_idempotent_for_pending_assignment(self):
        leave = make_leave_request(self.employee)
        with self._patch_notifications():
            assignment1 = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST, leave, requested_by=self.emp_user
            )
            assignment2 = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST, leave, requested_by=self.emp_user
            )
        self.assertEqual(assignment1.pk, assignment2.pk)


# ---------------------------------------------------------------------------
# Step transition tests (approve / reject)
# ---------------------------------------------------------------------------

class StepTransitionTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Trans-Dept", code="TRD")

        self.hr_user = make_user("tr-hr@test.com", role=User.Role.HR)
        self.hr_emp = make_employee(self.hr_user, "EMP-TRHR", self.dept)

        self.manager_user = make_user("tr-mgr@test.com", role=User.Role.MANAGER)
        self.manager_emp = make_employee(self.manager_user, "EMP-TRMGR", self.dept)

        self.emp_user = make_user("tr-emp@test.com")
        self.employee = make_employee(self.emp_user, "EMP-TR001", self.dept, manager=self.manager_emp)

        LeavePolicy.objects.get_or_create(pk=1)

        # Create an explicit single-step workflow (ROLE: HR) so we control the assignee
        self.single_wf = Workflow.objects.create(
            name="Single Step HR",
            module=Workflow.Module.LEAVE_REQUEST,
            is_active=True,
            priority=1,
            condition_operator=Workflow.ConditionOperator.ALWAYS,
        )
        WorkflowStep.objects.create(
            workflow=self.single_wf,
            name="HR Approval",
            sequence=1,
            assignment_type=WorkflowStep.AssignmentType.ROLE,
            role=User.Role.HR,
        )

    def _setup_assignment(self):
        leave = make_leave_request(self.employee)
        with patch("apps.workflow.services.workflow_service.NotificationService.notify_pending_approval"):
            assignment = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST, leave, requested_by=self.emp_user
            )
        return assignment, leave

    def test_approve_pending_step_completes_when_no_next_step(self):
        assignment, leave = self._setup_assignment()
        pending = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING).first()
        self.assertIsNotNone(pending, "Expected a PENDING approval instance")
        pending.assigned_user = self.hr_user
        pending.save(update_fields=["assigned_user", "updated_at"])

        with patch("apps.workflow.services.workflow_service.NotificationService.notify_pending_approval"), \
             patch("apps.workflow.services.workflow_service.NotificationService.notify_workflow_completed"), \
             patch("apps.leave_management.services.leave_service.LeaveRequestService.finalize_workflow_approval"):
            WorkflowService.approve(self.hr_user, pending, comments="Looks good")

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, WorkflowAssignment.Status.APPROVED)
        pending.refresh_from_db()
        self.assertEqual(pending.status, ApprovalInstance.Status.APPROVED)

    def test_reject_pending_step_stops_workflow(self):
        assignment, leave = self._setup_assignment()
        pending = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING).first()
        self.assertIsNotNone(pending)
        pending.assigned_user = self.hr_user
        pending.save(update_fields=["assigned_user", "updated_at"])

        with patch("apps.workflow.services.workflow_service.NotificationService.notify_workflow_completed"), \
             patch("apps.leave_management.services.leave_service.LeaveRequestService.finalize_workflow_rejection"):
            WorkflowService.reject(self.hr_user, pending, comments="Not approved")

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, WorkflowAssignment.Status.REJECTED)
        pending.refresh_from_db()
        self.assertEqual(pending.status, ApprovalInstance.Status.REJECTED)

    def test_approve_non_pending_raises_validation_error(self):
        assignment, leave = self._setup_assignment()
        # Get any instance and force it to APPROVED state
        instance = assignment.approval_instances.first()
        instance.status = ApprovalInstance.Status.APPROVED
        instance.save(update_fields=["status", "updated_at"])
        instance.assigned_user = self.hr_user
        instance.save(update_fields=["assigned_user", "updated_at"])

        with self.assertRaises(ValidationError):
            WorkflowService.approve(self.hr_user, instance)

    def test_wrong_user_cannot_approve(self):
        assignment, leave = self._setup_assignment()
        pending = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING).first()
        if pending:
            pending.assigned_user = self.hr_user
            pending.save(update_fields=["assigned_user", "updated_at"])
            wrong_user = make_user("wrong@test.com", role=User.Role.EMPLOYEE)
            with self.assertRaises(PermissionDenied):
                WorkflowService.approve(wrong_user, pending)


# ---------------------------------------------------------------------------
# Multi-step transition tests
# ---------------------------------------------------------------------------

class MultiStepTransitionTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="MultiStep-Dept", code="MSD")

        self.hr_user = make_user("ms-hr@test.com", role=User.Role.HR)
        self.hr_emp = make_employee(self.hr_user, "EMP-MSHR", self.dept)

        self.manager_user = make_user("ms-mgr@test.com", role=User.Role.MANAGER)
        self.manager_emp = make_employee(self.manager_user, "EMP-MSMGR", self.dept)

        self.emp_user = make_user("ms-emp@test.com")
        self.employee = make_employee(self.emp_user, "EMP-MS001", self.dept, manager=self.manager_emp)

        LeavePolicy.objects.get_or_create(pk=1)

        # Two-step workflow: step 1 = manager, step 2 = HR (role)
        self.multi_wf = Workflow.objects.create(
            name="Two-Step Leave",
            module=Workflow.Module.LEAVE_REQUEST,
            is_active=True,
            priority=1,
            condition_operator=Workflow.ConditionOperator.ALWAYS,
        )
        WorkflowStep.objects.create(
            workflow=self.multi_wf,
            name="Manager Approval",
            sequence=1,
            assignment_type=WorkflowStep.AssignmentType.PRIMARY_MANAGER,
        )
        WorkflowStep.objects.create(
            workflow=self.multi_wf,
            name="HR Final",
            sequence=2,
            assignment_type=WorkflowStep.AssignmentType.ROLE,
            role=User.Role.HR,
        )

    def test_step1_approved_step2_becomes_pending(self):
        leave = make_leave_request(self.employee)
        with patch("apps.workflow.services.workflow_service.NotificationService.notify_pending_approval"):
            assignment = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST, leave, requested_by=self.emp_user
            )

        step1 = assignment.approval_instances.filter(sequence=1).first()
        self.assertIsNotNone(step1)
        # Force step1 to be assigned to manager_user (primary manager resolution may fail in test)
        step1.status = ApprovalInstance.Status.PENDING
        step1.assigned_user = self.manager_user
        step1.save(update_fields=["status", "assigned_user", "updated_at"])
        assignment.current_step_sequence = 1
        assignment.save(update_fields=["current_step_sequence", "updated_at"])

        with patch("apps.workflow.services.workflow_service.NotificationService.notify_pending_approval"), \
             patch("apps.workflow.services.workflow_service.NotificationService.notify_workflow_completed"):
            WorkflowService.approve(self.manager_user, step1, comments="Step 1 approved")

        step2 = assignment.approval_instances.filter(sequence=2).first()
        self.assertIsNotNone(step2)
        step2.refresh_from_db()
        self.assertEqual(step2.status, ApprovalInstance.Status.PENDING)

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, WorkflowAssignment.Status.PENDING)
        self.assertEqual(assignment.current_step_sequence, 2)


# ---------------------------------------------------------------------------
# can_act / permission tests
# ---------------------------------------------------------------------------

class CanActTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Act-Dept", code="ACD")
        self.assigned_user = make_user("assigned@test.com", role=User.Role.HR)
        make_employee(self.assigned_user, "EMP-ACT", self.dept)

        self.other_user = make_user("other@test.com", role=User.Role.EMPLOYEE)
        make_employee(self.other_user, "EMP-OTH", self.dept)

        self.admin_user = make_user("admin@test.com", role=User.Role.ADMIN)

        emp_user = make_user("actlemp@test.com")
        employee = make_employee(emp_user, "EMP-ACTL", self.dept)

        LeavePolicy.objects.get_or_create(pk=1)

        leave = make_leave_request(employee)
        wf = Workflow.objects.create(
            name="Act WF",
            module=Workflow.Module.LEAVE_REQUEST,
            is_active=True,
            priority=1,
            condition_operator=Workflow.ConditionOperator.ALWAYS,
        )
        step = WorkflowStep.objects.create(
            workflow=wf,
            name="HR Step",
            sequence=1,
            assignment_type=WorkflowStep.AssignmentType.ROLE,
            role=User.Role.HR,
        )
        wa = WorkflowAssignment.objects.create(
            workflow=wf,
            module=Workflow.Module.LEAVE_REQUEST,
            requested_by=emp_user,
            content_type=__import__("django.contrib.contenttypes.models", fromlist=["ContentType"]).ContentType.objects.get_for_model(leave.__class__),
            object_id=leave.pk,
        )
        self.approval = ApprovalInstance.objects.create(
            workflow_assignment=wa,
            step=step,
            sequence=1,
            assigned_user=self.assigned_user,
            assigned_role=User.Role.HR,
            status=ApprovalInstance.Status.PENDING,
        )

    def test_assigned_user_can_act(self):
        self.assertTrue(WorkflowService.can_user_act_on_approval(self.assigned_user, self.approval))

    def test_other_user_cannot_act(self):
        self.assertFalse(WorkflowService.can_user_act_on_approval(self.other_user, self.approval))

    def test_admin_can_override(self):
        self.assertTrue(WorkflowService.can_user_act_on_approval(self.admin_user, self.approval))

    def test_already_approved_instance_cannot_be_acted_on(self):
        self.approval.status = ApprovalInstance.Status.APPROVED
        self.approval.save(update_fields=["status", "updated_at"])
        self.assertFalse(WorkflowService.can_user_act_on_approval(self.assigned_user, self.approval))


# ---------------------------------------------------------------------------
# Role-based assignment tests
# ---------------------------------------------------------------------------

class RoleBasedAssignmentTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Role-Dept", code="RLD")

        # Create an HR user — they should be the assignee for ROLE=HR steps
        self.hr_user = make_user("role-hr@test.com", role=User.Role.HR)
        self.hr_emp = make_employee(self.hr_user, "EMP-RHR", self.dept)

        self.emp_user = make_user("role-emp@test.com")
        self.employee = make_employee(self.emp_user, "EMP-REMP", self.dept)

        LeavePolicy.objects.get_or_create(pk=1)

        # Explicit single-step ROLE workflow
        self.role_wf = Workflow.objects.create(
            name="Role WF",
            module=Workflow.Module.LEAVE_REQUEST,
            is_active=True,
            priority=1,
            condition_operator=Workflow.ConditionOperator.ALWAYS,
        )
        WorkflowStep.objects.create(
            workflow=self.role_wf,
            name="HR Step",
            sequence=1,
            assignment_type=WorkflowStep.AssignmentType.ROLE,
            role=User.Role.HR,
        )

    def test_role_step_assigned_to_hr_user(self):
        leave = make_leave_request(self.employee)
        with patch("apps.workflow.services.workflow_service.NotificationService.notify_pending_approval"):
            assignment = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST, leave, requested_by=self.emp_user
            )
        pending = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING).first()
        self.assertIsNotNone(pending)
        self.assertEqual(pending.assigned_user, self.hr_user)
        self.assertEqual(pending.assigned_role, User.Role.HR)


# ---------------------------------------------------------------------------
# Primary-manager assignment tests
# ---------------------------------------------------------------------------

class PrimaryManagerAssignmentTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="PM-Dept", code="PMD")

        self.manager_user = make_user("pm-mgr@test.com", role=User.Role.MANAGER)
        self.manager_emp = make_employee(self.manager_user, "EMP-PMM", self.dept)

        self.emp_user = make_user("pm-emp@test.com")
        self.employee = make_employee(self.emp_user, "EMP-PMEMP", self.dept, manager=self.manager_emp)

        LeavePolicy.objects.get_or_create(pk=1)

        # Explicit single-step PRIMARY_MANAGER workflow
        self.pm_wf = Workflow.objects.create(
            name="PM WF",
            module=Workflow.Module.LEAVE_REQUEST,
            is_active=True,
            priority=1,
            condition_operator=Workflow.ConditionOperator.ALWAYS,
        )
        WorkflowStep.objects.create(
            workflow=self.pm_wf,
            name="Manager Approval",
            sequence=1,
            assignment_type=WorkflowStep.AssignmentType.PRIMARY_MANAGER,
        )

    def test_primary_manager_step_assigned_to_manager(self):
        leave = make_leave_request(self.employee)
        with patch("apps.workflow.services.workflow_service.NotificationService.notify_pending_approval"):
            assignment = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST, leave, requested_by=self.emp_user
            )
        pending = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING).first()
        self.assertIsNotNone(pending)
        self.assertEqual(pending.assigned_user, self.manager_user)


# ---------------------------------------------------------------------------
# WorkflowAssignment status reflects overall outcome
# ---------------------------------------------------------------------------

class AssignmentStatusTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Stat-Dept", code="STD")
        self.hr_user = make_user("stat-hr@test.com", role=User.Role.HR)
        self.hr_emp = make_employee(self.hr_user, "EMP-STHR", self.dept)
        self.emp_user = make_user("stat-emp@test.com")
        self.employee = make_employee(self.emp_user, "EMP-STEMP", self.dept)
        LeavePolicy.objects.get_or_create(pk=1)

        wf = Workflow.objects.create(
            name="Stat WF",
            module=Workflow.Module.LEAVE_REQUEST,
            is_active=True,
            priority=1,
            condition_operator=Workflow.ConditionOperator.ALWAYS,
        )
        WorkflowStep.objects.create(
            workflow=wf,
            name="HR Step",
            sequence=1,
            assignment_type=WorkflowStep.AssignmentType.ROLE,
            role=User.Role.HR,
        )

    def test_assignment_status_is_pending_initially(self):
        leave = make_leave_request(self.employee)
        with patch("apps.workflow.services.workflow_service.NotificationService.notify_pending_approval"):
            assignment = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST, leave, requested_by=self.emp_user
            )
        self.assertEqual(assignment.status, WorkflowAssignment.Status.PENDING)

    def test_assignment_status_becomes_rejected_on_rejection(self):
        leave = make_leave_request(self.employee)
        with patch("apps.workflow.services.workflow_service.NotificationService.notify_pending_approval"):
            assignment = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST, leave, requested_by=self.emp_user
            )

        pending = assignment.approval_instances.filter(status=ApprovalInstance.Status.PENDING).first()
        self.assertIsNotNone(pending)
        pending.assigned_user = self.hr_user
        pending.save(update_fields=["assigned_user", "updated_at"])

        with patch("apps.workflow.services.workflow_service.NotificationService.notify_workflow_completed"), \
             patch("apps.leave_management.services.leave_service.LeaveRequestService.finalize_workflow_rejection"):
            WorkflowService.reject(self.hr_user, pending)

        assignment.refresh_from_db()
        self.assertEqual(assignment.status, WorkflowAssignment.Status.REJECTED)


class WorkflowOrganizationScopingTest(TestCase):
    def setUp(self):
        self.org_one = Organization.objects.create(name="Workflow Org One", code="WORG1", slug="workflow-org-one")
        self.org_two = Organization.objects.create(name="Workflow Org Two", code="WORG2", slug="workflow-org-two")
        self.dept_one = Department.objects.create(name="WF Org1 Dept", code="WF1", organization=self.org_one)
        self.dept_two = Department.objects.create(name="WF Org2 Dept", code="WF2", organization=self.org_two)

        self.hr_org_one = make_user("wf-org1-hr@test.com", role=User.Role.HR, organization=self.org_one)
        self.hr_org_two = make_user("wf-org2-hr@test.com", role=User.Role.HR, organization=self.org_two)
        self.employee_user = make_user("wf-org2-emp@test.com", organization=self.org_two)

        self.hr_emp_one = make_employee(self.hr_org_one, "WF-O1-HR", self.dept_one, organization=self.org_one)
        self.hr_emp_two = make_employee(self.hr_org_two, "WF-O2-HR", self.dept_two, organization=self.org_two)
        self.employee = make_employee(self.employee_user, "WF-O2-EMP", self.dept_two, organization=self.org_two)

        LeavePolicy.objects.get_or_create(organization=self.org_two)

        self.org_one_workflow = Workflow.objects.create(
            organization=self.org_one,
            name="Org One Leave Workflow",
            module=Workflow.Module.LEAVE_REQUEST,
            is_active=True,
            priority=1,
            condition_operator=Workflow.ConditionOperator.ALWAYS,
        )
        WorkflowStep.objects.create(
            organization=self.org_one,
            workflow=self.org_one_workflow,
            name="Org One HR Step",
            sequence=1,
            assignment_type=WorkflowStep.AssignmentType.ROLE,
            role=User.Role.HR,
        )

        self.org_two_workflow = Workflow.objects.create(
            organization=self.org_two,
            name="Org Two Leave Workflow",
            module=Workflow.Module.LEAVE_REQUEST,
            is_active=True,
            priority=1,
            condition_operator=Workflow.ConditionOperator.ALWAYS,
        )
        WorkflowStep.objects.create(
            organization=self.org_two,
            workflow=self.org_two_workflow,
            name="Org Two HR Step",
            sequence=1,
            assignment_type=WorkflowStep.AssignmentType.ROLE,
            role=User.Role.HR,
        )

    def test_start_workflow_selects_current_org_workflow_and_propagates_org(self):
        leave = make_leave_request(self.employee)
        leave.organization = self.org_two
        leave.save(update_fields=["organization", "updated_at"])

        with patch("apps.workflow.services.workflow_service.NotificationService.notify_pending_approval"):
            assignment = WorkflowService.start_workflow(
                Workflow.Module.LEAVE_REQUEST,
                leave,
                requested_by=self.employee_user,
            )

        pending = assignment.approval_instances.get(status=ApprovalInstance.Status.PENDING)
        self.assertEqual(assignment.organization, self.org_two)
        self.assertEqual(assignment.workflow, self.org_two_workflow)
        self.assertEqual(pending.organization, self.org_two)
        self.assertEqual(pending.assigned_user, self.hr_org_two)

        with patch("apps.workflow.services.workflow_service.NotificationService.notify_workflow_completed"), patch(
            "apps.leave_management.services.leave_service.LeaveRequestService.finalize_workflow_approval"
        ):
            WorkflowService.approve(self.hr_org_two, pending, comments="Approved in org two")

        action = pending.actions.order_by("-id").first()
        self.assertIsNotNone(action)
        self.assertEqual(action.organization, self.org_two)
