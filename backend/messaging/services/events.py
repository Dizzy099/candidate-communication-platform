from django.utils import timezone

from ..models import EventSource, Message, MessageEvent


def record_event(message: Message | None, kind: str, *, detail: str = "", status: str = "", **fields) -> MessageEvent:
    return MessageEvent.objects.create(
        message=message,
        source=fields.pop("source", EventSource.SYSTEM),
        kind=kind,
        status=status or (message.status if message else ""),
        detail=detail[:300],
        occurred_at=fields.pop("occurred_at", None) or timezone.now(),
        **fields,
    )
