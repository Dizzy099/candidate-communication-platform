import re

from django.db.models import F, OuterRef, Q, QuerySet, Subquery

from messaging.models import Message

from .models import Candidate

ORDERING_FIELDS = {"full_name", "created_at", "candidate_code", "phone", "last_message_at"}


def candidates_with_last_message() -> QuerySet[Candidate]:
    """Candidates annotated with their latest message in a single query (no N+1)."""
    latest = Message.objects.filter(candidate=OuterRef("pk")).order_by("-created_at")
    return Candidate.objects.annotate(
        last_message_id=Subquery(latest.values("id")[:1]),
        last_message_status=Subquery(latest.values("status")[:1]),
        last_message_at=Subquery(latest.values("created_at")[:1]),
    )


def filter_candidates(qs: QuerySet[Candidate], *, search: str = "", statuses: list[str] | None = None,
                      ordering: str = "") -> QuerySet[Candidate]:
    search = search.strip()
    if search:
        condition = Q(full_name__icontains=search) | Q(email__icontains=search) | Q(candidate_code__iexact=search)
        digits = re.sub(r"\D", "", search)
        if len(digits) >= 3:
            condition |= Q(phone__contains=digits)
        qs = qs.filter(condition)
    if statuses:
        condition = Q(last_message_status__in=[s for s in statuses if s != "none"])
        if "none" in statuses:
            condition |= Q(last_message_id__isnull=True)
        qs = qs.filter(condition)
    field = ordering.lstrip("-")
    if field in ORDERING_FIELDS:
        expression = F(field)
        if ordering.startswith("-"):
            qs = qs.order_by(expression.desc(nulls_last=True), "-id")
        else:
            qs = qs.order_by(expression.asc(nulls_last=True), "id")
    return qs
