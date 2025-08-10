import math
import pytest

from psychrometrics import (
    saturation_vp,
    humidity_ratio,
    delta_humidity_ratio,
    air_density,
    infiltration_load_l_per_day,
    occupant_load_l_per_day,
    pool_evaporation_l_per_day,
    dew_point,
    derate_factor,
)


def test_saturation_vp_monotonic():
    assert saturation_vp(10) < saturation_vp(20) < saturation_vp(30)


@pytest.mark.parametrize(
    "temp,rh_cur,rh_tar",
    [
        (25.0, 80.0, 60.0),
        (20.0, 90.0, 50.0),
        (30.0, 65.0, 55.0),
    ],
)
def test_delta_humidity_ratio_positive_when_target_lower(temp, rh_cur, rh_tar):
    dw = delta_humidity_ratio(temp, rh_cur, rh_tar)
    assert dw >= 0
    assert humidity_ratio(temp, rh_cur) >= humidity_ratio(temp, rh_tar)


def test_air_density_decreases_with_temp():
    assert air_density(10) > air_density(20) > air_density(30)


def test_infiltration_load_basic():
    lpd = infiltration_load_l_per_day(
        volume_m3=300.0, ach=0.5, temp_c=22.0, current_rh=80.0, target_rh=55.0
    )
    assert lpd > 0


def test_occupant_load_scaling():
    assert occupant_load_l_per_day(0) == 0
    assert occupant_load_l_per_day(1) > 0
    assert occupant_load_l_per_day(3) > occupant_load_l_per_day(1)


def test_pool_evaporation_zero_when_no_pool():
    assert (
        pool_evaporation_l_per_day(
            pool_area_m2=0, water_temp_c=28, indoor_temp_c=26, current_rh=60, air_velocity_mps=0.1
        )
        == 0
    )


def test_dew_point_bounds():
    assert dew_point(25, 50) > -50
    # Allow tiny floating error margin
    assert dew_point(25, 100) <= 25 + 1e-6  # cannot exceed temp


def test_derate_factor_clamped():
    assert 0.1 <= derate_factor(5, 40) <= 1.0
    assert 0.1 <= derate_factor(30, 80) <= 1.0


