from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="unsafe-development-secret-key-change-me-please-12345")
JWT_SIGNING_KEY = config("JWT_SIGNING_KEY", default=SECRET_KEY)
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
    cast=Csv(),
)
CORS_ALLOW_HEADERS = (*default_headers, "x-organization-id", "x-request-id")
TIME_ZONE = config("TIME_ZONE", default="Asia/Kolkata")

if len(JWT_SIGNING_KEY.encode("utf-8")) < 32:
    raise ImproperlyConfigured("JWT_SIGNING_KEY must be at least 32 bytes long for HS256 token signing.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "apps.core",
    "apps.accounts",
    "apps.employees",
    "apps.attendance",
    "apps.leave_management",
    "apps.workflow",
    "apps.audit",
    "apps.notifications",
    "apps.holidays",
    "apps.reports",
    "apps.payroll",
    "apps.performance",
    "apps.documents",
    "apps.lifecycle",
    "apps.scheduling",
    "apps.announcements",
    "apps.analytics",
    "apps.policy_engine",
    "apps.helpdesk",
    "apps.platform",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.middleware.RequestContextLoggingMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.TenantMiddleware",
    "apps.core.feature_flags.FeatureFlagMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="hrms_db"),
        "USER": config("POSTGRES_USER", default="poojyesh"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="admin"),
        "HOST": config("POSTGRES_HOST", default="127.0.0.1"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = "DENY"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_REDIS_URL = config("REDIS_URL", default="redis://127.0.0.1:6379/0")
_CACHE_BACKEND = config("CACHE_BACKEND", default="redis").lower()
if _CACHE_BACKEND == "locmem":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "atmispace-local",
            "KEY_PREFIX": "atmispace",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _REDIS_URL,
            "OPTIONS": {
                "socket_connect_timeout": 2,
                "socket_timeout": 2,
            },
            "KEY_PREFIX": "atmispace",
        }
    }

DASHBOARD_CACHE_TTL_SECONDS = config("DASHBOARD_CACHE_TTL_SECONDS", default=60, cast=int)
ORG_SETTINGS_CACHE_TTL_SECONDS = config("ORG_SETTINGS_CACHE_TTL_SECONDS", default=300, cast=int)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    # ── Throttling ────────────────────────────────────────────────────────
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.core.throttling.OrgApiThrottle",
        "apps.core.throttling.OrgApiAnonThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Auth endpoints — tight
        "auth_burst": config("THROTTLE_AUTH_BURST", default="10/minute"),
        "auth_sustained": config("THROTTLE_AUTH_SUSTAINED", default="100/hour"),
        # Platform (SUPER_ADMIN) endpoints
        "platform_burst": config("THROTTLE_PLATFORM_BURST", default="60/minute"),
        "platform_sustained": config("THROTTLE_PLATFORM_SUSTAINED", default="2000/day"),
        # Standard org API
        "org_api": config("THROTTLE_ORG_API", default="300/minute"),
        "org_api_anon": config("THROTTLE_ORG_API_ANON", default="30/minute"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("ACCESS_TOKEN_MINUTES", default=30, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=config("REFRESH_TOKEN_DAYS", default=7, cast=int)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "UPDATE_LAST_LOGIN": True,
}

CELERY_BROKER_URL = config("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    # Leave carry-forward — 1st of each month at midnight
    "monthly-leave-carry-forward": {
        "task": "apps.leave_management.tasks.process_monthly_leave_carry_forward",
        "schedule": crontab(minute=0, hour=0, day_of_month=1),
    },
    # Workflow stuck approvals — every morning at 08:00
    "workflow-stuck-alerts": {
        "task": "apps.workflow.tasks.alert_stuck_workflow_assignments",
        "schedule": crontab(minute=0, hour=8),
    },
    # Document expiry reminders — daily at 07:00
    "document-expiry-reminders": {
        "task": "apps.documents.tasks.send_document_expiry_reminders",
        "schedule": crontab(minute=0, hour=7),
    },
    # Lifecycle task reminders — daily at 07:30
    "lifecycle-task-reminders": {
        "task": "apps.lifecycle.tasks.send_lifecycle_task_reminders",
        "schedule": crontab(minute=30, hour=7),
    },
    # Performance review reminders — daily at 08:30
    "performance-review-reminders": {
        "task": "apps.performance.tasks.send_pending_performance_review_reminders",
        "schedule": crontab(minute=30, hour=8),
    },
    # Helpdesk ticket reminders — daily at 09:00
    "helpdesk-ticket-reminders": {
        "task": "apps.helpdesk.tasks.remind_pending_helpdesk_tickets",
        "schedule": crontab(minute=0, hour=9),
    },
    # Schedule conflict reminders — daily at 09:30
    "schedule-conflict-reminders": {
        "task": "apps.scheduling.tasks.remind_unresolved_schedule_conflicts",
        "schedule": crontab(minute=30, hour=9),
    },
    # Announcement acknowledgement reminders — daily at 10:00
    "announcement-ack-reminders": {
        "task": "apps.announcements.tasks.send_acknowledgement_reminders",
        "schedule": crontab(minute=0, hour=10),
    },
    # Analytics snapshot refresh — daily at 01:00
    "analytics-snapshot-refresh": {
        "task": "apps.analytics.tasks.refresh_analytics_snapshots",
        "schedule": crontab(minute=0, hour=1),
    },
}

EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=25, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="hrms@atmispace.local")

LOG_LEVEL = config("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "apps.core.logging.JsonFormatter",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "loggers": {
        "atmispace": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "atmispace.request": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "atmispace.tasks": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "atmispace.alerts": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "atmispace.platform": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "atmispace.payroll": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "atmispace.workflow": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "atmispace.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
