import pytest
import respx
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
    settings.TOMTOM_API_KEY = "test-key"
    cache.clear()


@pytest.fixture
def router():
    """An isolated respx router per test (never the global one)."""
    with respx.mock(assert_all_called=False) as r:
        yield r
