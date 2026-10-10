"""Hourly forecast series and picking the right value for an arrival time.

Open-Meteo hourly semantics: `wind_speed_10m` is the instantaneous value at the
timestamp, while `rain`, `showers`, `snowfall` and `wind_gusts_10m` describe the
preceding hour (H-1, H]. For an ETA t we therefore use the hour ending at or
after t (ceil) for those, and interpolate only the sustained wind.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

HOUR_S = 3600


@dataclass(frozen=True)
class HourlySeries:
    start_epoch: int  # timestamp of index 0, on the hour (UTC)
    wind_mph: list[float | None]
    gust_mph: list[float | None]
    rain_in: list[float | None]  # rain + showers over the preceding hour
    snow_in: list[float | None]  # snowfall depth over the preceding hour
    temp_f: list[float | None]
    weather_code: list[int | None]

    @property
    def end_epoch(self) -> int:
        return self.start_epoch + (len(self.wind_mph) - 1) * HOUR_S


@dataclass(frozen=True)
class WeatherSample:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float
    temp_f: float | None
    weather_code: int | None


def _at(values: list, i: int):
    return values[i] if 0 <= i < len(values) else None


def sample_at(series: HourlySeries, epoch_s: float) -> WeatherSample | None:
    """Weather the truck meets at `epoch_s`, or None when the forecast has no data."""
    offset = (epoch_s - series.start_epoch) / HOUR_S
    hi = math.ceil(offset)
    lo = math.floor(offset)

    w0, w1 = _at(series.wind_mph, lo), _at(series.wind_mph, hi)
    gust = _at(series.gust_mph, hi)
    rain = _at(series.rain_in, hi)
    snow = _at(series.snow_in, hi)
    if None in (w0, w1, gust, rain, snow):
        return None
    wind = w0 + (w1 - w0) * (offset - lo)
    return WeatherSample(
        wind_mph=wind,
        gust_mph=max(gust, wind),
        rain_in_hr=rain,
        snow_in_hr=snow,
        temp_f=_at(series.temp_f, hi),
        weather_code=_at(series.weather_code, hi),
    )


def forecast_confidence(lead_hours: float) -> str:
    """Rough skill bands: HRRR covers ~48 h, GFS turns 3-hourly after ~120 h."""
    if lead_hours < 48:
        return "high"
    if lead_hours < 120:
        return "medium"
    return "low"
