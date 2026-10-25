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
from .providers import ProviderError, WebhookError, get_provider
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
    {"suffix": "000", "behaviour": "Invalid recipient (permanent failure, no retry)"},
    {"suffix": "111", "behaviour": "Temporary provider error once, then sent by automatic retry"},
    {"suffix": "222", "behaviour": "Rate limited once (Retry-After), then sent"},
    {"suffix": "333", "behaviour": "Sent, then delivery fails (manual retry allowed)"},
    {"suffix": "444", "behaviour": "Delivered but never read"},
    {"suffix": "555", "behaviour": "Duplicate and out-of-order status updates"},
    {"suffix": "666", "behaviour": "Fails 3 automatic attempts; succeeds on manual retry"},
    {"suffix": "777", "behaviour": "Always fails temporarily (shows the retry limit)"},
]


class ProviderHealthView(APIView):
    def get(self, request):
        provider = get_provider()
        health = provider.health()
        payload = {
            "provider": {
                "name": provider.name,
                "display_name": provider.display_name,
                "channel": provider.channel,
                "simulated": provider.simulated,
            },
            "status": health.status,
            "detail": health.detail,
            "checked_at": health.checked_at,
            "stats": _stats(),
            "demo_controls_enabled": settings.DEMO_CONTROLS_ENABLED and provider.simulated,
            "scenarios": SIMULATOR_SCENARIOS if provider.simulated else [],
        }
        return Response(payload)


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
    provider = get_provider()
    if provider_name != provider.name:
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
