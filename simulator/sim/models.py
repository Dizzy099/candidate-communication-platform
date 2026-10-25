import secrets

from django.db import models


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


class SimulatedMessage(models.Model):
    id = models.CharField(primary_key=True, max_length=40)
    idempotency_key = models.CharField(max_length=100, unique=True)
    client_reference = models.CharField(max_length=100, blank=True, default="")
    to = models.CharField(max_length=32, db_index=True)
    channel = models.CharField(max_length=20, default="sms")
    body_length = models.PositiveIntegerField()  # message text itself is not stored
    callback_url = models.URLField(max_length=500)
    scenario = models.CharField(max_length=40)
    status = models.CharField(max_length=20, default="sent")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SubmissionCounter(models.Model):
    """How many times a given idempotency key was submitted (drives fail-N-times scenarios)."""

    idempotency_key = models.CharField(primary_key=True, max_length=100)
    attempts = models.PositiveIntegerField(default=0)


class OutboundEvent(models.Model):
    """Webhook outbox: status changes waiting to be delivered to the platform."""

    id = models.CharField(primary_key=True, max_length=40)
    message = models.ForeignKey(SimulatedMessage, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=20)
    error_code = models.CharField(max_length=60, blank=True, default="")
    error_message = models.CharField(max_length=200, blank=True, default="")
    occurred_at = models.DateTimeField()
    next_attempt_at = models.DateTimeField(db_index=True)
    applied_to_message = models.BooleanField(default=False)
    extra_deliveries = models.PositiveSmallIntegerField(default=0)  # >0 => send duplicates
    delivery_attempts = models.PositiveSmallIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True, blank=True)
    gave_up = models.BooleanField(default=False)
    last_error = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["next_attempt_at"]


class SimulatorState(models.Model):
    """Singleton row holding switchable simulator behaviour."""

    outage = models.BooleanField(default=False)

    @classmethod
    def get(cls) -> "SimulatorState":
        state, _ = cls.objects.get_or_create(pk=1)
        return state
