"""Worker side: claim due messages, submit them to the provider, record outcomes.

Concurrency model
-----------------
* A message is *claimed* with a conditional UPDATE (``status`` must still be
  queued/scheduled). Only one worker can win, on SQLite and PostgreSQL alike.
* The provider call happens **outside** any transaction. Results are written
  afterwards in a short ``select_for_update`` transaction that re-reads the
  row, so a webhook that arrived meanwhile is never overwritten.
* A claimed message carries a lease. If a worker dies mid-send the lease
  expires and the message is re-queued with the *same* idempotency key, so a
  provider that honours idempotency keys will not send it twice.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ..models import (
    AttemptOutcome,
    AttemptTrigger,
    ErrorCategory,
    EventKind,
    Message,
    MessageAttempt,
    MessageStatus,
)
from ..policy import backoff_seconds, should_auto_retry
from ..providers import (
    CommunicationProvider,
    OutboundMessage,
    ProviderError,
    SendResult,
    UnknownProvider,
    get_provider,
)
from .events import record_event

logger = logging.getLogger(__name__)

CLAIMABLE = (MessageStatus.QUEUED, MessageStatus.SCHEDULED)


def webhook_url(provider: CommunicationProvider) -> str:
    base = settings.PROVIDER["PUBLIC_WEBHOOK_BASE_URL"].rstrip("/")
    return f"{base}/api/webhooks/provider/{provider.name}/"


def recover_stale_leases(now=None) -> int:
    """Re-queue messages whose worker disappeared mid-send."""
    now = now or timezone.now()
    recovered = 0
    for message_id in Message.objects.filter(status=MessageStatus.SENDING, lease_expires_at__lt=now).values_list(
        "id", flat=True
    ):
        with transaction.atomic():
            updated = Message.objects.filter(
                id=message_id, status=MessageStatus.SENDING, lease_expires_at__lt=now
            ).update(status=MessageStatus.QUEUED, next_attempt_at=now, lease_expires_at=None, next_trigger=AttemptTrigger.AUTO_RETRY)
            if updated:
                MessageAttempt.objects.filter(message_id=message_id, outcome=AttemptOutcome.IN_PROGRESS).update(
                    outcome=AttemptOutcome.FAILED, error_code="worker_interrupted", finished_at=now
                )
                message = Message.objects.get(id=message_id)
                record_event(message, EventKind.RETRY_SCHEDULED, detail="Send was interrupted; retrying with the same idempotency key.")
                recovered += 1
    if recovered:
        logger.warning("Recovered %s message(s) with expired send leases", recovered)
    return recovered


def claim_due_messages(now=None, limit: int | None = None) -> list:
    now = now or timezone.now()
    limit = limit or settings.MESSAGING["WORKER_BATCH_SIZE"]
    lease_until = now + timedelta(seconds=settings.MESSAGING["SENDING_LEASE_SECONDS"])
    due_ids = list(
        Message.objects.filter(status__in=CLAIMABLE, next_attempt_at__lte=now)
        .order_by("next_attempt_at", "created_at")
        .values_list("id", flat=True)[:limit]
    )
    claimed = []
    for message_id in due_ids:
        won = Message.objects.filter(id=message_id, status__in=CLAIMABLE, next_attempt_at__lte=now).update(
            status=MessageStatus.SENDING,
            lease_expires_at=lease_until,
            attempt_count=F("attempt_count") + 1,
            updated_at=now,
        )
        if won:
            claimed.append(message_id)
    return claimed


def process_message(message_id) -> None:
    try:
        message = Message.objects.select_related("candidate").get(id=message_id, status=MessageStatus.SENDING)
    except Message.DoesNotExist:
        logger.info("Message %s no longer claimable (deleted or updated); skipping", message_id)
        return
    try:
        provider = get_provider(message.provider)
    except UnknownProvider:
        provider = None

    attempt = MessageAttempt.objects.create(
        message=message,
        number=message.attempt_count,
        trigger=message.next_trigger,
        idempotency_key=message.idempotency_key,
        started_at=timezone.now(),
    )
    outbound = OutboundMessage(
        client_reference=str(message.id),
        idempotency_key=message.idempotency_key,
        to_phone=message.candidate.phone,
        to_email=message.candidate.email,
        body=message.body,
        channel=message.channel,
        status_callback_url=webhook_url(provider) if provider else "",
    )
    try:
        if provider is None:
            raise ProviderError(ErrorCategory.CONFIGURATION, "provider_not_configured",
                                f"Provider '{message.provider}' is no longer configured.")
        result = provider.send(outbound)
    except ProviderError as error:
        logger.info("Message %s attempt %s failed: %s/%s", message.id, attempt.number, error.category, error.code)
        _record_failure(message.id, attempt.id, error)
    except Exception:  # noqa: BLE001 - never let one message crash the worker loop
        logger.exception("Unexpected error sending message %s", message.id)
        _record_failure(
            message.id,
            attempt.id,
            ProviderError("unknown", "unexpected_error", "An unexpected error occurred while sending."),
        )
    else:
        logger.info("Message %s accepted by %s as %s", message.id, message.provider, result.provider_message_id)
        _record_success(message.id, attempt.id, result)


def _record_success(message_id, attempt_id, result: SendResult) -> None:
    now = timezone.now()
    with transaction.atomic():
        message = Message.objects.select_for_update().filter(id=message_id).first()
        if message is None:
            return
        MessageAttempt.objects.filter(id=attempt_id).update(
            outcome=AttemptOutcome.ACCEPTED, provider_message_id=result.provider_message_id, finished_at=now
        )
        message.provider_message_id = result.provider_message_id
        message.sent_at = message.sent_at or now
        message.lease_expires_at = None
        message.next_attempt_at = None
        if message.status == MessageStatus.SENDING:
            # A webhook may already have moved it further (e.g. delivered); keep that.
            message.status = MessageStatus.SENT
            message.error_category = message.error_code = message.error_detail = ""
            message.failed_at = None
        message.save()
        record_event(
            message,
            EventKind.SUBMITTED,
            status=MessageStatus.SENT,
            detail=f"Accepted by provider (reference {result.provider_message_id}).",
            provider_message_id=result.provider_message_id,
        )


def _record_failure(message_id, attempt_id, error: ProviderError) -> None:
    now = timezone.now()
    with transaction.atomic():
        message = Message.objects.select_for_update().filter(id=message_id).first()
        if message is None:
            return
        MessageAttempt.objects.filter(id=attempt_id).update(
            outcome=AttemptOutcome.FAILED,
            error_category=error.category,
            error_code=error.code[:60],
            http_status=error.http_status,
            retry_after_seconds=error.retry_after_seconds,
            finished_at=now,
        )
        record_event(
            message,
            EventKind.ATTEMPT_FAILED,
            status=MessageStatus.FAILED,
            detail=f"Attempt {message.attempt_count} failed: {error.message}",
        )
        if message.status != MessageStatus.SENDING:
            # The provider told us the real outcome via webhook while we waited.
            return
        message.error_category = error.category
        message.error_code = error.code[:60]
        message.error_detail = error.message[:300]
        message.lease_expires_at = None
        if should_auto_retry(error.category, message.attempt_count):
            delay = error.retry_after_seconds or backoff_seconds(message.attempt_count)
            message.status = MessageStatus.QUEUED
            message.next_attempt_at = now + timedelta(seconds=delay)
            message.next_trigger = AttemptTrigger.AUTO_RETRY
            message.save()
            record_event(
                message,
                EventKind.RETRY_SCHEDULED,
                detail=f"Retrying automatically in {delay:g}s (attempt {message.attempt_count + 1}).",
            )
        else:
            message.status = MessageStatus.FAILED
            message.failed_at = now
            message.next_attempt_at = None
            message.save()


def run_once(now=None) -> int:
    """One worker tick. Returns how many messages were processed."""
    recover_stale_leases(now)
    claimed = claim_due_messages(now)
    for message_id in claimed:
        process_message(message_id)
    return len(claimed)
