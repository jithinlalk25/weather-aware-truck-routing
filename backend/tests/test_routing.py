from datetime import UTC, datetime, timedelta

import httpx

from trips.services.routing import get_route_options

from .fakes import CHICAGO, DENVER, arc, tomtom_payload, tomtom_route

DEPART = datetime.now(UTC) + timedelta(hours=1)


def tomtom(router):
    return router.route(host="api.tomtom.com", path__startswith="/routing/")


def test_drops_near_duplicates_and_slow_alternatives(router):
    main = tomtom_route(arc(CHICAGO, DENVER))
    dup = tomtom_route(arc(CHICAGO, DENVER, bulge_deg=0.001), speed=24.9)
    slow = tomtom_route(arc(CHICAGO, DENVER, bulge_deg=2.0), speed=12)  # >1.4x slower
    ok = tomtom_route(arc(CHICAGO, DENVER, bulge_deg=-1.0), speed=24)

    def respond(request: httpx.Request):
        if "circle(" in request.url.path:  # forced via-points find nothing new
            return httpx.Response(400, json={"detailedError": {"message": "NO_ROUTE_FOUND"}})
        return httpx.Response(200, json=tomtom_payload(main, dup, slow, ok))

    tomtom(router).mock(side_effect=respond)
    opts = get_route_options(CHICAGO, DENVER, DEPART, 70_000)
    lengths = [r.length_m for r in opts.routes]
    assert lengths == [main["summary"]["lengthInMeters"], ok["summary"]["lengthInMeters"]]
    assert any("Only 2 distinct" in n for n in opts.notes)


def test_forces_alternatives_through_via_points_when_needed(router):
    main = tomtom_route(arc(CHICAGO, DENVER))
    north = tomtom_route(arc(CHICAGO, DENVER, bulge_deg=0.9), speed=24)
    south = tomtom_route(arc(CHICAGO, DENVER, bulge_deg=-0.9), speed=24)

    def respond(request: httpx.Request):
        path = request.url.path
        if "circle(" not in path:
            return httpx.Response(200, json=tomtom_payload(main))
        lat = float(path.split("circle(")[1].split(",")[0])
        return httpx.Response(200, json=tomtom_payload(north if lat > 41 else south))

    tomtom(router).mock(side_effect=respond)
    opts = get_route_options(CHICAGO, DENVER, DEPART, 70_000)
    assert len(opts.routes) == 3
    assert [r.source for r in opts.routes] == ["tomtom", "via", "via"]
    assert any("fewer than 3" in n for n in opts.notes)


def test_picks_fastest_alternatives_that_are_distinct(monkeypatch):
    from trips.services import routing

    def raw(name, hours):
        return routing.RawRoute([(0, 0), (1, 1)], 1000, hours * 3600, 0, [], source=name)

    fast, similar, distinct, distinct2, too_slow = (
        raw("fast", 10), raw("similar", 10.5), raw("distinct", 11), raw("distinct2", 13.5),
        raw("too_slow", 14.5),
    )
    overlaps = {frozenset(("fast", "similar")): 0.81, frozenset(("similar", "distinct")): 0.3}
    monkeypatch.setattr(
        routing, "_overlap",
        lambda a, b: overlaps.get(frozenset((a.source, b.source)), 0.05),
    )
    picked = [fast]
    routing._pick_distinct(picked, [too_slow, distinct2, similar, distinct], max_ratio=1.4)
    # "similar" shares 81% with the fastest route; "too_slow" exceeds 1.4x.
    assert [r.source for r in picked] == ["fast", "distinct", "distinct2"]
