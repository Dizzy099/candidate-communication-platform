"""SimuText public API (v1).

POST /v1/messages              submit a message (Bearer auth, Idempotency-Key header)
GET  /v1/messages/<id>         current status of a submitted message
GET  /v1/health                service health
POST /v1/simulator/outage      demo control: start/stop a simulated outage
"""

import hmac
import json
import math
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import scenarios
from .models import OutboundEvent, SimulatedMessage, SimulatorState, SubmissionCounter, new_id
from .ratelimit import TokenBucket

CFG = settings.SIMULATOR
bucket = TokenBucket(CFG["RATE_LIMIT_PER_SECOND"], CFG["RATE_LIMIT_BURST"])


def error(status: int, code: str, message: str, retry_after: int | None = None) -> JsonResponse:
    response = JsonResponse({"error": {"code": code, "message": message}}, status=status)
    if retry_after is not None:
        response["Retry-After"] = str(retry_after)
    return response


def authorized(request) -> bool:
    expected = CFG["API_KEY"]
    header = request.headers.get("Authorization", "")
    return bool(expected) and header.startswith("Bearer ") and hmac.compare_digest(header[7:], expected)


def serialize(message: SimulatedMessage) -> dict:
    return {
        "id": message.id,
        "status": message.status,
        "to": message.to,
        "channel": message.channel,
        "client_reference": message.client_reference,
        "created_at": message.created_at.isoformat(),
    }


def _valid_callback(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


@csrf_exempt
@require_POST
def submit_message(request):
    if not authorized(request):
        return error(401, "unauthorized", "Missing or invalid API key.")
    if SimulatorState.get().outage:
        return error(503, "service_unavailable", "SimuText is experiencing an outage.", retry_after=10)
    wait = bucket.take()
    if wait:
        return error(429, "rate_limited", "Rate limit exceeded.", retry_after=max(1, math.ceil(wait)))

    key = request.headers.get("Idempotency-Key", "").strip()
    if not key or len(key) > 100:
        return error(400, "missing_idempotency_key", "An Idempotency-Key header (max 100 chars) is required.")
    try:
        data = json.loads(request.body)
        to, body, callback = str(data["to"]), str(data["body"]), str(data["callback_url"])
    except (ValueError, KeyError, TypeError):
        return error(400, "invalid_request", "Body must be JSON with 'to', 'body' and 'callback_url'.")
    if not body.strip():
        return error(400, "invalid_request", "'body' must not be empty.")
    if not _valid_callback(callback):
        return error(400, "invalid_request", "'callback_url' must be an http(s) URL.")

    existing = SimulatedMessage.objects.filter(idempotency_key=key).first()
    if existing:
        return JsonResponse(serialize(existing), status=200)  # idempotent replay: no second send

    SubmissionCounter.objects.get_or_create(idempotency_key=key)
    SubmissionCounter.objects.filter(idempotency_key=key).update(attempts=F("attempts") + 1)
    attempt = SubmissionCounter.objects.get(idempotency_key=key).attempts

    channel = str(data.get("channel", "sms"))[:20]
    if channel not in ("sms", "email"):
        return error(400, "invalid_request", "'channel' must be 'sms' or 'email'.")
    if not scenarios.valid_recipient(to, channel):
        expected = "an email address" if channel == "email" else "an E.164 phone number"
        return error(422, "invalid_recipient", f"'to' must be {expected}.")
    if len(body) > CFG["MAX_BODY_LENGTH"]:
        return error(400, "content_too_long", f"Message exceeds {CFG['MAX_BODY_LENGTH']} characters.")

    scenario = scenarios.build_scenario(
        scenarios.scenario_key(to, channel),
        delivery_delay=CFG["DELIVERY_DELAY_SECONDS"],
        read_delay=CFG["READ_DELAY_SECONDS"],
        previous_messages_to_number=SimulatedMessage.objects.filter(to=to).count(),
    )
    rejection = scenarios.rejection_for_attempt(scenario, attempt)
    if rejection:
        return error(rejection.http_status, rejection.code, rejection.message, rejection.retry_after)

    now = timezone.now()
    try:
        with transaction.atomic():
            message = SimulatedMessage.objects.create(
                id=new_id("sim"),
                idempotency_key=key,
                client_reference=str(data.get("client_reference", ""))[:100],
                to=to,
                channel=channel,
                body_length=len(body),
                callback_url=callback,
                scenario=scenario.key,
            )
            OutboundEvent.objects.bulk_create(
                OutboundEvent(
                    id=new_id("evt"),
                    message=message,
                    status=planned.status,
                    error_code=planned.error_code,
                    error_message=planned.error_message,
                    occurred_at=now + timedelta(seconds=planned.delay_seconds),
                    next_attempt_at=now + timedelta(seconds=planned.delay_seconds),
                    extra_deliveries=planned.extra_deliveries,
                )
                for planned in scenario.events
            )
    except IntegrityError:
        message = SimulatedMessage.objects.get(idempotency_key=key)  # concurrent duplicate submission
        return JsonResponse(serialize(message), status=200)
    return JsonResponse(serialize(message), status=201)


@require_GET
def message_detail(request, message_id: str):
    if not authorized(request):
        return error(401, "unauthorized", "Missing or invalid API key.")
    message = SimulatedMessage.objects.filter(id=message_id).first()
    if message is None:
        return error(404, "not_found", "No such message.")
    return JsonResponse(serialize(message))


@require_GET
def health(request):
    if SimulatorState.get().outage:
        return JsonResponse({"status": "outage", "time": timezone.now().isoformat()}, status=503)
    return JsonResponse({"status": "operational", "time": timezone.now().isoformat()})


@csrf_exempt
@require_POST
def set_outage(request):
    if not authorized(request):
        return error(401, "unauthorized", "Missing or invalid API key.")
    try:
        enabled = json.loads(request.body)["enabled"]
    except (ValueError, KeyError, TypeError):
        return error(400, "invalid_request", "Body must be JSON with boolean 'enabled'.")
    if not isinstance(enabled, bool):
        return error(400, "invalid_request", "'enabled' must be a boolean.")
    SimulatorState.objects.update_or_create(pk=1, defaults={"outage": enabled})
    return JsonResponse({"outage": enabled})
