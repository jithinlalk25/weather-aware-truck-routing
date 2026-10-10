from functools import lru_cache

from timezonefinder import TimezoneFinder

from domain.geo import in_us

# IANA zones whose territory is in the United States (zone.tab, country code US).
# Points inside the rough US bounding boxes that resolve to any other zone are in
# Canada, Mexico or open water.
US_TIMEZONES = frozenset({
    "America/New_York", "America/Detroit", "America/Kentucky/Louisville",
    "America/Kentucky/Monticello", "America/Indiana/Indianapolis", "America/Indiana/Vincennes",
    "America/Indiana/Winamac", "America/Indiana/Marengo", "America/Indiana/Petersburg",
    "America/Indiana/Vevay", "America/Chicago", "America/Indiana/Tell_City",
    "America/Indiana/Knox", "America/Menominee", "America/North_Dakota/Center",
    "America/North_Dakota/New_Salem", "America/North_Dakota/Beulah", "America/Denver",
    "America/Boise", "America/Phoenix", "America/Los_Angeles", "America/Anchorage",
    "America/Juneau", "America/Sitka", "America/Metlakatla", "America/Yakutat",
    "America/Nome", "America/Adak", "Pacific/Honolulu",
})


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    return TimezoneFinder()


def tz_at(lat: float, lon: float) -> str:
    return _finder().timezone_at(lat=lat, lng=lon) or "UTC"


def is_us_location(lat: float, lon: float) -> bool:
    return in_us((lat, lon)) and tz_at(lat, lon) in US_TIMEZONES
