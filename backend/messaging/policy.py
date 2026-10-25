"""Failure classification, recruiter-facing copy and retry rules in one place.

| Category             | Automatic retry | Manual retry | Why                                   |
|----------------------|-----------------|--------------|---------------------------------------|
| invalid_recipient    | no              | no           | Same number will fail again           |
| content_rejected     | no              | no           | Same text will be rejected again      |
| rate_limited         | yes (Retry-After)| yes         | Provider asked us to slow down        |
| provider_error       | yes (backoff)   | yes          | Temporary fault on the provider side  |
| provider_unavailable | yes (backoff)   | yes          | Provider unreachable / in outage      |
| delivery_failed      | no              | yes          | Phone may be reachable later          |
| configuration        | no              | yes          | Needs an admin fix first, then retry  |
| unknown              | no              | yes          | Unclassified; let a human decide      |
"""

from dataclasses import dataclass

from django.conf import settings

from .models import ErrorCategory, Message, MessageStatus

AUTO_RETRY_CATEGORIES = frozenset({
    ErrorCategory.RATE_LIMITED,
    ErrorCategory.PROVIDER_ERROR,
    ErrorCategory.PROVIDER_UNAVAILABLE,
})
MANUAL_RETRY_CATEGORIES = AUTO_RETRY_CATEGORIES | {
    ErrorCategory.DELIVERY_FAILED,
    ErrorCategory.CONFIGURATION,
    ErrorCategory.UNKNOWN,
}


@dataclass(frozen=True)
class ErrorCopy:
    title: str
    explanation: str


ERROR_COPY: dict[str, ErrorCopy] = {
    ErrorCategory.INVALID_RECIPIENT: ErrorCopy(
        "Invalid mobile number",
        "The provider says this number can't receive messages. Check the candidate's mobile number; "
        "retrying won't help.",
    ),
    ErrorCategory.CONTENT_REJECTED: ErrorCopy(
        "Message rejected",
        "The provider rejected this message text. Edit the message and send it again.",
    ),
    ErrorCategory.RATE_LIMITED: ErrorCopy(
        "Sending too fast",
        "The provider limited how many messages we can send right now. The platform waits and retries "
        "automatically.",
    ),
    ErrorCategory.PROVIDER_ERROR: ErrorCopy(
        "Temporary provider error",
        "The messaging service had a temporary problem. The platform retries automatically; you can "
        "also retry manually.",
    ),
    ErrorCategory.PROVIDER_UNAVAILABLE: ErrorCopy(
        "Messaging service unavailable",
        "The messaging service couldn't be reached. Your message is saved; retry once the service is "
        "back.",
    ),
    ErrorCategory.DELIVERY_FAILED: ErrorCopy(
        "Not delivered",
        "The provider accepted the message but couldn't deliver it to the candidate's phone "
        "(for example, the phone is switched off). You can try again later.",
    ),
    ErrorCategory.CONFIGURATION: ErrorCopy(
        "Messaging not configured",
        "The provider rejected the platform's credentials. An administrator must fix the configuration "
        "before this can be retried.",
    ),
    ErrorCategory.UNKNOWN: ErrorCopy(
        "Unexpected provider response",
        "Something unexpected happened while sending. You can retry; if it keeps failing, contact support.",
    ),
}


def error_copy(category: str) -> ErrorCopy | None:
    return ERROR_COPY.get(category) if category else None


def backoff_seconds(failed_attempts: int) -> float:
    """Exponential backoff: base, 2x base, 4x base ... capped. ``failed_attempts`` >= 1."""
    cfg = settings.MESSAGING
    return min(cfg["BACKOFF_BASE_SECONDS"] * (2 ** max(failed_attempts - 1, 0)), cfg["BACKOFF_MAX_SECONDS"])


def should_auto_retry(category: str, attempt_count: int) -> bool:
    cfg = settings.MESSAGING
    limit = min(cfg["AUTO_ATTEMPTS"], cfg["MAX_ATTEMPTS"])
    return category in AUTO_RETRY_CATEGORIES and attempt_count < limit


def retry_block_reason(message: Message) -> str | None:
    """``None`` when a recruiter may retry; otherwise a sentence explaining why not."""
    if message.status != MessageStatus.FAILED:
        return "Only failed messages can be retried."
    if message.error_category not in MANUAL_RETRY_CATEGORIES:
        return "This failure is permanent, so retrying would fail again."
    if message.attempt_count >= message.max_attempts:
        return f"Retry limit reached ({message.max_attempts} attempts)."
    return None
