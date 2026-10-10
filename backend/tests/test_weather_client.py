import httpx
import pytest

from domain.lattice import Node
from trips.services import weather
from trips.services.errors import UpstreamRateLimited, WeatherUnavailable

from .fakes import open_meteo_responder

NODES = [Node(0.1, 400 + i, -900) for i in range(120)]  # 3 batches of 50/50/20


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(weather.time, "sleep", lambda s: None)


def test_retries_transient_503(router):
    ok = open_meteo_responder()
    calls = iter([httpx.Response(503, json={"reason": "The service is overloaded"})])

    def respond(request):
        return next(calls, None) or ok(request)

    route = router.get(host="api.open-meteo.com").mock(side_effect=respond)
    result = weather.get_series(NODES[:10])
    assert len(result.series) == 10 and not result.unavailable
    assert route.call_count == 2


def test_a_failing_batch_degrades_to_no_data(router):
    ok = open_meteo_responder()

    def respond(request):
        if request.url.params["latitude"].startswith("50,"):  # third batch: 50.0..51.9 N
            return httpx.Response(503)
        return ok(request)

    router.get(host="api.open-meteo.com").mock(side_effect=respond)
    result = weather.get_series(NODES)
    assert len(result.unavailable) == 20  # the last batch failed every retry
    assert len(result.series) == 100


def test_mostly_failing_raises_friendly_503(router):
    router.get(host="api.open-meteo.com").mock(return_value=httpx.Response(503))
    with pytest.raises(WeatherUnavailable):
        weather.get_series(NODES)


def test_rate_limit_is_not_retried(router):
    route = router.get(host="api.open-meteo.com").mock(return_value=httpx.Response(429))
    with pytest.raises(UpstreamRateLimited):
        weather.get_series(NODES[:5])
    assert route.call_count == 1


def test_failures_are_not_cached(router):
    router.get(host="api.open-meteo.com").mock(return_value=httpx.Response(503))
    with pytest.raises(WeatherUnavailable):
        weather.get_series(NODES[:5])
    router.get(host="api.open-meteo.com").mock(side_effect=open_meteo_responder())
    assert len(weather.get_series(NODES[:5]).series) == 5
