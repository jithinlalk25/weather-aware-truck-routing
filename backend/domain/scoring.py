"""Route summaries and the recommendation.

Preference order from the brief, with No Travel placed ahead of Severe:
    1. fewest No-Travel miles
    2. fewest Severe miles
    3. fewest High miles
    4. lowest average risk (mile-weighted, Low=0 ... No Travel=4)
    5. shortest travel time (including HOS pauses when enabled)
Miles are compared at 0.1 mi and average risk at 0.01 so float noise never
decides a recommendation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .geo import METERS_PER_MILE
from .risk import RiskLevel

LEVEL_KEYS = {
    RiskLevel.LOW: "low",
    RiskLevel.MODERATE: "moderate",
    RiskLevel.HIGH: "high",
    RiskLevel.SEVERE: "severe",
    RiskLevel.NO_TRAVEL: "no_travel",
}
NO_DATA_KEY = "no_data"
UNKNOWN_AVG = 99.0  # sorts routes with no usable weather last


@dataclass(frozen=True)
class ScoredCheckpoint:
    share_m: float
    level: RiskLevel | None  # None = no forecast data


@dataclass(frozen=True)
class RouteScore:
    label: str
    distance_m: float
    drive_s: float
    total_s: float
    miles: dict[str, float]
    avg_risk: float | None

    def key(self) -> tuple[float, float, float, float, float]:
        return (
            round(self.miles["no_travel"], 1),
            round(self.miles["severe"], 1),
            round(self.miles["high"], 1),
            round(self.avg_risk, 2) if self.avg_risk is not None else UNKNOWN_AVG,
            round(self.total_s),
        )


def score_route(label: str, checkpoints: Sequence[ScoredCheckpoint], distance_m: float,
                drive_s: float, total_s: float) -> RouteScore:
    miles = {key: 0.0 for key in (*LEVEL_KEYS.values(), NO_DATA_KEY)}
    weighted = 0.0
    known_m = 0.0
    for cp in checkpoints:
        mi = cp.share_m / METERS_PER_MILE
        if cp.level is None:
            miles[NO_DATA_KEY] += mi
            continue
        miles[LEVEL_KEYS[cp.level]] += mi
        weighted += int(cp.level) * cp.share_m
        known_m += cp.share_m
    avg = weighted / known_m if known_m > 0 else None
    return RouteScore(label, distance_m, drive_s, total_s, miles, avg)


def rank_routes(scores: Sequence[RouteScore]) -> list[RouteScore]:
    return sorted(scores, key=lambda s: s.key())


def _fmt_mi(x: float) -> str:
    return f"{x:,.1f} mi"


def _fmt_dur(seconds: float) -> str:
    h, m = divmod(round(seconds / 60), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _fmt_avg(avg: float | None) -> str:
    return "n/a" if avg is None else f"{avg:.2f}"


_CRITERIA = (
    ("no_travel", "No-Travel"),
    ("severe", "Severe"),
    ("high", "High"),
)


@dataclass(frozen=True)
class Recommendation:
    label: str
    headline: str
    decided_by: str  # no_travel | severe | high | avg_risk | time | tie | only
    warnings: tuple[str, ...]
    why_not: dict[str, str]  # other route label -> why it ranks below the winner
    tradeoff: str | None  # extra travel time accepted versus the fastest route


def _first_difference(a: RouteScore, b: RouteScore) -> int | None:
    return next((i for i, (x, y) in enumerate(zip(a.key(), b.key(), strict=True)) if x != y), None)


def _decided_by(i: int | None) -> str:
    if i is None:
        return "tie"
    return (*(key for key, _ in _CRITERIA), "avg_risk", "time")[i]


def _why_not(best: RouteScore, other: RouteScore) -> str:
    i = _first_difference(best, other)
    if i is None:
        return f"Ties with Route {best.label} on every criterion."
    if i < len(_CRITERIA):
        key, name = _CRITERIA[i]
        return (f"{_fmt_mi(other.miles[key])} of {name} weather vs "
                f"{_fmt_mi(best.miles[key])} on Route {best.label}.")
    if i == 3:
        mod = other.miles["moderate"]
        detail = f" ({_fmt_mi(mod)} Moderate)" if mod > 0 else ""
        return (f"Higher average risk{detail}: {_fmt_avg(other.avg_risk)} vs "
                f"{_fmt_avg(best.avg_risk)} on Route {best.label}.")
    return f"Same weather risk, but {_fmt_dur(other.total_s - best.total_s)} longer."


def recommend(scores: Sequence[RouteScore]) -> Recommendation:
    ranked = rank_routes(scores)
    best = ranked[0]
    warnings = []
    if best.key()[0] > 0:  # the best route has No-Travel miles, so every route does
        warnings.append(
            "Every route crosses No-Travel conditions at this departure time. "
            "Consider delaying departure."
        )
    if best.miles[NO_DATA_KEY] > 0:
        warnings.append(
            f"{_fmt_mi(best.miles[NO_DATA_KEY])} of Route {best.label} has no forecast data."
        )
    why_not = {s.label: _why_not(best, s) for s in ranked[1:]}

    fastest = min(scores, key=lambda s: s.total_s)
    tradeoff = None
    if fastest is not best and fastest.total_s - best.total_s < -60:
        tradeoff = (
            f"Takes {_fmt_dur(best.total_s - fastest.total_s)} longer than the fastest option, "
            f"Route {fastest.label}, to avoid its weather."
        )

    if len(ranked) == 1:
        return Recommendation(best.label, f"Route {best.label} is the only route found.",
                              "only", tuple(warnings), why_not, tradeoff)

    # Headlines compare the winner with the runner-up only, and say so: a third
    # route may beat the winner on a later criterion after losing an earlier one.
    other = ranked[1]
    i = _first_difference(best, other)
    decided = _decided_by(i)
    if i is not None and i < len(_CRITERIA):
        key, name = _CRITERIA[i]
        headline = (
            f"Route {best.label} has fewer {name} miles than the runner-up, Route {other.label}: "
            f"{_fmt_mi(best.miles[key])} vs {_fmt_mi(other.miles[key])}."
        )
    elif decided == "avg_risk":
        headline = (
            f"Severe and High miles tie with the runner-up, Route {other.label}, so Route "
            f"{best.label} wins on lower average risk: {_fmt_avg(best.avg_risk)} vs "
            f"{_fmt_avg(other.avg_risk)}."
        )
    elif decided == "time":
        headline = (
            f"Weather risk ties with the runner-up, Route {other.label}, so Route {best.label} "
            f"wins as the faster trip: {_fmt_dur(best.total_s)} vs {_fmt_dur(other.total_s)}."
        )
    else:
        headline = f"Routes tie on every criterion; Route {best.label} is listed first."
    return Recommendation(best.label, headline, decided, tuple(warnings), why_not, tradeoff)
