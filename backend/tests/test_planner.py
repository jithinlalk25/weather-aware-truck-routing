from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from domain.geo import METERS_PER_MILE
from trips.models import TripPlan
from trips.services.planner import Place, PlanRequest, build_plan, resolve_departure

from .fakes import CHICAGO, DENVER, arc, open_meteo_responder, tomtom_payload, tomtom_route


def mock_providers(router, routes, **weather):
    router.route(host="api.tomtom.com", path__startswith="/routing/").mock(
        return_value=httpx.Response(200, json=routes))
    router.route(host="api.open-meteo.com").mock(side_effect=open_meteo_responder(**weather))


def request(**over):
    local_now = datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None, second=0,
                                                                   microsecond=0)
    base = dict(
        origin=Place("Chicago, IL", *CHICAGO),
        destination=Place("Denver, CO", *DENVER),
        departure_local=local_now + timedelta(hours=1),
        load_lb=42_000,
        interval_mi=25,
        wind_mode="sustained",
        hos=True,
    )
    base.update(over)
    return PlanRequest(**base)


@pytest.fixture
def three_routes():
    main = tomtom_route(arc(CHICAGO, DENVER))
    north = tomtom_route(arc(CHICAGO, DENVER, bulge_deg=1.2), speed=24)
    south = tomtom_route(arc(CHICAGO, DENVER, bulge_deg=-1.2), speed=23.5)
    return tomtom_payload(main, north, south)


@pytest.mark.django_db
def test_plan_recommends_route_avoiding_wind(router, three_routes):
    # Severe-band wind (48 mph) north of 41.6N: with 42,000 lb that is No Travel.
    mock_providers(router, three_routes,
                   wind_fn=lambda lat, lon: 48.0 if lat > 41.6 and lon > -101 else 12.0)

    plan = build_plan(request())
    routes = {r.label: r for r in plan.routes.all()}
    assert set(routes) == {"A", "B", "C"}
    assert routes["B"].miles_by_level["no_travel"] > routes["C"].miles_by_level["no_travel"]
    assert plan.recommended_label != "B"
    assert plan.decided_by in {"no_travel", "severe", "high", "avg_risk", "time"}
    assert routes[plan.recommended_label].rank == 1


@pytest.mark.django_db
def test_checkpoints_cover_route_and_etas_increase(router, three_routes):
    mock_providers(router, three_routes)

    plan = build_plan(request(interval_mi=10))
    for route in plan.routes.all():
        cps = route.checkpoints
        total_mi = route.distance_m / METERS_PER_MILE
        assert cps[0]["dist_mi"] == 0
        assert cps[-1]["dist_mi"] == pytest.approx(total_mi, abs=0.1)
        assert sum(c["share_mi"] for c in cps) == pytest.approx(total_mi, abs=0.5)
        assert sum(route.miles_by_level.values()) == pytest.approx(total_mi, abs=0.5)
        etas = [c["eta"] for c in cps]
        assert etas == sorted(etas)
        assert all(c["level"] == 0 for c in cps)  # calm weather everywhere


@pytest.mark.django_db
def test_hos_adds_pauses_and_shifts_arrival(router, three_routes):
    mock_providers(router, three_routes)

    with_hos = build_plan(request(hos=True)).routes.get(label="A")
    without = build_plan(request(hos=False)).routes.get(label="A")
    assert without.rest_stops == []
    assert {s["kind"] for s in with_hos.rest_stops} >= {"break", "rest"}  # ~19 h of driving
    assert with_hos.total_s - with_hos.drive_s == pytest.approx(
        sum(s["duration_s"] for s in with_hos.rest_stops))
    assert with_hos.checkpoints[-1]["eta"] > without.checkpoints[-1]["eta"]
    # The path holds still during each pause: two vertices at the same spot.
    times = [p[3] for p in with_hos.path]
    assert times == sorted(times)


@pytest.mark.django_db
def test_gust_mode_is_more_conservative(router, three_routes):
    mock_providers(router, three_routes, wind_fn=lambda lat, lon: 22.0)

    sustained = build_plan(request(wind_mode="sustained")).routes.get(label="A")
    gust = build_plan(request(wind_mode=TripPlan.WindMode.GUST)).routes.get(label="A")
    assert sustained.miles_by_level["moderate"] == 0  # 22 mph -> Low
    assert gust.miles_by_level["moderate"] > 0  # 30.8 mph gusts -> Moderate


def test_departure_window():
    now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    dep = resolve_departure(datetime(2026, 10, 10, 9, 0), "America/Chicago", now)
    assert dep == datetime(2026, 10, 10, 14, 0, tzinfo=UTC)  # CDT = UTC-5
    with pytest.raises(Exception, match="past"):
        resolve_departure(datetime(2026, 10, 10, 6, 0), "America/Chicago", now)
    with pytest.raises(Exception, match="7 days"):
        resolve_departure(datetime(2026, 10, 18, 9, 0), "America/Chicago", now)


@pytest.mark.django_db
def test_unavailable_weather_cells_become_no_data(router, three_routes, monkeypatch):
    from trips.services import weather

    mock_providers(router, three_routes)
    real_get_series = weather.get_series

    def lose_one_cell(nodes):
        result = real_get_series(nodes)
        lost = sorted(result.series)[0]
        del result.series[lost]
        result.unavailable.add(lost)
        return result

    monkeypatch.setattr(weather, "get_series", lose_one_cell)
    plan = build_plan(request())
    no_data = [c for r in plan.routes.all() for c in r.checkpoints if c["level"] is None]
    assert no_data and all(c["factor"].startswith("Weather service unavailable") for c in no_data)
    assert any("failed for 1 of" in n for n in plan.notes)
