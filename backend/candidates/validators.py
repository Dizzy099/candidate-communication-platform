"""Normalisation and validation for candidate contact details.

Supported region: India. Mobile numbers are stored in E.164 form
(``+919876543210``) so the same person can't be added twice with different
spacing or prefixes.
"""

import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

_PHONE_SEPARATORS = re.compile(r"[\s\-().]")
_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")
_NAME_ALLOWED = re.compile(r"^[^\W\d_]+(?:(?:\. ?|[ '\-])[^\W\d_]+)*\.?$")

PHONE_HELP = "Enter a valid 10-digit Indian mobile number, e.g. +91 98765 43210."


def normalize_indian_mobile(raw: str) -> str:
    """Return ``+91XXXXXXXXXX`` or raise ValidationError.

    Accepts common ways people type Indian mobile numbers:
    ``9876543210``, ``09876543210``, ``919876543210``, ``+91 98765-43210``.
    """
    value = _PHONE_SEPARATORS.sub("", (raw or "").strip())
    if value.startswith("+"):
        if not value.startswith("+91"):
            raise ValidationError("Only Indian (+91) mobile numbers are supported.")
        digits = value[3:]
    elif len(value) == 12 and value.startswith("91"):
        digits = value[2:]
    elif len(value) == 11 and value.startswith("0"):
        digits = value[1:]
    else:
        digits = value
    if not digits.isdigit() or not _INDIAN_MOBILE.match(digits):
        raise ValidationError(PHONE_HELP)
    return f"+91{digits}"


def format_phone_display(e164: str) -> str:
    """``+919876543210`` -> ``+91 9876543210`` (the format used in the design)."""
    if e164.startswith("+91") and len(e164) == 13:
        return f"+91 {e164[3:]}"
    return e164


def normalize_full_name(raw: str) -> str:
    name = " ".join((raw or "").split())
    if len(name) < 2:
        raise ValidationError("Enter the candidate's full name (at least 2 characters).")
    if len(name) > 100:
        raise ValidationError("Name can be at most 100 characters.")
    if not _NAME_ALLOWED.match(name):
        raise ValidationError("Name can contain letters, spaces, apostrophes, hyphens and dots only.")
    return name


def normalize_email(raw: str) -> str:
    email = (raw or "").strip().lower()
    if not email:
        raise ValidationError("Enter an email address.")
    if len(email) > 254:
        raise ValidationError("Email can be at most 254 characters.")
    try:
        validate_email(email)
    except ValidationError as exc:
        raise ValidationError("Enter a valid email address, e.g. name@example.com.") from exc
    return email
