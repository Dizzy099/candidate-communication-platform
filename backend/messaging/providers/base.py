"""The contract every communication provider adapter implements.

Business logic (``messaging.services``) only talks to this interface, so a
real provider (Twilio, WhatsApp Cloud API, Resend...) can be added as one new
adapter without touching sending, retry or status-tracking code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OutboundMessage:
    client_reference: str  # our message ID, echoed back in status updates
    idempotency_key: str  # same key on retries -> provider must not send twice
    to_phone: str  # E.164
    to_email: str
    body: str
    channel: str
    status_callback_url: str


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str
    status: str  # provider-confirmed status after submission, e.g. "sent"


@dataclass(frozen=True)
class ProviderHealth:
    status: str  # "operational" | "degraded" | "unavailable"
    detail: str
    checked_at: datetime


@dataclass(frozen=True)
class StatusUpdate:
    provider_event_id: str
    provider_message_id: str
    client_reference: str
    status: str  # "sent" | "delivered" | "read" | "failed"
    occurred_at: datetime
    error_code: str = ""
    error_message: str = ""


class ProviderError(Exception):
    """A classified send failure. ``message`` is safe to store and display."""

    def __init__(
        self,
        category: str,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
        retry_after_seconds: int | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retry_after_seconds = retry_after_seconds


class WebhookError(Exception):
    """Webhook rejected. ``status_code`` is 401 for bad signatures, 400 for bad payloads."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class CommunicationProvider(ABC):
    name: str = ""
    display_name: str = ""
    channel: str = "sms"
    simulated: bool = False

    @abstractmethod
    def send(self, message: OutboundMessage) -> SendResult:
        """Submit one message. Raises ProviderError on failure."""

    @abstractmethod
    def health(self) -> ProviderHealth:
        """Report provider reachability; must not raise."""

    @abstractmethod
    def parse_webhook(self, headers: dict[str, str], body: bytes) -> StatusUpdate:
        """Verify authenticity and parse a status notification. Raises WebhookError."""

    def set_outage(self, enabled: bool) -> None:  # pragma: no cover - only simulators support it
        raise NotImplementedError("This provider cannot simulate outages.")
