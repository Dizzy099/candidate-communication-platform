"""Delivers due status events to the platform's webhook (at-least-once).

Like real providers: non-2xx responses and network errors are retried with
exponential backoff, then given up after ``WEBHOOK_MAX_ATTEMPTS``.
"""

import json
import logging
import threading
import time
from datetime import timedelta

import httpx
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from .models import OutboundEvent
from .signing import sign_payload

logger = logging.getLogger(__name__)
RANK = {"sent": 1, "delivered": 2, "read": 3}


def payload_for(event: OutboundEvent) -> dict:
    message = event.message
    return {
        "event_id": event.id,
        "type": "message.status",
        "message_id": message.id,
        "client_reference": message.client_reference,
        "status": event.status,
        "occurred_at": event.occurred_at.isoformat(),
        "error": {"code": event.error_code, "message": event.error_message} if event.error_code else None,
    }


def _apply_to_simulated_message(event: OutboundEvent) -> None:
    message = event.message
    if event.status == "failed" or RANK.get(event.status, 0) > RANK.get(message.status, 0):
        message.status = event.status
        message.save(update_fields=["status", "updated_at"])
    event.applied_to_message = True


def deliver_due_events(client: httpx.Client, now=None, limit: int = 50) -> int:
    cfg = settings.SIMULATOR
    now = now or timezone.now()
    due = list(
        OutboundEvent.objects.select_related("message")
        .filter(delivered_at__isnull=True, gave_up=False, next_attempt_at__lte=now)
        .order_by("next_attempt_at")[:limit]
    )
    for event in due:
        if not event.applied_to_message:
            _apply_to_simulated_message(event)
        body = json.dumps(payload_for(event)).encode()
        headers = {
            "Content-Type": "application/json",
            "X-Sim-Signature": sign_payload(cfg["WEBHOOK_SECRET"], int(time.time()), body),
        }
        try:
            response = client.post(event.message.callback_url, content=body, headers=headers)
            ok, failure = response.is_success, f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            ok, failure = False, type(exc).__name__
        if ok:
            if event.extra_deliveries:
                # Deliberately resend the identical event (same event_id) shortly after.
                event.extra_deliveries -= 1
                event.next_attempt_at = now + timedelta(milliseconds=500)
            else:
                event.delivered_at = now
            event.last_error = ""
        else:
            event.delivery_attempts += 1
            event.last_error = failure[:200]
            if event.delivery_attempts >= cfg["WEBHOOK_MAX_ATTEMPTS"]:
                event.gave_up = True
                logger.warning("Giving up on event %s after %s attempts", event.id, event.delivery_attempts)
            else:
                event.next_attempt_at = now + timedelta(seconds=min(2 ** event.delivery_attempts, 60))
        event.save()
    return len(due)


def run_dispatcher(stop: threading.Event) -> None:
    cfg = settings.SIMULATOR
    interval = cfg["DISPATCH_INTERVAL_SECONDS"]
    with httpx.Client(timeout=cfg["WEBHOOK_TIMEOUT_SECONDS"]) as client:
        while not stop.is_set():
            close_old_connections()
            try:
                delivered = deliver_due_events(client)
            except Exception:  # noqa: BLE001 - keep dispatching; the error is logged
                logger.exception("Dispatcher iteration failed")
                delivered = 0
            if not delivered:
                stop.wait(interval)
