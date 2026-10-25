import logging

from django.conf import settings
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from candidates.models import Candidate
from core.exceptions import ApiError

from .models import Message, MessageBatch, MessageStatus, MessageTemplate
from .providers import ProviderError, UnknownProvider, WebhookError, get_provider, list_providers
from .serializers import (
    BatchSerializer,
    BulkSendSerializer,
    MessageDetailSerializer,
    SendMessageSerializer,
    TemplateSerializer,
)
from .services import actions, templating
from .services.enqueue import enqueue_batch
from .services.status_updates import apply_status_update

logger = logging.getLogger(__name__)

MAX_WEBHOOK_BYTES = 64 * 1024


class HistoryPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100


class CandidateMessagesView(ListAPIView):
    """GET: a candidate's communication history, newest first. POST: message one candidate."""

    serializer_class = MessageDetailSerializer
    pagination_class = HistoryPagination

    def get_candidate(self) -> Candidate:
        return get_object_or_404(Candidate, pk=self.kwargs["candidate_id"])

    def get_queryset(self):
        candidate = self.get_candidate()
        return (
            Message.objects.filter(candidate=candidate)
            .prefetch_related("events", "attempts")
            .order_by("-created_at")
        )

    def post(self, request, candidate_id: int):
        candidate = self.get_candidate()
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = enqueue_batch(candidates=[candidate], **serializer.validated_data)
        messages = list(result.batch.messages.prefetch_related("events", "attempts"))
        if len(messages) != 1 or messages[0].candidate_id != candidate.id:
            raise ApiError("This request ID was already used for a different send.", "request_id_conflict", 409)
        message = messages[0]
        return Response(
            MessageDetailSerializer(message).data,
            status=status.HTTP_202_ACCEPTED if result.created else status.HTTP_200_OK,
        )


class BatchViewSet(viewsets.ViewSet):
    """POST: send one message to many candidates. GET: per-recipient results."""

    def create(self, request):
        serializer = BulkSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        result = enqueue_batch(candidates=data.pop("candidate_ids"), **data)
        return Response(
            BatchSerializer(result.batch).data,
            status=status.HTTP_202_ACCEPTED if result.created else status.HTTP_200_OK,
        )

    def retrieve(self, request, pk=None):
        batch = get_object_or_404(MessageBatch, pk=pk)
        return Response(BatchSerializer(batch).data)


class MessageViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk=None):
        message = get_object_or_404(Message.objects.prefetch_related("events", "attempts"), pk=pk)
        return Response(MessageDetailSerializer(message).data)

    def retry(self, request, pk=None):
        message = actions.request_manual_retry(pk)
        message = Message.objects.prefetch_related("events", "attempts").get(pk=message.pk)
        return Response(MessageDetailSerializer(message).data, status=status.HTTP_202_ACCEPTED)

    def cancel(self, request, pk=None):
        message = actions.cancel_scheduled(pk)
        message = Message.objects.prefetch_related("events", "attempts").get(pk=message.pk)
        return Response(MessageDetailSerializer(message).data)


class TemplateViewSet(viewsets.ModelViewSet):
    queryset = MessageTemplate.objects.all()
    serializer_class = TemplateSerializer
    pagination_class = None


@api_view(["GET"])
def template_variables(request):
    return Response([{"name": name, "token": f"{{{{{name}}}}}", "description": desc}
                     for name, (desc, _) in templating.VARIABLES.items()])


def _stats() -> dict:
    counts = dict(Message.objects.values_list("status").annotate(n=Count("id")))
    get = lambda s: counts.get(s, 0)  # noqa: E731
    return {
        "total": sum(counts.values()),
        "sent": get(MessageStatus.SENT) + get(MessageStatus.DELIVERED) + get(MessageStatus.READ),
        "delivered": get(MessageStatus.DELIVERED) + get(MessageStatus.READ),
        "read": get(MessageStatus.READ),
        "failed": get(MessageStatus.FAILED),
        "in_progress": get(MessageStatus.QUEUED) + get(MessageStatus.SENDING),
        "scheduled": get(MessageStatus.SCHEDULED),
    }


