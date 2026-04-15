from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from apps.accounts.models import User
from apps.audit.services.audit_service import AuditService
from apps.helpdesk.models import HelpdeskCategory, HelpdeskComment, HelpdeskTicket
from apps.notifications.services.notification_service import NotificationService


class HelpdeskCategoryService:
    @staticmethod
    def create_category(validated_data, actor):
        category = HelpdeskCategory.objects.create(**validated_data)
        AuditService.log(actor=actor, action="helpdesk.category.created", entity=category, after=category)
        return category

    @staticmethod
    def update_category(instance, validated_data, actor):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="helpdesk.category.updated", entity=instance, before=before, after=instance)
        return instance


class HelpdeskService:
    MANAGE_ROLES = {User.Role.HR, User.Role.ACCOUNTS, User.Role.ADMIN}

    @staticmethod
    def _assign_default_owner(category):
        return User.objects.filter(role=category.owner_role, is_active=True).order_by("date_joined", "id").first()

    @staticmethod
    @transaction.atomic
    def create_ticket(validated_data, actor):
        requester = validated_data.get("requester") or getattr(actor, "employee_profile", None)
        if requester is None:
            raise exceptions.ValidationError({"requester": "A requester employee is required."})

        category = validated_data["category"]
        assigned_user = HelpdeskService._assign_default_owner(category)
        ticket = HelpdeskTicket.objects.create(
            requester=requester,
            category=category,
            assigned_role=category.owner_role,
            assigned_user=assigned_user,
            subject=validated_data["subject"],
            description=validated_data["description"],
            priority=validated_data.get("priority", HelpdeskTicket.Priority.MEDIUM),
        )
        if assigned_user:
            NotificationService.create_notification(
                assigned_user,
                NotificationService._resolve_type("HELPDESK"),
                f"New helpdesk ticket: {ticket.subject}",
                f"A new {category.name.lower()} request was created by {requester.user.full_name}.",
            )
        AuditService.log(actor=actor, action="helpdesk.ticket.created", entity=ticket, after=ticket)
        return ticket

    @staticmethod
    def update_ticket(instance, validated_data, actor):
        current_employee = getattr(actor, "employee_profile", None)
        can_manage = actor.role in HelpdeskService.MANAGE_ROLES or actor == instance.assigned_user
        can_requester_edit = current_employee and instance.requester_id == current_employee.pk and instance.status == HelpdeskTicket.Status.OPEN
        if not can_manage and not can_requester_edit:
            raise exceptions.PermissionDenied("You cannot update this ticket.")

        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="helpdesk.ticket.updated", entity=instance, before=before, after=instance)
        return instance

    @staticmethod
    def add_comment(ticket, user, message, is_internal=False):
        if is_internal and user.role not in HelpdeskService.MANAGE_ROLES:
            raise exceptions.PermissionDenied("Internal comments are restricted to support roles.")
        comment = HelpdeskComment.objects.create(ticket=ticket, author=user, message=message, is_internal=is_internal)
        if ticket.requester.user_id != user.pk:
            NotificationService.create_notification(
                ticket.requester.user,
                NotificationService._resolve_type("HELPDESK"),
                f"Update on ticket: {ticket.subject}",
                "A new update was added to your helpdesk ticket.",
            )
        AuditService.log(actor=user, action="helpdesk.comment.created", entity=comment, after=comment)
        return comment

    @staticmethod
    def resolve(ticket, user, resolution_notes=""):
        if user.role not in HelpdeskService.MANAGE_ROLES and user != ticket.assigned_user:
            raise exceptions.PermissionDenied("You cannot resolve this ticket.")
        before = AuditService.snapshot(ticket)
        ticket.status = HelpdeskTicket.Status.RESOLVED
        ticket.resolution_notes = resolution_notes
        ticket.resolved_at = timezone.now()
        ticket.save(update_fields=["status", "resolution_notes", "resolved_at", "updated_at"])
        NotificationService.create_notification(
            ticket.requester.user,
            NotificationService._resolve_type("HELPDESK"),
            f"Ticket resolved: {ticket.subject}",
            "Your helpdesk ticket has been resolved.",
        )
        AuditService.log(actor=user, action="helpdesk.ticket.resolved", entity=ticket, before=before, after=ticket)
        return ticket

    @staticmethod
    def close(ticket, user):
        current_employee = getattr(user, "employee_profile", None)
        if user.role not in HelpdeskService.MANAGE_ROLES and (
            current_employee is None or ticket.requester_id != current_employee.pk
        ):
            raise exceptions.PermissionDenied("You cannot close this ticket.")
        before = AuditService.snapshot(ticket)
        ticket.status = HelpdeskTicket.Status.CLOSED
        ticket.save(update_fields=["status", "updated_at"])
        AuditService.log(actor=user, action="helpdesk.ticket.closed", entity=ticket, before=before, after=ticket)
        return ticket
