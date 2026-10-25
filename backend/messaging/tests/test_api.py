"""HTTP API for sending, bulk results, history, retry/cancel, templates and provider health."""

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from core.testing import ApiTestCase, make_candidate
from messaging.models import Message, MessageStatus, MessageTemplate
from messaging.services.dispatch import run_once

from messaging.providers.registry import override_provider

from .fakes import FakeProvider, invalid_recipient, temporary_error, unavailable


class SendMessageApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.asha = make_candidate("Asha Verma", "+919800000001")

    def url(self, candidate=None):
        return f"/api/candidates/{(candidate or self.asha).pk}/messages"

    def test_send_to_one_candidate_returns_queued_message(self):
        response = self.client.post(self.url(), {"body": "Hi {{first_name}}"}, format="json")
        self.assertEqual(response.status_code, 202, response.json())
        body = response.json()
        self.assertEqual((body["status"], body["body"], body["candidate_id"]), ("queued", "Hi Asha", self.asha.pk))
        self.assertEqual(body["events"][0]["kind"], "queued")

    def test_double_submit_with_same_request_id_creates_one_message(self):
        payload = {"body": "Hello", "client_request_id": "c3f1a2b4-0000-4000-8000-000000000001"}
        first = self.client.post(self.url(), payload, format="json")
        second = self.client.post(self.url(), payload, format="json")
        self.assertEqual((first.status_code, second.status_code), (202, 200))
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(Message.objects.count(), 1)

    def test_validation_errors(self):
        cases = [
            ({"body": "   "}, "body", "Type the message"),
            ({"body": "x" * 1001}, "body", "at most 1000"),
            ({"body": "Hi {{nickname}}"}, "body", "Unknown variable"),
            ({"body": "Hi {{first_name}"}, "body", "unmatched braces"),
            ({"body": "Hi", "scheduled_at": (timezone.now() - timedelta(hours=1)).isoformat()}, "scheduled_at", "future"),
            ({"body": "Hi", "scheduled_at": (timezone.now() + timedelta(days=40)).isoformat()}, "scheduled_at", "30 days"),
        ]
        for payload, field, text in cases:
            with self.subTest(payload=str(payload)[:40]):
                response = self.client.post(self.url(), payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(text, response.json()["error"]["fields"][field])
        self.assertEqual(Message.objects.count(), 0)

    def test_unknown_candidate_is_404(self):
        response = self.client.post("/api/candidates/9999/messages", {"body": "Hi"}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_unknown_provider_is_rejected(self):
        response = self.client.post(self.url(), {"body": "Hi", "provider": "carrier_pigeon"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown provider", response.json()["error"]["fields"]["provider"])

    def test_scheduled_send(self):
        when = timezone.now() + timedelta(hours=2)
        response = self.client.post(self.url(), {"body": "Later", "scheduled_at": when.isoformat()}, format="json")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "scheduled")
        self.assertTrue(response.json()["can_cancel"])


class BulkSendApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.people = [
            make_candidate("Asha Verma", "+919800000001"),
            make_candidate("Bina Rao", "+919800000002"),
            make_candidate("Chetan Das", "+919800000003"),
        ]

    def test_mixed_outcomes_are_reported_per_recipient(self):
        self.provider.queue("+919800000001", invalid_recipient())
        self.provider.queue("+919800000002", unavailable(), unavailable(), unavailable())
        response = self.client.post("/api/message-batches", {
            "candidate_ids": [p.pk for p in self.people], "body": "Interview tomorrow, {{first_name}}",
        }, format="json")
        self.assertEqual(response.status_code, 202)
        batch = response.json()
        self.assertEqual(batch["recipient_count"], 3)
        self.assertEqual(batch["summary"]["processing"], 3)
        self.assertFalse(batch["summary"]["complete"])

        for step in range(3):
            run_once(now=timezone.now() + timedelta(seconds=100 * step))
        result = self.client.get(f"/api/message-batches/{batch['id']}").json()
        summary = result["summary"]
        self.assertEqual((summary["total"], summary["submitted"], summary["failed"], summary["processing"]), (3, 1, 2, 0))
        self.assertTrue(summary["complete"])
        by_name = {m["candidate"]["full_name"]: m for m in result["messages"]}
        self.assertEqual(by_name["Chetan Das"]["status"], "sent")
        self.assertEqual(by_name["Asha Verma"]["error"]["title"], "Invalid mobile number")
        self.assertFalse(by_name["Asha Verma"]["can_retry"])
        self.assertEqual(by_name["Bina Rao"]["error"]["category"], "provider_unavailable")
        self.assertTrue(by_name["Bina Rao"]["can_retry"])
        self.assertEqual(by_name["Chetan Das"]["body"], "Interview tomorrow, Chetan")

    def test_rejects_missing_or_empty_recipients(self):
        response = self.client.post("/api/message-batches", {"candidate_ids": [], "body": "Hi"}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/message-batches", {"candidate_ids": [self.people[0].pk, 9999], "body": "Hi"},
                                    format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("no longer exist", response.json()["error"]["fields"]["candidate_ids"])
        self.assertEqual(Message.objects.count(), 0)

    def test_duplicate_ids_are_messaged_once(self):
        pk = self.people[0].pk
        response = self.client.post("/api/message-batches", {"candidate_ids": [pk, pk, pk], "body": "Hi"}, format="json")
        self.assertEqual(response.json()["recipient_count"], 1)

    @override_settings(MESSAGING={**settings.MESSAGING, "MAX_BATCH_RECIPIENTS": 2})
    def test_batch_size_limit(self):
        response = self.client.post("/api/message-batches", {"candidate_ids": [p.pk for p in self.people], "body": "Hi"},
                                    format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("at most 2", response.json()["error"]["fields"]["candidate_ids"])


class HistoryRetryCancelApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.asha = make_candidate("Asha Verma", "+919800000001")

    def send(self, body="Hi", **extra):
        return self.client.post(f"/api/candidates/{self.asha.pk}/messages", {"body": body, **extra}, format="json").json()

    def test_history_is_newest_first_with_events_and_attempts(self):
        older = self.send("First")
        Message.objects.filter(pk=older["id"]).update(created_at=timezone.now() - timedelta(days=1))
        self.send("Second")
        run_once()
        response = self.client.get(f"/api/candidates/{self.asha.pk}/messages")
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual([m["body"] for m in results], ["Second", "First"])
        self.assertEqual(results[0]["status"], "sent")
        self.assertEqual(results[0]["attempts"][0]["outcome"], "accepted")
        self.assertIn("submitted", [e["kind"] for e in results[0]["events"]])

    def test_empty_history(self):
        response = self.client.get(f"/api/candidates/{self.asha.pk}/messages")
        self.assertEqual(response.json()["results"], [])

    def test_manual_retry_of_eligible_failure(self):
        self.provider.queue(self.asha.phone, temporary_error(), temporary_error(), temporary_error())
        message = self.send()
        for step in range(3):
            run_once(now=timezone.now() + timedelta(seconds=100 * step))
        response = self.client.post(f"/api/messages/{message['id']}/retry")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")
        self.assertIn("manual_retry", [e["kind"] for e in response.json()["events"]])
        run_once()
        detail = self.client.get(f"/api/messages/{message['id']}").json()
        self.assertEqual(detail["status"], "sent")
        self.assertEqual(detail["attempt_count"], 4)
        self.assertEqual(detail["attempts"][-1]["trigger"], "manual_retry")

    def test_retry_refused_for_permanent_failure_and_non_failed(self):
        self.provider.queue(self.asha.phone, invalid_recipient())
        failed = self.send()
        run_once()
        response = self.client.post(f"/api/messages/{failed['id']}/retry")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "retry_not_allowed")

        sent = self.send("again")
        run_once()
        self.assertEqual(self.client.post(f"/api/messages/{sent['id']}/retry").status_code, 409)

    def test_retry_refused_when_attempt_limit_reached(self):
        message = self.send()
        Message.objects.filter(pk=message["id"]).update(
            status=MessageStatus.FAILED, error_category="provider_error", attempt_count=5)
        response = self.client.post(f"/api/messages/{message['id']}/retry")
        self.assertEqual(response.status_code, 409)
        self.assertIn("Retry limit", response.json()["error"]["message"])

    def test_cancel_scheduled_message(self):
        message = self.send(scheduled_at=(timezone.now() + timedelta(hours=1)).isoformat())
        response = self.client.post(f"/api/messages/{message['id']}/cancel")
        self.assertEqual((response.status_code, response.json()["status"]), (200, "cancelled"))
        self.assertEqual(run_once(now=timezone.now() + timedelta(hours=2)), 0)
        self.assertEqual(self.client.post(f"/api/messages/{message['id']}/cancel").status_code, 409)


class TemplateApiTests(ApiTestCase):
    def test_create_list_update_delete(self):
        created = self.client.post("/api/templates", {"name": "Reminder", "body": "Hi {{first_name}}"}, format="json")
        self.assertEqual(created.status_code, 201)
        tid = created.json()["id"]
        self.assertEqual([t["name"] for t in self.client.get("/api/templates").json()], ["Reminder"])
        patched = self.client.patch(f"/api/templates/{tid}", {"body": "Hello {{full_name}}"}, format="json")
        self.assertEqual(patched.json()["body"], "Hello {{full_name}}")
        self.assertEqual(self.client.delete(f"/api/templates/{tid}").status_code, 204)
        self.assertFalse(MessageTemplate.objects.exists())

    def test_template_validation(self):
        MessageTemplate.objects.create(name="Reminder", body="Hi")
        response = self.client.post("/api/templates", {"name": "reminder", "body": "Hi {{salary}}"}, format="json")
        self.assertEqual(response.status_code, 400)
        fields = response.json()["error"]["fields"]
        self.assertIn("already exists", fields["name"])
        self.assertIn("salary", fields["body"])

    def test_variables_endpoint(self):
        tokens = [v["token"] for v in self.client.get("/api/template-variables").json()]
        self.assertIn("{{first_name}}", tokens)


class ProviderApiTests(ApiTestCase):
    def test_health_reports_status_stats_and_simulation_flag(self):
        asha = make_candidate()
        self.client.post(f"/api/candidates/{asha.pk}/messages", {"body": "Hi"}, format="json")
        run_once()
        body = self.client.get("/api/provider/health").json()
        self.assertEqual(body["status"], "operational")
        self.assertEqual(body["default_provider"], "fake")
        self.assertTrue(body["providers"][0]["simulated"])
        self.assertEqual(body["stats"]["sent"], 1)
        self.provider.health_status = "unavailable"
        self.assertEqual(self.client.get("/api/provider/health").json()["status"], "unavailable")

    @override_settings(DEMO_CONTROLS_ENABLED=False)
    def test_outage_control_disabled(self):
        response = self.client.post("/api/provider/simulator/outage", {"enabled": True}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(self.provider.outage)

    @override_settings(DEMO_CONTROLS_ENABLED=True)
    def test_outage_control_enabled(self):
        response = self.client.post("/api/provider/simulator/outage", {"enabled": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.provider.outage)
        self.assertEqual(self.client.post("/api/provider/simulator/outage", {"enabled": "yes"}, format="json").status_code, 400)

    def test_unhandled_errors_do_not_leak_details(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        with mock.patch("messaging.views.Message.objects.exists", side_effect=RuntimeError("db password=hunter2")),                 self.assertLogs("core.exceptions", level="ERROR"):
            response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "server_error")
        self.assertNotIn("hunter2", response.content.decode())


class MultipleProviderTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.email = FakeProvider(name="fake_email", channel="email")
        context = override_provider(self.provider, self.email)
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.asha = make_candidate("Asha Verma", "+919800000001", "asha@example.com")

    def test_recruiter_chooses_the_provider_per_message(self):
        sms = self.client.post(f"/api/candidates/{self.asha.pk}/messages", {"body": "By SMS"}, format="json").json()
        mail = self.client.post(f"/api/candidates/{self.asha.pk}/messages", {"body": "By email", "provider": "fake_email"},
                                format="json").json()
        self.assertEqual((sms["provider"], sms["channel"]), ("fake", "sms"))
        self.assertEqual((mail["provider"], mail["channel"], mail["provider_label"]), ("fake_email", "email", "Fake email provider"))
        run_once()
        self.assertEqual([c.body for c in self.provider.calls], ["By SMS"])
        self.assertEqual([(c.body, c.to_email) for c in self.email.calls], [("By email", "asha@example.com")])
        self.assertTrue(self.email.calls[0].status_callback_url.endswith("/api/webhooks/provider/fake_email/"))

    def test_failure_wording_matches_the_channel(self):
        self.email.queue("asha@example.com", invalid_recipient())
        message = self.client.post(f"/api/candidates/{self.asha.pk}/messages", {"body": "Hi", "provider": "fake_email"},
                                   format="json").json()
        run_once()
        detail = self.client.get(f"/api/messages/{message['id']}").json()
        self.assertEqual(detail["error"]["title"], "Invalid email address")

    def test_health_lists_every_provider(self):
        self.email.health_status = "unavailable"
        body = self.client.get("/api/provider/health").json()
        self.assertEqual([p["name"] for p in body["providers"]], ["fake", "fake_email"])
        self.assertEqual(body["status"], "unavailable", "overall status is the worst provider status")
