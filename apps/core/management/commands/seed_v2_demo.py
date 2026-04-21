from __future__ import annotations

from calendar import monthrange
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.analytics.services.analytics_service import AnalyticsService
from apps.announcements.models import Announcement
from apps.announcements.services.announcement_service import AnnouncementService
from apps.attendance.models import Attendance, AttendanceRegularization
from apps.attendance.services.regularization_service import AttendanceRegularizationService
from apps.documents.models import DocumentType, EmployeeDocument, MandatoryDocumentRule
from apps.documents.services.document_service import EmployeeDocumentService
from apps.employees.models import Department, Employee, OrganizationSettings, ShiftTemplate
from apps.helpdesk.models import HelpdeskCategory, HelpdeskTicket
from apps.helpdesk.services.helpdesk_service import HelpdeskService
from apps.holidays.models import Holiday, HolidayCalendar
from apps.holidays.services.holiday_service import HolidayService
from apps.leave_management.models import EarnedLeaveAdjustment, LeaveBalance, LeavePolicy, LeaveRequest
from apps.leave_management.services.leave_service import EarnedLeaveAdjustmentService, LeavePolicyService, LeaveRequestService
from apps.lifecycle.models import EmployeeChangeRequest, EmployeeOnboarding, OffboardingCase, OnboardingPlan, OnboardingTaskTemplate
from apps.lifecycle.services.lifecycle_service import EmployeeChangeRequestService, EmployeeOnboardingService, OffboardingService
from apps.payroll.models import PayrollAdjustment, PayrollCycle, PayrollRun, SalaryComponent, SalaryComponentTemplate, SalaryRevision
from apps.payroll.services.payroll_governance_service import PayrollGovernanceService, SalaryRevisionService
from apps.performance.models import PerformanceCycle, PerformanceGoal, PerformanceReview, RatingScale
from apps.performance.services.performance_service import PerformanceGoalService, PerformanceReviewService
from apps.policy_engine.models import PolicyRule
from apps.policy_engine.services.policy_rule_service import PolicyRuleService
from apps.scheduling.models import ShiftRotationRule
from apps.scheduling.services.scheduling_service import SchedulingService
from apps.workflow.models import Workflow
from apps.workflow.services.workflow_service import WorkflowService


