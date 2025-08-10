from validator import pool_evap_l_per_day, infiltration_l_per_day, pulldown_air_l
from sizing import compute_load_components


def test_pool_28c_baseline_range():
    # 27.2 m², 28/28/60%, low, uncovered in standard mode should be in plausible 100-150 L/day range
    v = pool_evap_l_per_day(27.2, 28, 28, 60, mode='standard', air_movement_level='low', activity="low", covered_h_per_day=0)
    assert 100 <= v <= 150


def test_pool_32c_higher():
    v32 = pool_evap_l_per_day(27.2, 32, 28, 60, mode='standard', air_movement_level='low', activity="low", covered_h_per_day=0)
    assert v32 > 100


def test_infiltration_309m3_ach1():
    # vent_level 'standard' maps to 0.8 ACH; scale to 1.0 manually by adjusting expectations
    infil_low = infiltration_l_per_day(309, 28, 60, 28, 90, vent_level='standard')  # 0.8 ACH
    assert 45 <= infil_low <= 70


def test_infiltration_72m3_ach1():
    infil_low = infiltration_l_per_day(72, 28, 60, 28, 90, vent_level='standard')
    assert 10 <= infil_low <= 20


def test_pulldown_air_only():
    pd = pulldown_air_l(309, 28, 90, 60)
    # Air-only pulldown at 28C 90->60% is ~2.6 L for 309 m3
    assert 2.0 <= pd <= 3.5


def test_field_residential_scenario_still_low_vent():
    r = compute_load_components(
        current_rh=90,
        target_rh=60,
        indoor_temp_c=28,
        volume_m3=72,  # ~30 m² x 2.4 m room as in example
        pool_area_m2=32,
        water_temp_c=28,
        outdoor_temp_c=28,
        outdoor_rh_percent=90,
        air_movement_level='still',
        vent_level='low',
        mode='field_calibrated',
    )
    assert 80 <= r['total_lpd'] <= 120


