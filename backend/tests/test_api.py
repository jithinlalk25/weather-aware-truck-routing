from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from rest_framework.test import APIClient

from .fakes import CHICAGO, DENVER, arc, open_meteo_responder, tomtom_payload, tomtom_route


def body(**over):
    dep = datetime.now(ZoneInfo("America/Chicago")) + timedelta(hours=2)
    data = {
        "origin": {"label": "Chicago, IL", "lat": CHICAGO[0], "lon": CHICAGO[1]},
        "destination": {"label": "Denver, CO", "lat": DENVER[0], "lon": DENVER[1]},
        "departure_local": dep.strftime("%Y-%m-%dT%H:%M"),
        "load_lb": 38_000,
        "interval_mi": 50,
        "wind_mode": "sustained",
        "hos": True,
    }
    data.update(over)
    return data


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def mocked():
    with respx.mock(assert_all_called=False) as router:
        routes = tomtom_payload(
            tomtom_route(arc(CHICAGO, DENVER)),
            tomtom_route(arc(CHICAGO, DENVER, bulge_deg=1.1), speed=24),
            tomtom_route(arc(CHICAGO, DENVER, bulge_deg=-1.1), speed=24),
        )
        router.route(host="api.tomtom.com", path__startswith="/routing/").mock(
            return_value=httpx.Response(200, json=routes))
        router.route(host="api.open-meteo.com").mock(side_effect=open_meteo_responder(
            rain_fn=lambda lat, lon: 0.3 if lon < -100 else 0.0))
        yield router


@pytest.mark.django_db
def test_create_and_fetch_plan(api, mocked):
    res = api.post("/api/plans", body(), format="json")
    assert res.status_code == 201, res.content
    plan = res.json()
    assert plan["origin"]["tz"] == "America/Chicago"
    assert len(plan["routes"]) == 3
    rec = plan["recommendation"]
    assert rec["label"] in "ABC" and rec["headline"]
    route = plan["routes"][0]
    for key in ("distance_mi", "total_s", "miles_by_level", "path", "checkpoints", "rest_stops"):
        assert key in route
    cp = route["checkpoints"][-1]
    assert {"eta", "tz", "level", "factor", "rain_in_hr", "confidence"} <= set(cp)

    again = api.get(f"/api/plans/{plan['id']}")
    assert again.status_code == 200
    assert again.json()["recommendation"] == rec


@pytest.mark.django_db
def test_heatmap_shape(api, mocked):
    plan_id = api.post("/api/plans", body(), format="json").json()["id"]
    res = api.get(f"/api/plans/{plan_id}/heatmap")
    assert res.status_code == 200
    hm = res.json()
    cells = len(hm["cells"]) // 2
    assert 0 < cells <= 120
    assert hm["hours"] == 49
    for values in hm["layers"].values():
        assert len(values) == cells * 49
    # Rain of 0.3 in/hr west of 100W shows up as High risk (index 2.x).
    assert max(v for v in hm["layers"]["risk"] if v is not None) >= 2
    assert api.get(f"/api/plans/{plan_id}/heatmap").json() == hm  # persisted snapshot


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("over", "field"),
    [
        ({"origin": {"label": "Toronto", "lat": 43.65, "lon": -79.38}}, "origin"),
        ({"interval_mi": 15}, "interval_mi"),
        ({"load_lb": 90_000}, "load_lb"),
        ({"departure_local": "2020-01-01T08:00"}, "departure_local"),
    ],
)
def test_validation_errors(api, mocked, over, field):
    res = api.post("/api/plans", body(**over), format="json")
    assert res.status_code == 400
    assert field in res.json()


@pytest.mark.django_db
def test_geocode(api):
    with respx.mock() as router:
        router.route(host="api.tomtom.com", path__startswith="/search/").mock(
            return_value=httpx.Response(200, json={"results": [
                {"address": {"freeformAddress": "Dallas, TX"},
                 "position": {"lat": 32.78, "lon": -96.80}},
                {"address": {"freeformAddress": "Dallas, TX"},  # duplicate label
                 "position": {"lat": 32.77, "lon": -96.79}},
            ]}))
        res = api.get("/api/geocode", {"q": "dalla"})
    assert res.status_code == 200
    assert res.json()["results"] == [
        {"label": "Dallas, TX", "lat": 32.78, "lon": -96.80, "tz": "America/Chicago"}]
    assert api.get("/api/geocode", {"q": "da"}).json()["results"] == []


@pytest.mark.django_db
def test_upstream_rate_limit_is_reported(api):
    with respx.mock() as router:
        router.route(host="api.tomtom.com").mock(return_value=httpx.Response(429))
        res = api.post("/api/plans", body(), format="json")
    assert res.status_code == 503
    assert "rate limit" in res.json()["detail"].lower()


@pytest.mark.django_db
def test_incomplete_heatmap_is_not_persisted(api, mocked, monkeypatch):
    from trips.models import TripPlan
    from trips.services import weather

    plan_id = api.post("/api/plans", body(), format="json").json()["id"]
    real = weather.get_series

    def lose_one(nodes):
        result = real(nodes)
        lost = sorted(result.series)[0]
        del result.series[lost]
        result.unavailable.add(lost)
        return result

    monkeypatch.setattr(weather, "get_series", lose_one)
    hm = api.get(f"/api/plans/{plan_id}/heatmap").json()
    assert hm["complete"] is False
    assert TripPlan.objects.get(pk=plan_id).heatmap is None  # retried on the next request
