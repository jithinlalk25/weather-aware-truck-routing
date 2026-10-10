import pytest

from domain.weather import HourlySeries, sample_at

T0 = 1_760_000_400  # an exact hour


def series(n=4, **over):
    base = dict(
        wind_mph=[10.0, 20.0, 30.0, 40.0][:n],
        gust_mph=[15.0, 25.0, 35.0, 45.0][:n],
        rain_in=[0.0, 0.1, 0.2, 0.3][:n],
        snow_in=[0.0, 0.0, 1.0, 2.0][:n],
        temp_f=[50.0, 49.0, 48.0, 47.0][:n],
        weather_code=[0, 61, 63, 65][:n],
    )
    base.update(over)
    return HourlySeries(start_epoch=T0, **base)


def test_on_the_hour_uses_that_hour():
    s = sample_at(series(), T0 + 3600)
    assert (s.wind_mph, s.gust_mph, s.rain_in_hr, s.snow_in_hr) == (20, 25, 0.1, 0)


def test_between_hours_interpolates_wind_and_uses_ending_hour_for_accumulations():
    s = sample_at(series(), T0 + 3600 + 900)  # 01:15 -> hour ending 02:00
    assert s.wind_mph == pytest.approx(22.5)
    assert (s.gust_mph, s.rain_in_hr, s.snow_in_hr) == (35, 0.2, 1.0)


def test_beyond_horizon_is_no_data():
    assert sample_at(series(), T0 + 3 * 3600 + 1) is None
    assert sample_at(series(), T0 - 1) is None


def test_null_values_are_no_data():
    assert sample_at(series(rain_in=[0.0, None, 0.2, 0.3]), T0 + 3600) is None
