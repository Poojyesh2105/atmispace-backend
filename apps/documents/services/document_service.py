from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User
from apps.audit.services.audit_service import AuditService
from apps.documents.models import DocumentType, EmployeeDocument, MandatoryDocumentRule
from apps.notifications.services.notification_service import NotificationService
from apps.policy_engine.services.policy_rule_service import PolicyRuleService


class DocumentTypeService:
    @staticmethod
    def create_type(validated_data, actor):
        document_type = DocumentType.objects.create(**validated_data)
        AuditService.log(actor=actor, action="documents.type.created", entity=document_type, after=document_type)
        return document_type

    @staticmethod
    def update_type(instance, validated_data, actor):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="documents.type.updated", entity=instance, before=before, after=instance)
        return instance


class MandatoryDocumentRuleService:
    @staticmethod
    def create_rule(validated_data, actor):
        rule = MandatoryDocumentRule.objects.create(**validated_data)
        AuditService.log(actor=actor, action="documents.rule.created", entity=rule, after=rule)
        return rule

    @staticmethod
    def update_rule(instance, validated_data, actor):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="documents.rule.updated", entity=instance, before=before, after=instance)
        return instance


class EmployeeDocumentService:
    @staticmethod
    def _can_manage_document(user, employee):
        current_employee = getattr(user, "employee_profile", None)
        if user.role in {User.Role.HR, User.Role.ADMIN}:
            return True
        if user.role == User.Role.MANAGER and current_employee:
            return employee.pk == current_employee.pk or employee.manager_id == current_employee.pk or employee.secondary_manager_id == current_employee.pk
        return bool(current_employee and current_employee.pk == employee.pk)

    @staticmethod
    @transaction.atomic
    def create_document(validated_data, actor):
        employee = validated_data["employee"]
        if not EmployeeDocumentService._can_manage_document(actor, employee):
            raise exceptions.PermissionDenied("You cannot upload documents for this employee.")

        document = EmployeeDocument.objects.create(**validated_data)
        PolicyRuleService.evaluate("COMPLIANCE", document, actor=actor, persist=True)
        NotificationService.create_notification(
            employee.user,
            NotificationService._resolve_type("DOCUMENT_VERIFIED"),
            "Document uploaded",
            f"{document.document_type.name} was uploaded to your compliance vault and is pending verification.",
        )
        AuditService.log(actor=actor, action="documents.employee_document.created", entity=document, after=document)
        return document

    @staticmethod
    def update_document(instance, validated_data, actor):
        if not EmployeeDocumentService._can_manage_document(actor, instance.employee):
            raise exceptions.PermissionDenied("You cannot update documents for this employee.")
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if instance.expiry_date and instance.expiry_date < timezone.localdate():
            instance.status = EmployeeDocument.Status.EXPIRED
        instance.save()
        PolicyRuleService.evaluate("COMPLIANCE", instance, actor=actor, persist=True)
        AuditService.log(actor=actor, action="documents.employee_document.updated", entity=instance, before=before, after=instance)
        return instance

    @staticmethod
    def verify_document(user, instance, remarks=""):
        if user.role not in {User.Role.HR, User.Role.ADMIN}:
            raise exceptions.PermissionDenied("Only HR or Admin can verify documents.")
        before = AuditService.snapshot(instance)
        instance.status = EmployeeDocument.Status.VERIFIED
        instance.verified_by = user
        instance.verified_at = timezone.now()
        instance.remarks = remarks
        instance.save(update_fields=["status", "verified_by", "verified_at", "remarks", "updated_at"])
        NotificationService.create_notification(
            instance.employee.user,
            NotificationService._resolve_type("DOCUMENT_VERIFIED"),
            "Document verified",
            f"{instance.document_type.name} has been verified.",
        )
        AuditService.log(actor=user, action="documents.employee_document.verified", entity=instance, before=before, after=instance)
        return instance

    @staticmethod
    def reject_document(user, instance, remarks=""):
        if user.role not in {User.Role.HR, User.Role.ADMIN}:
            raise exceptions.PermissionDenied("Only HR or Admin can reject documents.")
        before = AuditService.snapshot(instance)
        instance.status = EmployeeDocument.Status.REJECTED
        instance.verified_by = user
        instance.verified_at = timezone.now()
        instance.remarks = remarks
        instance.save(update_fields=["status", "verified_by", "verified_at", "remarks", "updated_at"])
        NotificationService.create_notification(
            instance.employee.user,
            NotificationService._resolve_type("DOCUMENT_VERIFIED"),
            "Document rejected",
            f"{instance.document_type.name} needs re-upload or correction. {remarks}".strip(),
        )
        AuditService.log(actor=user, action="documents.employee_document.rejected", entity=instance, before=before, after=instance)
        return instance

