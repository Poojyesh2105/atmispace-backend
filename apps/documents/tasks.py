from celery import shared_task

from apps.documents.selectors.document_selectors import DocumentSelectors
from apps.notifications.services.notification_service import NotificationService


@shared_task
def send_document_expiry_reminders():
    reminders = []
    for document in DocumentSelectors.get_expiring_documents(days=30):
        reminders.append(
            NotificationService.create_notification(
                document.employee.user,
                NotificationService._resolve_type("DOCUMENT_EXPIRY"),
                "Document renewal reminder",
                f"{document.document_type.name} expires on {document.expiry_date.isoformat()}. Please renew it.",
            )
        )
    return len(reminders)

