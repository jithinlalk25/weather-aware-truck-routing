import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
    settings.TOMTOM_API_KEY = "test-key"
    cache.clear()
