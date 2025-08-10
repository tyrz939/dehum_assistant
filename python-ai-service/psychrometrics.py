"""Psychrometrics and sizing primitives – pure functions.

These functions avoid side effects and logging and are suitable for unit/property tests.
Includes precise helpers for vapor pressure, humidity ratio, and air density.
"""
from __future__ import annotations

import math
from typing import Literal

ATM_KPA = 101.325


def saturation_vp(temp_c: float) -> float:
    """Legacy saturation vapor pressure (kPa) using Magnus formula (kept for BC)."""
    return 0.61094 * math.exp((17.625 * temp_c) / (temp_c + 243.04))


def saturation_vp_kpa(t_c: float) -> float:
    """Saturation vapor pressure (kPa) using ASHRAE-style constants."""
    return 0.61078 * math.exp((17.2694 * t_c) / (t_c + 237.3))


def humidity_ratio(t_c: float, rh_percent: float) -> float:
    """Humidity ratio W (kg/kg dry air) at temperature and RH.

    Uses 101.325 kPa standard pressure and clamps RH to [0, 100].
    """
    rh_clamped = max(0.0, min(100.0, rh_percent))
    pws = saturation_vp_kpa(t_c)
    pw = (rh_clamped / 100.0) * pws
    return 0.62198 * pw / max(ATM_KPA - pw, 1e-9)


def delta_humidity_ratio(temp_c: float, current_rh: float, target_rh: float) -> float:
    """Delta W = W(current) - W(target) ≥ 0 when target_rh < current_rh."""
    w_cur = humidity_ratio(temp_c, current_rh)
    w_tar = humidity_ratio(temp_c, target_rh)
    return w_cur - w_tar


def air_density(temp_c: float) -> float:
    """Legacy approximate dry-air density (kg/m³). Kept for backward compatibility."""
    return 1.2 * (293.15 / (273.15 + temp_c))


def air_density_moist(t_c: float, rh_percent: float) -> float:
    """Moist air density (kg/m³) using ideal gas mixture of dry air and water vapor."""
    T = t_c + 273.15
    R_d, R_v = 287.055, 461.495
    p = ATM_KPA * 1000.0
    pws = saturation_vp_kpa(t_c) * 1000.0
    pw = max(0.0, min(1.0, rh_percent / 100.0)) * pws
    pd = max(p - pw, 0.0)
    return pd / (R_d * T) + pw / (R_v * T)


def infiltration_load_l_per_day(
    volume_m3: float,
    ach: float,
    temp_c: float,
    current_rh: float,
    target_rh: float,
    vent_factor: float = 1.0,
) -> float:
    if volume_m3 <= 0:
        return 0.0
    if ach < 0:
        ach = 0.0
    dw = max(0.0, delta_humidity_ratio(temp_c, current_rh, target_rh))
    mass_air = air_density(temp_c) * volume_m3
    kg_per_h = ach * mass_air * dw
    l_per_day = kg_per_h * 24.0 * max(vent_factor, 0.0)
    return max(0.0, l_per_day)


def occupant_load_l_per_day(people_count: int) -> float:
    if people_count <= 0:
        return 0.0
    gph = people_count * 80.0  # moderate activity
    return (gph * 24.0) / 1000.0


def evaporation_activity_coeff(activity: Literal["none", "low", "medium", "high"]) -> float:
    mapping = {
        "none": 0.05,
        "low": 0.065,
        "medium": 0.10,
        "high": 0.15,
    }
    return mapping.get(activity.lower(), 0.05)


def pool_evaporation_l_per_day(
    pool_area_m2: float,
    water_temp_c: float,
    indoor_temp_c: float,
    current_rh: float,
    air_velocity_mps: float,
    pool_activity: Literal["none", "low", "medium", "high"] = "none",
) -> float:
    if pool_area_m2 <= 0:
        return 0.0

    p_a = (current_rh / 100.0) * saturation_vp(indoor_temp_c)
    p_w = saturation_vp(water_temp_c)
    delta_p = max(p_w - p_a, 0.0)
    delta_p = min(delta_p, 2.5)  # cap to prevent unrealistic rates

    c_base = evaporation_activity_coeff(pool_activity)
    c = c_base + 0.3 * max(air_velocity_mps, 0.0)

    temp_diff = max(water_temp_c - indoor_temp_c, 0.0)
    c *= (1.0 + 0.04 * temp_diff)  # reduced sensitivity

    w_kg_per_h = pool_area_m2 * c * delta_p
    return round(max(0.0, w_kg_per_h) * 24.0, 1)


def dew_point(temp_c: float, rh_percent: float) -> float:
    if rh_percent <= 0 or rh_percent > 100:
        return -100.0
    pv = (rh_percent / 100.0) * saturation_vp(temp_c)
    if pv <= 0:
        return -100.0
    alpha = math.log(pv / 0.61094)
    return 243.04 * alpha / (17.625 - alpha)


def derate_factor(temp_c: float, rh_percent: float) -> float:
    """Derating factor for capacity; clamped to [0.1, 1.0]."""
    td = dew_point(temp_c, rh_percent)
    td_norm = max(td, 0.0) / 26.0
    return min(1.0, max(0.1, td_norm ** 1.5))


