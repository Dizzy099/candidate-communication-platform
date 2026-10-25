"""Django settings for the Candidate Communication Platform API.

Every deployment-specific value comes from environment variables (see
``backend/.env.example``). Defaults are safe for production: DEBUG is off and
a secret key must be provided unless DEBUG is explicitly enabled.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false.")
    SECRET_KEY = "dev-only-insecure-secret-key"  # noqa: S105 - only used with DEBUG=True

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "core",
    "candidates",
    "messaging",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database -----------------------------------------------------------------
# SQLite for zero-setup local development; PostgreSQL via DATABASE_URL elsewhere.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=env_int("DB_CONN_MAX_AGE", 60),
    )
}
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    # WAL + IMMEDIATE transactions let the API, worker and webhook handler
    # write concurrently without "database is locked" errors at demo scale.
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"]["OPTIONS"] = {
        "transaction_mode": "IMMEDIATE",
        "timeout": 20,
        "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True  # all timestamps are stored as timezone-aware UTC

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- API ----------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    # No user accounts in scope (documented in README); the demo is a single
    # shared recruiter workspace protected by throttling instead.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 10,
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ["core.throttling.WriteRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"writes": os.getenv("API_WRITE_THROTTLE_RATE", "120/min")},
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

# Behind a TLS-terminating proxy (Render, Fly, HF Spaces...) trust X-Forwarded-Proto.
if env_bool("DJANGO_BEHIND_PROXY", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# --- Communication provider ---------------------------------------------------
PROVIDER = {
    "BACKEND": os.getenv("PROVIDER_BACKEND", "simulator"),
    "BASE_URL": os.getenv("PROVIDER_BASE_URL", "http://127.0.0.1:8001"),
    "API_KEY": os.getenv("PROVIDER_API_KEY", ""),
    "WEBHOOK_SECRET": os.getenv("PROVIDER_WEBHOOK_SECRET", ""),
    "TIMEOUT_SECONDS": env_float("PROVIDER_TIMEOUT_SECONDS", 5.0),
    # Base URL the provider uses to reach our webhook endpoint.
    "PUBLIC_WEBHOOK_BASE_URL": os.getenv("PUBLIC_WEBHOOK_BASE_URL", "http://127.0.0.1:8000"),
    "WEBHOOK_TOLERANCE_SECONDS": env_int("PROVIDER_WEBHOOK_TOLERANCE_SECONDS", 300),
}
DEMO_CONTROLS_ENABLED = env_bool("DEMO_CONTROLS_ENABLED", False)

MESSAGING = {
    "MAX_BODY_LENGTH": env_int("MESSAGE_MAX_BODY_LENGTH", 1000),
    "MAX_BATCH_RECIPIENTS": env_int("MESSAGE_MAX_BATCH_RECIPIENTS", 500),
    # Total submission attempts per message (automatic + manual).
    "MAX_ATTEMPTS": env_int("MESSAGE_MAX_ATTEMPTS", 5),
    # Attempts the worker makes on its own before handing over to the recruiter.
    "AUTO_ATTEMPTS": env_int("MESSAGE_AUTO_ATTEMPTS", 3),
    "BACKOFF_BASE_SECONDS": env_float("RETRY_BACKOFF_BASE_SECONDS", 2.0),
    "BACKOFF_MAX_SECONDS": env_float("RETRY_BACKOFF_MAX_SECONDS", 60.0),
    "WORKER_BATCH_SIZE": env_int("WORKER_BATCH_SIZE", 25),
    "WORKER_POLL_INTERVAL_SECONDS": env_float("WORKER_POLL_INTERVAL_SECONDS", 0.5),
    "SENDING_LEASE_SECONDS": env_int("SENDING_LEASE_SECONDS", 60),
    "MAX_SCHEDULE_DAYS": env_int("MESSAGE_MAX_SCHEDULE_DAYS", 30),
}

# --- Logging ------------------------------------------------------------------
# Candidate contact details and message bodies are never logged; log lines
# reference opaque IDs only.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
        "httpx": {"level": "WARNING"},
    },
}

if len(sys.argv) > 1 and sys.argv[1] == "test":
    LOGGING["root"]["level"] = "CRITICAL"
    LOGGING["loggers"]["django.request"] = {"level": "CRITICAL"}  # keep test output readable; assertLogs still works
