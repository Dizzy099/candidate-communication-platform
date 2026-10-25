"""Deterministic behaviour keyed on the last three digits of the recipient number.

| Suffix | Scenario                | Behaviour                                                |
|--------|-------------------------|----------------------------------------------------------|
| 000    | invalid_recipient       | 422 on every submission                                  |
| 111    | temporary_error_once    | 500 on the 1st submission of a key, then normal          |
| 222    | rate_limited_once       | 429 + Retry-After on the 1st submission, then normal     |
| 333    | delivery_fails_first    | first message to the number: sent, then ``failed``       |
| 444    | delivered_never_read    | sent -> delivered, no read                               |
| 555    | duplicates_out_of_order | ``read`` before ``delivered``; every event sent twice    |
| 666    | fails_until_manual      | 500 on submissions 1-3, normal from the 4th              |
| 777    | always_temporary_error  | 500 on every submission                                  |
| other  | normal                  | sent -> delivered -> read                                |

Email channel: an address containing ``bounce`` is an invalid recipient and one
containing ``deferred`` fails delivery the first time; everything else is normal.

No randomness: the same input always produces the same behaviour.
"""

import re
from dataclasses import dataclass, field

E164 = re.compile(r"^\+[1-9]\d{7,14}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Rejection:
    http_status: int
    code: str
    message: str
    retry_after: int | None = None


@dataclass(frozen=True)
class PlannedEvent:
    status: str
    delay_seconds: float
    error_code: str = ""
    error_message: str = ""
    extra_deliveries: int = 0


@dataclass(frozen=True)
class Scenario:
    key: str
    failing_attempts: int = 0  # submissions (per idempotency key) that fail before success
    rejection: Rejection | None = None
    events: tuple[PlannedEvent, ...] = field(default_factory=tuple)


TEMPORARY = Rejection(500, "internal_error", "Temporary internal error. Please retry.")
SUFFIXES = {
    "000": "invalid_recipient",
    "111": "temporary_error_once",
    "222": "rate_limited_once",
    "333": "delivery_fails_first",
    "444": "delivered_never_read",
    "555": "duplicates_out_of_order",
    "666": "fails_until_manual",
    "777": "always_temporary_error",
}


EMAIL_MARKERS = {"bounce": "invalid_recipient", "deferred": "delivery_fails_first"}


def scenario_key(to: str, channel: str = "sms") -> str:
    if channel == "email":
        local = to.split("@", 1)[0].lower()
        return next((key for marker, key in EMAIL_MARKERS.items() if marker in local), "normal")
    return SUFFIXES.get(to[-3:], "normal")


def valid_recipient(to: str, channel: str) -> bool:
    return bool(EMAIL.match(to) if channel == "email" else E164.match(to))


def build_scenario(key: str, *, delivery_delay: float, read_delay: float, previous_messages_to_number: int) -> Scenario:
    normal = (PlannedEvent("delivered", delivery_delay), PlannedEvent("read", read_delay))
    if key == "invalid_recipient":
        return Scenario(key, failing_attempts=10**9,
                        rejection=Rejection(422, "invalid_recipient", "The recipient number is not reachable."))
    if key == "temporary_error_once":
        return Scenario(key, failing_attempts=1, rejection=TEMPORARY, events=normal)
    if key == "rate_limited_once":
        return Scenario(key, failing_attempts=1, events=normal,
                        rejection=Rejection(429, "rate_limited", "Too many requests.", retry_after=3))
    if key == "delivery_fails_first" and previous_messages_to_number == 0:
        return Scenario(key, events=(PlannedEvent("failed", delivery_delay, "undeliverable", "Handset unreachable."),))
    if key == "delivered_never_read":
        return Scenario(key, events=(PlannedEvent("delivered", delivery_delay),))
    if key == "duplicates_out_of_order":
        return Scenario(key, events=(
            PlannedEvent("read", delivery_delay, extra_deliveries=1),
            PlannedEvent("delivered", delivery_delay + 1, extra_deliveries=1),
        ))
    if key == "fails_until_manual":
        return Scenario(key, failing_attempts=3, rejection=TEMPORARY, events=normal)
    if key == "always_temporary_error":
        return Scenario(key, failing_attempts=10**9, rejection=TEMPORARY)
    return Scenario("normal", events=normal)


def rejection_for_attempt(scenario: Scenario, attempt_number: int) -> Rejection | None:
    """``attempt_number`` counts submissions of one idempotency key, starting at 1."""
    if scenario.rejection and attempt_number <= scenario.failing_attempts:
        return scenario.rejection
    return None
