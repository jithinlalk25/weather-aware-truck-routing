"""Corridor weather grid for the 0-48 h heatmap slider.

Returns one value per lattice node per hour (T+0..T+48 from departure) for the
combined risk index and the raw variables. Values are packed hour-major so the
frontend can turn each hour into a small image without reshaping.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from domain.lattice import KM_PER_DEG, STEPS_DEG, corridor_nodes, fill_holes
from domain.risk import risk_index
from domain.weather import sample_at

from ..models import TripPlan
from . import weather

HOURS = 48
NODE_CAP = 120  # the frontend smooths cells, so ~120 locations look continuous
CORRIDOR_KM = 50.0


def _estimate_nodes(route_km: float, step: float, mean_lat: float) -> float:
    cell_km2 = (step * KM_PER_DEG) ** 2 * math.cos(math.radians(mean_lat))
    return route_km * 2 * CORRIDOR_KM / cell_km2


def _choose_corridor(routes: list[list[list[float]]]):
    route_km = sum(r[-1][2] for r in routes) / 1000  # path entries carry road distance
    shapes = [[(lat, lon) for lon, lat, *_ in r] for r in routes]
    mean_lat = sum(p[0] for s in shapes for p in s) / sum(len(s) for s in shapes)
    nodes = set()
    for step in STEPS_DEG:
        if _estimate_nodes(route_km, step, mean_lat) > NODE_CAP * 2:
            continue  # cheap pre-filter; overlapping routes make the estimate high
        nodes = fill_holes(corridor_nodes(shapes, step, CORRIDOR_KM))
        if len(nodes) <= NODE_CAP:
            return step, nodes
    return STEPS_DEG[-1], nodes or fill_holes(corridor_nodes(shapes, STEPS_DEG[-1], CORRIDOR_KM))


def _r(x: float | None, nd: int) -> float | None:
    return None if x is None else round(x, nd)


def build_heatmap(plan: TripPlan) -> dict:
    routes = [r.path for r in plan.routes.all()]
    step, nodes = _choose_corridor(routes)
    nodes = sorted(nodes)
    series = weather.get_series(nodes).series

    i0 = min(n.i for n in nodes)
    j0 = min(n.j for n in nodes)
    cells = [v for n in nodes for v in (n.j - j0, n.i - i0)]  # (x, y) from south-west corner
    width = max(n.j for n in nodes) - j0 + 1
    height = max(n.i for n in nodes) - i0 + 1

    start = plan.departure_at.timestamp()
    gust_mode = plan.wind_mode == TripPlan.WindMode.GUST
    names = ("risk", "wind", "gust", "rain", "snow")
    layers: dict[str, list[float | None]] = {k: [] for k in names}
    for h in range(HOURS + 1):
        t = start + h * 3600
        for n in nodes:
            ws = sample_at(series[n], t) if n in series else None
            if ws is None:
                for values in layers.values():
                    values.append(None)
                continue
            wind_for_rules = ws.gust_mph if gust_mode else ws.wind_mph
            layers["risk"].append(
                round(risk_index(wind_for_rules, ws.rain_in_hr, ws.snow_in_hr, plan.load_lb), 2)
            )
            layers["wind"].append(_r(ws.wind_mph, 1))
            layers["gust"].append(_r(ws.gust_mph, 1))
            layers["rain"].append(_r(ws.rain_in_hr, 3))
            layers["snow"].append(_r(ws.snow_in_hr, 3))

    return {
        "step_deg": step,
        "origin": {"lat": i0 * step, "lon": j0 * step},  # center of cell (0, 0)
        "width": width,
        "height": height,
        "cells": cells,
        "start": round(start),
        "hours": HOURS + 1,
        "layers": layers,
        "generated_at": datetime.now(UTC).isoformat(),
    }
