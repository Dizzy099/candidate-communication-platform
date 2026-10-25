"""Candidate-specific variables for message templates, e.g. ``Hi {{first_name}}``."""

import re
from collections.abc import Callable

from candidates.models import Candidate
from candidates.validators import format_phone_display

VARIABLES: dict[str, tuple[str, Callable[[Candidate], str]]] = {
    "first_name": ("Candidate's first name", lambda c: c.first_name),
    "full_name": ("Candidate's full name", lambda c: c.full_name),
    "candidate_id": ("Candidate ID, e.g. A1B2C3", lambda c: c.candidate_code),
    "phone": ("Mobile number", lambda c: format_phone_display(c.phone)),
    "email": ("Email address", lambda c: c.email),
}
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def template_problems(body: str) -> list[str]:
    """Human-readable problems with the variables in ``body`` (empty list = valid)."""
    problems = []
    unknown = sorted({name for name in _PLACEHOLDER.findall(body) if name not in VARIABLES})
    if unknown:
        allowed = ", ".join(f"{{{{{name}}}}}" for name in VARIABLES)
        problems.append(f"Unknown variable(s): {', '.join(unknown)}. Available: {allowed}.")
    leftover = _PLACEHOLDER.sub("", body)
    if "{{" in leftover or "}}" in leftover:
        problems.append("Variables must look like {{first_name}}; check for unmatched braces.")
    return problems


def render(body: str, candidate: Candidate) -> str:
    """Fill in variables. Call only after ``template_problems`` returned no problems."""
    return _PLACEHOLDER.sub(lambda match: VARIABLES[match.group(1)][1](candidate), body)


def uses_variables(body: str) -> bool:
    return bool(_PLACEHOLDER.search(body))
