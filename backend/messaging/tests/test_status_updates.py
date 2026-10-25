"""Provider status notifications: transitions, duplicates, out-of-order and stale events."""

import itertools
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.testing import make_candidate
from messaging.models import ErrorCategory, EventKind, Message, MessageAttempt, MessageEvent, MessageStatus
from messaging.providers import StatusUpdate
from messaging.services.actions import request_manual_retry
from messaging.services.status_updates import Outcome, apply_status_update

_ids = itertools.count(1)


def update(message: Message, status: str, *, event_id=None, provider_message_id=None, seconds=0, **extra):
    return StatusUpdate(
        provider_event_id=event_id or f"evt_{next(_ids)}",
        provider_message_id=provider_message_id or message.provider_message_id or "unknown",
        client_reference=str(message.id),
        status=status,
        occurred_at=timezone.now() + timedelta(seconds=seconds),
        **extra,
    )


class StatusUpdateTests(TestCase):
    def setUp(self):
        self.candidate = make_candidate()
        self.message = Message.objects.create(
            candidate=self.candidate, body="Hi", provider="fake", status=MessageStatus.SENT,
            provider_message_id="pm_1", idempotency_key="k1", sent_at=timezone.now(), attempt_count=1,
        )

    def apply(self, *args, **kwargs):
        outcome = apply_status_update("fake", update(self.message, *args, **kwargs))
        self.message.refresh_from_db()
        return outcome

    def test_forward_transitions_are_applied_with_timestamps(self):
        self.assertEqual(self.apply("delivered", seconds=1), Outcome.APPLIED)
        self.assertEqual(self.message.status, MessageStatus.DELIVERED)
        self.assertIsNotNone(self.message.delivered_at)
        self.assertEqual(self.apply("read", seconds=2), Outcome.APPLIED)
        self.assertEqual(self.message.status, MessageStatus.READ)
        self.assertIsNotNone(self.message.read_at)

    def test_duplicate_event_is_acknowledged_but_not_reapplied(self):
        self.assertEqual(self.apply("delivered", event_id="evt_dup"), Outcome.APPLIED)
        self.assertEqual(self.apply("delivered", event_id="evt_dup"), Outcome.DUPLICATE)
        self.assertEqual(MessageEvent.objects.filter(provider_event_id="evt_dup").count(), 1)

    def test_out_of_order_event_cannot_regress_status(self):
        self.assertEqual(self.apply("read", seconds=5), Outcome.APPLIED)
        self.assertEqual(self.apply("delivered", seconds=4), Outcome.IGNORED)
        self.assertEqual(self.message.status, MessageStatus.READ)
        self.assertIsNotNone(self.message.delivered_at, "read implies delivered")
        ignored = self.message.events.get(kind=EventKind.STATUS_IGNORED)
        self.assertFalse(ignored.applied)
        self.assertIn("out-of-order", ignored.detail)

    def test_failure_after_delivery_is_ignored(self):
        self.apply("delivered")
        self.assertEqual(self.apply("failed", error_code="undeliverable"), Outcome.IGNORED)
        self.assertEqual(self.message.status, MessageStatus.DELIVERED)

    def test_delivery_failure_is_classified_and_explained(self):
        outcome = self.apply("failed", error_code="undeliverable", error_message="Handset unreachable.")
        self.assertEqual(outcome, Outcome.APPLIED)
        self.assertEqual(self.message.status, MessageStatus.FAILED)
        self.assertEqual(self.message.error_category, ErrorCategory.DELIVERY_FAILED)
        self.assertEqual(self.message.error_detail, "Handset unreachable.")

    def test_unknown_message_is_recorded_for_audit(self):
        stray = StatusUpdate("evt_stray", "pm_missing", "", "delivered", timezone.now())
        self.assertEqual(apply_status_update("fake", stray), Outcome.UNKNOWN_MESSAGE)
        event = MessageEvent.objects.get(provider_event_id="evt_stray")
        self.assertIsNone(event.message)
        self.assertFalse(event.applied)

    def test_event_for_superseded_send_is_ignored_after_manual_retry(self):
        MessageAttempt.objects.create(message=self.message, number=1, trigger="initial", idempotency_key="k1",
                                      outcome="accepted", provider_message_id="pm_1", started_at=timezone.now())
        self.apply("failed", error_code="undeliverable")
        request_manual_retry(self.message.id)
        self.message.refresh_from_db()
        self.assertIsNone(self.message.provider_message_id)
        late = update(self.message, "delivered", provider_message_id="pm_1")
        self.assertEqual(apply_status_update("fake", late), Outcome.IGNORED)
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, MessageStatus.QUEUED)

    def test_provider_truth_wins_after_a_timeout(self):
        # We timed out (no provider ID) and scheduled a retry, but the provider did accept it.
        Message.objects.filter(pk=self.message.pk).update(
            status=MessageStatus.QUEUED, provider_message_id=None, error_category=ErrorCategory.PROVIDER_UNAVAILABLE,
            next_attempt_at=timezone.now() + timedelta(seconds=5),
        )
        self.message.refresh_from_db()
        outcome = apply_status_update("fake", update(self.message, "delivered", provider_message_id="pm_late"))
        self.assertEqual(outcome, Outcome.APPLIED)
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, MessageStatus.DELIVERED)
        self.assertEqual(self.message.provider_message_id, "pm_late")
        self.assertIsNone(self.message.next_attempt_at, "pending retry must be cancelled")
        self.assertEqual(self.message.error_category, "")
