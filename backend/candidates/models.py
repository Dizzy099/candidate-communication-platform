import secrets
import string

from django.db import IntegrityError, models, transaction

_LETTERS = string.ascii_uppercase
_DIGITS = string.digits


def generate_candidate_code() -> str:
    """Six characters alternating letter/digit, e.g. ``A1B2C3`` (as in the design)."""
    return "".join(secrets.choice(_LETTERS if i % 2 == 0 else _DIGITS) for i in range(6))


class Candidate(models.Model):
    candidate_code = models.CharField(max_length=6, unique=True, editable=False)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=16, unique=True, help_text="E.164, e.g. +919876543210")
    email = models.EmailField(max_length=254, unique=True, help_text="Stored lower-cased")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["full_name"])]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.candidate_code})"

    @property
    def first_name(self) -> str:
        return self.full_name.split(" ")[0]

    def save(self, *args, **kwargs):
        if self.candidate_code:
            return super().save(*args, **kwargs)
        # Retry on the (very unlikely) code collision; each try is its own savepoint.
        for _ in range(10):
            self.candidate_code = generate_candidate_code()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError as exc:
                if "candidate_code" not in str(exc):
                    raise
        raise IntegrityError("Could not generate a unique candidate code.")
