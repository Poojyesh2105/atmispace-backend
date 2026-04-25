import logging

from celery import shared_task

from apps.documents.selectors.document_selectors import DocumentSelectors
from apps.notifications.services.notification_service import NotificationService

task_logger = logging.getLogger("atmispace.tasks")


@shared_task
def send_document_expiry_reminders():
    """
    Org-aware: send expiry reminders for documents expiring within 30 days,
    scoped per organization.
    """
    from apps.core.models import Organization

    total = 0
    for org in Organization.objects.filter(is_active=True):
        try:
            expiring = DocumentSelectors.get_expiring_documents(days=30, organization=org)
            for document in expiring:
                try:
                    NotificationService.create_notification(
                        document.employee.user,
                        NotificationService._resolve_type("DOCUMENT_EXPIRY"),
                        "Document renewal reminder",
                        f"{document.document_type.name} expires on "
                        f"{document.expiry_date.isoformat()}. Please renew it.",
                    )
                    total += 1
                except Exception as exc:  # noqa: BLE001
                    task_logger.error(
                        "documents.expiry.notify_error",
                        extra={"org_id": org.pk, "doc_id": document.pk, "error": str(exc)},
                        exc_info=True,
                    )
        except Exception as exc:  # noqa: BLE001
            task_logger.error(
                "documents.expiry.org_error",
                extra={"event": "documents.expiry.org_error",
                       "org_id": org.pk, "error": str(exc)},
                exc_info=True,
            )
    task_logger.info("documents.expiry.done", extra={"event": "documents.expiry.done", "total": total})
    return {"reminders_sent": total}
