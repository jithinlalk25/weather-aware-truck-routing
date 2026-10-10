"""Builds a trip plan: routes -> checkpoints -> ETAs -> weather -> risk -> recommendation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from rest_framework.exceptions import ValidationError

from domain import hos as hos_rules
from domain.geo import METERS_PER_MILE, LatLon, haversine_m, simplify_indices
from domain.lattice import smallest_step, snap, snap_all
from domain.profile import RouteProfile
from domain.risk import assess
from domain.sampling import checkpoint_distances, distance_shares
from domain.scoring import ScoredCheckpoint, recommend, score_route
from domain.weather import forecast_confidence, sample_at

from ..models import TripPlan
from . import routing, weather
from .timezones import tz_at

TARE_LB = 35_000  # assumed empty tractor-trailer weight; TomTom needs gross weight
MAX_DEPARTURE_AHEAD = timedelta(days=7)
PAST_GRACE = timedelta(minutes=15)
CHECKPOINT_NODE_CAP = 300
PATH_TOLERANCE_M = 40.0
LABELS = "ABC"


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float

    @property
    def latlon(self) -> LatLon:
        return (self.lat, self.lon)


@dataclass(frozen=True)
class PlanRequest:
    origin: Place
    destination: Place
    departure_local: datetime  # naive, in the origin's local time zone
    load_lb: int
    interval_mi: int
    wind_mode: str  # "sustained" | "gust"
    hos: bool


def resolve_departure(local: datetime, tz: str, now: datetime | None = None) -> datetime:
    """Origin-local wall time -> aware UTC, validated against the allowed window."""
    now = now or datetime.now(UTC)
    # zoneinfo resolves DST gaps/folds per PEP 495 (fold=0: the earlier offset).
    departure = local.replace(tzinfo=ZoneInfo(tz)).astimezone(UTC)
    if departure < now - PAST_GRACE:
        raise ValidationError({"departure_local": "Departure time is in the past."})
    if departure > now + MAX_DEPARTURE_AHEAD:
        raise ValidationError({"departure_local": "Departure must be within the next 7 days."})
    return max(departure, now + timedelta(minutes=1))


@dataclass
class _RoutePrep:
    label: str
    raw: routing.RawRoute
    profile: RouteProfile
    pauses: list[hos_rules.Pause]
    cp_dist: list[float]
    cp_share: list[float]
    cp_points: list[LatLon]
    cp_elapsed: list[float]

    @property
    def total_s(self) -> float:
        return self.profile.total_drive_s + hos_rules.total_pause_s(self.pauses)


def _prepare(label: str, raw: routing.RawRoute, interval_m: float, use_hos: bool) -> _RoutePrep:
    profile = RouteProfile.build(raw.points, raw.length_m, raw.drive_s, raw.progress)
    pauses = hos_rules.hos_pauses(profile.total_drive_s) if use_hos else []
    dist = checkpoint_distances(profile.total_m, interval_m)
    points = [profile.point_at(d) for d in dist]
    elapsed = [hos_rules.elapsed_at(profile.drive_s_at(d), pauses) for d in dist]
    return _RoutePrep(label, raw, profile, pauses, dist, distance_shares(dist), points, elapsed)


def _path(prep: _RoutePrep) -> list[list[float]]:
    """Simplified geometry with distance and elapsed time per vertex.

    HOS pauses appear as two vertices at the same place (start and end of the
    stop) so the frontend can interpolate the truck's position at any time.
    """
    prof, pauses = prep.profile, prep.pauses
    entries = []
    for i in simplify_indices(prof.points, PATH_TOLERANCE_M):
        lat, lon = prof.points[i]
        d = prof.dist_m[i]
        entries.append((hos_rules.elapsed_at(prof.drive_s[i], pauses), lon, lat, d))
    for p in pauses:
        d = prof.dist_at_drive_s(p.at_drive_s)
        lat, lon = prof.point_at(d)
        start = hos_rules.elapsed_at(p.at_drive_s, pauses)
        entries.append((start, lon, lat, d))
        entries.append((start + p.duration_s, lon, lat, d))
    entries.sort(key=lambda e: (e[0], e[3]))
    return [[round(lon, 5), round(lat, 5), round(d), round(t)] for t, lon, lat, d in entries]


def _rest_stops(prep: _RoutePrep) -> list[dict]:
    stops = []
    for p in prep.pauses:
        d = prep.profile.dist_at_drive_s(p.at_drive_s)
        lat, lon = prep.profile.point_at(d)
        stops.append({
            "kind": p.kind,
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "dist_mi": round(d / METERS_PER_MILE, 1),
            "start_elapsed_s": round(hos_rules.elapsed_at(p.at_drive_s, prep.pauses)),
            "duration_s": round(p.duration_s),
            "tz": tz_at(lat, lon),
        })
    return stops


def build_plan(req: PlanRequest, now: datetime | None = None) -> TripPlan:
    if haversine_m(req.origin.latlon, req.destination.latlon) < 1000:
        raise ValidationError({"destination": "Origin and destination are the same place."})
    origin_tz = tz_at(req.origin.lat, req.origin.lon)
    departure = resolve_departure(req.departure_local, origin_tz, now)
    dep_epoch = departure.timestamp()

    options = routing.get_route_options(
        req.origin.latlon, req.destination.latlon, departure, req.load_lb + TARE_LB
    )
    interval_m = req.interval_mi * METERS_PER_MILE
    preps = [_prepare(LABELS[i], raw, interval_m, req.hos) for i, raw in enumerate(options.routes)]

    # One lattice for all checkpoints, as fine as the per-plan location budget allows.
    all_points = [p for prep in preps for p in prep.cp_points]
    step = smallest_step(lambda s: len(snap_all(all_points, s)), CHECKPOINT_NODE_CAP)
    series = weather.get_series(snap_all(all_points, step))

    gust_mode = req.wind_mode == TripPlan.WindMode.GUST
    now_epoch = (now or datetime.now(UTC)).timestamp()
    scores, route_rows = [], []
    for prep in preps:
        checkpoints, scored = [], []
        for i, (d, share, pt, elapsed) in enumerate(
            zip(prep.cp_dist, prep.cp_share, prep.cp_points, prep.cp_elapsed, strict=True)
        ):
            eta = dep_epoch + elapsed
            node = snap(pt, step)
            ws = sample_at(series[node], eta)
            lead_h = (eta - now_epoch) / 3600
            cp = {
                "i": i,
                "dist_mi": round(d / METERS_PER_MILE, 1),
                "share_mi": round(share / METERS_PER_MILE, 2),
                "lat": round(pt[0], 5),
                "lon": round(pt[1], 5),
                "elapsed_s": round(elapsed),
                "eta": round(eta),
                "tz": tz_at(*pt),
                "confidence": forecast_confidence(lead_h),
                "cell": [node.lat, node.lon],
            }
            if ws is None:
                cp.update(level=None, factor="No forecast data for this time")
                scored.append(ScoredCheckpoint(share, None))
            else:
                wind_for_rules = ws.gust_mph if gust_mode else ws.wind_mph
                a = assess(wind_for_rules, ws.rain_in_hr, ws.snow_in_hr, req.load_lb,
                           wind_label="gust" if gust_mode else "wind")
                cp.update(
                    level=int(a.level),
                    levels={"wind": int(a.wind), "rain": int(a.rain), "snow": int(a.snow)},
                    load_escalated=a.load_escalated,
                    factor=a.factor_text,
                    wind_mph=round(ws.wind_mph, 1),
                    gust_mph=round(ws.gust_mph, 1),
                    rain_in_hr=round(ws.rain_in_hr, 3),
                    snow_in_hr=round(ws.snow_in_hr, 3),
                    temp_f=None if ws.temp_f is None else round(ws.temp_f),
                    weather_code=ws.weather_code,
                )
                scored.append(ScoredCheckpoint(share, a.level))
            checkpoints.append(cp)

        score = score_route(prep.label, scored, prep.profile.total_m,
                            prep.profile.total_drive_s, prep.total_s)
        scores.append(score)
        route_rows.append((prep, score, checkpoints))

    rec = recommend(scores)
    ranks = {s.label: i + 1 for i, s in enumerate(sorted(scores, key=lambda s: s.key()))}

    with transaction.atomic():
        plan = TripPlan.objects.create(
            origin_label=req.origin.label,
            origin_lat=req.origin.lat,
            origin_lon=req.origin.lon,
            origin_tz=origin_tz,
            dest_label=req.destination.label,
            dest_lat=req.destination.lat,
            dest_lon=req.destination.lon,
            dest_tz=tz_at(req.destination.lat, req.destination.lon),
            departure_at=departure,
            load_lb=req.load_lb,
            interval_mi=req.interval_mi,
            wind_mode=req.wind_mode,
            hos_enabled=req.hos,
            recommended_label=rec.label,
            recommendation=rec.headline,
            decided_by=rec.decided_by,
            tradeoff=rec.tradeoff or "",
            why_not=rec.why_not,
            warnings=list(rec.warnings),
            notes=options.notes,
            weather_meta={
                "source": "Open-Meteo (best-match models)",
                "lattice_step_deg": step,
                "locations": len({snap(p, step) for p in all_points}),
                "tare_lb": TARE_LB,
            },
        )
        for prep, score, checkpoints in route_rows:
            plan.routes.create(
                label=prep.label,
                rank=ranks[prep.label],
                source=prep.raw.source,
                distance_m=prep.profile.total_m,
                drive_s=prep.profile.total_drive_s,
                total_s=prep.total_s,
                traffic_delay_s=prep.raw.traffic_delay_s,
                arrival_at=departure + timedelta(seconds=prep.total_s),
                miles_by_level={k: round(v, 1) for k, v in score.miles.items()},
                avg_risk=None if score.avg_risk is None else round(score.avg_risk, 3),
                path=_path(prep),
                checkpoints=checkpoints,
                rest_stops=_rest_stops(prep),
            )
    return plan
