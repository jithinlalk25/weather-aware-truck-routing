"""TomTom truck routing and selection of three distinct route options."""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from django.conf import settings
from django.core.cache import cache

from domain.geo import (
    LatLon,
    PointIndex,
    bearing_deg,
    haversine_m,
    offset_point,
    resample,
)
from domain.profile import ProgressMark

from .errors import NoRouteFound, NotConfigured, UpstreamError, UpstreamRateLimited
from .http import client
from .timezones import is_us_location

log = logging.getLogger(__name__)

TOMTOM_ROUTE_URL = "https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
LB_TO_KG = 0.45359237
TARGET_ROUTES = 3
MAX_TIME_RATIO = 1.4  # alternatives may be at most 40% slower than the fastest
MAX_TIME_RATIO_FORCED = 1.6  # forced (via-point) alternatives get a little more slack
DISTINCT_MAX_OVERLAP = 0.7  # an option must differ from the others by >= 30% of its length
TOMTOM_ALTERNATIVES = 3  # 5 doubles latency (~11 s) without adding useful options
VIA_RADIUS_M = 30_000
ROUTE_CACHE_S = 30 * 60


@dataclass
class RawRoute:
    points: list[LatLon]
    length_m: float
    drive_s: float
    traffic_delay_s: float
    progress: list[ProgressMark]
    source: str = "tomtom"  # "tomtom" or "via" (forced alternative)
    _shape: _Shape | None = field(default=None, repr=False)

    @property
    def shape(self) -> _Shape:
        if self._shape is None:
            self._shape = _Shape(self.points)
        return self._shape


class _Shape:
    """Pre-sampled geometry for fast overlap checks between routes."""

    TOLERANCE_M = 250.0

    def __init__(self, points: list[LatLon]):
        self.samples = resample(points, 1000.0)
        self.index = PointIndex(resample(points, self.TOLERANCE_M / 2))

    def overlap_with(self, other: _Shape) -> float:
        hits = sum(1 for p in self.samples if other.index.near(p, self.TOLERANCE_M))
        return hits / len(self.samples)


def _overlap(a: RawRoute, b: RawRoute) -> float:
    return max(a.shape.overlap_with(b.shape), b.shape.overlap_with(a.shape))


def _fmt(p: LatLon) -> str:
    return f"{p[0]:.6f},{p[1]:.6f}"


def _parse(payload: dict, source: str) -> list[RawRoute]:
    routes = []
    for r in payload.get("routes", []):
        points = [(pt["latitude"], pt["longitude"]) for leg in r["legs"] for pt in leg["points"]]
        summary = r["summary"]
        progress = [
            ProgressMark(int(m["pointIndex"]), float(m.get("distanceInMeters", 0.0)),
                         float(m.get("travelTimeInSeconds", 0.0)))
            for m in r.get("progress", [])
        ]
        routes.append(RawRoute(
            points=points,
            length_m=float(summary["lengthInMeters"]),
            drive_s=float(summary["travelTimeInSeconds"]),
            traffic_delay_s=float(summary.get("trafficDelayInSeconds", 0)),
            progress=progress,
            source=source,
        ))
    return routes


