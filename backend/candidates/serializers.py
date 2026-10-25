from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from messaging.models import MessageStatus

from . import validators
from .models import Candidate


def _required(label: str) -> dict:
    return {"required": f"Enter the candidate's {label}.", "blank": f"Enter the candidate's {label}."}


def _run(normalizer, value):
    try:
        return normalizer(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages[0]) from exc


class CandidateSerializer(serializers.ModelSerializer):
    # Declared explicitly so uniqueness is checked *after* normalisation.
    full_name = serializers.CharField(max_length=200, error_messages=_required("full name"))
    phone = serializers.CharField(max_length=32, error_messages=_required("mobile number"))
    email = serializers.CharField(max_length=320, error_messages=_required("email address"))
    phone_display = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = ["id", "candidate_code", "full_name", "phone", "phone_display", "email", "created_at", "last_message"]
        read_only_fields = ["id", "candidate_code", "created_at"]

    def get_phone_display(self, obj: Candidate) -> str:
        return validators.format_phone_display(obj.phone)

    def get_last_message(self, obj: Candidate):
        message_id = getattr(obj, "last_message_id", None)
        if not message_id:
            return None
        status = obj.last_message_status
        return {
            "id": str(message_id),
            "status": status,
            "status_label": MessageStatus(status).label,
            "created_at": serializers.DateTimeField().to_representation(obj.last_message_at),
        }

    def validate_full_name(self, value: str) -> str:
        return _run(validators.normalize_full_name, value)

    def validate_phone(self, value: str) -> str:
        phone = _run(validators.normalize_indian_mobile, value)
        existing = Candidate.objects.filter(phone=phone).exclude(pk=getattr(self.instance, "pk", None)).first()
        if existing:
            raise serializers.ValidationError(
                f"A candidate with this mobile number already exists: {existing.full_name} ({existing.candidate_code})."
            )
        return phone

    def validate_email(self, value: str) -> str:
        email = _run(validators.normalize_email, value)
        existing = Candidate.objects.filter(email=email).exclude(pk=getattr(self.instance, "pk", None)).first()
        if existing:
            raise serializers.ValidationError(
                f"A candidate with this email already exists: {existing.full_name} ({existing.candidate_code})."
            )
        return email


class BulkDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1, max_length=500,
        error_messages={"min_length": "Select at least one candidate.", "empty": "Select at least one candidate."},
    )
