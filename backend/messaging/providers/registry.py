from contextlib import contextmanager
from functools import lru_cache

from django.conf import settings
from django.utils.module_loading import import_string

from .base import CommunicationProvider

PROVIDER_CLASSES = {
    "simulator": "messaging.providers.simulator.SimulatorProvider",
    "simulator_email": "messaging.providers.simulator.SimulatorEmailProvider",
}


class UnknownProvider(LookupError):
    pass


_override: dict[str, CommunicationProvider] | None = None


@lru_cache(maxsize=1)
def _configured_providers() -> dict[str, CommunicationProvider]:
    """Instantiate every backend in ``PROVIDER["BACKENDS"]`` (short names or dotted paths)."""
    providers: dict[str, CommunicationProvider] = {}
    for backend in settings.PROVIDER["BACKENDS"]:
        provider = import_string(PROVIDER_CLASSES.get(backend, backend))(settings.PROVIDER)
        providers[provider.name] = provider
    return providers


def _providers() -> dict[str, CommunicationProvider]:
    return _override if _override is not None else _configured_providers()


def list_providers() -> list[CommunicationProvider]:
    return list(_providers().values())


def get_provider(name: str | None = None) -> CommunicationProvider:
    """The named provider, or the default (first configured) one when ``name`` is None."""
    providers = _providers()
    if name is None:
        return next(iter(providers.values()))
    try:
        return providers[name]
    except KeyError:
        raise UnknownProvider(name) from None


def reset_provider_cache() -> None:
    _configured_providers.cache_clear()


@contextmanager
def override_provider(*providers: CommunicationProvider):
    """Use these providers everywhere for the duration of a test (first one is the default)."""
    global _override
    previous, _override = _override, {p.name: p for p in providers}
    try:
        yield providers[0]
    finally:
        _override = previous
