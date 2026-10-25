from django.db import IntegrityError, transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.exceptions import ApiError

from .models import Candidate
from .selectors import candidates_with_last_message, filter_candidates
from .serializers import BulkDeleteSerializer, CandidateSerializer


class CandidateViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """List/search, add, view and delete candidates.

    Query params for list: ``search``, ``status`` (comma list, ``none`` = never
    messaged), ``ordering`` (e.g. ``-last_message_at``), ``page``, ``page_size``.
    """

    serializer_class = CandidateSerializer

    def get_queryset(self):
        params = self.request.query_params
        statuses = [s for s in params.get("status", "").split(",") if s]
        return filter_candidates(
            candidates_with_last_message(),
            search=params.get("search", ""),
            statuses=statuses,
            ordering=params.get("ordering", ""),
        )

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError as exc:
            # Two identical submissions raced past validation; the DB constraint caught it.
            raise ApiError(
                "A candidate with this mobile number or email already exists.", "duplicate_candidate", 409
            ) from exc

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # Re-read with annotations so the response matches list items exactly.
        candidate = candidates_with_last_message().get(pk=response.data["id"])
        response.data = self.get_serializer(candidate).data
        return response

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        serializer = BulkDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = set(serializer.validated_data["ids"])
        with transaction.atomic():
            found = set(Candidate.objects.filter(id__in=ids).values_list("id", flat=True))
            Candidate.objects.filter(id__in=found).delete()
        return Response(
            {"deleted": len(found), "not_found": sorted(ids - found)},
            status=status.HTTP_200_OK,
        )
