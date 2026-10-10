"""Regular lat/lon lattice that weather is fetched on.

Snapping to a shared lattice lets checkpoints from overlapping routes, the
heatmap corridor and later plans reuse the same forecast cells (and cache
entries). The step adapts so a plan never needs more than a fixed number of
weather locations: Open-Meteo bills every location as one API call.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from .geo import LatLon, haversine_m, resample

# Multiples of 0.1 deg, so every coarser lattice point is also a 0.1 deg point and
# heatmap cells reuse cached checkpoint forecasts.
STEPS_DEG = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0)
KM_PER_DEG = 111.2


@dataclass(frozen=True, order=True)
class Node:
    step: float
    i: int  # latitude index
    j: int  # longitude index

    @property
    def lat(self) -> float:
        return round(self.i * self.step, 4)

    @property
    def lon(self) -> float:
        return round(self.j * self.step, 4)


def snap(p: LatLon, step: float) -> Node:
    return Node(step, round(p[0] / step), round(p[1] / step))


def snap_all(points: Iterable[LatLon], step: float) -> set[Node]:
    return {snap(p, step) for p in points}


def smallest_step(count_nodes: Callable[[float], int], cap: int,
                  steps: Sequence[float] = STEPS_DEG) -> float:
    """Finest lattice step whose node count stays within `cap`."""
    for step in steps:
        if count_nodes(step) <= cap:
            return step
    return steps[-1]


def corridor_nodes(routes: Sequence[Sequence[LatLon]], step: float,
                   radius_km: float = 50.0) -> set[Node]:
    """Lattice nodes within `radius_km` of any route (at least one cell wide)."""
    radius_m = max(radius_km, step * KM_PER_DEG * 0.75) * 1000
    sample_m = step * KM_PER_DEG * 1000 / 2
    reach_i = math.ceil(radius_m / (step * KM_PER_DEG * 1000)) + 1
    nodes: set[Node] = set()
    for route in routes:
        for p in resample(route, sample_m):
            center = snap(p, step)
            reach_j = math.ceil(reach_i / max(math.cos(math.radians(p[0])), 0.2))
            for di in range(-reach_i, reach_i + 1):
                for dj in range(-reach_j, reach_j + 1):
                    node = Node(step, center.i + di, center.j + dj)
                    if node in nodes:
                        continue
                    if haversine_m(p, (node.lat, node.lon)) <= radius_m:
                        nodes.add(node)
    return nodes


def fill_holes(nodes: set[Node]) -> set[Node]:
    """Add lattice cells fully enclosed by the corridor (e.g. between two routes).

    Flood-fills the empty cells reachable from outside the bounding box; any
    empty cell not reached is a hole and becomes part of the corridor.
    """
    if not nodes:
        return nodes
    step = next(iter(nodes)).step
    taken = {(n.i, n.j) for n in nodes}
    i0, i1 = min(i for i, _ in taken) - 1, max(i for i, _ in taken) + 1
    j0, j1 = min(j for _, j in taken) - 1, max(j for _, j in taken) + 1
    outside = {(i0, j0)}
    stack = [(i0, j0)]
    while stack:
        i, j = stack.pop()
        for ni, nj in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if i0 <= ni <= i1 and j0 <= nj <= j1 and (ni, nj) not in taken \
                    and (ni, nj) not in outside:
                outside.add((ni, nj))
                stack.append((ni, nj))
    holes = {
        Node(step, i, j)
        for i in range(i0, i1 + 1)
        for j in range(j0, j1 + 1)
        if (i, j) not in taken and (i, j) not in outside
    }
    return nodes | holes
