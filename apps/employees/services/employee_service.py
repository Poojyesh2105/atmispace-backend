from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from rest_framework import exceptions

from apps.accounts.models import User
from apps.audit.services.audit_service import AuditService
from apps.core.services import OrganizationService
from apps.employees.models import Department, Employee, OrganizationSettings, ShiftTemplate
from apps.employees.selectors import EmployeeSelectors


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
        return EmployeeSelectors.get_queryset_for_user(user)

    @staticmethod
    def _validate_manage_access(actor, instance: Employee):
        if not actor or not getattr(actor, "is_authenticated", False):
            return
        if actor.role == User.Role.HR and instance.user.role == User.Role.ADMIN:
            raise exceptions.PermissionDenied("HR users cannot delete Admin employee records.")

    @staticmethod
    @transaction.atomic
    def create_employee(validated_data, actor=None):
        from apps.leave_management.models import LeaveBalance
        from apps.leave_management.services.leave_service import LeavePolicyService

        user_data = validated_data.pop("user")
        password = validated_data.pop("password", None)
        force_password_reset = validated_data.pop("force_password_reset", False)
        organization = OrganizationService.resolve_for_actor(actor)
        user = User.objects.create_user(
            email=user_data["email"],
            password=password or "ChangeMe123!",
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            role=user_data.get("role", User.Role.EMPLOYEE),
        )
        if organization:
            user.organization = organization
            user.save(update_fields=["organization", "updated_at"])
        if force_password_reset:
            user.force_password_reset = True
            user.save(update_fields=["force_password_reset"])
        if organization:
            validated_data["organization"] = organization
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
        AuditService.log(actor=actor or user, action="employee.created", entity=employee, after=EmployeeService._snapshot_employee(employee))
        return employee

    @staticmethod
    @transaction.atomic
    def update_employee(instance: Employee, validated_data, actor=None):
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
        AuditService.log(
            actor=actor or instance.user,
            action="employee.updated",
            entity=instance,
            before=before,
            after=EmployeeService._snapshot_employee(instance),
        )
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
    def get_queryset(actor=None):
        return EmployeeSelectors.get_department_queryset(actor)

    @staticmethod
    def create_department(validated_data, actor=None):
        organization = OrganizationService.resolve_for_actor(actor)
        if organization:
            validated_data.setdefault("organization", organization)
        return Department.objects.create(**validated_data)

    @staticmethod
    def update_department(instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class OrganizationSettingsService:
    CACHE_KEY_TEMPLATE = "organization-settings:{organization_id}"

    @staticmethod
    def _cache_key(organization_id):
        return OrganizationSettingsService.CACHE_KEY_TEMPLATE.format(organization_id=organization_id or "global")

    @staticmethod
    def get_settings(actor=None, organization=None):
        resolved_organization = OrganizationService.resolve_for_actor(actor, organization=organization)
        cache_key = OrganizationSettingsService._cache_key(getattr(resolved_organization, "pk", None))
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        queryset = EmployeeSelectors.get_settings_queryset(actor)
        if resolved_organization:
            settings_instance, _ = queryset.get_or_create(
                organization=resolved_organization,
                defaults={"organization_name": resolved_organization.name},
            )
        else:
            settings_instance, _ = queryset.get_or_create(pk=1, defaults={"organization_name": "Organization"})
        cache.set(cache_key, settings_instance, timeout=settings.ORG_SETTINGS_CACHE_TTL_SECONDS)
        return settings_instance

    @staticmethod
    def update_settings(validated_data, actor=None, organization=None):
        settings_instance = OrganizationSettingsService.get_settings(actor=actor, organization=organization)
        for attr, value in validated_data.items():
            setattr(settings_instance, attr, value)
        if resolved_organization := OrganizationService.resolve_for_actor(actor, organization=organization):
            settings_instance.organization = resolved_organization
        settings_instance.save()
        cache.delete(OrganizationSettingsService._cache_key(getattr(settings_instance.organization, "pk", None)))
        return settings_instance


class ShiftTemplateService:
    @staticmethod
    def get_queryset(actor=None):
        return EmployeeSelectors.get_shift_queryset(actor)

    @staticmethod
    def create_shift(validated_data, actor=None):
        organization = OrganizationService.resolve_for_actor(actor)
        if organization:
            validated_data.setdefault("organization", organization)
        return ShiftTemplate.objects.create(**validated_data)

    @staticmethod
    def update_shift(instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
