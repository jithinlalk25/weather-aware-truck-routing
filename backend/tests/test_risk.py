import pytest

from domain.risk import (
    RiskLevel as L,
)
from domain.risk import (
    assess,
    load_escalation,
    rain_level,
    risk_index,
    snow_level,
    wind_level,
)


@pytest.mark.parametrize(
    ("mph", "expected"),
    [
        (0, L.LOW), (24.99, L.LOW),
        (25, L.MODERATE), (34.6, L.MODERATE), (34.99, L.MODERATE),
        (35, L.HIGH), (44.99, L.HIGH),
        (45, L.SEVERE), (54.99, L.SEVERE),
        (55, L.NO_TRAVEL), (80, L.NO_TRAVEL),
    ],
)
def test_wind_bands(mph, expected):
    assert wind_level(mph) == expected


@pytest.mark.parametrize(
    ("in_hr", "expected"),
    [
        (0, L.LOW), (0.0999, L.LOW),
        (0.10, L.MODERATE), (0.2499, L.MODERATE),
        (0.25, L.HIGH), (0.4999, L.HIGH),
        (0.50, L.SEVERE), (1.00, L.SEVERE),
        (1.0001, L.NO_TRAVEL),
    ],
)
def test_rain_bands(in_hr, expected):
    assert rain_level(in_hr) == expected


@pytest.mark.parametrize(
    ("in_hr", "expected"),
    [
        (0, L.LOW), (0.4999, L.LOW),
        (0.5, L.MODERATE), (0.9999, L.MODERATE),
        (1.0, L.HIGH), (1.9999, L.HIGH),
        (2.0, L.SEVERE), (3.0, L.SEVERE),
        (3.0001, L.NO_TRAVEL),
    ],
)
def test_snow_bands(in_hr, expected):
    assert snow_level(in_hr) == expected


@pytest.mark.parametrize(
    ("mph", "load", "expected"),
    [
        (55, 0, L.NO_TRAVEL),                 # >=55 mph: any load
        (54.9, 30_000, None),                 # exactly 30,000 lb does not trigger
        (45, 30_001, L.NO_TRAVEL),
        (54.9, 30_001, L.NO_TRAVEL),
        (44.9, 30_001, None),                 # 30k rule needs 45-54 mph
        (35, 40_000, None),                   # exactly 40,000 lb does not trigger
        (35, 40_001, L.SEVERE),
        (44.9, 40_001, L.SEVERE),
        (34.9, 80_000, None),
    ],
)
def test_load_rules(mph, load, expected):
    assert load_escalation(mph, load) == expected


def test_checkpoint_takes_worst_condition():
    a = assess(wind_mph=10, rain_in_hr=0.3, snow_in_hr=0.6, load_lb=20_000)
    assert (a.wind, a.rain, a.snow) == (L.LOW, L.HIGH, L.MODERATE)
    assert a.level == L.HIGH
    assert not a.load_escalated
    assert a.factors == ("rain 0.30 in/hr",)


def test_load_escalates_wind():
    a = assess(wind_mph=47, rain_in_hr=0, snow_in_hr=0, load_lb=42_000)
    assert a.wind == L.SEVERE
    assert a.level == L.NO_TRAVEL
    assert a.load_escalated
    assert "47 mph wind + 42,000 lb load" in a.factor_text


def test_load_never_downgrades():
    # Heavy snow is already No Travel; the High-wind load rule (-> Severe) must not lower it.
    a = assess(wind_mph=40, rain_in_hr=0, snow_in_hr=3.5, load_lb=45_000)
    assert a.level == L.NO_TRAVEL
    assert not a.load_escalated


def test_load_rule_not_flagged_when_weather_already_worse():
    a = assess(wind_mph=40, rain_in_hr=0.7, snow_in_hr=0, load_lb=45_000)
    assert a.level == L.SEVERE  # rain Severe == load Severe
    assert not a.load_escalated


@pytest.mark.parametrize(
    ("wind", "rain", "snow", "load"),
    [
        (w, r, s, ld)
        for w in (0, 12.5, 24.99, 25, 30, 35, 44.99, 45, 50, 55, 70)
        for r in (0, 0.05, 0.1, 0.3, 0.5, 1.0, 1.5)
        for s in (0, 0.5, 2.5, 3.0, 3.1)
        for ld in (0, 35_000, 45_000)
    ],
)
def test_index_floor_matches_level(wind, rain, snow, load):
    idx = risk_index(wind, rain, snow, load)
    assert 0 <= idx <= 4
    assert int(idx) == assess(wind, rain, snow, load).level
