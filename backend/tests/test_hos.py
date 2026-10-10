from domain.hos import BREAK_S, HOUR, REST_S, elapsed_at, hos_pauses


def test_short_trip_needs_no_pauses():
    assert hos_pauses(7.9 * HOUR) == []
    assert hos_pauses(8 * HOUR) == []  # arriving exactly at 8 h needs no break


def test_break_after_eight_hours():
    pauses = hos_pauses(10 * HOUR)
    assert [(p.at_drive_s / HOUR, p.kind) for p in pauses] == [(8, "break")]


def test_rest_after_eleven_hours_then_new_cycle():
    pauses = hos_pauses(30 * HOUR)
    assert [(p.at_drive_s / HOUR, p.kind) for p in pauses] == [
        (8, "break"),
        (11, "rest"),
        (19, "break"),
        (22, "rest"),
    ]


def test_elapsed_includes_prior_pauses_only():
    pauses = hos_pauses(30 * HOUR)
    assert elapsed_at(5 * HOUR, pauses) == 5 * HOUR
    assert elapsed_at(8 * HOUR, pauses) == 8 * HOUR  # arrives, then takes the break
    assert elapsed_at(9 * HOUR, pauses) == 9 * HOUR + BREAK_S
    assert elapsed_at(12 * HOUR, pauses) == 12 * HOUR + BREAK_S + REST_S
