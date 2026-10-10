"""Synthetic TomTom / Open-Meteo responses for planner and API tests."""

import math
import time
from urllib.parse import parse_qs, urlparse

import httpx

from domain.geo import cumulative_m

CHICAGO = (41.8781, -87.6298)
DENVER = (39.7392, -104.9903)
SPEED_MPS = 25.0  # ~56 mph


def arc(a, b, bulge_deg=0.0, n=600):
    """Points from a to b, bowed north (+) or south (-) by `bulge_deg` at the midpoint."""
    pts = []
    for k in range(n + 1):
        t = k / n
        lat = a[0] + (b[0] - a[0]) * t + bulge_deg * math.sin(math.pi * t)
        lon = a[1] + (b[1] - a[1]) * t
        pts.append((lat, lon))
    return pts


def tomtom_route(points, speed=SPEED_MPS, road_factor=1.05):
    dist = [d * road_factor for d in cumulative_m(points)]
    progress = [
        {"pointIndex": i, "distanceInMeters": dist[i], "travelTimeInSeconds": dist[i] / speed}
        for i in range(0, len(points), 50)
    ] + [{"pointIndex": len(points) - 1, "distanceInMeters": dist[-1],
          "travelTimeInSeconds": dist[-1] / speed}]
    return {
        "summary": {"lengthInMeters": dist[-1], "travelTimeInSeconds": dist[-1] / speed,
                    "trafficDelayInSeconds": 0},
        "legs": [{"points": [{"latitude": p[0], "longitude": p[1]} for p in points]}],
        "progress": progress,
    }


def tomtom_payload(*routes):
    return {"routes": list(routes)}


def open_meteo_responder(wind_fn=lambda lat, lon: 10.0, rain_fn=lambda lat, lon: 0.0,
                         snow_fn=lambda lat, lon: 0.0):
    """httpx side effect: hourly series whose values depend only on location."""
    start = int(time.time() // 86400 * 86400)
    hours = 14 * 24

    def handler(request: httpx.Request) -> httpx.Response:
        q = parse_qs(urlparse(str(request.url)).query)
        lats = [float(x) for x in q["latitude"][0].split(",")]
        lons = [float(x) for x in q["longitude"][0].split(",")]
        items = []
        for lat, lon in zip(lats, lons, strict=True):
            w, r, s = wind_fn(lat, lon), rain_fn(lat, lon), snow_fn(lat, lon)
            items.append({"hourly": {
                "time": [start + h * 3600 for h in range(hours)],
                "wind_speed_10m": [w] * hours,
                "wind_gusts_10m": [w * 1.4] * hours,
                "rain": [r] * hours,
                "showers": [0.0] * hours,
                "snowfall": [s] * hours,
                "temperature_2m": [50.0] * hours,
                "weather_code": [0] * hours,
            }})
        return httpx.Response(200, json=items if len(items) > 1 else items[0])

    return handler
