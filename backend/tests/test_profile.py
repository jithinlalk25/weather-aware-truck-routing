import pytest

from domain.geo import cumulative_m
from domain.profile import ProgressMark, RouteProfile

PTS = [(40.0, -100.0), (40.0, -99.9), (40.0, -99.8), (40.0, -99.7), (40.0, -99.6)]


def test_without_progress_scales_to_provider_totals():
    flat = cumulative_m(PTS)[-1]
    prof = RouteProfile.build(PTS, total_m=flat * 1.1, total_drive_s=4000)
    assert prof.total_m == pytest.approx(flat * 1.1)
    assert prof.drive_s[2] == pytest.approx(2000)


def test_progress_marks_anchor_distance_and_time():
    prog = [ProgressMark(0, 0, 0), ProgressMark(2, 20_000, 1000), ProgressMark(4, 30_000, 3000)]
    prof = RouteProfile.build(PTS, 30_000, 3000, prog)
    assert prof.dist_m[2] == 20_000 and prof.drive_s[2] == 1000
    assert prof.dist_m[1] == pytest.approx(10_000, rel=1e-3)
    assert prof.drive_s[3] == pytest.approx(2000, rel=1e-3)
    assert prof.drive_s_at(25_000) == pytest.approx(2000, rel=1e-3)
    assert prof.dist_at_drive_s(500) == pytest.approx(10_000, rel=1e-3)