SIMULATOR_SCENARIOS = [
    {"channel": "sms", "match": "Number ends in 000", "behaviour": "Invalid recipient (permanent failure, no retry)"},
    {"channel": "sms", "match": "Number ends in 111", "behaviour": "Temporary provider error once, then sent by automatic retry"},
    {"channel": "sms", "match": "Number ends in 222", "behaviour": "Rate limited once (Retry-After), then sent"},
    {"channel": "sms", "match": "Number ends in 333", "behaviour": "First message to the number fails delivery; retry succeeds"},
    {"channel": "sms", "match": "Number ends in 444", "behaviour": "Delivered but never read"},
    {"channel": "sms", "match": "Number ends in 555", "behaviour": "Duplicate and out-of-order status updates"},
    {"channel": "sms", "match": "Number ends in 666", "behaviour": "Fails 3 automatic attempts; succeeds on manual retry"},
    {"channel": "sms", "match": "Number ends in 777", "behaviour": "Always fails temporarily (shows the retry limit)"},
    {"channel": "email", "match": "Address contains 'bounce'", "behaviour": "Mailbox doesn't exist (permanent failure)"},
    {"channel": "email", "match": "Address contains 'deferred'", "behaviour": "First email fails delivery; retry succeeds"},
]
HEALTH_ORDER = {"operational": 0, "degraded": 1, "unavailable": 2}


class ProviderHealthView(APIView):
    """Health of every configured provider plus overall message statistics."""

    def get(self, request):
        providers = []
        for provider in list_providers():
            health = provider.health()
            providers.append({
                "name": provider.name,
                "display_name": provider.display_name,
                "channel": provider.channel,
                "simulated": provider.simulated,
                "status": health.status,
                "detail": health.detail,
                "checked_at": health.checked_at,
            })
        worst = max(providers, key=lambda p: HEALTH_ORDER.get(p["status"], 2))
        any_simulated = any(p["simulated"] for p in providers)
        return Response({
            "status": worst["status"],
            "detail": worst["detail"],
            "checked_at": worst["checked_at"],
            "default_provider": providers[0]["name"],
            "providers": providers,
            "stats": _stats(),
            "demo_controls_enabled": settings.DEMO_CONTROLS_ENABLED and any_simulated,
            "scenarios": SIMULATOR_SCENARIOS if any_simulated else [],
        })


class SimulatorOutageView(APIView):
    """Demo-only control: ask the simulator to start/stop a simulated outage."""

    def post(self, request):
        provider = get_provider()
        if not (settings.DEMO_CONTROLS_ENABLED and provider.simulated):
            raise ApiError("Demo controls are disabled.", "demo_controls_disabled", 403)
        enabled = request.data.get("enabled")
        if not isinstance(enabled, bool):
            raise ApiError("'enabled' must be true or false.", "validation_error", 400)
        try:
            provider.set_outage(enabled)
        except ProviderError as exc:
            raise ApiError("Couldn't reach the simulator to change its state.", "provider_unreachable", 502) from exc
        return Response({"outage": enabled})


@api_view(["GET"])
def health(request):
    Message.objects.exists()  # touches the database
    return Response({"status": "ok"})


@csrf_exempt
@require_POST
def provider_webhook(request, provider_name: str):
    """Status notifications from the provider. Authenticated by HMAC signature."""
    try:
        provider = get_provider(provider_name)
    except UnknownProvider:
        return JsonResponse({"error": {"code": "unknown_provider", "message": "Unknown provider."}}, status=404)
    if len(request.body) > MAX_WEBHOOK_BYTES:
        return JsonResponse({"error": {"code": "payload_too_large", "message": "Payload too large."}}, status=413)
    try:
        update = provider.parse_webhook(dict(request.headers), request.body)
    except WebhookError as exc:
        logger.warning("Rejected %s webhook: %s", provider.name, exc)
        return JsonResponse({"error": {"code": "invalid_webhook", "message": str(exc)}}, status=exc.status_code)
    outcome = apply_status_update(provider.name, update)
    logger.info("Webhook %s for %s: %s", update.provider_event_id, update.provider_message_id, outcome.value)
    return JsonResponse({"result": outcome.value})
