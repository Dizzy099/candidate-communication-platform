import hashlib
import hmac
import json
from datetime import timedelta
from unittest import mock

import httpx
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from sim import views
from sim.dispatcher import deliver_due_events
from sim.models import OutboundEvent, SimulatedMessage, SimulatorState
from sim.ratelimit import TokenBucket
from sim.scenarios import build_scenario, rejection_for_attempt, scenario_key

SIM = {
    "API_KEY": "key", "WEBHOOK_SECRET": "secret", "DELIVERY_DELAY_SECONDS": 3, "READ_DELAY_SECONDS": 8,
    "RATE_LIMIT_PER_SECOND": 1000, "RATE_LIMIT_BURST": 1000, "MAX_BODY_LENGTH": 1600,
    "DISPATCH_INTERVAL_SECONDS": 0.25, "WEBHOOK_TIMEOUT_SECONDS": 1, "WEBHOOK_MAX_ATTEMPTS": 3,
}


class ScenarioTests(SimpleTestCase):
    def scenario(self, to, previous=0):
        return build_scenario(scenario_key(to), delivery_delay=3, read_delay=8, previous_messages_to_number=previous)

    def test_suffix_mapping(self):
        self.assertEqual(scenario_key("+919800000000"), "invalid_recipient")
        self.assertEqual(scenario_key("+919800000123"), "normal")

    def test_fail_n_times_then_succeed(self):
        once = self.scenario("+919800000111")
        self.assertIsNotNone(rejection_for_attempt(once, 1))
        self.assertIsNone(rejection_for_attempt(once, 2))
        manual = self.scenario("+919800000666")
        self.assertEqual([rejection_for_attempt(manual, n) is None for n in (1, 2, 3, 4)], [False, False, False, True])

    def test_delivery_failure_only_first_time_for_a_number(self):
        self.assertEqual([e.status for e in self.scenario("+919800000333").events], ["failed"])
        self.assertEqual([e.status for e in self.scenario("+919800000333", previous=1).events], ["delivered", "read"])

    def test_out_of_order_scenario_sends_read_before_delivered_twice_each(self):
        events = self.scenario("+919800000555").events
        self.assertEqual([(e.status, e.extra_deliveries) for e in events], [("read", 1), ("delivered", 1)])
        self.assertLess(events[0].delay_seconds, events[1].delay_seconds)


class TokenBucketTests(SimpleTestCase):
    def test_refills_over_time(self):
        now = [0.0]
        bucket = TokenBucket(rate_per_second=1, burst=2, clock=lambda: now[0])
        self.assertEqual([bucket.take(), bucket.take()], [0.0, 0.0])
        self.assertGreater(bucket.take(), 0)
        now[0] += 1.0
        self.assertEqual(bucket.take(), 0.0)


