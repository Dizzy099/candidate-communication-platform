"""HTTP adapter for the SimuText provider simulator (``/simulator`` service).

The simulator is a separate process with its own database. This adapter talks
to it exactly like it would talk to a real provider: authenticated HTTP calls
out, HMAC-signed webhooks in.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime

import httpx
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ..models import ErrorCategory
from .base import (
    CommunicationProvider,
    OutboundMessage,
    ProviderError,
    ProviderHealth,
    SendResult,
    StatusUpdate,
    WebhookError,
)

SIGNATURE_HEADER = "X-Sim-Signature"
WEBHOOK_STATUSES = {"sent", "delivered", "read", "failed"}


def sign_payload(secret: str, timestamp: int, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return f"t={timestamp},v1={mac.hexdigest()}"


class SimulatorProvider(CommunicationProvider):
    name = "simulator"
    display_name = "SimuText (simulated SMS provider)"
    channel = "sms"
    simulated = True

    def __init__(self, config: dict):
        self.base_url = config["BASE_URL"].rstrip("/")
        self.api_key = config["API_KEY"]
        self.webhook_secret = config["WEBHOOK_SECRET"]
        self.timeout = config["TIMEOUT_SECONDS"]
        self.tolerance = config["WEBHOOK_TOLERANCE_SECONDS"]
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        return self._client

    # --- sending ----------------------------------------------------------
    def send(self, message: OutboundMessage) -> SendResult:
        if not self.api_key:
            raise ProviderError(ErrorCategory.CONFIGURATION, "missing_api_key", "Provider API key is not configured.")
        payload = {
            "to": message.to_phone,
            "body": message.body,
            "channel": message.channel,
            "client_reference": message.client_reference,
            "callback_url": message.status_callback_url,
        }
        try:
            response = self.client.post(
                "/v1/messages", json=payload, headers={"Idempotency-Key": message.idempotency_key}
            )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                ErrorCategory.PROVIDER_UNAVAILABLE, "timeout", "The provider did not respond in time."
            ) from exc
        except httpx.TransportError as exc:
            raise ProviderError(
                ErrorCategory.PROVIDER_UNAVAILABLE, "connection_failed", "Could not connect to the provider."
            ) from exc

        if response.status_code in (200, 201):
            try:
                data = response.json()
                return SendResult(provider_message_id=str(data["id"]), status=str(data["status"]))
            except (ValueError, KeyError, TypeError) as exc:
                raise ProviderError(
                    ErrorCategory.UNKNOWN, "malformed_response", "The provider returned an unreadable response.",
                    http_status=response.status_code,
                ) from exc
        raise self._classify(response)

    @staticmethod
    def _classify(response: httpx.Response) -> ProviderError:
        status = response.status_code
        try:
            code = str(response.json().get("error", {}).get("code", ""))
        except (ValueError, AttributeError):
            code = ""
        retry_after = None
        if response.headers.get("Retry-After", "").isdigit():
            retry_after = int(response.headers["Retry-After"])
        detail = f"Provider responded with HTTP {status}" + (f" ({code})." if code else ".")

        if status == 422 or code == "invalid_recipient":
            category = ErrorCategory.INVALID_RECIPIENT
        elif status == 400 and code in {"content_too_long", "content_rejected"}:
            category = ErrorCategory.CONTENT_REJECTED
        elif status in (401, 403):
            category = ErrorCategory.CONFIGURATION
        elif status == 429:
            category = ErrorCategory.RATE_LIMITED
            retry_after = retry_after or 5
        elif status == 503:
            category = ErrorCategory.PROVIDER_UNAVAILABLE
        elif status >= 500:
            category = ErrorCategory.PROVIDER_ERROR
        else:
            category = ErrorCategory.UNKNOWN
        return ProviderError(category, code or f"http_{status}", detail, http_status=status, retry_after_seconds=retry_after)

    # --- health -------------------------------------------------------------
    def health(self) -> ProviderHealth:
        now = timezone.now()
        try:
            response = self.client.get("/v1/health", timeout=2.0)
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return ProviderHealth("unavailable", "The messaging service can't be reached.", now)
        if response.status_code == 200 and data.get("status") == "operational":
            return ProviderHealth("operational", "All systems operational.", now)
        if data.get("status") == "outage":
            return ProviderHealth("unavailable", "The provider is reporting an outage.", now)
        return ProviderHealth("degraded", "The provider reported a problem.", now)

    def set_outage(self, enabled: bool) -> None:
        try:
            response = self.client.post("/v1/simulator/outage", json={"enabled": enabled}, timeout=3.0)
        except httpx.HTTPError as exc:
            raise ProviderError(
                ErrorCategory.PROVIDER_UNAVAILABLE, "connection_failed", "Could not connect to the provider."
            ) from exc
        if response.status_code != 200:
            raise self._classify(response)

    # --- webhooks -----------------------------------------------------------
    def verify_signature(self, header: str, body: bytes, now: float | None = None) -> None:
        if not self.webhook_secret:
            raise WebhookError("Webhook secret is not configured.", 401)
        try:
            parts = dict(item.split("=", 1) for item in header.split(","))
            timestamp = int(parts["t"])
            received = parts["v1"]
        except (ValueError, KeyError):
            raise WebhookError("Missing or malformed signature.", 401) from None
        now = time.time() if now is None else now
        if abs(now - timestamp) > self.tolerance:
            raise WebhookError("Signature timestamp outside the allowed window.", 401)
        expected = sign_payload(self.webhook_secret, timestamp, body).split("v1=", 1)[1]
        if not hmac.compare_digest(expected, received):
            raise WebhookError("Invalid signature.", 401)

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> StatusUpdate:
        self.verify_signature(headers.get(SIGNATURE_HEADER, ""), body)
        try:
            data = json.loads(body)
            status = str(data["status"])
            occurred_at = parse_datetime(str(data["occurred_at"]))
            error = data.get("error") or {}
            update = StatusUpdate(
                provider_event_id=str(data["event_id"]),
                provider_message_id=str(data["message_id"]),
                client_reference=str(data.get("client_reference") or ""),
                status=status,
                occurred_at=occurred_at if isinstance(occurred_at, datetime) else None,
                error_code=str(error.get("code", ""))[:60],
                error_message=str(error.get("message", ""))[:300],
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            raise WebhookError("Malformed webhook payload.", 400) from None
        if status not in WEBHOOK_STATUSES or update.occurred_at is None:
            raise WebhookError("Unsupported status or timestamp.", 400)
        if timezone.is_naive(update.occurred_at):
            raise WebhookError("Timestamp must include a timezone.", 400)
        return update
