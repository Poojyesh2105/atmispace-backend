from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.announcements.models import Announcement, AnnouncementAcknowledgement
from apps.audit.services.audit_service import AuditService
from apps.notifications.services.notification_service import NotificationService


class AnnouncementService:
    @staticmethod
    def create(validated_data, actor):
        announcement = Announcement.objects.create(created_by=actor, **validated_data)
        AuditService.log(actor=actor, action="announcement.created", entity=announcement, after=announcement)
        return announcement

    @staticmethod
    def update(instance, validated_data, actor):
        before = AuditService.snapshot(instance)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        AuditService.log(actor=actor, action="announcement.updated", entity=instance, before=before, after=instance)
        return instance

    @staticmethod
    def _get_recipients(announcement):
        users = User.objects.filter(is_active=True)
        if announcement.audience_type == Announcement.AudienceType.ROLE and announcement.role:
            return users.filter(role=announcement.role)
        if announcement.audience_type == Announcement.AudienceType.DEPARTMENT and announcement.department_id:
            return users.filter(employee_profile__department_id=announcement.department_id)
        if announcement.audience_type == Announcement.AudienceType.INDIVIDUAL and announcement.target_user_id:
            return users.filter(pk=announcement.target_user_id)
        return users

    @staticmethod
    @transaction.atomic
    def publish(announcement, actor):
        before = AuditService.snapshot(announcement)
        announcement.is_published = True
        announcement.published_at = timezone.now()
        announcement.save(update_fields=["is_published", "published_at", "updated_at"])

        for user in AnnouncementService._get_recipients(announcement):
            NotificationService.create_notification(
                user,
                NotificationService._resolve_type("ANNOUNCEMENT"),
                announcement.title,
                announcement.summary or "A new announcement has been published.",
            )

        AuditService.log(actor=actor, action="announcement.published", entity=announcement, before=before, after=announcement)
        return announcement

    @staticmethod
    def acknowledge(announcement, user):
        acknowledgement, _ = AnnouncementAcknowledgement.objects.get_or_create(
            announcement=announcement,
            user=user,
            defaults={"acknowledged_at": timezone.now()},
        )
        if not acknowledgement.acknowledged_at:
            acknowledgement.acknowledged_at = timezone.now()
            acknowledgement.save(update_fields=["acknowledged_at", "updated_at"])
        return acknowledgement

