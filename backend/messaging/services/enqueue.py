"""Turn a compose action into persisted, independently tracked messages.

Nothing here calls the provider. Messages are written as ``queued`` (or
``scheduled``) in one short transaction and the worker delivers them, so a
slow provider can never hold a database transaction open, and one candidate's
failure never blocks another's message.
"""

from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from candidates.models import Candidate

from ..models import EventKind, EventSource, Message, MessageBatch, MessageEvent, MessageStatus, MessageTemplate
from ..providers import get_provider
from . import templating


@dataclass(frozen=True)
class EnqueueResult:
    batch: MessageBatch
    created: bool  # False when the client_request_id was seen before (idempotent replay)


def initial_idempotency_key(message: Message) -> str:
    return f"msg_{message.id.hex}_1"


def enqueue_batch(
    *,
    candidates: list[Candidate],
    body: str,
    client_request_id: str | None = None,
    template: MessageTemplate | None = None,
    scheduled_at: datetime | None = None,
    provider_name: str | None = None,
) -> EnqueueResult:
    if client_request_id:
        existing = MessageBatch.objects.filter(client_request_id=client_request_id).first()
        if existing:
            return EnqueueResult(existing, created=False)

    provider = get_provider(provider_name)
    now = timezone.now()
    status = MessageStatus.SCHEDULED if scheduled_at else MessageStatus.QUEUED
    max_attempts = settings.MESSAGING["MAX_ATTEMPTS"]

    try:
        with transaction.atomic():
            batch = MessageBatch.objects.create(
                client_request_id=client_request_id or None,
                body=body,
                template=template,
                channel=provider.channel,
                provider=provider.name,
                scheduled_at=scheduled_at,
                recipient_count=len(candidates),
            )
            messages = []
            for candidate in candidates:
                message = Message(
                    candidate=candidate,
                    batch=batch,
                    body=templating.render(body, candidate),
                    channel=provider.channel,
                    provider=provider.name,
                    status=status,
                    scheduled_at=scheduled_at,
                    next_attempt_at=scheduled_at or now,
                    max_attempts=max_attempts,
                )
                message.idempotency_key = initial_idempotency_key(message)
                messages.append(message)
            Message.objects.bulk_create(messages)
            detail = (
                f"Scheduled for {timezone.localtime(scheduled_at):%d-%m-%Y %I:%M %p}."
                if scheduled_at else "Queued for sending."
            )
            MessageEvent.objects.bulk_create(
                MessageEvent(
                    message=message,
                    source=EventSource.SYSTEM,
                    kind=EventKind.SCHEDULED if scheduled_at else EventKind.QUEUED,
                    status=status,
                    detail=detail,
                    occurred_at=now,
                )
                for message in messages
            )
    except IntegrityError:
        # A concurrent request with the same client_request_id won the race.
        if client_request_id:
            existing = MessageBatch.objects.filter(client_request_id=client_request_id).first()
            if existing:
                return EnqueueResult(existing, created=False)
        raise
    return EnqueueResult(batch, created=True)
