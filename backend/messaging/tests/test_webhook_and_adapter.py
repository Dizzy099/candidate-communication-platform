"""The simulator adapter (HTTP contract, error classification, signatures) and the webhook endpoint."""

import json
import time

import httpx
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.testing import make_candidate
from messaging.models import ErrorCategory, Message, MessageStatus
from messaging.providers import OutboundMessage, ProviderError, WebhookError
from messaging.providers.registry import reset_provider_cache
from messaging.providers.simulator import SimulatorProvider, sign_payload

CONFIG = {
    "BACKEND": "simulator", "BASE_URL": "http://sim.test", "API_KEY": "key", "WEBHOOK_SECRET": "secret",
    "TIMEOUT_SECONDS": 1.0, "PUBLIC_WEBHOOK_BASE_URL": "http://api.test", "WEBHOOK_TOLERANCE_SECONDS": 300,
}
OUTBOUND = OutboundMessage("ref-1", "idem-1", "+919800000001", "a@example.com", "Hi", "sms", "http://api.test/hook")


def provider_with(handler) -> SimulatorProvider:
    provider = SimulatorProvider(CONFIG)
    provider._client = httpx.Client(base_url=CONFIG["BASE_URL"], transport=httpx.MockTransport(handler))
    return provider


def responds(status: int, body=None, headers=None):
    return lambda request: httpx.Response(status, json=body or {}, headers=headers)


class AdapterSendTests(SimpleTestCase):
    def test_success_sends_auth_idempotency_key_and_callback(self):
        seen = {}

        def handler(request):
            seen.update(headers=request.headers, body=json.loads(request.content))
            return httpx.Response(201, json={"id": "sim_1", "status": "sent"})

        provider = SimulatorProvider(CONFIG)
        provider._client = httpx.Client(base_url="http://sim.test", headers={"Authorization": "Bearer key"},
                                        transport=httpx.MockTransport(handler))
        result = provider.send(OUTBOUND)
        self.assertEqual((result.provider_message_id, result.status), ("sim_1", "sent"))
        self.assertEqual(seen["headers"]["Idempotency-Key"], "idem-1")
        self.assertEqual(seen["headers"]["Authorization"], "Bearer key")
        self.assertEqual(seen["body"]["callback_url"], "http://api.test/hook")
        self.assertEqual(seen["body"]["client_reference"], "ref-1")

    def test_error_classification(self):
        cases = [
            (422, {"error": {"code": "invalid_recipient"}}, None, ErrorCategory.INVALID_RECIPIENT),
            (400, {"error": {"code": "content_too_long"}}, None, ErrorCategory.CONTENT_REJECTED),
            (401, {"error": {"code": "unauthorized"}}, None, ErrorCategory.CONFIGURATION),
            (429, {"error": {"code": "rate_limited"}}, {"Retry-After": "4"}, ErrorCategory.RATE_LIMITED),
            (503, {"error": {"code": "service_unavailable"}}, None, ErrorCategory.PROVIDER_UNAVAILABLE),
            (500, {"error": {"code": "internal_error"}}, None, ErrorCategory.PROVIDER_ERROR),
            (418, {}, None, ErrorCategory.UNKNOWN),
        ]
        for status, body, headers, category in cases:
            with self.subTest(status=status), self.assertRaises(ProviderError) as ctx:
                provider_with(responds(status, body, headers)).send(OUTBOUND)
            self.assertEqual(ctx.exception.category, category)
        with self.assertRaises(ProviderError) as ctx:
            provider_with(responds(429, {}, {"Retry-After": "4"})).send(OUTBOUND)
        self.assertEqual(ctx.exception.retry_after_seconds, 4)

    def test_network_failures_mean_unavailable(self):
        def timeout(request):
            raise httpx.ReadTimeout("slow", request=request)

        def refused(request):
            raise httpx.ConnectError("refused", request=request)

        for handler, code in [(timeout, "timeout"), (refused, "connection_failed")]:
            with self.subTest(code=code), self.assertRaises(ProviderError) as ctx:
                provider_with(handler).send(OUTBOUND)
            self.assertEqual((ctx.exception.category, ctx.exception.code), (ErrorCategory.PROVIDER_UNAVAILABLE, code))

    def test_malformed_success_response_is_unknown(self):
        with self.assertRaises(ProviderError) as ctx:
            provider_with(responds(201, {"unexpected": True})).send(OUTBOUND)
        self.assertEqual(ctx.exception.category, ErrorCategory.UNKNOWN)

    def test_missing_api_key_is_configuration_error(self):
        provider = SimulatorProvider({**CONFIG, "API_KEY": ""})
        with self.assertRaises(ProviderError) as ctx:
            provider.send(OUTBOUND)
        self.assertEqual(ctx.exception.category, ErrorCategory.CONFIGURATION)

    def test_health_mapping(self):
        self.assertEqual(provider_with(responds(200, {"status": "operational"})).health().status, "operational")
        self.assertEqual(provider_with(responds(503, {"status": "outage"})).health().status, "unavailable")

        def down(request):
            raise httpx.ConnectError("refused", request=request)

        self.assertEqual(provider_with(down).health().status, "unavailable")