class Command(BaseCommand):
    help = "Seed comprehensive Version 2 HRMS demo data, including workflow-backed approvals."

    demo_users = [
        {
            "email": "teamlead@atmispace.com",
            "password": "TeamLead@123",
            "first_name": "Ishita",
            "last_name": "K",
            "role": User.Role.EMPLOYEE,
            "employee_id": "EMP007",
            "designation": "Senior Software Engineer",
            "department_code": "ENG",
            "department_role": Employee.DepartmentRole.TEAM_LEAD,
            "hire_date": "2022-08-01",
            "shift_name": "Morning",
            "ctc_per_annum": Decimal("1080000.00"),
        },
        {
            "email": "newhire@atmispace.com",
            "password": "NewHire@123",
            "first_name": "Neha",
            "last_name": "M",
            "role": User.Role.EMPLOYEE,
            "employee_id": "EMP008",
            "designation": "Associate Software Engineer",
            "department_code": "ENG",
            "department_role": Employee.DepartmentRole.MEMBER,
            "hire_date": "2026-03-25",
            "shift_name": "Morning",
            "ctc_per_annum": Decimal("540000.00"),
        },
        {
            "email": "departing@atmispace.com",
            "password": "Departing@123",
            "first_name": "Rahul",
            "last_name": "P",
            "role": User.Role.EMPLOYEE,
            "employee_id": "EMP009",
            "designation": "Support Engineer",
            "department_code": "OPS",
            "department_role": Employee.DepartmentRole.MEMBER,
            "hire_date": "2024-04-10",
            "shift_name": "Night",
            "ctc_per_annum": Decimal("660000.00"),
        },
    ]

    def handle(self, *args, **options):
        call_command("seed_mvp")

        today = timezone.localdate()
        context = self._build_context()
        self._ensure_organization_settings()
        leave_policy = self._ensure_leave_policy()
        self._ensure_demo_users(context)
        self._ensure_reporting_lines(context)
        self._ensure_leave_balances(context, leave_policy)
        holiday_calendar = self._ensure_holidays(context, today)
        self._ensure_policy_rules(context)
        self._ensure_documents(context, today)
        self._ensure_announcements(context)
        self._ensure_helpdesk(context)
        self._ensure_leave_requests_and_adjustments(context, today)
        self._ensure_attendance_and_regularizations(context, today)
        self._ensure_performance(context, today)
        offboarding_case = self._ensure_lifecycle(context, today)
        self._ensure_scheduling(context, holiday_calendar, offboarding_case, today)
        self._ensure_payroll(context, today)
        AnalyticsService.refresh_snapshots(snapshot_date=today)
        self._print_summary(context)

    def _build_context(self):
        return {
            "departments": {department.code: department for department in Department.objects.all()},
            "shifts": {shift.name: shift for shift in ShiftTemplate.objects.all()},
            "users": {user.email: user for user in User.objects.select_related("employee_profile")},
            "employees": {
                employee.user.email: employee
                for employee in Employee.objects.select_related("user", "manager", "secondary_manager", "department", "shift_template")
            },
        }

    def _refresh_context(self, context):
        context.update(self._build_context())

    def _ensure_organization_settings(self):
        settings, _ = OrganizationSettings.objects.get_or_create(
            pk=1,
            defaults={
                "organization_name": "Atmispace Labs",
                "company_policies": "Remote-friendly engineering culture, workflow-backed approvals, payroll governance, and compliance tracking.",
            },
        )
        settings.organization_name = "Atmispace Labs"
        settings.company_policies = (
            "Remote-friendly engineering culture, workflow-backed approvals, payroll governance, "
            "compliance checks, and structured onboarding/offboarding."
        )
        settings.save(update_fields=["organization_name", "company_policies", "updated_at"])

    def _ensure_leave_policy(self):
        return LeavePolicyService.update_policy(
            {
                "casual_days_onboarding": Decimal("12.0"),
                "sick_days_onboarding": Decimal("8.0"),
                "earned_days_onboarding": Decimal("6.0"),
                "monthly_sick_leave_limit": Decimal("2.0"),
                "monthly_earned_leave_limit": Decimal("1.0"),
                "compensate_with_earned_leave": True,
                "excess_leave_becomes_lop": True,
            }
        )

    def _ensure_demo_users(self, context):
        for record in self.demo_users:
            department = context["departments"][record["department_code"]]
            shift_template = context["shifts"][record["shift_name"]]

            user, created = User.objects.get_or_create(
                email=record["email"],
                defaults={
                    "first_name": record["first_name"],
                    "last_name": record["last_name"],
                    "role": record["role"],
                    "is_staff": record["role"] == User.Role.ADMIN,
                },
            )
            if created or not user.check_password(record["password"]):
                user.set_password(record["password"])
            user.first_name = record["first_name"]
            user.last_name = record["last_name"]
            user.role = record["role"]
            user.is_staff = record["role"] == User.Role.ADMIN
            user.save()

            Employee.objects.update_or_create(
                user=user,
                defaults={
                    "employee_id": record["employee_id"],
                    "designation": record["designation"],
                    "department": department,
                    "hire_date": record["hire_date"],
                    "employment_type": Employee.EmploymentType.FULL_TIME,
                    "department_role": record["department_role"],
                    "shift_template": shift_template,
                    "shift_name": shift_template.name,
                    "shift_start_time": shift_template.start_time,
                    "shift_end_time": shift_template.end_time,
                    "ctc_per_annum": record["ctc_per_annum"],
                    "phone_number": "+91-9000000000",
                    "address": "Bengaluru, India",
                    "emergency_contact_name": "Demo Contact",
                    "emergency_contact_phone": "+91-9111111111",
                    "is_active": True,
                },
            )

        self._refresh_context(context)

    def _ensure_reporting_lines(self, context):
        manager = context["employees"]["manager@atmispace.com"]
        team_lead = context["employees"]["teamlead@atmispace.com"]

        relations = {
            "teamlead@atmispace.com": (manager, None),
            "employee@atmispace.com": (manager, team_lead),
            "ops@atmispace.com": (manager, team_lead),
            "newhire@atmispace.com": (manager, team_lead),
            "departing@atmispace.com": (manager, team_lead),
        }
        for email, (primary_manager, secondary_manager) in relations.items():
            employee = context["employees"][email]
            employee.manager = primary_manager
            employee.secondary_manager = secondary_manager
            employee.save(update_fields=["manager", "secondary_manager", "updated_at"])

        self._refresh_context(context)

    def _ensure_leave_balances(self, context, leave_policy):
        default_allocations = {
            LeaveBalance.LeaveType.CASUAL: leave_policy.casual_days_onboarding,
            LeaveBalance.LeaveType.SICK: leave_policy.sick_days_onboarding,
            LeaveBalance.LeaveType.EARNED: leave_policy.earned_days_onboarding,
            LeaveBalance.LeaveType.LOP: Decimal("0.0"),
        }
        for employee in context["employees"].values():
            for leave_type, allocated_days in default_allocations.items():
                LeaveBalance.objects.update_or_create(
                    employee=employee,
                    leave_type=leave_type,
                    defaults={"allocated_days": allocated_days, "used_days": Decimal("0.0")},
                )

    def _ensure_holidays(self, context, today):
        calendar, _ = HolidayCalendar.objects.get_or_create(
            name="India Default Calendar",
            defaults={
                "country_code": "IN",
                "description": "Default Indian holiday calendar for demo employees.",
                "is_default": True,
            },
        )
        calendar.country_code = "IN"
        calendar.description = "Default Indian holiday calendar for demo employees."
        calendar.is_default = True
        calendar.save(update_fields=["country_code", "description", "is_default", "updated_at"])

        holidays = [
            ("Founders Day", today + timedelta(days=3), False),
            ("Quarterly Recharge Day", today + timedelta(days=16), True),
            ("Republic Day", today.replace(month=1, day=26), False),
        ]
        for name, holiday_date, is_optional in holidays:
            Holiday.objects.update_or_create(
                calendar=calendar,
                date=holiday_date,
                name=name,
                defaults={"is_optional": is_optional},
            )

        for employee in context["employees"].values():
            HolidayService.assign_calendar(employee, calendar)

        return calendar

    def _ensure_policy_rules(self, context):
        actor = context["users"]["admin@atmispace.com"]
        rules = [
            {
                "name": "Demo leave request logging",
                "module": PolicyRule.Module.LEAVE,
                "description": "Capture demo leave policy evaluations for request flows.",
                "priority": 10,
                "condition_field": "",
                "condition_operator": PolicyRule.Operator.ALWAYS,
                "condition_value": None,
                "effect_type": PolicyRule.EffectType.WARN,
                "effect_message": "Leave request evaluated by the demo policy engine.",
            },
            {
                "name": "Demo attendance regularization logging",
                "module": PolicyRule.Module.ATTENDANCE,
                "description": "Capture regularization policy evaluations for demo flows.",
                "priority": 10,
                "condition_field": "",
                "condition_operator": PolicyRule.Operator.ALWAYS,
                "condition_value": None,
                "effect_type": PolicyRule.EffectType.FLAG,
                "effect_message": "Attendance regularization evaluated by the demo policy engine.",
            },
            {
                "name": "Pending document verification warning",
                "module": PolicyRule.Module.COMPLIANCE,
                "description": "Flag uploaded documents that still require verification.",
                "priority": 10,
                "condition_field": "status",
                "condition_operator": PolicyRule.Operator.EQUALS,
                "condition_value": EmployeeDocument.Status.PENDING,
                "effect_type": PolicyRule.EffectType.WARN,
                "effect_message": "Document requires verification before the employee is fully compliant.",
            },
            {
                "name": "Lifecycle governance logging",
                "module": PolicyRule.Module.LIFECYCLE,
                "description": "Track lifecycle policy checks during offboarding and employee changes.",
                "priority": 10,
                "condition_field": "",
                "condition_operator": PolicyRule.Operator.ALWAYS,
                "condition_value": None,
                "effect_type": PolicyRule.EffectType.FLAG,
                "effect_message": "Lifecycle case evaluated by the demo policy engine.",
            },
            {
                "name": "Payroll governance readiness check",
                "module": PolicyRule.Module.PAYROLL,
                "description": "Track payroll cycle evaluations before run generation.",
                "priority": 10,
                "condition_field": "",
                "condition_operator": PolicyRule.Operator.ALWAYS,
                "condition_value": None,
                "effect_type": PolicyRule.EffectType.WARN,
                "effect_message": "Payroll cycle evaluated by the demo policy engine.",
            },
        ]
        for rule_data in rules:
            rule, created = PolicyRule.objects.get_or_create(
                name=rule_data["name"],
                module=rule_data["module"],
                defaults=rule_data,
            )
            if not created:
                PolicyRuleService.update_rule(rule, rule_data, actor)

    def _ensure_documents(self, context, today):
        hr_user = context["users"]["hr@atmispace.com"]
        eng_department = context["departments"]["ENG"]

        document_types = {
            "PAN Card": {"category": "Identity", "requires_expiry": False, "is_mandatory_default": True},
            "Aadhaar Card": {"category": "Identity", "requires_expiry": False, "is_mandatory_default": True},
            "Passport": {"category": "Travel", "requires_expiry": True, "is_mandatory_default": False},
        }
        for name, config in document_types.items():
            DocumentType.objects.update_or_create(
                name=name,
                defaults={
                    "category": config["category"],
                    "description": f"{name} document requirement for the demo tenant.",
                    "requires_expiry": config["requires_expiry"],
                    "is_mandatory_default": config["is_mandatory_default"],
                    "is_active": True,
                },
            )

        for rule_name, document_name, due_days in (
            ("Engineering PAN collection", "PAN Card", 2),
            ("Engineering Aadhaar collection", "Aadhaar Card", 2),
            ("Engineering passport reminder", "Passport", 30),
        ):
            document_type = DocumentType.objects.get(name=document_name)
            MandatoryDocumentRule.objects.update_or_create(
                name=rule_name,
                defaults={
                    "document_type": document_type,
                    "department": eng_department,
                    "employment_type": Employee.EmploymentType.FULL_TIME,
                    "due_days_from_joining": due_days,
                    "is_active": True,
                },
            )

        document_specs = [
            {
                "employee_email": "employee@atmispace.com",
                "actor_email": "employee@atmispace.com",
                "document_type": "PAN Card",
                "title": "[Demo] PAN Card Upload",
                "file_name": "employee-pan.pdf",
                "file_url": "https://example.com/demo/employee-pan.pdf",
                "issued_date": today - timedelta(days=600),
                "expiry_date": None,
                "target_status": EmployeeDocument.Status.VERIFIED,
                "remarks": "Verified as part of demo compliance setup.",
            },
            {
                "employee_email": "newhire@atmispace.com",
                "actor_email": "newhire@atmispace.com",
                "document_type": "Aadhaar Card",
                "title": "[Demo] Aadhaar Pending Verification",
                "file_name": "newhire-aadhaar.pdf",
                "file_url": "https://example.com/demo/newhire-aadhaar.pdf",
                "issued_date": today - timedelta(days=300),
                "expiry_date": None,
                "target_status": EmployeeDocument.Status.PENDING,
                "remarks": "",
            },
            {
                "employee_email": "departing@atmispace.com",
                "actor_email": "departing@atmispace.com",
                "document_type": "Passport",
                "title": "[Demo] Passport Expiring Soon",
                "file_name": "departing-passport.pdf",
                "file_url": "https://example.com/demo/departing-passport.pdf",
                "issued_date": today - timedelta(days=800),
                "expiry_date": today + timedelta(days=20),
                "target_status": EmployeeDocument.Status.VERIFIED,
                "remarks": "Verified, but expiring soon for analytics visibility.",
            },
            {
                "employee_email": "ops@atmispace.com",
                "actor_email": "ops@atmispace.com",
                "document_type": "PAN Card",
                "title": "[Demo] PAN Re-upload Needed",
                "file_name": "ops-pan.pdf",
                "file_url": "https://example.com/demo/ops-pan.pdf",
                "issued_date": today - timedelta(days=450),
                "expiry_date": None,
                "target_status": EmployeeDocument.Status.REJECTED,
                "remarks": "Name mismatch in uploaded copy.",
            },
        ]

        for spec in document_specs:
            employee = context["employees"][spec["employee_email"]]
            actor = context["users"][spec["actor_email"]]
            document_type = DocumentType.objects.get(name=spec["document_type"])
            document = EmployeeDocument.objects.filter(employee=employee, title=spec["title"]).first()
            if not document:
                document = EmployeeDocumentService.create_document(
                    {
                        "employee": employee,
                        "document_type": document_type,
                        "title": spec["title"],
                        "file_name": spec["file_name"],
                        "file_url": spec["file_url"],
                        "issued_date": spec["issued_date"],
                        "expiry_date": spec["expiry_date"],
                        "remarks": "",
                    },
                    actor=actor,
                )
            if spec["target_status"] == EmployeeDocument.Status.VERIFIED and document.status != EmployeeDocument.Status.VERIFIED:
                EmployeeDocumentService.verify_document(hr_user, document, remarks=spec["remarks"])
            elif spec["target_status"] == EmployeeDocument.Status.REJECTED and document.status != EmployeeDocument.Status.REJECTED:
                EmployeeDocumentService.reject_document(hr_user, document, remarks=spec["remarks"])

    def _ensure_announcements(self, context):
        admin_user = context["users"]["admin@atmispace.com"]
        engineering = context["departments"]["ENG"]
        all_hands, _ = Announcement.objects.get_or_create(
            title="[Demo] Company Policy Refresh",
            defaults={
                "summary": "Please acknowledge the refreshed remote work and security policies.",
                "body": "This announcement exists to demonstrate required acknowledgement tracking.",
                "audience_type": Announcement.AudienceType.ALL,
                "created_by": admin_user,
                "starts_at": timezone.now() - timedelta(days=1),
                "ends_at": timezone.now() + timedelta(days=10),
                "show_on_dashboard": True,
                "requires_acknowledgement": True,
            },
        )
        if not all_hands.is_published:
            AnnouncementService.publish(all_hands, admin_user)

        engineering_notice, _ = Announcement.objects.get_or_create(
            title="[Demo] Engineering Roster Change",
            defaults={
                "summary": "Night support rotation has been enabled for the next sprint.",
                "body": "This announcement demonstrates department-scoped notices.",
                "audience_type": Announcement.AudienceType.DEPARTMENT,
                "department": engineering,
                "created_by": admin_user,
                "starts_at": timezone.now() - timedelta(hours=2),
                "ends_at": timezone.now() + timedelta(days=5),
                "show_on_dashboard": True,
                "requires_acknowledgement": False,
            },
        )
        if not engineering_notice.is_published:
            AnnouncementService.publish(engineering_notice, admin_user)

        AnnouncementService.acknowledge(all_hands, context["users"]["employee@atmispace.com"])
        AnnouncementService.acknowledge(all_hands, context["users"]["teamlead@atmispace.com"])

    def _ensure_helpdesk(self, context):
        categories = [
            ("HR Support", User.Role.HR, "General HR employee service requests."),
            ("Payroll Support", User.Role.ACCOUNTS, "Payroll, reimbursement, and payslip requests."),
            ("IT Admin Support", User.Role.ADMIN, "Admin-managed device and access requests."),
        ]
        for name, owner_role, description in categories:
            HelpdeskCategory.objects.update_or_create(
                name=name,
                defaults={"owner_role": owner_role, "description": description, "is_active": True},
            )

        tickets = [
            {
                "requester": "employee@atmispace.com",
                "category": "IT Admin Support",
                "subject": "[Demo] VPN access issue",
                "description": "VPN drops during deployment windows. This ticket remains open for dashboard testing.",
                "priority": HelpdeskTicket.Priority.HIGH,
                "comments": [],
                "resolve_by": None,
            },
            {
                "requester": "ops@atmispace.com",
                "category": "Payroll Support",
                "subject": "[Demo] Payslip clarification request",
                "description": "Need a breakdown of the LOP deduction on the current payroll cycle.",
                "priority": HelpdeskTicket.Priority.MEDIUM,
                "comments": [("accounts@atmispace.com", "Reviewing the payroll register now.", False)],
                "resolve_by": "accounts@atmispace.com",
            },
            {
                "requester": "newhire@atmispace.com",
                "category": "HR Support",
                "subject": "[Demo] Onboarding policy acknowledgement question",
                "description": "Need clarification on the remote reimbursement policy during onboarding.",
                "priority": HelpdeskTicket.Priority.LOW,
                "comments": [("hr@atmispace.com", "Adding the reimbursement policy summary here for reference.", False)],
                "resolve_by": None,
            },
        ]

        for spec in tickets:
            requester = context["employees"][spec["requester"]]
            category = HelpdeskCategory.objects.get(name=spec["category"])
            ticket = HelpdeskTicket.objects.filter(requester=requester, subject=spec["subject"]).first()
            if not ticket:
                ticket = HelpdeskService.create_ticket(
                    {
                        "requester": requester,
                        "category": category,
                        "subject": spec["subject"],
                        "description": spec["description"],
                        "priority": spec["priority"],
                    },
                    actor=requester.user,
                )
            for author_email, message, is_internal in spec["comments"]:
                if not ticket.comments.filter(message=message).exists():
                    HelpdeskService.add_comment(ticket, context["users"][author_email], message, is_internal=is_internal)
            if spec["resolve_by"] and ticket.status != HelpdeskTicket.Status.RESOLVED:
                HelpdeskService.resolve(ticket, context["users"][spec["resolve_by"]], resolution_notes="Resolved in demo seed.")

    def _ensure_leave_requests_and_adjustments(self, context, today):
        manager_user = context["users"]["manager@atmispace.com"]
        team_lead_user = context["users"]["teamlead@atmispace.com"]
        hr_user = context["users"]["hr@atmispace.com"]

        leave_specs = [
            {
                "employee_email": "employee@atmispace.com",
                "leave_type": LeaveBalance.LeaveType.CASUAL,
                "duration_type": LeaveRequest.DurationType.FULL_DAY,
                "start_date": today + timedelta(days=6),
                "end_date": today + timedelta(days=7),
                "reason": "[Demo] Family travel pending manager",
                "advance_to": "MANAGER_PENDING",
            },
            {
                "employee_email": "newhire@atmispace.com",
                "leave_type": LeaveBalance.LeaveType.SICK,
                "duration_type": LeaveRequest.DurationType.FULL_DAY,
                "start_date": today + timedelta(days=12),
                "end_date": today + timedelta(days=12),
                "reason": "[Demo] Medical leave pending secondary manager",
                "advance_to": "SECONDARY_PENDING",
            },
            {
                "employee_email": "ops@atmispace.com",
                "leave_type": LeaveBalance.LeaveType.EARNED,
                "duration_type": LeaveRequest.DurationType.FULL_DAY,
                "start_date": today + timedelta(days=18),
                "end_date": today + timedelta(days=18),
                "reason": "[Demo] Earned leave pending HR",
                "advance_to": "HR_PENDING",
            },
            {
                "employee_email": "departing@atmispace.com",
                "leave_type": LeaveBalance.LeaveType.LOP,
                "duration_type": LeaveRequest.DurationType.FULL_DAY,
                "start_date": today - timedelta(days=6),
                "end_date": today - timedelta(days=5),
                "reason": "[Demo] Approved LOP for payroll test",
                "advance_to": "APPROVED",
            },
        ]

        for spec in leave_specs:
            employee_user = context["users"][spec["employee_email"]]
            leave_request = LeaveRequest.objects.filter(
                employee=employee_user.employee_profile,
                reason=spec["reason"],
                start_date=spec["start_date"],
                end_date=spec["end_date"],
            ).first()
            if not leave_request:
                leave_request = LeaveRequestService.apply_leave(
                    employee_user,
                    {
                        "leave_type": spec["leave_type"],
                        "duration_type": spec["duration_type"],
                        "start_date": spec["start_date"],
                        "end_date": spec["end_date"],
                        "reason": spec["reason"],
                    },
                )
                PolicyRuleService.evaluate("LEAVE", leave_request, actor=employee_user, persist=True, raise_on_block=False)

            self._progress_leave_request(leave_request, spec["advance_to"], manager_user, team_lead_user, hr_user)

        adjustment_specs = [
            {
                "employee_email": "employee@atmispace.com",
                "work_date": self._previous_weekend(today, offset=0),
                "days": Decimal("1.0"),
                "reason": "[Demo] Weekend deployment support",
                "approve_by": "manager@atmispace.com",
            },
            {
                "employee_email": "newhire@atmispace.com",
                "work_date": self._previous_weekend(today, offset=1),
                "days": Decimal("0.5"),
                "reason": "[Demo] Weekend onboarding support",
                "approve_by": None,
            },
        ]
        for spec in adjustment_specs:
            actor = context["users"][spec["employee_email"]]
            adjustment = EarnedLeaveAdjustment.objects.filter(
                employee=actor.employee_profile,
                work_date=spec["work_date"],
                reason=spec["reason"],
            ).first()
            if not adjustment:
                adjustment = EarnedLeaveAdjustmentService.apply_adjustment(
                    actor,
                    {"work_date": spec["work_date"], "days": spec["days"], "reason": spec["reason"]},
                )
            if spec["approve_by"] and adjustment.status == EarnedLeaveAdjustment.Status.PENDING:
                EarnedLeaveAdjustmentService.approve_adjustment(
                    context["users"][spec["approve_by"]],
                    adjustment,
                    approver_note="Approved via demo seed.",
                )

    def _progress_leave_request(self, leave_request, target_state, manager_user, team_lead_user, hr_user):
        if leave_request.status != LeaveRequest.Status.PENDING:
            return

        assignment = WorkflowService.get_assignment_for_object(Workflow.Module.LEAVE_REQUEST, leave_request)
        if not assignment:
            return

        pending = WorkflowService.get_pending_approval_for_assignment(assignment)
        if target_state == "MANAGER_PENDING" or not pending:
            return

        if target_state in {"SECONDARY_PENDING", "HR_PENDING", "APPROVED"} and pending.sequence == 1:
            LeaveRequestService.approve_leave(manager_user, leave_request, approver_note="Manager approved in demo seed.")
            leave_request.refresh_from_db()
            assignment = WorkflowService.get_assignment_for_object(Workflow.Module.LEAVE_REQUEST, leave_request)
            pending = WorkflowService.get_pending_approval_for_assignment(assignment)

        if target_state in {"HR_PENDING", "APPROVED"} and pending and pending.sequence == 2:
            LeaveRequestService.approve_leave(team_lead_user, leave_request, approver_note="Secondary manager approved in demo seed.")
            leave_request.refresh_from_db()
            assignment = WorkflowService.get_assignment_for_object(Workflow.Module.LEAVE_REQUEST, leave_request)
            pending = WorkflowService.get_pending_approval_for_assignment(assignment)

        if target_state == "APPROVED" and pending and pending.sequence == 3:
            LeaveRequestService.approve_leave(hr_user, leave_request, approver_note="HR approved in demo seed.")

    def _ensure_attendance_and_regularizations(self, context, today):
        engineer = context["employees"]["employee@atmispace.com"]
        overtime_date = today - timedelta(days=4)
        check_in = timezone.make_aware(datetime.combine(overtime_date, time(hour=9)))
        check_out = timezone.make_aware(datetime.combine(overtime_date, time(hour=20, minute=30)))
        Attendance.objects.update_or_create(
            employee=engineer,
            attendance_date=overtime_date,
            defaults={
                "check_in": check_in,
                "check_out": check_out,
                "current_session_check_in": None,
                "break_started_at": None,
                "break_minutes": 45,
                "current_session_break_minutes": 0,
                "status": Attendance.Status.PRESENT,
                "notes": "Seeded overtime attendance for analytics.",
                "total_work_minutes": int((check_out - check_in).total_seconds() // 60) - 45,
            },
        )

        regularization_specs = [
            {
                "employee_email": "employee@atmispace.com",
                "date": today - timedelta(days=8),
                "reason": "[Demo] Missed punch pending manager",
                "requested_check_in": time(hour=10, minute=5),
                "requested_check_out": time(hour=19, minute=15),
                "approve_by": None,
            },
            {
                "employee_email": "newhire@atmispace.com",
                "date": today - timedelta(days=9),
                "reason": "[Demo] Missed punch approved",
                "requested_check_in": time(hour=9, minute=15),
                "requested_check_out": time(hour=18, minute=10),
                "approve_by": "manager@atmispace.com",
            },
        ]
        for spec in regularization_specs:
            actor = context["users"][spec["employee_email"]]
            requested_check_in = timezone.make_aware(datetime.combine(spec["date"], spec["requested_check_in"]))
            requested_check_out = timezone.make_aware(datetime.combine(spec["date"], spec["requested_check_out"]))
            regularization = AttendanceRegularization.objects.filter(
                employee=actor.employee_profile,
                date=spec["date"],
                reason=spec["reason"],
            ).first()
            if not regularization:
                regularization = AttendanceRegularizationService.apply_regularization(
                    actor,
                    {
                        "date": spec["date"],
                        "requested_check_in": requested_check_in,
                        "requested_check_out": requested_check_out,
                        "reason": spec["reason"],
                    },
                )
                PolicyRuleService.evaluate("ATTENDANCE", regularization, actor=actor, persist=True, raise_on_block=False)
            if spec["approve_by"] and regularization.status == AttendanceRegularization.Status.PENDING:
                AttendanceRegularizationService.approve_regularization(
                    context["users"][spec["approve_by"]],
                    regularization,
                    approver_note="Approved via demo seed.",
                )

    def _ensure_performance(self, context, today):
        hr_user = context["users"]["hr@atmispace.com"]
        manager_user = context["users"]["manager@atmispace.com"]

        scale, _ = RatingScale.objects.get_or_create(
            name="Five Point Scale",
            defaults={
                "min_rating": Decimal("1.0"),
                "max_rating": Decimal("5.0"),
                "labels": ["Needs Improvement", "Developing", "Meets Expectations", "Strong", "Outstanding"],
                "is_active": True,
            },
        )
        cycle, _ = PerformanceCycle.objects.get_or_create(
            name="FY26 Mid-Year Review",
            defaults={
                "description": "Version 2 demo performance cycle.",
                "start_date": today.replace(month=1, day=1),
                "end_date": today.replace(month=6, day=30),
                "self_review_due_date": today + timedelta(days=7),
                "manager_review_due_date": today + timedelta(days=14),
                "hr_review_due_date": today + timedelta(days=21),
                "status": PerformanceCycle.Status.ACTIVE,
                "rating_scale": scale,
            },
        )
        if cycle.rating_scale_id != scale.id or cycle.status != PerformanceCycle.Status.ACTIVE:
            cycle.rating_scale = scale
            cycle.status = PerformanceCycle.Status.ACTIVE
            cycle.save(update_fields=["rating_scale", "status", "updated_at"])

        goal_specs = [
            ("employee@atmispace.com", PerformanceGoal.Category.KPI, "[Demo] API latency improvement", "Reduce P95 API latency to < 180ms", "35%", Decimal("40.00")),
            ("newhire@atmispace.com", PerformanceGoal.Category.GOAL, "[Demo] Complete onboarding sprint", "Ship first feature PR and close onboarding plan", "60%", Decimal("30.00")),
            ("ops@atmispace.com", PerformanceGoal.Category.KRA, "[Demo] Operations SLA adherence", "Maintain 98% on-time operations SLA", "92%", Decimal("30.00")),
        ]
        for email, category, title, target_value, progress_value, weight in goal_specs:
            employee = context["employees"][email]
            goal = PerformanceGoal.objects.filter(cycle=cycle, employee=employee, title=title).first()
            payload = {
                "cycle": cycle,
                "employee": employee,
                "category": category,
                "title": title,
                "description": title,
                "target_value": target_value,
                "progress_value": progress_value,
                "weight": weight,
                "status": PerformanceGoal.Status.ACTIVE,
            }
            if goal:
                PerformanceGoalService.update_goal(goal, payload, actor=manager_user)
            else:
                PerformanceGoalService.create_goal(payload, actor=manager_user)

        self._seed_performance_review(
            review=PerformanceReviewService.ensure_review(cycle, context["employees"]["employee@atmispace.com"]),
            employee_user=context["users"]["employee@atmispace.com"],
            manager_user=manager_user,
            hr_user=hr_user,
            target_state="MANAGER_PENDING",
        )
        self._seed_performance_review(
            review=PerformanceReviewService.ensure_review(cycle, context["employees"]["newhire@atmispace.com"]),
            employee_user=context["users"]["newhire@atmispace.com"],
            manager_user=manager_user,
            hr_user=hr_user,
            target_state="HR_PENDING",
        )
        self._seed_performance_review(
            review=PerformanceReviewService.ensure_review(cycle, context["employees"]["ops@atmispace.com"]),
            employee_user=context["users"]["ops@atmispace.com"],
            manager_user=manager_user,
            hr_user=hr_user,
            target_state="COMPLETED",
        )

    def _seed_performance_review(self, review, employee_user, manager_user, hr_user, target_state):
        if review.status == PerformanceReview.Status.SELF_PENDING:
            PerformanceReviewService.submit_self_review(
                employee_user,
                review,
                {
                    "self_summary": f"{review.employee.user.full_name} submitted the demo self review for {review.cycle.name}.",
                    "self_rating": Decimal("4.0"),
                },
            )
            review.refresh_from_db()

        if target_state in {"HR_PENDING", "COMPLETED"} and review.status == PerformanceReview.Status.MANAGER_PENDING:
            PerformanceReviewService.submit_manager_review(
                manager_user,
                review,
                {
                    "manager_summary": "Manager calibration completed during demo seeding.",
                    "manager_rating": Decimal("4.2"),
                },
            )
            review.refresh_from_db()

        if target_state == "COMPLETED" and review.status == PerformanceReview.Status.HR_PENDING:
            PerformanceReviewService.submit_hr_review(
                hr_user,
                review,
                {
                    "hr_summary": "HR finalized the demo review after calibration.",
                    "final_rating": Decimal("4.3"),
                },
            )

    def _ensure_lifecycle(self, context, today):
        hr_user = context["users"]["hr@atmispace.com"]
        manager_user = context["users"]["manager@atmispace.com"]
        admin_user = context["users"]["admin@atmispace.com"]
        engineering = context["departments"]["ENG"]

        plan, _ = OnboardingPlan.objects.get_or_create(
            name="Engineering New Joiner Demo Plan",
            defaults={
                "description": "Demo onboarding plan for Version 2 lifecycle flows.",
                "department": engineering,
                "employment_type": Employee.EmploymentType.FULL_TIME,
                "default_duration_days": 10,
                "is_active": True,
            },
        )
        templates = [
            ("Submit PAN and Aadhaar", User.Role.HR, OnboardingTaskTemplate.TaskType.DOCUMENT, 1, 1),
            ("Acknowledge security policy", User.Role.EMPLOYEE, OnboardingTaskTemplate.TaskType.POLICY, 2, 2),
            ("Provision GitHub and VPN access", User.Role.ADMIN, OnboardingTaskTemplate.TaskType.ACCESS, 3, 2),
            ("Attend manager onboarding session", User.Role.MANAGER, OnboardingTaskTemplate.TaskType.TRAINING, 4, 4),
        ]
        for title, owner_role, task_type, sequence, due_offset_days in templates:
            OnboardingTaskTemplate.objects.update_or_create(
                plan=plan,
                title=title,
                defaults={
                    "description": title,
                    "owner_role": owner_role,
                    "task_type": task_type,
                    "sequence": sequence,
                    "due_offset_days": due_offset_days,
                    "is_required": True,
                },
            )

        newhire = context["employees"]["newhire@atmispace.com"]
        onboarding = EmployeeOnboarding.objects.filter(employee=newhire, plan=plan).first()
        if not onboarding:
            onboarding = EmployeeOnboardingService.create_onboarding(
                {
                    "employee": newhire,
                    "plan": plan,
                    "start_date": newhire.hire_date,
                    "due_date": newhire.hire_date + timedelta(days=10),
                    "notes": "Demo onboarding tracker.",
                },
                actor=hr_user,
            )
        first_task = onboarding.tasks.order_by("sequence", "id").first()
        if first_task and first_task.status != first_task.Status.COMPLETED:
            EmployeeOnboardingService.complete_task(hr_user, first_task, notes="Completed during demo seeding.")

        offboarding = OffboardingCase.objects.filter(
            employee=context["employees"]["departing@atmispace.com"],
            reason="[Demo] Planned resignation workflow",
        ).first()
        if not offboarding:
            offboarding = OffboardingService.create_case(
                {
                    "employee": context["employees"]["departing@atmispace.com"],
                    "notice_start_date": today - timedelta(days=5),
                    "last_working_day": today + timedelta(days=20),
                    "reason": "[Demo] Planned resignation workflow",
                },
                actor=hr_user,
            )

        promotion_request = EmployeeChangeRequest.objects.filter(
            employee=context["employees"]["employee@atmispace.com"],
            change_type=EmployeeChangeRequest.ChangeType.PROMOTION,
            justification="[Demo] Promotion request pending HR",
        ).first()
        if not promotion_request:
            promotion_request = EmployeeChangeRequestService.create_change_request(
                {
                    "employee": context["employees"]["employee@atmispace.com"],
                    "change_type": EmployeeChangeRequest.ChangeType.PROMOTION,
                    "proposed_designation": "Senior Software Engineer",
                    "proposed_department_role": Employee.DepartmentRole.TEAM_LEAD,
                    "proposed_effective_date": today + timedelta(days=20),
                    "justification": "[Demo] Promotion request pending HR",
                },
                actor=manager_user,
            )
        self._advance_workflow_step(Workflow.Module.LIFECYCLE_CASE, promotion_request, manager_user)

        comp_revision = EmployeeChangeRequest.objects.filter(
            employee=context["employees"]["newhire@atmispace.com"],
            change_type=EmployeeChangeRequest.ChangeType.COMPENSATION_REVISION,
            justification="[Demo] Compensation revision pending Admin",
        ).first()
        if not comp_revision:
            comp_revision = EmployeeChangeRequestService.create_change_request(
                {
                    "employee": context["employees"]["newhire@atmispace.com"],
                    "change_type": EmployeeChangeRequest.ChangeType.COMPENSATION_REVISION,
                    "proposed_ctc_per_annum": Decimal("600000.00"),
                    "proposed_effective_date": today + timedelta(days=15),
                    "justification": "[Demo] Compensation revision pending Admin",
                },
                actor=manager_user,
            )
        self._advance_workflow_step(Workflow.Module.LIFECYCLE_CASE, comp_revision, manager_user)
        self._advance_workflow_step(Workflow.Module.LIFECYCLE_CASE, comp_revision, hr_user)

        existing_revision = SalaryRevision.objects.filter(
            employee=context["employees"]["teamlead@atmispace.com"],
            reason="[Demo] Historical salary correction",
        ).first()
        if not existing_revision:
            SalaryRevisionService.apply_revision(
                actor=admin_user,
                employee=context["employees"]["teamlead@atmispace.com"],
                new_ctc=Decimal("1140000.00"),
                effective_date=today - timedelta(days=45),
                reason="[Demo] Historical salary correction",
            )

        return offboarding

    def _ensure_scheduling(self, context, holiday_calendar, offboarding_case, today):
        admin_user = context["users"]["admin@atmispace.com"]
        engineering = context["departments"]["ENG"]
        morning_shift = context["shifts"]["Morning"]
        night_shift = context["shifts"]["Night"]
        rotation_rule, _ = ShiftRotationRule.objects.get_or_create(
            name="Engineering Demo Rotation",
            defaults={
                "description": "Alternate morning and night shift coverage for engineering demos.",
                "department": engineering,
                "rotation_pattern": [morning_shift.id, night_shift.id],
                "holiday_strategy": ShiftRotationRule.HolidayStrategy.MARK_CONFLICT,
                "is_active": True,
            },
        )

        rotation_employees = [
            context["employees"]["teamlead@atmispace.com"],
            context["employees"]["employee@atmispace.com"],
            context["employees"]["newhire@atmispace.com"],
        ]
        SchedulingService.bulk_assign(rotation_employees, morning_shift, today + timedelta(days=1), today + timedelta(days=2), admin_user)
        SchedulingService.apply_rotation(rotation_rule, rotation_employees, today + timedelta(days=4), today + timedelta(days=6), admin_user)

        holiday_date = Holiday.objects.filter(calendar=holiday_calendar).order_by("date").last().date
        SchedulingService.assign_shift(
            context["employees"]["employee@atmispace.com"],
            holiday_date,
            morning_shift,
            admin_user,
            notes="Holiday conflict demo entry.",
        )
        SchedulingService.assign_shift(
            context["employees"]["departing@atmispace.com"],
            offboarding_case.last_working_day + timedelta(days=2),
            night_shift,
            admin_user,
            notes="Offboarding conflict demo entry.",
        )

    def _ensure_payroll(self, context, today):
        accounts_user = context["users"]["accounts@atmispace.com"]
        admin_user = context["users"]["admin@atmispace.com"]
        current_cycle = self._ensure_payroll_cycle(
            name=f"Payroll {today.strftime('%b %Y')} Demo",
            payroll_month=today.replace(day=1),
            notes="Current payroll cycle pending admin release approval.",
            actor=accounts_user,
        )
        previous_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        previous_cycle = self._ensure_payroll_cycle(
            name=f"Payroll {previous_month.strftime('%b %Y')} Demo",
            payroll_month=previous_month,
            notes="Previous payroll cycle released for demo history.",
            actor=accounts_user,
        )

        salary_template, _ = SalaryComponentTemplate.objects.get_or_create(
            name="Standard Salary Structure",
            defaults={
                "description": "Default salary component package used by demo employees.",
                "is_default": True,
                "is_active": True,
            },
        )
        basic_component, _ = SalaryComponent.objects.update_or_create(
            template=salary_template,
            code="BASIC",
            defaults={
                "name": "Basic Salary",
                "description": "Demo basic salary component.",
                "component_type": SalaryComponent.ComponentType.EARNING,
                "calculation_type": SalaryComponent.CalculationType.PERCENT_OF_GROSS,
                "value": Decimal("50.00"),
                "display_order": 10,
                "is_active": True,
                "is_taxable": True,
                "is_part_of_gross": True,
            },
        )
        SalaryComponent.objects.update_or_create(
            template=salary_template,
            code="PF",
            defaults={
                "name": "Provident Fund",
                "description": "Demo PF deduction based on Basic Salary.",
                "component_type": SalaryComponent.ComponentType.DEDUCTION,
                "calculation_type": SalaryComponent.CalculationType.PERCENT_OF_COMPONENT,
                "base_component": basic_component,
                "value": Decimal("12.00"),
                "display_order": 100,
                "is_active": True,
                "has_employer_contribution": True,
                "employer_contribution_value": Decimal("12.00"),
                "deduct_employer_contribution": False,
                "is_part_of_gross": False,
            },
        )

        self._ensure_payroll_adjustment(
            current_cycle,
            context["employees"]["employee@atmispace.com"],
            PayrollAdjustment.AdjustmentType.EARNING,
            Decimal("5000.00"),
            "[Demo] Sprint delivery bonus",
            accounts_user,
        )
        self._ensure_payroll_adjustment(
            current_cycle,
            context["employees"]["newhire@atmispace.com"],
            PayrollAdjustment.AdjustmentType.DEDUCTION,
            Decimal("1500.00"),
            "[Demo] Asset recovery deduction",
            accounts_user,
        )

        self._ensure_payroll_run(current_cycle, accounts_user, target_status=PayrollRun.Status.RELEASE_PENDING, approver=admin_user)
        self._ensure_payroll_run(previous_cycle, accounts_user, target_status=PayrollRun.Status.RELEASED, approver=admin_user)

    def _ensure_payroll_cycle(self, name, payroll_month, notes, actor):
        _, days_in_month = monthrange(payroll_month.year, payroll_month.month)
        cycle = PayrollCycle.objects.filter(name=name).first()
        payload = {
            "name": name,
            "payroll_month": payroll_month,
            "start_date": payroll_month,
            "end_date": payroll_month.replace(day=days_in_month),
            "notes": notes,
        }
        if cycle:
            PayrollGovernanceService.update_cycle(cycle, payload, actor)
            return cycle
        return PayrollGovernanceService.create_cycle(payload, actor)

    def _ensure_payroll_adjustment(self, cycle, employee, adjustment_type, amount, reason, actor):
        if PayrollAdjustment.objects.filter(cycle=cycle, employee=employee, reason=reason).exists():
            return
        PayrollGovernanceService.create_adjustment(
            {
                "cycle": cycle,
                "employee": employee,
                "adjustment_type": adjustment_type,
                "amount": amount,
                "reason": reason,
            },
            actor,
        )

    def _ensure_payroll_run(self, cycle, actor, target_status, approver):
        try:
            run = cycle.run
        except PayrollRun.DoesNotExist:
            run = None
        if not run:
            run = PayrollGovernanceService.generate_run(actor, cycle)

        if target_status in {PayrollRun.Status.LOCKED, PayrollRun.Status.RELEASE_PENDING, PayrollRun.Status.RELEASED} and run.status == PayrollRun.Status.DRAFT:
            run = PayrollGovernanceService.lock_run(actor, run)

        if target_status in {PayrollRun.Status.RELEASE_PENDING, PayrollRun.Status.RELEASED} and run.status == PayrollRun.Status.LOCKED:
            run = PayrollGovernanceService.request_release(actor, run, notes="Release requested during demo seeding.")

        if target_status == PayrollRun.Status.RELEASED and run.status == PayrollRun.Status.RELEASE_PENDING:
            self._advance_workflow_step(Workflow.Module.PAYROLL_RELEASE, run, approver)

    def _advance_workflow_step(self, module, obj, actor):
        assignment = WorkflowService.get_assignment_for_object(module, obj)
        if not assignment:
            return
        approval = WorkflowService.get_pending_approval_for_assignment(assignment)
        if not approval or approval.assigned_user_id != actor.id:
            return
        WorkflowService.approve(actor, approval, comments="Approved during demo seeding.")

    def _previous_weekend(self, today, offset=0):
        candidate = today - timedelta(days=(today.weekday() - 5) % 7 or 7)
        return candidate - timedelta(days=7 * offset)

    def _print_summary(self, context):
        self.stdout.write(self.style.SUCCESS("Version 2 demo data seeded successfully."))
        self.stdout.write("")
        self.stdout.write("Workflow queues:")
        queue_users = [
            "manager@atmispace.com",
            "teamlead@atmispace.com",
            "hr@atmispace.com",
            "admin@atmispace.com",
            "accounts@atmispace.com",
        ]
        for email in queue_users:
            user = context["users"][email]
            pending_count = WorkflowService.list_pending_approvals_for_user(user).count()
            self.stdout.write(f"  {email}: {pending_count} pending approval(s)")

        self.stdout.write("")
        self.stdout.write("Additional demo credentials:")
        for record in self.demo_users:
            self.stdout.write(f"  {record['email']} / {record['password']}")
