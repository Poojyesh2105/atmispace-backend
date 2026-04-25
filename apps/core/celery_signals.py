import logging
import time

from celery.signals import task_failure, task_postrun, task_prerun, task_retry

from apps.accounts.models import User
from apps.notifications.services.notification_service import NotificationService


task_logger = logging.getLogger("atmispace.tasks")
alert_logger = logging.getLogger("atmispace.alerts")

_task_start_times: dict = {}


@task_prerun.connect
def log_task_start(task_id=None, task=None, **kwargs):
    _task_start_times[task_id] = time.monotonic()
    task_logger.info(
        "task.started",
        extra={
            "event": "task.started",
            "module_name": "celery",
            "action": "task_start",
            "task_name": getattr(task, "name", "unknown"),
            "task_id": task_id,
        },
    )


@task_postrun.connect
def log_task_complete(task_id=None, task=None, state=None, **kwargs):
    elapsed_ms = None
    start = _task_start_times.pop(task_id, None)
    if start is not None:
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)

    task_logger.info(
        "task.completed",
        extra={
            "event": "task.completed",
            "module_name": "celery",
            "action": "task_complete",
            "task_name": getattr(task, "name", "unknown"),
            "task_id": task_id,
            "status_code": state,
            "duration_ms": elapsed_ms,
        },
    )


@task_retry.connect
def log_task_retry(request=None, reason=None, **kwargs):
    task_logger.warning(
        "task.retrying",
        extra={
            "event": "task.retrying",
            "module_name": "celery",
            "action": "task_retry",
            "task_name": getattr(request, "task", "unknown"),
            "task_id": getattr(request, "id", None),
            "reason": str(reason),
        },
    )


@task_failure.connect
def log_task_failure(task_id=None, exception=None, traceback=None, sender=None, **kwargs):
    task_name = getattr(sender, "name", "unknown")
    elapsed_ms = None
    start = _task_start_times.pop(task_id, None)
    if start is not None:
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)

    alert_logger.error(
        f"task.failed: {exception}",
        extra={
            "event": "task.failed",
            "module_name": "celery",
            "action": "task_failure",
            "task_name": task_name,
            "task_id": task_id,
            "exception_type": type(exception).__name__ if exception else None,
            "duration_ms": elapsed_ms,
        },
        exc_info=True,
    )

    # Notify SUPER_ADMIN and ADMIN users of task failures
    admins = User.objects.filter(role__in=[User.Role.ADMIN, User.Role.SUPER_ADMIN], is_active=True)[:10]
    for admin in admins:
        try:
            NotificationService.create_notification(
                admin,
                NotificationService._resolve_type("GENERIC"),
                "Background job failed",
                f"Task '{task_name}' failed with {type(exception).__name__}. Task id: {task_id}.",
                send_email=False,
            )
        except Exception:
            pass  # Never let notification errors cascade
