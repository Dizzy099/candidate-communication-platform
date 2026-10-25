"""Apply provider status notifications safely.

Rules (also documented in the README):

1. **Duplicates** - an event ID we've already stored is acknowledged and
   ignored (unique constraint on ``provider + provider_event_id``).
2. **Forward only** - sent -> delivered -> read. A lower or equal status
   (late or repeated event) is recorded but not applied.
3. **Failure after success** - a ``failed`` report for a message already
   delivered/read is ignored.
4. **Superseded sends** - events for an earlier provider message (before a
   manual retry) never touch the current attempt.
5. **Provider truth wins** - if a send timed out on our side but the provider
   reports it delivered, the delivery is applied and any pending retry stops.
6. **Unknown messages** - recorded for auditing and acknowledged, so the
   provider does not retry forever (e.g. the candidate was deleted).
"""

import uuid
from enum import Enum

from django.db import IntegrityError, transaction

from ..models import (
    STATUS_RANK,
    ErrorCategory,
    EventKind,
    EventSource,
    Message,
    MessageAttempt,
    MessageEvent,
    MessageStatus,
)
from ..providers import StatusUpdate


class Outcome(str, Enum):
    APPLIED = "applied"
    IGNORED = "ignored"
    DUPLICATE = "duplicate"
    UNKNOWN_MESSAGE = "unknown_message"


def _find_message(provider_name: str, update: StatusUpdate):
    qs = Message.objects.select_for_update()
    message = qs.filter(provider=provider_name, provider_message_id=update.provider_message_id).first()
    if message is None and update.client_reference:
        try:
            message = qs.filter(id=uuid.UUID(update.client_reference), provider=provider_name).first()
        except ValueError:
            return None
    return message


def _decide(message: Message, update: StatusUpdate) -> tuple[bool, str]:
    new, current = update.status, message.status
    if message.provider_message_id != update.provider_message_id:
        superseded = MessageAttempt.objects.filter(
            message=message, provider_message_id=update.provider_message_id
        ).exists()
        if message.provider_message_id or superseded:
            return False, "Update belongs to an earlier send attempt."
    if current == MessageStatus.CANCELLED:
        return False, "Message was cancelled."
    if new == MessageStatus.FAILED:
        if current in (MessageStatus.DELIVERED, MessageStatus.READ):
            return False, f"Message is already {current}; failure report ignored."
        if current == MessageStatus.FAILED:
            return False, "Message is already marked as failed."
        return True, ""
    if current == MessageStatus.FAILED:
        if message.error_category == ErrorCategory.DELIVERY_FAILED:
            return False, "Delivery already failed; late update ignored."
        return True, ""  # we saw a submission error, but the provider did accept it
    if STATUS_RANK[new] <= STATUS_RANK.get(current, 0):
        return False, f"Message is already {current}; out-of-order or repeated '{new}' update ignored."
    return True, ""


def _apply(message: Message, update: StatusUpdate) -> None:
    at = update.occurred_at
    message.status = update.status
    message.provider_message_id = message.provider_message_id or update.provider_message_id
    message.lease_expires_at = None
    message.next_attempt_at = None
    if update.status == MessageStatus.FAILED:
        message.failed_at = at
        message.error_category = ErrorCategory.DELIVERY_FAILED
        message.error_code = update.error_code or "delivery_failed"
        message.error_detail = update.error_message or "The provider reported that delivery failed."
    else:
        message.sent_at = message.sent_at or at
        if update.status in (MessageStatus.DELIVERED, MessageStatus.READ):
            message.delivered_at = message.delivered_at or at
        if update.status == MessageStatus.READ:
            message.read_at = at
        message.failed_at = None
        message.error_category = message.error_code = message.error_detail = ""
    message.save()


def apply_status_update(provider_name: str, update: StatusUpdate) -> Outcome:
    event_fields = {
        "source": EventSource.PROVIDER,
        "provider": provider_name,
        "provider_event_id": update.provider_event_id,
        "provider_message_id": update.provider_message_id,
        "status": update.status,
        "occurred_at": update.occurred_at,
    }
    try:
        with transaction.atomic():
            if MessageEvent.objects.filter(provider=provider_name, provider_event_id=update.provider_event_id).exists():
                return Outcome.DUPLICATE
            message = _find_message(provider_name, update)
            if message is None:
                MessageEvent.objects.create(
                    message=None, kind=EventKind.UNKNOWN_MESSAGE, applied=False,
                    detail="No matching message (it may have been deleted).", **event_fields,
                )
                return Outcome.UNKNOWN_MESSAGE
            should_apply, reason = _decide(message, update)
            if should_apply:
                _apply(message, update)
                detail = f"Provider reported '{update.status}'."
                if update.status == MessageStatus.FAILED:
                    detail = f"Provider reported delivery failure: {message.error_detail}"
                MessageEvent.objects.create(message=message, kind=EventKind.STATUS_CHANGED, detail=detail[:300], **event_fields)
                return Outcome.APPLIED
            MessageEvent.objects.create(
                message=message, kind=EventKind.STATUS_IGNORED, applied=False, detail=reason, **event_fields
            )
            return Outcome.IGNORED
    except IntegrityError:
        # The same event was processed concurrently; the unique constraint caught it.
        return Outcome.DUPLICATE
