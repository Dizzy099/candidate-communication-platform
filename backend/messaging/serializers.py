import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from candidates.models import Candidate
from candidates.validators import format_phone_display

from .models import (
    IN_FLIGHT_STATUSES,
    Message,
    MessageAttempt,
    MessageBatch,
    MessageEvent,
    MessageStatus,
    MessageTemplate,
)
from .policy import error_copy, retry_block_reason
from .services import templating

_CLIENT_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


# --- output -------------------------------------------------------------------
class MessageEventSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display")

    class Meta:
        model = MessageEvent
        fields = ["id", "kind", "kind_label", "source", "status", "detail", "applied", "occurred_at"]


class MessageAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttempt
        fields = [
            "number", "trigger", "outcome", "error_category", "error_code", "http_status",
            "retry_after_seconds", "provider_message_id", "started_at", "finished_at",
        ]


class MessageSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display")
    candidate_id = serializers.IntegerField()
    batch_id = serializers.UUIDField(allow_null=True)
    error = serializers.SerializerMethodField()
    can_retry = serializers.SerializerMethodField()
    retry_block_reason = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    retry_scheduled = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id", "candidate_id", "batch_id", "body", "channel", "provider", "status", "status_label",
            "provider_message_id", "attempt_count", "max_attempts", "next_attempt_at", "retry_scheduled",
            "error", "can_retry", "retry_block_reason", "can_cancel",
            "created_at", "scheduled_at", "sent_at", "delivered_at", "read_at", "failed_at", "cancelled_at",
            "updated_at",
        ]

    def get_error(self, obj: Message):
        copy = error_copy(obj.error_category)
        if copy is None:
            return None
        return {
            "category": obj.error_category,
            "code": obj.error_code,
            "title": copy.title,
            "explanation": copy.explanation,
            "technical_detail": obj.error_detail,
        }

    def get_can_retry(self, obj: Message) -> bool:
        return retry_block_reason(obj) is None

    def get_retry_block_reason(self, obj: Message):
        return retry_block_reason(obj) if obj.status == MessageStatus.FAILED else None

    def get_can_cancel(self, obj: Message) -> bool:
        return obj.status == MessageStatus.SCHEDULED

    def get_retry_scheduled(self, obj: Message) -> bool:
        """True while the worker is waiting to retry a temporary failure."""
        return obj.status == MessageStatus.QUEUED and bool(obj.error_category)


class MessageDetailSerializer(MessageSerializer):
    events = MessageEventSerializer(many=True, read_only=True)
    attempts = MessageAttemptSerializer(many=True, read_only=True)

    class Meta(MessageSerializer.Meta):
        fields = MessageSerializer.Meta.fields + ["events", "attempts"]


class RecipientCandidateSerializer(serializers.ModelSerializer):
    phone_display = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = ["id", "candidate_code", "full_name", "phone_display"]

    def get_phone_display(self, obj: Candidate) -> str:
        return format_phone_display(obj.phone)


class BatchMessageSerializer(MessageSerializer):
    candidate = RecipientCandidateSerializer(read_only=True)

    class Meta(MessageSerializer.Meta):
        fields = MessageSerializer.Meta.fields + ["candidate"]


def batch_summary(messages) -> dict:
    counts = {status: 0 for status in MessageStatus.values}
    for message in messages:
        counts[message.status] += 1
    processing = sum(counts[s] for s in IN_FLIGHT_STATUSES)
    return {
        "total": len(messages),
        "processing": processing,
        "scheduled": counts[MessageStatus.SCHEDULED],
        "submitted": counts[MessageStatus.SENT] + counts[MessageStatus.DELIVERED] + counts[MessageStatus.READ],
        "delivered": counts[MessageStatus.DELIVERED] + counts[MessageStatus.READ],
        "read": counts[MessageStatus.READ],
        "failed": counts[MessageStatus.FAILED],
        "cancelled": counts[MessageStatus.CANCELLED],
        "retrying": sum(1 for m in messages if m.status == MessageStatus.QUEUED and m.error_category),
        "complete": processing == 0,
    }


