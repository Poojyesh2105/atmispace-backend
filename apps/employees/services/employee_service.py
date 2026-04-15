from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from rest_framework import exceptions

from apps.accounts.models import User
from apps.audit.services.audit_service import AuditService
from apps.employees.models import Department, Employee, OrganizationSettings, ShiftTemplate


class EmployeeService:
    @staticmethod
    def _snapshot_employee(instance):
        data = AuditService.snapshot(instance)
        if instance and getattr(instance, "user", None):
            data.update(
                {
                    "email": instance.user.email,
                    "first_name": instance.user.first_name,
                    "last_name": instance.user.last_name,
                    "role": instance.user.role,
                }
            )
        return data

    @staticmethod
    def get_employee_queryset_for_user(user):
        queryset = Employee.objects.select_related(
            "user",
            "department",
            "manager__user",
            "secondary_manager__user",
            "shift_template",
        )
        employee = getattr(user, "employee_profile", None)

        if user.role in {User.Role.MANAGER, User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}:
            return queryset
        if employee:
            return queryset.filter(pk=employee.pk)
        return queryset.none()

    @staticmethod
    def _validate_manage_access(actor, instance: Employee):
        if not actor or not getattr(actor, "is_authenticated", False):
            return
        if actor.role == User.Role.HR and instance.user.role == User.Role.ADMIN:
            raise exceptions.PermissionDenied("HR users cannot delete Admin employee records.")

    @staticmethod
    @transaction.atomic
    def create_employee(validated_data):
        from apps.leave_management.models import LeaveBalance
        from apps.leave_management.services.leave_service import LeavePolicyService

        user_data = validated_data.pop("user")
        password = validated_data.pop("password", None)
        user = User.objects.create_user(
            email=user_data["email"],
            password=password or "ChangeMe123!",
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            role=user_data.get("role", User.Role.EMPLOYEE),
        )
        employee = Employee.objects.create(user=user, **validated_data)
        policy = LeavePolicyService.get_policy()
        default_allocations = {
            LeaveBalance.LeaveType.CASUAL: policy.casual_days_onboarding,
            LeaveBalance.LeaveType.SICK: policy.sick_days_onboarding,
            LeaveBalance.LeaveType.EARNED: policy.earned_days_onboarding,
            LeaveBalance.LeaveType.LOP: 0,
        }
        for leave_type in LeaveBalance.LeaveType.values:
            LeaveBalance.objects.get_or_create(
                employee=employee,
                leave_type=leave_type,
                defaults={"allocated_days": default_allocations.get(leave_type, 0), "used_days": 0},
            )
        AuditService.log(actor=user, action="employee.created", entity=employee, after=EmployeeService._snapshot_employee(employee))
        return employee

    @staticmethod
    @transaction.atomic
    def update_employee(instance: Employee, validated_data):
        before = EmployeeService._snapshot_employee(instance)
        user_data = validated_data.pop("user", {})
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        if password:
            instance.user.set_password(password)
        instance.user.save()
        AuditService.log(actor=instance.user, action="employee.updated", entity=instance, before=before, after=EmployeeService._snapshot_employee(instance))
        return instance

    @staticmethod
    def _delete_related_workflow_assignments(instance: Employee):
        from apps.attendance.models import AttendanceRegularization
        from apps.leave_management.models import LeaveRequest
        from apps.workflow.models import Workflow, WorkflowAssignment

        leave_request_ids = list(instance.leave_requests.values_list("id", flat=True))
        if leave_request_ids:
            WorkflowAssignment.objects.filter(
                module=Workflow.Module.LEAVE_REQUEST,
                content_type=ContentType.objects.get_for_model(LeaveRequest),
                object_id__in=leave_request_ids,
            ).delete()

        regularization_ids = list(instance.attendance_regularizations.values_list("id", flat=True))
        if regularization_ids:
            WorkflowAssignment.objects.filter(
                module=Workflow.Module.ATTENDANCE_REGULARIZATION,
                content_type=ContentType.objects.get_for_model(AttendanceRegularization),
                object_id__in=regularization_ids,
            ).delete()

    @staticmethod
    @transaction.atomic
    def delete_employee(instance: Employee, actor=None):
        before = EmployeeService._snapshot_employee(instance)
        target_user = instance.user
        EmployeeService._validate_manage_access(actor, instance)
        audit_actor = actor if getattr(actor, "pk", None) else None
        if audit_actor and audit_actor.pk == target_user.pk:
            audit_actor = None

        EmployeeService._delete_related_workflow_assignments(instance)
        target_user.delete()

        AuditService.log(
            actor=audit_actor,
            action="employee.deleted",
            entity_type="employees.employee",
            entity_id=before.get("id"),
            before=before,
        )


class DepartmentService:
    @staticmethod
    def get_queryset():
        return Department.objects.all().prefetch_related("employees")

    @staticmethod
    def create_department(validated_data):
        return Department.objects.create(**validated_data)

    @staticmethod
    def update_department(instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class OrganizationSettingsService:
    @staticmethod
    def get_settings():
        settings, _ = OrganizationSettings.objects.get_or_create(pk=1, defaults={"organization_name": "Organization"})
        return settings

    @staticmethod
    def update_settings(validated_data):
        settings = OrganizationSettingsService.get_settings()
        for attr, value in validated_data.items():
            setattr(settings, attr, value)
        settings.save()
        return settings


class ShiftTemplateService:
    @staticmethod
    def get_queryset():
        return ShiftTemplate.objects.all()

    @staticmethod
    def create_shift(validated_data):
        return ShiftTemplate.objects.create(**validated_data)

    @staticmethod
    def update_shift(instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
