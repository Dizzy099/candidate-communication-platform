"""Background worker: delivers queued and scheduled messages and runs automatic retries.

Run alongside the API:  python manage.py run_worker
"""

import logging
import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import OperationalError, close_old_connections

from messaging.services.dispatch import run_once

logger = logging.getLogger("messaging.worker")


class Command(BaseCommand):
    help = "Deliver queued/scheduled messages and run automatic retries."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process one round of due messages and exit.")

    def handle(self, *args, **options):
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        interval = settings.MESSAGING["WORKER_POLL_INTERVAL_SECONDS"]
        self.stdout.write(f"Message worker started (polling every {interval}s). Press Ctrl+C to stop.")
        while not stop.is_set():
            close_old_connections()
            processed = 0
            try:
                processed = run_once()
            except OperationalError:
                logger.warning("Database busy; will try again shortly", exc_info=True)
            except Exception:  # noqa: BLE001 - keep the worker alive; the error is logged
                logger.exception("Worker iteration failed")
            if options["once"]:
                break
            if processed == 0:
                stop.wait(interval)  # idle poll interval, not simulated work
        self.stdout.write("Message worker stopped.")
