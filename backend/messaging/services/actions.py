"""Recruiter actions on an existing message: manual retry and cancelling a schedule."""

from django.db import transaction
from django.utils import timezone

from core.exceptions import ApiError

from ..models import AttemptTrigger, ErrorCategory, EventKind, Message, MessageStatus
from ..policy import retry_block_reason
from .events import record_event


def request_manual_retry(message_id) -> Message:
    with transaction.atomic():
        message = Message.objects.select_for_update().filter(id=message_id).first()
        if message is None:
            raise ApiError("Message not found.", "not_found", 404)
        reason = retry_block_reason(message)
        if reason:
            raise ApiError(reason, "retry_not_allowed", 409)

        previous_error = message.get_error_category_display()
        if message.error_category == ErrorCategory.DELIVERY_FAILED:
            # The provider accepted the previous send, so this is a genuinely new
            # send: it needs a fresh idempotency key and provider reference.
            message.idempotency_key = f"msg_{message.id.hex}_{message.attempt_count + 1}"
            message.provider_message_id = None
            message.sent_at = None
        message.status = MessageStatus.QUEUED
        message.next_attempt_at = timezone.now()
        message.next_trigger = AttemptTrigger.MANUAL_RETRY
        message.failed_at = None
        message.error_category = message.error_code = message.error_detail = ""
        message.save()
        record_event(
            message,
            EventKind.MANUAL_RETRY,
            detail=f"Retry requested after '{previous_error}' (attempt {message.attempt_count + 1} of {message.max_attempts}).",
        )
    return message


def cancel_scheduled(message_id) -> Message:
    now = timezone.now()
    with transaction.atomic():
        updated = Message.objects.filter(id=message_id, status=MessageStatus.SCHEDULED).update(
            status=MessageStatus.CANCELLED, cancelled_at=now, next_attempt_at=None, updated_at=now
        )
        message = Message.objects.filter(id=message_id).first()
        if message is None:
            raise ApiError("Message not found.", "not_found", 404)
        if not updated:
            raise ApiError("Only scheduled messages that haven't started sending can be cancelled.", "cancel_not_allowed", 409)
        record_event(message, EventKind.CANCELLED, detail="Scheduled message cancelled by recruiter.")
    return message