class BatchSerializer(serializers.ModelSerializer):
    summary = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField()

    class Meta:
        model = MessageBatch
        fields = ["id", "body", "channel", "provider", "recipient_count", "scheduled_at", "created_at", "summary", "messages"]

    def _messages(self, obj):
        if not hasattr(obj, "_message_cache"):
            obj._message_cache = list(obj.messages.select_related("candidate").order_by("candidate__full_name"))
        return obj._message_cache

    def get_summary(self, obj):
        return batch_summary(self._messages(obj))

    def get_messages(self, obj):
        return BatchMessageSerializer(self._messages(obj), many=True).data


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = ["id", "name", "body", "created_at", "updated_at"]
        extra_kwargs = {
            "name": {"error_messages": {"blank": "Give the template a name.", "required": "Give the template a name."}},
            "body": {"error_messages": {"blank": "Template text can't be empty.", "required": "Template text can't be empty."}},
        }

    def validate_name(self, value: str) -> str:
        value = " ".join(value.split())
        clash = MessageTemplate.objects.filter(name__iexact=value).exclude(pk=getattr(self.instance, "pk", None))
        if clash.exists():
            raise serializers.ValidationError("A template with this name already exists.")
        return value

    def validate_body(self, value: str) -> str:
        value = value.strip()
        limit = settings.MESSAGING["MAX_BODY_LENGTH"]
        if len(value) > limit:
            raise serializers.ValidationError(f"Template text can be at most {limit} characters.")
        problems = templating.template_problems(value)
        if problems:
            raise serializers.ValidationError(" ".join(problems))
        return value


# --- input --------------------------------------------------------------------
class SendMessageSerializer(serializers.Serializer):
    body = serializers.CharField(
        trim_whitespace=True,
        error_messages={"blank": "Type the message you want to send.", "required": "Type the message you want to send."},
    )
    client_request_id = serializers.CharField(required=False, allow_blank=True, max_length=64)
    template_id = serializers.PrimaryKeyRelatedField(
        queryset=MessageTemplate.objects.all(), required=False, allow_null=True, source="template",
        error_messages={"does_not_exist": "That template no longer exists."},
    )
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_body(self, value: str) -> str:
        limit = settings.MESSAGING["MAX_BODY_LENGTH"]
        if len(value) > limit:
            raise serializers.ValidationError(f"Messages can be at most {limit} characters ({len(value)} now).")
        problems = templating.template_problems(value)
        if problems:
            raise serializers.ValidationError(" ".join(problems))
        return value

    def validate_client_request_id(self, value: str) -> str | None:
        if not value:
            return None
        if not _CLIENT_REQUEST_ID.match(value):
            raise serializers.ValidationError("Invalid request ID.")
        return value

    def validate_scheduled_at(self, value):
        if value is None:
            return None
        now = timezone.now()
        if value < now + timedelta(seconds=30):
            raise serializers.ValidationError("Pick a time at least 1 minute in the future.")
        max_days = settings.MESSAGING["MAX_SCHEDULE_DAYS"]
        if value > now + timedelta(days=max_days):
            raise serializers.ValidationError(f"Messages can be scheduled up to {max_days} days ahead.")
        return value


class BulkSendSerializer(SendMessageSerializer):
    candidate_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        error_messages={"min_length": "Select at least one candidate.", "empty": "Select at least one candidate."},
    )

    def validate_candidate_ids(self, value: list[int]) -> list[Candidate]:
        unique_ids = list(dict.fromkeys(value))
        limit = settings.MESSAGING["MAX_BATCH_RECIPIENTS"]
        if len(unique_ids) > limit:
            raise serializers.ValidationError(f"You can message at most {limit} candidates at once.")
        candidates = Candidate.objects.in_bulk(unique_ids)
        missing = [cid for cid in unique_ids if cid not in candidates]
        if missing:
            raise serializers.ValidationError(
                f"{len(missing)} selected candidate(s) no longer exist. Refresh the list and try again."
            )
        return [candidates[cid] for cid in unique_ids]
