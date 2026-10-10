"""Checkpoint placement along a route and the miles each checkpoint represents."""

from __future__ import annotations

ALLOWED_INTERVALS_MI = (10, 25, 50)


def checkpoint_distances(total_m: float, interval_m: float) -> list[float]:
    """Origin, every `interval_m` along the road, and the destination."""
    if interval_m <= 0:
        raise ValueError("interval must be positive")
    if total_m <= 0:
        return [0.0]
    out = []
    k = 0
    while k * interval_m < total_m:
        out.append(k * interval_m)
        k += 1
    out.append(total_m)
    return out


def distance_shares(distances: list[float]) -> list[float]:
    """Road distance each checkpoint represents: half the gap to each neighbor.

    Shares sum exactly to the route length, so per-level mileage adds up.
    """
    n = len(distances)
    if n == 1:
        return [0.0]
    shares = []
    for i in range(n):
        prev_gap = distances[i] - distances[i - 1] if i > 0 else 0.0
        next_gap = distances[i + 1] - distances[i] if i < n - 1 else 0.0
        shares.append((prev_gap + next_gap) / 2)
    return shares
