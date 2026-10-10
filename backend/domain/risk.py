"""Weather risk classification.

Implements the assessment's risk table and load rules exactly:

    Condition  Low        Moderate    High        Severe      No Travel
    Wind       <25 mph    25-34       35-44       45-54       >=55 mph
    Rain       <0.10 in/h 0.10-0.25   0.25-0.50   0.50-1.00   >1.00
    Snow       <0.5 in/h  0.5-1.0     1.0-2.0     2.0-3.0     >3.0

    Load rules: >=55 mph -> No Travel (any load)
                45-54 mph and load >30,000 lb -> No Travel
                35-44 mph and load >40,000 lb -> Severe

Band edges are treated as half-open float intervals that include their lower
bound (so 34.6 mph is Moderate, 0.25 in/h is High). The table's top bands are
written as ">1.00" and ">3.0", so exactly 1.00 in/h rain and 3.0 in/h snow are
Severe, not No Travel. Load rules only ever escalate a level.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
    RiskLevel.SEVERE: "Severe",
    RiskLevel.NO_TRAVEL: "No Travel",
}

# Lower edges of Moderate, High, Severe. The No Travel edge is listed separately
# because its inclusivity differs between wind (>=) and rain/snow (>).
WIND_EDGES_MPH = (25.0, 35.0, 45.0)
WIND_NO_TRAVEL_MPH = 55.0  # inclusive
RAIN_EDGES_IN_HR = (0.10, 0.25, 0.50)
RAIN_NO_TRAVEL_IN_HR = 1.00  # exclusive
SNOW_EDGES_IN_HR = (0.5, 1.0, 2.0)
SNOW_NO_TRAVEL_IN_HR = 3.0  # exclusive

LOAD_NO_TRAVEL_LB = 30_000  # with Severe-band wind (45-54 mph), load > this -> No Travel
LOAD_SEVERE_LB = 40_000  # with High-band wind (35-44 mph), load > this -> Severe


@dataclass(frozen=True)
class _Scale:
    """One weather variable's banding."""

    edges: tuple[float, float, float]
    no_travel: float
    no_travel_inclusive: bool

    def level(self, value: float) -> RiskLevel:
        if value > self.no_travel or (self.no_travel_inclusive and value == self.no_travel):
            return RiskLevel.NO_TRAVEL
        level = RiskLevel.LOW
        for i, edge in enumerate(self.edges):
            if value >= edge:
                level = RiskLevel(i + 1)
        return level

    def index(self, value: float) -> float:
        """Continuous 0-4 risk index; floor(index) == level(value).

        Linear inside each band so heatmaps can blend smoothly between cells.
        """
        level = self.level(value)
        if level == RiskLevel.NO_TRAVEL:
            return 4.0
        bounds = (0.0, *self.edges, self.no_travel)
        lo, hi = bounds[level], bounds[level + 1]
        frac = (value - lo) / (hi - lo) if hi > lo else 0.0
        return level + min(max(frac, 0.0), 0.999)


WIND = _Scale(WIND_EDGES_MPH, WIND_NO_TRAVEL_MPH, no_travel_inclusive=True)
RAIN = _Scale(RAIN_EDGES_IN_HR, RAIN_NO_TRAVEL_IN_HR, no_travel_inclusive=False)
SNOW = _Scale(SNOW_EDGES_IN_HR, SNOW_NO_TRAVEL_IN_HR, no_travel_inclusive=False)


def wind_level(mph: float) -> RiskLevel:
    return WIND.level(mph)


def rain_level(in_hr: float) -> RiskLevel:
    return RAIN.level(in_hr)


def snow_level(in_hr: float) -> RiskLevel:
    return SNOW.level(in_hr)


def load_escalation(wind_mph: float, load_lb: float) -> RiskLevel | None:
    """Minimum level imposed by the load rules, or None if no rule fires."""
    if wind_mph >= WIND_NO_TRAVEL_MPH:
        return RiskLevel.NO_TRAVEL
    if wind_mph >= WIND_EDGES_MPH[2] and load_lb > LOAD_NO_TRAVEL_LB:
        return RiskLevel.NO_TRAVEL
    if wind_mph >= WIND_EDGES_MPH[1] and load_lb > LOAD_SEVERE_LB:
        return RiskLevel.SEVERE
    return None


@dataclass(frozen=True)
class Assessment:
    level: RiskLevel
    wind: RiskLevel
    rain: RiskLevel
    snow: RiskLevel
    load_escalated: bool
    factors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def factor_text(self) -> str:
        return "; ".join(self.factors)


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float,
           wind_label: str = "wind") -> Assessment:
    """Classify one checkpoint: worst of wind/rain/snow, then load escalation.

    `wind_mph` is whichever wind value the caller classifies on (sustained or
    gust); `wind_label` names it in the explanation text.
    """
    w, r, s = WIND.level(wind_mph), RAIN.level(rain_in_hr), SNOW.level(snow_in_hr)
    base = max(w, r, s)
    escalated = load_escalation(wind_mph, load_lb)
    level = max(base, escalated) if escalated is not None else base
    load_escalated = escalated is not None and escalated > base

    factors: list[str] = []
    if load_escalated:
        factors.append(
            f"{wind_mph:.0f} mph {wind_label} + {load_lb:,.0f} lb load → {level.label}"
        )
    elif level > RiskLevel.LOW:
        if w == level:
            factors.append(f"{wind_label} {wind_mph:.0f} mph")
        if r == level:
            factors.append(f"rain {rain_in_hr:.2f} in/hr")
        if s == level:
            factors.append(f"snow {snow_in_hr:.2f} in/hr")
    return Assessment(level, w, r, s, load_escalated, tuple(factors))


def risk_index(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> float:
    """Continuous 0-4 index for heatmaps, consistent with `assess` (floor == level)."""
    idx = max(WIND.index(wind_mph), RAIN.index(rain_in_hr), SNOW.index(snow_in_hr))
    escalated = load_escalation(wind_mph, load_lb)
    if escalated is not None:
        idx = max(idx, float(escalated))
    return 4.0 if idx >= 4.0 else math.floor(idx * 1000) / 1000
