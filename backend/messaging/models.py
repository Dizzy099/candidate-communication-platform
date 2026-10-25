import uuid

from django.db import models
from django.db.models import Q


class MessageStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    QUEUED = "queued", "Queued"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    READ = "read", "Read"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


# Progress order for provider-confirmed states. A status update may only move
# a message forward, so duplicate or late events can never regress it.
STATUS_RANK = {
    MessageStatus.SCHEDULED: 0,
    MessageStatus.QUEUED: 0,
    MessageStatus.SENDING: 1,
    MessageStatus.SENT: 2,
    MessageStatus.DELIVERED: 3,
    MessageStatus.READ: 4,
}
IN_FLIGHT_STATUSES = (MessageStatus.QUEUED, MessageStatus.SENDING)


class ErrorCategory(models.TextChoices):
    INVALID_RECIPIENT = "invalid_recipient", "Invalid recipient"
    CONTENT_REJECTED = "content_rejected", "Content rejected"
    RATE_LIMITED = "rate_limited", "Rate limited"
    PROVIDER_ERROR = "provider_error", "Temporary provider error"
    PROVIDER_UNAVAILABLE = "provider_unavailable", "Provider unavailable"
    DELIVERY_FAILED = "delivery_failed", "Delivery failed"
    CONFIGURATION = "configuration", "Configuration error"
    UNKNOWN = "unknown", "Unknown error"


class MessageTemplate(models.Model):
    name = models.CharField(max_length=80, unique=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class MessageBatch(models.Model):
    """One compose action: the same text sent to one or more candidates."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_request_id = models.CharField(
        max_length=64, unique=True, null=True, blank=True,
        help_text="Idempotency key from the client; repeats return the original batch.",
    )
    body = models.TextField(help_text="Text as composed, before template variables are filled in.")
    template = models.ForeignKey(MessageTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    channel = models.CharField(max_length=20, default="sms")
    provider = models.CharField(max_length=40)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    recipient_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey("candidates.Candidate", on_delete=models.CASCADE, related_name="messages")
    batch = models.ForeignKey(MessageBatch, null=True, blank=True, on_delete=models.CASCADE, related_name="messages")
    body = models.TextField(help_text="Final text sent to this candidate (variables filled in).")
    channel = models.CharField(max_length=20, default="sms")
    provider = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=MessageStatus.choices, default=MessageStatus.QUEUED)

    provider_message_id = models.CharField(max_length=100, null=True, blank=True)
    # Sent with every submission so the provider can de-duplicate retries.
    idempotency_key = models.CharField(max_length=100)

    scheduled_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    next_trigger = models.CharField(max_length=20, default="initial")
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)

    error_category = models.CharField(max_length=30, choices=ErrorCategory.choices, blank=True, default="")
    error_code = models.CharField(max_length=60, blank=True, default="")
    error_detail = models.CharField(max_length=300, blank=True, default="")

    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="msg_due_idx"),
            models.Index(fields=["candidate", "-created_at"], name="msg_history_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_message_id"],
                condition=Q(provider_message_id__isnull=False),
                name="uniq_provider_message_id",
            ),
        ]

    def __str__(self) -> str:
        return f"Message {self.id} [{self.status}]"


class AttemptTrigger(models.TextChoices):
    INITIAL = "initial", "Initial send"
    AUTO_RETRY = "auto_retry", "Automatic retry"
    MANUAL_RETRY = "manual_retry", "Manual retry"


class AttemptOutcome(models.TextChoices):
    IN_PROGRESS = "in_progress", "In progress"
    ACCEPTED = "accepted", "Accepted by provider"
    FAILED = "failed", "Failed"


class MessageAttempt(models.Model):
    """One submission of a message to the provider."""

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attempts")
    number = models.PositiveSmallIntegerField()
    trigger = models.CharField(max_length=20, choices=AttemptTrigger.choices)
    idempotency_key = models.CharField(max_length=100)
    outcome = models.CharField(max_length=20, choices=AttemptOutcome.choices, default=AttemptOutcome.IN_PROGRESS)
    error_category = models.CharField(max_length=30, choices=ErrorCategory.choices, blank=True, default="")
    error_code = models.CharField(max_length=60, blank=True, default="")
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    retry_after_seconds = models.PositiveIntegerField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=100, null=True, blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["message", "number"], name="uniq_attempt_number")]


class EventSource(models.TextChoices):
    SYSTEM = "system", "Platform"
    PROVIDER = "provider", "Provider"


class EventKind(models.TextChoices):
    QUEUED = "queued", "Queued"
    SCHEDULED = "scheduled", "Scheduled"
    SUBMITTED = "submitted", "Accepted by provider"
    ATTEMPT_FAILED = "attempt_failed", "Send attempt failed"
    RETRY_SCHEDULED = "retry_scheduled", "Retry scheduled"
    MANUAL_RETRY = "manual_retry", "Retry requested"
    STATUS_CHANGED = "status_changed", "Status updated"
    STATUS_IGNORED = "status_ignored", "Status update ignored"
    CANCELLED = "cancelled", "Cancelled"
    UNKNOWN_MESSAGE = "unknown_message", "Update for unknown message"


class MessageEvent(models.Model):
    """Audit trail: platform actions and every provider status notification."""

    message = models.ForeignKey(Message, null=True, blank=True, on_delete=models.CASCADE, related_name="events")
    source = models.CharField(max_length=10, choices=EventSource.choices)
    kind = models.CharField(max_length=20, choices=EventKind.choices)
    status = models.CharField(max_length=20, blank=True, default="")
    provider = models.CharField(max_length=40, blank=True, default="")
    provider_event_id = models.CharField(max_length=100, null=True, blank=True)
    provider_message_id = models.CharField(max_length=100, blank=True, default="")
    applied = models.BooleanField(default=True)
    detail = models.CharField(max_length=300, blank=True, default="")
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_event_id"],
                condition=Q(provider_event_id__isnull=False),
                name="uniq_provider_event_id",
            ),
        ]
