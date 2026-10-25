import json
from collections import defaultdict

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from messaging.providers import (
    CommunicationProvider,
    OutboundMessage,
    ProviderError,
    ProviderHealth,
    SendResult,
    StatusUpdate,
    WebhookError,
)


class FakeProvider(CommunicationProvider):
    """In-memory provider whose responses are scripted per recipient phone number."""

    name = "fake"
    display_name = "Fake provider"
    channel = "sms"
    simulated = True

    def __init__(self, name: str = "fake", channel: str = "sms"):
        self.name = name
        self.channel = channel
        self.display_name = f"Fake {channel} provider"
        self.script: dict[str, list] = defaultdict(list)
        self.calls: list[OutboundMessage] = []
        self.health_status = "operational"
        self.outage: bool | None = None

    def queue(self, phone: str, *outcomes) -> None:
        """Outcomes are ProviderError/Exception instances (raised) or "ok"."""
        self.script[phone].extend(outcomes)

    def send(self, message: OutboundMessage) -> SendResult:
        self.calls.append(message)
        recipient = message.to_email if self.channel == "email" else message.to_phone
        outcome = self.script[recipient].pop(0) if self.script[recipient] else "ok"
        if isinstance(outcome, Exception):
            raise outcome
        return SendResult(provider_message_id=f"{self.name}_{len(self.calls)}", status="sent")

    def health(self) -> ProviderHealth:
        return ProviderHealth(self.health_status, "test", timezone.now())

    def parse_webhook(self, headers, body) -> StatusUpdate:
        if headers.get("X-Test-Auth") != "ok":
            raise WebhookError("bad signature", 401)
        data = json.loads(body)
        return StatusUpdate(
            provider_event_id=data["event_id"],
            provider_message_id=data["message_id"],
            client_reference=data.get("client_reference", ""),
            status=data["status"],
            occurred_at=parse_datetime(data["occurred_at"]),
        )

    def set_outage(self, enabled: bool) -> None:
        self.outage = enabled


def temporary_error(**kwargs) -> ProviderError:
    return ProviderError("provider_error", "internal_error", "Provider responded with HTTP 500.", http_status=500, **kwargs)


def invalid_recipient() -> ProviderError:
    return ProviderError("invalid_recipient", "invalid_recipient", "Provider responded with HTTP 422.", http_status=422)


def rate_limited(seconds: int = 7) -> ProviderError:
    return ProviderError("rate_limited", "rate_limited", "Provider responded with HTTP 429.", http_status=429,
                         retry_after_seconds=seconds)


def unavailable() -> ProviderError:
    return ProviderError("provider_unavailable", "connection_failed", "Could not connect to the provider.")
