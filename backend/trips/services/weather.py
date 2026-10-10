"""Open-Meteo hourly forecasts for lattice nodes, cached and rate-budgeted.

Open-Meteo bills every location in a request as one call (free tier: 600/min,
5,000/h, 10,000/day). We request at most 7 variables and 14 days so each
location costs exactly one call, cache each node's series for an hour, and keep
a shared per-minute budget so a burst of plans fails fast with a clear message
instead of tripping the provider's limit.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx
from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import APIException

from domain.lattice import Node
from domain.weather import HourlySeries

from .errors import UpstreamError, UpstreamRateLimited, WeatherUnavailable
from .http import client

log = logging.getLogger(__name__)

FREE_URL = "https://api.open-meteo.com/v1/forecast"
COMMERCIAL_URL = "https://customer-api.open-meteo.com/v1/forecast"
HOURLY_VARS = (
    "wind_speed_10m",
    "wind_gusts_10m",
    "rain",
    "showers",
    "snowfall",
    "temperature_2m",
    "weather_code",
)
FORECAST_DAYS = 14
BATCH_SIZE = 20  # ~300 KB per response; big responses are likelier to stall mid-transfer
WORKERS = 4
CACHE_S = 3600
MINUTE_BUDGET = 560  # stay under the free tier's 600 calls/minute
RETRY_DELAYS_S = (1.0, 2.0, 4.0)  # Open-Meteo occasionally answers 503 "overloaded"
RETRY_BUDGET_S = 25.0  # stop retrying a batch after this long, so requests stay bounded
MAX_UNAVAILABLE_SHARE = 0.25  # tolerate a failed batch rather than failing the plan


def _cache_key(node: Node) -> str:
    # Keyed by coordinates (not lattice step) so coarser heatmap lattices reuse
    # checkpoint forecasts wherever the grids coincide.
    return f"om:{node.lat:.4f}:{node.lon:.4f}"


def _take_budget(calls: int) -> None:
    if settings.OPEN_METEO_API_KEY:
        return
    bucket = f"om-budget:{int(time.time() // 60)}"
    cache.add(bucket, 0, 120)
    try:
        used = cache.incr(bucket, calls)
    except ValueError:  # the key expired between add() and incr()
        cache.set(bucket, calls, 120)
        used = calls
    if used > MINUTE_BUDGET:
        cache.decr(bucket, calls)
        raise UpstreamRateLimited(
            "The free weather API's per-minute limit is in use. Please retry in a minute."
        )


def _merge_rain(rain: list, showers: list | None) -> list[float | None]:
    showers = showers or [None] * len(rain)
    return [None if r is None else r + (s or 0.0) for r, s in zip(rain, showers, strict=True)]


def _parse(item: dict) -> HourlySeries:
    h = item["hourly"]
    return HourlySeries(
        start_epoch=int(h["time"][0]),
        wind_mph=h["wind_speed_10m"],
        gust_mph=h["wind_gusts_10m"],
        rain_in=_merge_rain(h["rain"], h.get("showers")),
        snow_in=h["snowfall"],
        temp_f=h.get("temperature_2m") or [None] * len(h["time"]),
        weather_code=h.get("weather_code") or [None] * len(h["time"]),
    )


def _fetch_batch(nodes: list[Node]) -> dict[Node, HourlySeries]:
    params = {
        "latitude": ",".join(f"{n.lat:g}" for n in nodes),
        "longitude": ",".join(f"{n.lon:g}" for n in nodes),
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "temperature_unit": "fahrenheit",
        "timezone": "GMT",
        "timeformat": "unixtime",
        "forecast_days": FORECAST_DAYS,
    }
    url = FREE_URL
    if settings.OPEN_METEO_API_KEY:
        url, params["apikey"] = COMMERCIAL_URL, settings.OPEN_METEO_API_KEY

    deadline = time.monotonic() + RETRY_BUDGET_S
    for attempt, delay in enumerate((*RETRY_DELAYS_S, None)):
        try:
            with client(timeout=10) as http:
                resp = http.get(url, params=params)
            problem = f"HTTP {resp.status_code}" if resp.status_code >= 500 else None
            if resp.status_code < 400:
                data = resp.json()
        except httpx.HTTPError as exc:
            problem = type(exc).__name__
        except ValueError:  # body cut off mid-transfer
            problem = "truncated response"
        if problem is None:
            break
        if delay is None or time.monotonic() + delay > deadline:
            raise WeatherUnavailable()
        log.warning("Open-Meteo %s (attempt %d); retrying", problem, attempt + 1)
        time.sleep(delay)

    if resp.status_code == 429:
        raise UpstreamRateLimited(
            "The weather provider's rate limit was reached. Please retry in a minute."
        )
    if resp.status_code >= 400:
        try:
            reason = resp.json().get("reason", "")
        except ValueError:
            reason = ""
        raise UpstreamError(f"Weather provider error ({resp.status_code}). {reason}".strip())
    items = data if isinstance(data, list) else [data]
    return {node: _parse(item) for node, item in zip(nodes, items, strict=True)}


@dataclass
class SeriesResult:
    series: dict[Node, HourlySeries]
    unavailable: set[Node] = field(default_factory=set)  # provider failed for these


def get_series(nodes: Iterable[Node]) -> SeriesResult:
    """Hourly series for every node, from cache where possible.

    If a few batches still fail after retries, the rest of the plan is usable:
    those nodes are reported as unavailable (their checkpoints show "No data").
    Only when more than MAX_UNAVAILABLE_SHARE of the nodes are missing does the
    request fail.
    """
    nodes = sorted(set(nodes))
    keys = {_cache_key(n): n for n in nodes}
    found = cache.get_many(list(keys))
    result = SeriesResult({keys[k]: v for k, v in found.items()})
    missing = [n for n in nodes if n not in result.series]
    if not missing:
        return result

    _take_budget(len(missing))
    batches = [missing[i:i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
    log.info("Open-Meteo: fetching %d nodes in %d batches", len(missing), len(batches))
    errors: list[APIException] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_fetch_batch, batch): batch for batch in batches}
        for future, batch in futures.items():
            try:
                fetched = future.result()
            except UpstreamRateLimited:
                raise
            except (UpstreamError, WeatherUnavailable) as exc:
                errors.append(exc)
                result.unavailable.update(batch)
                continue
            result.series.update(fetched)
            cache.set_many({_cache_key(n): s for n, s in fetched.items()}, CACHE_S)

    if errors and len(result.unavailable) > MAX_UNAVAILABLE_SHARE * len(nodes):
        raise errors[0]
    if errors:
        log.warning("Open-Meteo: %d of %d nodes unavailable", len(result.unavailable), len(nodes))
    return result
