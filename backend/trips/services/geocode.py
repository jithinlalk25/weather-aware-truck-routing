"""US place search (typeahead) via TomTom Fuzzy Search."""

from __future__ import annotations

from urllib.parse import quote

import httpx
from django.conf import settings
from django.core.cache import cache

from .errors import NotConfigured, UpstreamError, UpstreamRateLimited
from .http import client
from .timezones import is_us_location, tz_at

TOMTOM_SEARCH_URL = "https://api.tomtom.com/search/2/search/{query}.json"
CACHE_S = 24 * 3600


def search_places(query: str, limit: int = 5) -> list[dict]:
    q = " ".join(query.split())[:120]
    key = f"geo:{q.lower()}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    if not settings.TOMTOM_API_KEY:
        raise NotConfigured("TOMTOM_API_KEY is not set.")

    params = {
        "key": settings.TOMTOM_API_KEY,
        "typeahead": "true",
        "limit": limit,
        "countrySet": "US",
        "idxSet": "Geo,PAD,Addr,Str",
        "language": "en-US",
    }
    try:
        with client(timeout=10) as http:
            resp = http.get(TOMTOM_SEARCH_URL.format(query=quote(q, safe="")), params=params)
    except httpx.HTTPError as exc:
        raise UpstreamError(f"Place search failed: {exc}") from exc
    if resp.status_code == 429:
        raise UpstreamRateLimited("Place search rate limit reached.")
    if resp.status_code >= 400:
        raise UpstreamError(f"Place search error ({resp.status_code}).")

    places = []
    seen = set()
    for r in resp.json().get("results", []):
        pos = r.get("position") or {}
        lat, lon = pos.get("lat"), pos.get("lon")
        label = (r.get("address") or {}).get("freeformAddress")
        if lat is None or lon is None or not label or label in seen or not is_us_location(lat, lon):
            continue
        seen.add(label)
        places.append({"label": label, "lat": lat, "lon": lon, "tz": tz_at(lat, lon)})
    cache.set(key, places, CACHE_S)
    return places
