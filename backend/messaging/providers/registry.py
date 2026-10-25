from contextlib import contextmanager
from functools import lru_cache

from django.conf import settings
from django.utils.module_loading import import_string

from .base import CommunicationProvider

PROVIDER_BACKENDS = {
    "simulator": "messaging.providers.simulator.SimulatorProvider",
}

_override: CommunicationProvider | None = None


@lru_cache(maxsize=1)
def _configured_provider() -> CommunicationProvider:
    backend = settings.PROVIDER["BACKEND"]
    return import_string(PROVIDER_BACKENDS.get(backend, backend))(settings.PROVIDER)


def get_provider() -> CommunicationProvider:
    """Return the configured provider. ``PROVIDER_BACKEND`` is a short name or a dotted path."""
    return _override if _override is not None else _configured_provider()


def reset_provider_cache() -> None:
    _configured_provider.cache_clear()


@contextmanager
def override_provider(provider: CommunicationProvider):
    """Use ``provider`` everywhere for the duration of a test."""
    global _override
    previous, _override = _override, provider
    try:
        yield provider
    finally:
        _override = previous
