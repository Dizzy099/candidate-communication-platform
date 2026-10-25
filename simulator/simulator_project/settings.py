"""SimuText - a standalone fake SMS provider used instead of a real one.

It runs as its own process with its own database and talks to the main
platform only over HTTP: the platform calls its API, and it calls the
platform's webhook with HMAC-signed status updates.
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


DEBUG = env_bool("SIM_DEBUG", False)
SECRET_KEY = os.getenv("SIM_DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("SIM_DJANGO_SECRET_KEY must be set when SIM_DEBUG is false.")
    SECRET_KEY = "simulator-dev-only-secret"  # noqa: S105

ALLOWED_HOSTS = [h.strip() for h in os.getenv("SIM_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = ["django.contrib.contenttypes", "sim"]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "simulator_project.urls"
WSGI_APPLICATION = "simulator_project.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        env="SIM_DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'simulator.sqlite3'}"
    )
}
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"]["OPTIONS"] = {
        "transaction_mode": "IMMEDIATE",
        "timeout": 20,
        "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

SIMULATOR = {
    "API_KEY": os.getenv("SIM_API_KEY", ""),
    "WEBHOOK_SECRET": os.getenv("SIM_WEBHOOK_SECRET", ""),
    "DELIVERY_DELAY_SECONDS": float(os.getenv("SIM_DELIVERY_DELAY_SECONDS", "3")),
    "READ_DELAY_SECONDS": float(os.getenv("SIM_READ_DELAY_SECONDS", "8")),
    "RATE_LIMIT_PER_SECOND": float(os.getenv("SIM_RATE_LIMIT_PER_SECOND", "20")),
    "RATE_LIMIT_BURST": float(os.getenv("SIM_RATE_LIMIT_BURST", "40")),
    "MAX_BODY_LENGTH": int(os.getenv("SIM_MAX_BODY_LENGTH", "1600")),
    "DISPATCH_INTERVAL_SECONDS": float(os.getenv("SIM_DISPATCH_INTERVAL_SECONDS", "0.25")),
    "WEBHOOK_TIMEOUT_SECONDS": float(os.getenv("SIM_WEBHOOK_TIMEOUT_SECONDS", "5")),
    "WEBHOOK_MAX_ATTEMPTS": int(os.getenv("SIM_WEBHOOK_MAX_ATTEMPTS", "8")),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s [simulator] %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.getenv("SIM_LOG_LEVEL", "INFO")},
    "loggers": {"httpx": {"level": "WARNING"}, "django.db.backends": {"level": "WARNING"}},
}

if len(sys.argv) > 1 and sys.argv[1] == "test":
    LOGGING["root"]["level"] = "CRITICAL"
    LOGGING["loggers"]["django.request"] = {"level": "CRITICAL"}