@override_settings(SIMULATOR=SIM)
class ApiTests(TestCase):
    def setUp(self):
        patcher = mock.patch.object(views, "CFG", SIM)
        patcher.start()
        self.addCleanup(patcher.stop)
        bucket = mock.patch.object(views, "bucket", TokenBucket(1000, 1000))
        bucket.start()
        self.addCleanup(bucket.stop)

    def submit(self, to="+919800000123", key="idem-1", body="Hello", auth="Bearer key", **extra):
        payload = {"to": to, "body": body, "callback_url": "http://api.test/hook", "client_reference": "ref", **extra}
        headers = {"HTTP_IDEMPOTENCY_KEY": key}
        if auth:
            headers["HTTP_AUTHORIZATION"] = auth
        return self.client.post("/v1/messages", data=json.dumps(payload), content_type="application/json", **headers)

    def test_accepts_message_and_plans_status_events(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "sent")
        message = SimulatedMessage.objects.get()
        self.assertEqual(message.body_length, 5)
        self.assertEqual(list(message.events.order_by("next_attempt_at").values_list("status", flat=True)),
                         ["delivered", "read"])

    def test_requires_api_key(self):
        self.assertEqual(self.submit(auth=None).status_code, 401)
        self.assertEqual(self.submit(auth="Bearer wrong").status_code, 401)

    def test_idempotent_replay_does_not_send_twice(self):
        first = self.submit()
        second = self.submit()
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(SimulatedMessage.objects.count(), 1)
        self.assertEqual(OutboundEvent.objects.count(), 2)

    def test_scenario_rejections(self):
        self.assertEqual(self.submit(to="+919800000000").status_code, 422)
        self.assertEqual(self.submit(to="+919800000111", key="k111").status_code, 500)
        self.assertEqual(self.submit(to="+919800000111", key="k111").status_code, 201)
        limited = self.submit(to="+919800000222", key="k222")
        self.assertEqual((limited.status_code, limited["Retry-After"]), (429, "3"))

    def test_validation(self):
        self.assertEqual(self.submit(to="98000").status_code, 422)
        self.assertEqual(self.submit(body="x" * 1601, key="long").json()["error"]["code"], "content_too_long")
        self.assertEqual(self.submit(key="").status_code, 400)
        self.assertEqual(self.submit(body="  ", key="blank").status_code, 400)

    def test_outage_and_health(self):
        self.assertEqual(self.client.get("/v1/health").json()["status"], "operational")
        response = self.client.post("/v1/simulator/outage", data='{"enabled": true}', content_type="application/json",
                                    HTTP_AUTHORIZATION="Bearer key")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SimulatorState.get().outage)
        self.assertEqual(self.submit().status_code, 503)
        self.assertEqual(self.client.get("/v1/health").status_code, 503)

    def test_rate_limit(self):
        with mock.patch.object(views, "bucket", TokenBucket(rate_per_second=0.001, burst=1)):
            self.assertEqual(self.submit(key="a").status_code, 201)
            response = self.submit(key="b")
        self.assertEqual(response.status_code, 429)
        self.assertTrue(int(response["Retry-After"]) >= 1)


@override_settings(SIMULATOR=SIM)
class DispatcherTests(TestCase):
    def setUp(self):
        self.message = SimulatedMessage.objects.create(
            id="sim_1", idempotency_key="k", client_reference="ref", to="+919800000123", body_length=5,
            callback_url="http://api.test/hook", scenario="normal",
        )
        self.now = timezone.now()
        self.requests = []

    def event(self, **fields):
        defaults = {"id": "evt_1", "message": self.message, "status": "delivered", "occurred_at": self.now,
                    "next_attempt_at": self.now}
        return OutboundEvent.objects.create(**{**defaults, **fields})

    def client_returning(self, status: int):
        def handler(request):
            self.requests.append(request)
            return httpx.Response(status)
        return httpx.Client(transport=httpx.MockTransport(handler))

    def test_delivers_signed_payload(self):
        self.event()
        self.assertEqual(deliver_due_events(self.client_returning(200), now=self.now), 1)
        request = self.requests[0]
        payload = json.loads(request.content)
        self.assertEqual((payload["event_id"], payload["status"], payload["client_reference"]), ("evt_1", "delivered", "ref"))
        parts = dict(p.split("=", 1) for p in request.headers["X-Sim-Signature"].split(","))
        expected = hmac.new(b"secret", f"{parts['t']}.".encode() + request.content, hashlib.sha256).hexdigest()
        self.assertEqual(parts["v1"], expected)
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, "delivered")
        self.assertIsNotNone(OutboundEvent.objects.get().delivered_at)

    def test_future_events_wait(self):
        self.event(next_attempt_at=self.now + timedelta(seconds=10))
        self.assertEqual(deliver_due_events(self.client_returning(200), now=self.now), 0)

    def test_failed_delivery_is_retried_with_backoff_then_abandoned(self):
        event = self.event()
        client = self.client_returning(500)
        deliver_due_events(client, now=self.now)
        event.refresh_from_db()
        self.assertEqual((event.delivery_attempts, event.delivered_at), (1, None))
        self.assertEqual(event.next_attempt_at, self.now + timedelta(seconds=2))
        deliver_due_events(client, now=self.now + timedelta(seconds=3))
        deliver_due_events(client, now=self.now + timedelta(seconds=10))
        event.refresh_from_db()
        self.assertTrue(event.gave_up)

    def test_extra_deliveries_resend_identical_event(self):
        self.event(extra_deliveries=1)
        client = self.client_returning(200)
        deliver_due_events(client, now=self.now)
        deliver_due_events(client, now=self.now + timedelta(seconds=1))
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[0].content, self.requests[1].content)
        self.assertIsNotNone(OutboundEvent.objects.get().delivered_at)
