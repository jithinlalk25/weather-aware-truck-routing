"""Small geodesy helpers. Coordinates are (lat, lon) in degrees unless noted."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Iterable, Sequence

EARTH_RADIUS_M = 6_371_008.8
METERS_PER_MILE = 1609.344

LatLon = tuple[float, float]


def haversine_m(a: LatLon, b: LatLon) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def cumulative_m(points: Sequence[LatLon]) -> list[float]:
    out = [0.0]
    for i in range(1, len(points)):
        out.append(out[-1] + haversine_m(points[i - 1], points[i]))
    return out


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def interpolate_along(points: Sequence[LatLon], dist: Sequence[float], d: float) -> LatLon:
    """Point at distance `d` along a polyline whose vertex distances are `dist`."""
    if d <= dist[0]:
        return points[0]
    if d >= dist[-1]:
        return points[-1]
    i = bisect_right(dist, d) - 1
    span = dist[i + 1] - dist[i]
    t = (d - dist[i]) / span if span > 0 else 0.0
    return (lerp(points[i][0], points[i + 1][0], t), lerp(points[i][1], points[i + 1][1], t))


def interp_series(xs: Sequence[float], ys: Sequence[float], x: float) -> float:
    """Piecewise-linear y(x) for increasing xs, clamped at both ends."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect_right(xs, x) - 1
    span = xs[i + 1] - xs[i]
    t = (x - xs[i]) / span if span > 0 else 0.0
    return lerp(ys[i], ys[i + 1], t)


def _to_xy_m(p: LatLon, ref_lat_cos: float) -> tuple[float, float]:
    """Local equirectangular projection (meters); fine for simplification tolerances."""
    return (math.radians(p[1]) * EARTH_RADIUS_M * ref_lat_cos, math.radians(p[0]) * EARTH_RADIUS_M)


def simplify_indices(points: Sequence[LatLon], tolerance_m: float) -> list[int]:
    """Ramer-Douglas-Peucker; returns the indices of kept vertices (always first and last)."""
    n = len(points)
    if n <= 2:
        return list(range(n))
    ref_cos = math.cos(math.radians(sum(p[0] for p in points) / n))
    xy = [_to_xy_m(p, ref_cos) for p in points]
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    tol2 = tolerance_m * tolerance_m
    while stack:
        start, end = stack.pop()
        (x1, y1), (x2, y2) = xy[start], xy[end]
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        best_i, best_d2 = -1, tol2
        for i in range(start + 1, end):
            px, py = xy[i]
            if seg2 == 0:
                d2 = (px - x1) ** 2 + (py - y1) ** 2
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg2))
                d2 = (px - x1 - t * dx) ** 2 + (py - y1 - t * dy) ** 2
            if d2 > best_d2:
                best_i, best_d2 = i, d2
        if best_i >= 0:
            keep[best_i] = True
            stack.append((start, best_i))
            stack.append((best_i, end))
    return [i for i, k in enumerate(keep) if k]


def resample(points: Sequence[LatLon], step_m: float) -> list[LatLon]:
    """Points every `step_m` along the polyline (plus the last vertex)."""
    dist = cumulative_m(points)
    total = dist[-1]
    if total == 0:
        return [points[0]]
    count = max(1, int(total // step_m))
    out = [interpolate_along(points, dist, k * step_m) for k in range(count + 1)]
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


class PointIndex:
    """Grid hash of points for fast 'is anything within r meters' queries."""

    def __init__(self, points: Iterable[LatLon], cell_deg: float = 0.02):
        self.cell = cell_deg
        self.buckets: dict[tuple[int, int], list[LatLon]] = {}
        for p in points:
            self.buckets.setdefault(self._key(p), []).append(p)

    def _key(self, p: LatLon) -> tuple[int, int]:
        return (math.floor(p[0] / self.cell), math.floor(p[1] / self.cell))

    def near(self, p: LatLon, radius_m: float) -> bool:
        ki, kj = self._key(p)
        for di in (0, -1, 1):  # own cell first: most hits land there
            for dj in (0, -1, 1):
                for q in self.buckets.get((ki + di, kj + dj), ()):
                    if haversine_m(p, q) <= radius_m:
                        return True
        return False


def overlap_ratio(a: Sequence[LatLon], b: Sequence[LatLon], tolerance_m: float = 250.0,
                  step_m: float = 1000.0) -> float:
    """Share of route `a`'s length that lies within `tolerance_m` of route `b`."""
    sample_a = resample(a, step_m)
    index_b = PointIndex(resample(b, tolerance_m / 2))
    hits = sum(1 for p in sample_a if index_b.near(p, tolerance_m))
    return hits / len(sample_a)


def offset_point(p: LatLon, bearing_deg: float, distance_m: float) -> LatLon:
    """Destination point from `p` along `bearing_deg` for `distance_m` (great circle)."""
    lat1, lon1 = math.radians(p[0]), math.radians(p[1])
    brg = math.radians(bearing_deg)
    ang = distance_m / EARTH_RADIUS_M
    lat2 = math.asin(
        math.sin(lat1) * math.cos(ang) + math.cos(lat1) * math.sin(ang) * math.cos(brg)
    )
    lon2 = lon1 + math.atan2(math.sin(brg) * math.sin(ang) * math.cos(lat1),
                             math.cos(ang) - math.sin(lat1) * math.sin(lat2))
    return (math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180)


def bearing_deg(a: LatLon, b: LatLon) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


# Rough bounding boxes for the US (contiguous states, Alaska, Hawaii). Used to
# validate inputs and reject forced via-points that land abroad or offshore.
_US_BOXES = (
    (24.3, 49.5, -125.0, -66.8),
    (51.0, 71.6, -170.0, -129.9),
    (18.8, 22.4, -160.5, -154.6),
)


def in_us(p: LatLon) -> bool:
    return any(s <= p[0] <= n and w <= p[1] <= e for s, n, w, e in _US_BOXES)
