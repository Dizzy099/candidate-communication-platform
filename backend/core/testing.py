"""Shared test helpers."""

from django.core.cache import cache
from rest_framework.test import APITestCase

from candidates.models import Candidate
from messaging.providers.registry import override_provider
from messaging.tests.fakes import FakeProvider


def make_candidate(name: str = "Asha Verma", phone: str = "+919800000001", email: str | None = None) -> Candidate:
    email = email or f"{name.lower().replace(' ', '.')}@example.com"
    return Candidate.objects.create(full_name=name, phone=phone, email=email)


class ApiTestCase(APITestCase):
    """API test base: fresh throttle counters and a scripted fake provider."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.provider = FakeProvider()
        context = override_provider(self.provider)
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
