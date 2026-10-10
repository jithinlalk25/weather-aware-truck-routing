import pytest

from domain.geo import METERS_PER_MILE
from domain.sampling import checkpoint_distances, distance_shares

MI = METERS_PER_MILE


@pytest.mark.parametrize("interval", [10, 25, 50])
@pytest.mark.parametrize("total_mi", [3, 25, 49.9, 100, 1003.7])
def test_shares_sum_to_route_length(interval, total_mi):
    d = checkpoint_distances(total_mi * MI, interval * MI)
    assert d[0] == 0 and d[-1] == pytest.approx(total_mi * MI)
    assert sum(distance_shares(d)) == pytest.approx(total_mi * MI)


def test_checkpoints_every_interval_plus_destination():
    d = checkpoint_distances(60 * MI, 25 * MI)
    assert [round(x / MI, 3) for x in d] == [0, 25, 50, 60]
    assert [round(s / MI, 3) for s in distance_shares(d)] == [12.5, 25, 17.5, 5]


def test_exact_multiple_has_no_duplicate_end():
    d = checkpoint_distances(50 * MI, 25 * MI)
    assert [round(x / MI) for x in d] == [0, 25, 50]


def test_fill_holes_closes_gap_between_routes():
    from domain.lattice import Node, fill_holes

    ring = {Node(1.0, i, j) for i in range(5) for j in range(5) if i in (0, 4) or j in (0, 4)}
    filled = fill_holes(ring)
    assert Node(1.0, 2, 2) in filled
    assert len(filled) == 25
    open_shape = {Node(1.0, 0, j) for j in range(5)}
    assert fill_holes(open_shape) == open_shape
