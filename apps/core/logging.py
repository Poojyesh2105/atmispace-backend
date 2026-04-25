import json
import logging
from contextvars import ContextVar
from datetime import datetime


request_context: ContextVar[dict] = ContextVar("request_context", default={})


def set_request_context(**context):
    request_context.set(context)


def clear_request_context():
    request_context.set({})


def get_request_context():
    return request_context.get({})


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        payload.update(get_request_context())

        if hasattr(record, "event"):
            payload["event"] = record.event
        if hasattr(record, "module_name"):
            payload["module"] = record.module_name
        if hasattr(record, "action"):
            payload["action"] = record.action
        if hasattr(record, "status_code"):
            payload["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            payload["duration_ms"] = record.duration_ms
        if hasattr(record, "path"):
            payload["path"] = record.path
        if hasattr(record, "method"):
            payload["method"] = record.method
        if hasattr(record, "metric_key"):
            payload["metric_key"] = record.metric_key
        if hasattr(record, "metric_value"):
            payload["metric_value"] = record.metric_value
        if hasattr(record, "task_name"):
            payload["task_name"] = record.task_name
        if hasattr(record, "task_id"):
            payload["task_id"] = record.task_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)