class SignatureTests(SimpleTestCase):
    def setUp(self):
        self.provider = SimulatorProvider(CONFIG)
        self.body = b'{"x": 1}'

    def test_valid_signature_passes(self):
        now = int(time.time())
        self.provider.verify_signature(sign_payload("secret", now, self.body), self.body, now=now)

    def test_rejects_tampered_body_wrong_secret_stale_and_malformed(self):
        now = int(time.time())
        bad = [
            (sign_payload("secret", now, self.body), b'{"x": 2}', now),
            (sign_payload("other", now, self.body), self.body, now),
            (sign_payload("secret", now - 301, self.body), self.body, now),
            ("garbage", self.body, now),
            ("", self.body, now),
        ]
        for header, body, at in bad:
            with self.subTest(header=header[:20]), self.assertRaises(WebhookError) as ctx:
                self.provider.verify_signature(header, body, now=at)
            self.assertEqual(ctx.exception.status_code, 401)


@override_settings(PROVIDER=CONFIG)
class WebhookEndpointTests(TestCase):
    def setUp(self):
        reset_provider_cache()
        self.addCleanup(reset_provider_cache)
        self.message = Message.objects.create(
            candidate=make_candidate(), body="Hi", provider="simulator", status=MessageStatus.SENT,
            provider_message_id="sim_1", idempotency_key="k", attempt_count=1,
        )

    def post(self, payload: dict, secret="secret", provider="simulator"):
        body = json.dumps(payload).encode()
        return self.client.post(
            f"/api/webhooks/provider/{provider}/", data=body, content_type="application/json",
            HTTP_X_SIM_SIGNATURE=sign_payload(secret, int(time.time()), body),
        )

    def payload(self, **overrides):
        return {"event_id": "evt_1", "message_id": "sim_1", "client_reference": str(self.message.id),
                "status": "delivered", "occurred_at": timezone.now().isoformat(), **overrides}

    def test_signed_update_is_applied_then_deduplicated(self):
        first = self.post(self.payload())
        self.assertEqual((first.status_code, first.json()["result"]), (200, "applied"))
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, MessageStatus.DELIVERED)
        again = self.post(self.payload())
        self.assertEqual((again.status_code, again.json()["result"]), (200, "duplicate"))

    def test_bad_signature_is_rejected_without_changes(self):
        response = self.post(self.payload(), secret="wrong")
        self.assertEqual(response.status_code, 401)
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, MessageStatus.SENT)

    def test_malformed_payloads_are_rejected(self):
        for payload in [{"event_id": "e"}, self.payload(status="exploded"), self.payload(occurred_at="yesterday")]:
            with self.subTest(payload=payload):
                self.assertEqual(self.post(payload).status_code, 400)

    def test_unknown_provider_and_method(self):
        self.assertEqual(self.post(self.payload(), provider="other").status_code, 404)
        self.assertEqual(self.client.get("/api/webhooks/provider/simulator/").status_code, 405)
