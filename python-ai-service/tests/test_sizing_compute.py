import pytest

from sizing import compute_load_components


def test_components_sum_to_total():
    r = compute_load_components(
        current_rh=80,
        target_rh=55,
        indoor_temp_c=22,
        volume_m3=300,
        ach=0.5,
        people_count=2,
        pool_area_m2=0,
    )
    comps = r["components"]
    total = r["total_lpd"]
    s = comps["infiltration_lpd"] + comps["occupant_lpd"] + comps["pool_lpd"] + comps["additional_lpd"]
    assert abs(s - total) <= 0.1


def test_load_vs_ach_monotonic():
    r = compute_load_components(
        current_rh=85,
        target_rh=55,
        indoor_temp_c=24,
        length=10,
        width=6,
        height=3,
        ach=0.5,
        people_count=0,
        pool_area_m2=0,
    )
    series = r["plot_data"]["load_vs_ach"]
    vals = [p["total_lpd"] for p in series]
    assert vals == sorted(vals)


