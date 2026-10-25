"""Consistent, safe error responses.

Every error leaves the API as::

    {"error": {"code": "validation_error", "message": "...", "fields": {...}}}

Unexpected exceptions are logged server-side and returned as a generic 500 so
stack traces never reach the browser.
"""

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ApiError(exceptions.APIException):
    """Domain error with a stable machine-readable code."""

    def __init__(self, message: str, code: str, status_code: int = status.HTTP_400_BAD_REQUEST, extra=None):
        self.status_code = status_code
        self.extra = extra or {}
        super().__init__(detail=message, code=code)


def _flatten(detail):
    if isinstance(detail, list):
        return " ".join(str(item) for item in detail)
    return str(detail)


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API error in %s", context.get("view").__class__.__name__)
        return Response(
            {"error": {"code": "server_error", "message": "Something went wrong on our side. Please try again."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, exceptions.ValidationError):
        detail = exc.detail
        fields = {}
        message = "Please correct the highlighted fields."
        if isinstance(detail, dict):
            for key, value in detail.items():
                if key == "non_field_errors":
                    message = _flatten(value)
                else:
                    fields[key] = _flatten(value)
        else:
            message = _flatten(detail)
        body = {"error": {"code": "validation_error", "message": message, "fields": fields}}
    elif isinstance(exc, ApiError):
        body = {"error": {"code": exc.get_codes(), "message": str(exc.detail), **exc.extra}}
    elif isinstance(exc, exceptions.Throttled):
        body = {
            "error": {
                "code": "throttled",
                "message": "You're doing that too often. Please wait a moment and try again.",
            }
        }
    else:
        codes = exc.get_codes() if isinstance(exc, exceptions.APIException) else "error"
        body = {"error": {"code": codes if isinstance(codes, str) else "error", "message": _flatten(exc.detail)}}

    response.data = body
    return response