def _request(origin: LatLon, dest: LatLon, depart: datetime, gvw_lb: float,
             via: LatLon | None = None,
             alternatives: int = TOMTOM_ALTERNATIVES) -> list[RawRoute]:
    if not settings.TOMTOM_API_KEY:
        raise NotConfigured("TOMTOM_API_KEY is not set.")
    stops = [_fmt(origin)]
    if via is not None:
        stops.append(f"circle({_fmt(via)},{VIA_RADIUS_M})")
    stops.append(_fmt(dest))
    params: list[tuple[str, str | int]] = [
        ("key", settings.TOMTOM_API_KEY),
        ("travelMode", "truck"),
        ("vehicleCommercial", "true"),
        ("vehicleWeight", round(gvw_lb * LB_TO_KG)),
        ("departAt", depart.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
        ("traffic", "true"),
        ("routeType", "fastest"),
        ("routeRepresentation", "polyline"),
        ("extendedRouteRepresentation", "distance"),
        ("extendedRouteRepresentation", "travelTime"),
        ("maxAlternatives", alternatives if via is None else 0),
    ]
    url = TOMTOM_ROUTE_URL.format(locations=":".join(stops))
    try:
        with client(timeout=25) as http:
            resp = http.get(url, params=params)
    except httpx.HTTPError as exc:
        raise UpstreamError(f"TomTom routing request failed: {exc}") from exc
    if resp.status_code == 429:
        raise UpstreamRateLimited("TomTom rate limit reached. Please retry shortly.")
    if resp.status_code in (400, 404):
        detail = _error_detail(resp)
        if via is not None:
            return []  # a forced via-point that can't be routed is simply skipped
        raise NoRouteFound(detail or NoRouteFound.default_detail)
    if resp.status_code in (401, 403):
        raise UpstreamError("TomTom rejected the API key.")
    if resp.status_code >= 400:
        raise UpstreamError(f"TomTom routing error ({resp.status_code}).")
    return _parse(resp.json(), "via" if via is not None else "tomtom")


def _error_detail(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("detailedError") or resp.json().get("error") or {}
        return err.get("message", "") if isinstance(err, dict) else str(err)
    except ValueError:
        return ""


def _pick_distinct(picked: list[RawRoute], pool: list[RawRoute], max_ratio: float) -> None:
    """Add the fastest routes from `pool` that are distinct from everything picked.

    Distinct = sharing at most DISTINCT_MAX_OVERLAP of its length with any picked
    route; routes slower than `max_ratio` x the fastest are not offered.
    """
    fastest = min(r.drive_s for r in picked)
    for cand in sorted(pool, key=lambda r: r.drive_s):
        if len(picked) >= TARGET_ROUTES:
            return
        if cand.drive_s > fastest * max_ratio:
            return
        if all(_overlap(cand, p) <= DISTINCT_MAX_OVERLAP for p in picked):
            picked.append(cand)


def _via_candidates(main: RawRoute, origin: LatLon, dest: LatLon) -> list[LatLon]:
    """Points pushed off both sides of the main route's midpoint."""
    pts = main.points
    mid, before, after = pts[len(pts) // 2], pts[int(len(pts) * 0.45)], pts[int(len(pts) * 0.55)]
    heading = bearing_deg(before, after)
    straight = haversine_m(origin, dest)
    offset = min(max(0.15 * straight, 40_000), 150_000)
    out = []
    for side in (90, -90):
        p = offset_point(mid, heading + side, offset)
        if is_us_location(*p):
            out.append(p)
    return out


@dataclass
class RouteOptions:
    routes: list[RawRoute]
    notes: list[str]


def get_route_options(origin: LatLon, dest: LatLon, depart: datetime,
                      gvw_lb: float) -> RouteOptions:
    """Up to three distinct truck routes, fastest first."""
    key = "tt:" + hashlib.sha1(
        f"{_fmt(origin)}|{_fmt(dest)}|{int(depart.timestamp() // 300)}|{round(gvw_lb)}".encode()
    ).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached

    candidates = _request(origin, dest, depart, gvw_lb)
    if not candidates:
        raise NoRouteFound()
    candidates.sort(key=lambda r: r.drive_s)
    picked = [candidates[0]]
    _pick_distinct(picked, candidates[1:], MAX_TIME_RATIO)

    notes = []
    if len(picked) < TARGET_ROUTES:
        vias = _via_candidates(picked[0], origin, dest)
        with ThreadPoolExecutor(max_workers=2) as pool:
            forced = [r for batch in pool.map(
                lambda v: _request(origin, dest, depart, gvw_lb, via=v), vias) for r in batch]
        before = len(picked)
        _pick_distinct(picked, forced, MAX_TIME_RATIO_FORCED)
        if len(picked) > before:
            notes.append(
                "TomTom returned fewer than 3 distinct routes, so extra options were generated "
                "by routing through a point off each side of the main route."
            )
    if len(picked) < TARGET_ROUTES:
        notes.append(
            f"Only {len(picked)} distinct route(s) exist within {MAX_TIME_RATIO_FORCED:.1f}x "
            "of the fastest travel time for this trip."
        )

    result = RouteOptions(picked, notes)
    for r in result.routes:
        r._shape = None  # keep the cached object small
    cache.set(key, result, ROUTE_CACHE_S)
    return result
