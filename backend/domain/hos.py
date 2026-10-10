"""FMCSA Hours-of-Service pauses that shift ETAs on long trips.

Modeled (property-carrying driver, starting the trip with fresh clocks):
  * 30-minute break after 8 cumulative hours of driving without one.
  * 10 consecutive hours off duty after 11 hours of driving; resets both clocks.

Not modeled: the 14-hour on-duty window (never binds when the driver only drives
and takes these pauses: 11 h + 0.5 h < 14 h), the 60/70-hour weekly limit,
sleeper-berth splits, and on-duty time for loading or fueling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HOUR = 3600.0
BREAK_AFTER_S = 8 * HOUR
BREAK_S = 0.5 * HOUR
DRIVE_LIMIT_S = 11 * HOUR
REST_S = 10 * HOUR


@dataclass(frozen=True)
class Pause:
    at_drive_s: float  # cumulative drive time when the pause starts
    duration_s: float
    kind: Literal["break", "rest"]


def hos_pauses(total_drive_s: float) -> list[Pause]:
    """Pauses needed to legally drive `total_drive_s` seconds."""
    pauses: list[Pause] = []
    shift_start = 0.0  # drive time at the last 10-hour rest
    since_break_start = 0.0  # drive time at the last 30-minute break or rest
    while True:
        break_due = since_break_start + BREAK_AFTER_S
        rest_due = shift_start + DRIVE_LIMIT_S
        if rest_due <= break_due:
            if rest_due >= total_drive_s:
                break
            pauses.append(Pause(rest_due, REST_S, "rest"))
            shift_start = since_break_start = rest_due
        else:
            if break_due >= total_drive_s:
                break
            pauses.append(Pause(break_due, BREAK_S, "break"))
            since_break_start = break_due
    return pauses


def elapsed_at(drive_s: float, pauses: list[Pause]) -> float:
    """Wall-clock seconds since departure when cumulative drive time is `drive_s`.

    A pause that starts exactly at `drive_s` is not counted: the truck reaches
    that point, then stops.
    """
    return drive_s + sum(p.duration_s for p in pauses if p.at_drive_s < drive_s)


def total_pause_s(pauses: list[Pause]) -> float:
    return sum(p.duration_s for p in pauses)
