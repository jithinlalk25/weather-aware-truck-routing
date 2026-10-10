"""Road distance and drive time at every vertex of a route polyline."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .geo import LatLon, cumulative_m, interp_series, lerp


@dataclass(frozen=True)
class ProgressMark:
    """One entry of a routing provider's cumulative progress (TomTom `progress`)."""

    point_index: int
    distance_m: float
    drive_s: float


@dataclass(frozen=True)
class RouteProfile:
    points: list[LatLon]
    dist_m: list[float]  # cumulative road distance at each vertex
    drive_s: list[float]  # cumulative drive time at each vertex

    @property
    def total_m(self) -> float:
        return self.dist_m[-1]

    @property
    def total_drive_s(self) -> float:
        return self.drive_s[-1]

    @classmethod
    def build(cls, points: Sequence[LatLon], total_m: float, total_drive_s: float,
              progress: Sequence[ProgressMark] = ()) -> RouteProfile:
        """Spread the provider's road distance/time over every vertex.

        Progress marks are sparse; between two marks we interpolate by the
        straight-line (haversine) share of that stretch, as TomTom recommends.
        Without marks, distance and time are spread proportionally to haversine.
        """
        pts = list(points)
        n = len(pts)
        flat = cumulative_m(pts)
        anchors = {0: (0.0, 0.0), n - 1: (total_m, total_drive_s)}
        for mark in progress:
            if 0 <= mark.point_index < n:
                anchors[mark.point_index] = (mark.distance_m, mark.drive_s)
        idx = sorted(anchors)

        dist = [0.0] * n
        time = [0.0] * n
        for a, b in zip(idx, idx[1:], strict=False):
            (da, ta), (db, tb) = anchors[a], anchors[b]
            span = flat[b] - flat[a]
            for i in range(a, b + 1):
                t = (flat[i] - flat[a]) / span if span > 0 else (0.0 if i == a else 1.0)
                dist[i] = lerp(da, db, t)
                time[i] = lerp(ta, tb, t)
        # Guard against provider rounding producing tiny reversals.
        for i in range(1, n):
            dist[i] = max(dist[i], dist[i - 1])
            time[i] = max(time[i], time[i - 1])
        return cls(pts, dist, time)

    def point_at(self, d: float) -> LatLon:
        lat = interp_series(self.dist_m, [p[0] for p in self.points], d)
        lon = interp_series(self.dist_m, [p[1] for p in self.points], d)
        return (lat, lon)

    def drive_s_at(self, d: float) -> float:
        return interp_series(self.dist_m, self.drive_s, d)

    def dist_at_drive_s(self, t: float) -> float:
        return interp_series(self.drive_s, self.dist_m, t)
