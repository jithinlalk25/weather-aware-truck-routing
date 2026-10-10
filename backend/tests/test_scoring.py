import pytest

from domain.geo import METERS_PER_MILE
from domain.risk import RiskLevel as L
from domain.scoring import ScoredCheckpoint, recommend, score_route

MI = METERS_PER_MILE


def route(label, levels, total_s=36_000, share_mi=10.0):
    cps = [ScoredCheckpoint(share_mi * MI, lvl) for lvl in levels]
    return score_route(label, cps, len(levels) * share_mi * MI, total_s, total_s)


def test_mileage_and_average():
    s = route("A", [L.LOW, L.HIGH, L.SEVERE, None])
    assert s.miles["low"] == pytest.approx(10)
    assert s.miles["high"] == pytest.approx(10)
    assert s.miles["severe"] == pytest.approx(10)
    assert s.miles["no_data"] == pytest.approx(10)
    assert s.avg_risk == pytest.approx((0 + 2 + 3) / 3)  # no-data excluded


def test_fewest_severe_beats_fewer_high():
    a = route("A", [L.SEVERE, L.LOW, L.LOW])
    b = route("B", [L.HIGH, L.HIGH, L.HIGH])
    rec = recommend([a, b])
    assert rec.label == "B" and rec.decided_by == "severe"


def test_no_travel_ranks_above_severe():
    a = route("A", [L.NO_TRAVEL, L.LOW, L.LOW])
    b = route("B", [L.SEVERE, L.SEVERE, L.SEVERE])
    rec = recommend([a, b])
    assert rec.label == "B" and rec.decided_by == "no_travel"


def test_high_then_average_then_time():
    a = route("A", [L.HIGH, L.LOW], total_s=30_000)
    b = route("B", [L.MODERATE, L.LOW], total_s=40_000)
    assert recommend([a, b]).decided_by == "high"

    c = route("C", [L.MODERATE, L.MODERATE], total_s=30_000)
    d = route("D", [L.MODERATE, L.LOW], total_s=40_000)
    rec = recommend([c, d])
    assert rec.label == "D" and rec.decided_by == "avg_risk"

    e = route("E", [L.LOW, L.LOW], total_s=40_000)
    f = route("F", [L.LOW, L.LOW], total_s=30_000)
    rec = recommend([e, f])
    assert rec.label == "F" and rec.decided_by == "time"


def test_float_noise_does_not_decide():
    a = score_route("A", [ScoredCheckpoint(10 * MI + 1e-6, L.SEVERE)], 10 * MI, 100, 100)
    b = score_route("B", [ScoredCheckpoint(10 * MI, L.SEVERE)], 10 * MI, 200, 200)
    assert recommend([a, b]).label == "A"  # severe miles tie at 0.1 mi -> time decides


def test_warns_when_all_routes_have_no_travel():
    a = route("A", [L.NO_TRAVEL])
    b = route("B", [L.NO_TRAVEL, L.NO_TRAVEL])
    rec = recommend([a, b])
    assert rec.label == "A"
    assert any("Consider delaying" in w for w in rec.warnings)


def test_explains_every_other_route_and_the_time_tradeoff():
    fast = route("A", [L.MODERATE, L.LOW, L.LOW], total_s=30_000)
    calm = route("B", [L.LOW, L.LOW, L.LOW], total_s=38_640)
    calm_slow = route("C", [L.LOW, L.LOW, L.LOW], total_s=40_000)
    rec = recommend([fast, calm, calm_slow])
    assert rec.label == "B"
    assert rec.decided_by == "time"  # versus the runner-up, C
    assert rec.why_not["A"].startswith("Higher average risk (10.0 mi Moderate)")
    assert rec.why_not["C"] == "Same weather risk, but 23m longer."
    assert rec.tradeoff == (
        "Takes 2h 24m longer than the fastest option, Route A, to avoid its weather."
    )


def test_no_tradeoff_when_winner_is_fastest():
    a = route("A", [L.LOW], total_s=100)
    b = route("B", [L.HIGH], total_s=200)
    rec = recommend([a, b])
    assert rec.tradeoff is None
    assert rec.why_not == {"B": "10.0 mi of High weather vs 0.0 mi on Route A."}


def test_headline_compares_with_runner_up_only():
    # C loses on Severe miles but has the fewest High miles of all three.
    a = route("A", [L.HIGH, L.HIGH, L.LOW])
    b = route("B", [L.HIGH, L.HIGH, L.HIGH])
    c = route("C", [L.SEVERE, L.LOW, L.LOW])
    rec = recommend([a, b, c])
    assert rec.label == "A"
    assert rec.headline == (
        "Route A has fewer High miles than the runner-up, Route B: 20.0 mi vs 30.0 mi."
    )
    assert rec.why_not["C"] == "10.0 mi of Severe weather vs 0.0 mi on Route A."


def test_route_without_any_forecast_does_not_crash():
    a = route("A", [L.LOW, L.MODERATE], total_s=100)
    c = route("C", [None, None], total_s=50)
    rec = recommend([a, c])
    assert rec.label == "A"
    assert rec.why_not["C"] == "Higher average risk: n/a vs 0.50 on Route A."


def test_no_travel_warning_matches_the_ranking_precision():
    tiny = score_route("A", [ScoredCheckpoint(0.03 * MI, L.NO_TRAVEL),
                             ScoredCheckpoint(10 * MI, L.LOW)], 10 * MI, 100, 100)
    clean = route("B", [L.LOW], total_s=200)
    rec = recommend([tiny, clean])
    assert not any("Consider delaying" in w for w in rec.warnings)
