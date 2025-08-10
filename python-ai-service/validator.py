"""Validation-grade load calculators (pool, infiltration, pulldown).

Self-contained functions tuned to benchmark scenarios. These are used to
validate and inform the production sizing layer.
"""
from __future__ import annotations

from typing import Literal, Optional, Dict, Any

from psychrometrics import saturation_vp_kpa, humidity_ratio, air_density, air_density_moist


def pool_evap_l_per_day(
    area_m2: float,
    water_c: float,
    air_c: float,
    rh_target_pct: float,
    mode: str = "field_calibrated",  # "standard" or "field_calibrated"
    air_movement_level: str = "still",  # "still", "low", "medium"
    activity: Literal["none", "low", "medium", "high"] = "low",
    covered_h_per_day: float = 0.0,
    cover_reduction: float = 0.7,
    custom_params: Optional[Dict[str, Any]] = None,
) -> float:
    """Estimate pool evaporation (L/day ~ kg/day) with hybrid standard/field model.

    - Nonlinear air-film velocity factor: K = a + b * v_fpm ** c
    - C_standard default 0.00105; field bias 0.80 with minimum ratio 0.70 vs standard
    - Air movement map: still=0.0 m/s, low=0.1, medium=0.2
    """
    if area_m2 <= 0:
        return 0.0

    v_map = {"still": 0.05, "low": 0.1, "medium": 0.2}
    v_mps = v_map.get(air_movement_level, 0.0)
    v_fpm = max(v_mps, 0.0) * 196.8504

    dp = max(saturation_vp_kpa(water_c) - (saturation_vp_kpa(air_c) * max(rh_target_pct, 0.0) / 100.0), 0.0)
    AF = {"none": 1.0, "low": 1.2, "medium": 1.5, "high": 2.0}.get(activity, 1.2)

    params = custom_params or {}
    C_std = params.get("C_standard", 0.00105)
    a = params.get("a", 3.385)
    b = params.get("b", 8.957)
    c = params.get("c", 0.832)
    field_bias = params.get("field_bias", 0.80)
    min_ratio = params.get("min_ratio_vs_standard", 0.70)

    K = a + b * (v_fpm ** c)
    kg_h_std = area_m2 * C_std * dp * K * AF
    uh = max(24.0 - covered_h_per_day, 0.0)
    ch = min(max(covered_h_per_day, 0.0), 24.0)
    kg_day_std = kg_h_std * uh + kg_h_std * (1.0 - max(min(cover_reduction, 1.0), 0.0)) * ch
    Lpd_std = max(kg_day_std, 0.0)

    if mode == "standard":
        return round(Lpd_std, 1)

    Lpd_field = Lpd_std * field_bias
    Lpd_min = Lpd_std * min_ratio
    Lpd = max(Lpd_field, Lpd_min)
    return round(Lpd, 1)


def infiltration_l_per_day(
    volume_m3: float,
    indoor_c: float,
    rh_target_pct: float,
    outdoor_c: float,
    rh_out_pct: float,
    vent_level: str = "low",
) -> float:
    """Steady-state infiltration latent load using outdoor→indoor ΔW.
    vent_level: "low" (0.4 ACH) or "standard" (0.8 ACH). Default 0.4.
    Returns L/day (≈ kg/day).
    """
    if volume_m3 <= 0:
        return 0.0
    ach_map = {"low": 0.4, "standard": 0.8}
    ach = ach_map.get(vent_level, 0.5)
    W_out = humidity_ratio(outdoor_c, rh_out_pct)
    W_in = humidity_ratio(indoor_c, rh_target_pct)
    dW = max(W_out - W_in, 0.0)
    try:
        rho = air_density_moist(indoor_c, rh_target_pct)
    except Exception:
        rho = air_density(indoor_c)
    kg_h = dW * rho * volume_m3 * ach
    return round(max(kg_h * 24.0, 0.0), 1)


def calibrate_params(measured_data: list):
    """Fit C/a/b/c with guardrails. measured_data tuples: (area_m2, dp_kPa, v_fpm, AF, kg_per_h).
    Requires >=8 points. If scipy unavailable, raises ValueError.
    """
    if measured_data is None or len(measured_data) < 8:
        raise ValueError("Need >=8 datapoints for reliable fit")
    try:
        # Local imports to avoid hard dependency
        import numpy as np
        from scipy.optimize import curve_fit
    except Exception as e:
        raise ValueError(f"Calibration unavailable: {e}")

    def evap_func(X, C, a, b, c):
        area, dp, v_fpm, AF = X
        K = a + b * (v_fpm ** c)
        return area * C * dp * K * AF  # kg/h

    X = np.array([(d[0], d[1], d[2], d[3]) for d in measured_data], dtype=float)
    y = np.array([d[4] for d in measured_data], dtype=float)
    popt, _ = curve_fit(
        evap_func,
        X.T,
        y,
        p0=[0.00105, 3.385, 8.957, 0.832],
        bounds=([0.0005, 1.0, 5.0, 0.5], [0.0015, 10.0, 15.0, 1.0]),
        maxfev=20000,
    )
    return {"C_standard": float(popt[0]), "a": float(popt[1]), "b": float(popt[2]), "c": float(popt[3])}


def pulldown_air_l(
    volume_m3: float,
    indoor_c: float,
    rh_current_pct: float,
    rh_target_pct: float,
) -> float:
    """One-time air-only pulldown liters to drop from current to target RH.
    Does not include moisture in materials; air only.
    """
    if volume_m3 <= 0:
        return 0.0
    dW = max(humidity_ratio(indoor_c, rh_current_pct) - humidity_ratio(indoor_c, rh_target_pct), 0.0)
    rho = air_density_moist(indoor_c, rh_current_pct)
    kg = dW * rho * volume_m3
    return round(max(kg, 0.0), 1)


if __name__ == "__main__":
    print("Pool 28C still baseline:", pool_evap_l_per_day(32, 28, 28, 60, air_movement_level='still', activity="low"))
    try:
        fake = [(32, 1.7, 0.0, 1.2, 3.3)] * 8  # 3.3 kg/h ~ 79 L/day
        params = calibrate_params(fake)
        print("Fitted:", params)
    except Exception as e:
        print("Calibration demo skipped:", e)


