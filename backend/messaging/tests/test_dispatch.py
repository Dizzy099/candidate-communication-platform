"""Worker behaviour: sending, failure classification, automatic retries, leases, scheduling."""

from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from candidates.models import Candidate
from core.testing import make_candidate
from messaging.models import AttemptTrigger, ErrorCategory, EventKind, Message, MessageStatus
from messaging.policy import retry_block_reason
from messaging.providers.registry import override_provider
from messaging.services.dispatch import claim_due_messages, recover_stale_leases, run_once
from messaging.services.enqueue import enqueue_batch

from .fakes import FakeProvider, invalid_recipient, rate_limited, temporary_error, unavailable


def later(seconds: float):
    return timezone.now() + timedelta(seconds=seconds)


@override_settings(MESSAGING={
    "MAX_BODY_LENGTH": 1000, "MAX_BATCH_RECIPIENTS": 500, "MAX_ATTEMPTS": 5, "AUTO_ATTEMPTS": 3,
    "BACKOFF_BASE_SECONDS": 2.0, "BACKOFF_MAX_SECONDS": 60.0, "WORKER_BATCH_SIZE": 25,
    "WORKER_POLL_INTERVAL_SECONDS": 0.5, "SENDING_LEASE_SECONDS": 60, "MAX_SCHEDULE_DAYS": 30,
})
class DispatchTests(TestCase):
    def setUp(self):
        self.provider = FakeProvider()
        context = override_provider(self.provider)
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.asha = make_candidate("Asha Verma", "+919800000001")
        self.bina = make_candidate("Bina Rao", "+919800000002")
        self.chetan = make_candidate("Chetan Das", "+919800000003")

    def send(self, *candidates: Candidate, body="Hello {{first_name}}", **kwargs):
        return enqueue_batch(candidates=list(candidates), body=body, **kwargs).batch

    def message_for(self, candidate) -> Message:
        return Message.objects.get(candidate=candidate)

    def test_successful_send_records_provider_reference_and_trail(self):
        self.send(self.asha)
        message = self.message_for(self.asha)
        self.assertEqual(message.status, MessageStatus.QUEUED)
        self.assertEqual(message.body, "Hello Asha")

        self.assertEqual(run_once(), 1)
        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.SENT)
        self.assertEqual(message.provider_message_id, "fake_1")
        self.assertIsNotNone(message.sent_at)
        self.assertEqual(message.attempt_count, 1)
        self.assertEqual(list(message.events.values_list("kind", flat=True)), [EventKind.QUEUED, EventKind.SUBMITTED])
        attempt = message.attempts.get()
        self.assertEqual((attempt.outcome, attempt.trigger), ("accepted", AttemptTrigger.INITIAL))
        call = self.provider.calls[0]
        self.assertEqual(call.to_phone, "+919800000001")
        self.assertEqual(call.client_reference, str(message.id))
        self.assertTrue(call.status_callback_url.endswith("/api/webhooks/provider/fake/"))

    def test_permanent_failure_is_not_retried(self):
        self.provider.queue(self.asha.phone, invalid_recipient())
        self.send(self.asha)
        run_once()
        message = self.message_for(self.asha)
        self.assertEqual(message.status, MessageStatus.FAILED)
        self.assertEqual(message.error_category, ErrorCategory.INVALID_RECIPIENT)
        self.assertIsNone(message.next_attempt_at)
        self.assertEqual(run_once(now=later(120)), 0)
        self.assertEqual(len(self.provider.calls), 1)
        self.assertIn("permanent", retry_block_reason(message))

    def test_temporary_failure_retries_with_backoff_and_same_idempotency_key(self):
        self.provider.queue(self.asha.phone, temporary_error())
        self.send(self.asha)
        run_once()
        message = self.message_for(self.asha)
        self.assertEqual(message.status, MessageStatus.QUEUED)
        self.assertEqual(message.error_category, ErrorCategory.PROVIDER_ERROR)
        delay = (message.next_attempt_at - timezone.now()).total_seconds()
        self.assertTrue(1 < delay <= 2, delay)

        self.assertEqual(run_once(), 0, "must wait for the backoff")
        self.assertEqual(run_once(now=later(3)), 1)
        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.SENT)
        self.assertEqual(message.error_category, "")
        self.assertEqual(message.attempt_count, 2)
        self.assertEqual(list(message.attempts.values_list("trigger", flat=True)), ["initial", "auto_retry"])
        keys = {call.idempotency_key for call in self.provider.calls}
        self.assertEqual(len(keys), 1, "retries must reuse the idempotency key")

    def test_rate_limit_waits_for_retry_after(self):
        self.provider.queue(self.asha.phone, rate_limited(seconds=7))
        self.send(self.asha)
        run_once()
        message = self.message_for(self.asha)
        delay = (message.next_attempt_at - timezone.now()).total_seconds()
        self.assertTrue(6 < delay <= 7, delay)
        self.assertEqual(run_once(now=later(5)), 0)
        self.assertEqual(run_once(now=later(8)), 1)
        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.SENT)

    def test_auto_retries_stop_at_limit_then_manual_retry_is_allowed(self):
        self.provider.queue(self.asha.phone, unavailable(), unavailable(), unavailable())
        self.send(self.asha)
        for step in range(3):
            run_once(now=later(step * 100))
        message = self.message_for(self.asha)
        self.assertEqual(message.status, MessageStatus.FAILED)
        self.assertEqual(message.attempt_count, 3)
        self.assertEqual(message.error_category, ErrorCategory.PROVIDER_UNAVAILABLE)
        self.assertIsNone(retry_block_reason(message))
        self.assertEqual(run_once(now=later(1000)), 0)

    def test_bulk_send_tracks_each_recipient_independently(self):
        self.provider.queue(self.asha.phone, invalid_recipient())
        self.provider.queue(self.bina.phone, temporary_error())
        batch = self.send(self.asha, self.bina, self.chetan)
        self.assertEqual(batch.messages.count(), 3)
        self.assertEqual(run_once(), 3)
        statuses = {m.candidate.full_name: m.status for m in batch.messages.select_related("candidate")}
        self.assertEqual(statuses, {
            "Asha Verma": MessageStatus.FAILED,
            "Bina Rao": MessageStatus.QUEUED,  # waiting for automatic retry
            "Chetan Das": MessageStatus.SENT,
        })
        run_once(now=later(5))
        self.assertEqual(self.message_for(self.bina).status, MessageStatus.SENT)
        self.assertEqual(self.message_for(self.asha).status, MessageStatus.FAILED)

    def test_unexpected_exception_fails_one_message_without_stopping_others(self):
        self.provider.queue(self.asha.phone, RuntimeError("boom"))
        self.send(self.asha, self.bina)
        self.assertEqual(run_once(), 2)
        asha, bina = self.message_for(self.asha), self.message_for(self.bina)
        self.assertEqual((asha.status, asha.error_category), (MessageStatus.FAILED, ErrorCategory.UNKNOWN))
        self.assertEqual(bina.status, MessageStatus.SENT)
        self.assertNotIn("boom", asha.error_detail, "raw exception text must not leak to users")

    def test_claim_is_exclusive(self):
        self.send(self.asha)
        self.assertEqual(len(claim_due_messages()), 1)
        self.assertEqual(claim_due_messages(), [], "a claimed message can't be claimed twice")

    def test_stale_lease_is_requeued_with_same_key(self):
        self.send(self.asha)
        claim_due_messages()
        message = self.message_for(self.asha)
        key = message.idempotency_key
        self.assertEqual(message.status, MessageStatus.SENDING)
        self.assertEqual(recover_stale_leases(now=later(30)), 0, "lease still valid")
        self.assertEqual(recover_stale_leases(now=later(61)), 1)
        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.QUEUED)
        self.assertEqual(message.idempotency_key, key)

    def test_scheduled_message_waits_until_due(self):
        due = later(600)
        self.send(self.asha, scheduled_at=due)
        message = self.message_for(self.asha)
        self.assertEqual(message.status, MessageStatus.SCHEDULED)
        self.assertEqual(run_once(), 0)
        self.assertEqual(run_once(now=due + timedelta(seconds=1)), 1)
        message.refresh_from_db()
        self.assertEqual(message.status, MessageStatus.SENT)

    def test_candidate_deleted_after_queueing_is_skipped_safely(self):
        self.send(self.asha)
        self.asha.delete()
        self.assertEqual(run_once(), 0)
        self.assertEqual(self.provider.calls, [])

    def test_idempotent_enqueue_with_client_request_id(self):
        first = self.send(self.asha, client_request_id="req-12345678")
        second = enqueue_batch(candidates=[self.asha], body="Hello", client_request_id="req-12345678")
        self.assertFalse(second.created)
        self.assertEqual(second.batch.pk, first.pk)
        self.assertEqual(Message.objects.count(), 1)
