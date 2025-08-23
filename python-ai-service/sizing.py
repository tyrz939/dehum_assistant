"""Sizing composition using pure psychrometric functions.

Exposes a single entrypoint `compute_load_components` that returns structured
components and helper plot data for visualization.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List

from psychrometrics import air_density, humidity_ratio, air_density_moist
from validator import (
    pool_evap_l_per_day,
    infiltration_l_per_day,
    pulldown_air_l,
    calibrate_params,
)


def _normalize_dimensions(
    length: Optional[float], width: Optional[float], height: Optional[float], volume_m3: Optional[float]
) -> Dict[str, float]:
    if volume_m3 is not None:
        if volume_m3 <= 0:
            raise ValueError("volume_m3 must be greater than 0")
        # Do NOT fabricate dimensions when only volume is given.
        return {"volume": float(volume_m3), "length": 0.0, "width": 0.0, "height": 0.0}

    if length is None or width is None or height is None:
        raise ValueError("Either volume_m3 OR all three dimensions (length, width, height) must be provided")
    if length <= 0 or width <= 0 or height <= 0:
        raise ValueError("length, width, and height must be greater than 0")
    return {"volume": float(length * width * height), "length": float(length), "width": float(width), "height": float(height)}


def compute_load_components(
    *,
    current_rh: float,
    target_rh: float,
    indoor_temp: float,
    length: Optional[float] = None,
    width: Optional[float] = None,
    height: Optional[float] = None,
    volume_m3: Optional[float] = None,
    ach: float = 1.0,
    people_count: int = 0,
    pool_area_m2: float = 0.0,
    water_temp_c: Optional[float] = None,
    pool_activity: str = "low",
    vent_factor: float = 1.0,
    additional_loads_lpd: float = 0.0,
    air_velocity_mps: float = 0.12,
    outdoor_temp_c: Optional[float] = None,
    outdoor_rh_percent: Optional[float] = None,
    covered_hours_per_day: float = 0.0,
    cover_reduction: float = 0.7,
    # New hybrid-model params
    air_movement_level: str = "still",
    vent_level: str = "low",
    mode: str = "field_calibrated",
    field_bias: float = 0.80,
    min_ratio_vs_standard: float = 0.70,
    calibrate_to_data: bool = False,
    measured_data: Optional[list] = None,
) -> Dict[str, Any]:
    # Guard clauses (minimal): allow target_rh >= current_rh; clamp obvious bounds.
    if not (0 <= current_rh <= 100):
        current_rh = max(0.0, min(100.0, current_rh))
    if not (0 <= target_rh <= 100):
        target_rh = max(0.0, min(100.0, target_rh))
    if indoor_temp < -20 or indoor_temp > 60:
        raise ValueError("indoorTemp out of reasonable bounds (-20..60°C)")
    if air_velocity_mps < 0 or air_velocity_mps > 1.0:
        raise ValueError("air_velocity_mps must be between 0 and 1.0 m/s")

    dims = _normalize_dimensions(length, width, height, volume_m3)
    volume = dims["volume"]
    room_area_m2 = (dims["length"] * dims["width"]) if (dims["length"] > 0 and dims["width"] > 0) else 0.0

    # Defaults for outdoor design: if not provided, fall back to indoor/current to preserve legacy behavior
    out_T = outdoor_temp_c if outdoor_temp_c is not None else indoor_temp
    out_RH = outdoor_rh_percent if outdoor_rh_percent is not None else current_rh

    # Components (steady-state)
    infiltration_lpd = infiltration_l_per_day(
        volume_m3=volume,
        indoor_c=indoor_temp,
        rh_target_pct=target_rh,
        outdoor_c=out_T,
        rh_out_pct=out_RH,
        vent_level=vent_level,
    )
    occupant_lpd = max(0.0, people_count * 80.0 * 24.0 / 1000.0) if people_count > 0 else 0.0
    # Optional calibration
    custom_params = {"field_bias": field_bias, "min_ratio_vs_standard": min_ratio_vs_standard}
    if calibrate_to_data and measured_data and len(measured_data) >= 8:
        try:
            custom_params.update(calibrate_params(measured_data))
        except Exception:
            pass

    pool_lpd = pool_evap_l_per_day(
        area_m2=pool_area_m2,
        water_c=water_temp_c if water_temp_c is not None else 28.0,
        air_c=indoor_temp,
        rh_target_pct=target_rh,
        mode=mode,
        air_movement_level=air_movement_level,
        activity=pool_activity,
        covered_h_per_day=covered_hours_per_day,
        cover_reduction=cover_reduction,
        custom_params=custom_params,
    ) if pool_area_m2 > 0 else 0.0
    other_lpd = max(0.0, additional_loads_lpd)

    steady_total_lpd = round(max(0.0, infiltration_lpd) + occupant_lpd + pool_lpd + other_lpd, 1)
    latent_kw = round((steady_total_lpd / 24.0) * 0.694, 1)
    pulldown_l = pulldown_air_l(volume, indoor_temp, current_rh, target_rh) if target_rh < current_rh else 0.0

    # Plot data helpers
    components = [
        {"name": "infiltration", "value": round(infiltration_lpd, 1)},
        {"name": "occupants", "value": round(occupant_lpd, 1)},
        {"name": "pool", "value": round(pool_lpd, 1)},
        {"name": "additional", "value": round(other_lpd, 1)},
    ]

    # Load vs ACH curve (simple sample over typical values)
    ach_samples = [0.2, 0.5, 1.0, 1.5, 2.0]
    load_vs_ach: List[Dict[str, float]] = []
    for ach_s in ach_samples:
        # Compute infiltration using outdoor→indoor ΔW and variable ACH
        W_out = humidity_ratio(out_T, out_RH)
        W_in = humidity_ratio(indoor_temp, target_rh)
        dW = max(W_out - W_in, 0.0)
        try:
            rho_m = air_density_moist(indoor_temp, target_rh)
        except Exception:
            rho_m = air_density(indoor_temp)
        infl = max(0.0, dW * rho_m * volume * ach_s * 24.0)
        load_vs_ach.append({"ach": ach_s, "total_lpd": round(max(0.0, infl) + occupant_lpd + pool_lpd + other_lpd, 1)})

    notes = []
    notes.append(f"Volume: {volume:.1f} m³; ACH={ach}")
    notes.append(f"RH reduction target: {current_rh}% → {target_rh}% at {indoor_temp}°C")
    notes.append(f"Air density (dry approx): {air_density(indoor_temp):.2f} kg/m³")
    if pulldown_l > 0:
        notes.append(f"One-time air pulldown: {pulldown_l:.1f} L")
    if pool_area_m2 > 0 and mode == "field_calibrated":
        std_pool = pool_evap_l_per_day(
            area_m2=pool_area_m2,
            water_c=water_temp_c if water_temp_c is not None else 28.0,
            air_c=indoor_temp,
            rh_target_pct=target_rh,
            mode="standard",
            air_movement_level=air_movement_level,
            activity=pool_activity,
            covered_h_per_day=covered_hours_per_day,
            cover_reduction=cover_reduction,
            custom_params=custom_params,
        )
        notes.append(f"Standard vs Field: pool {std_pool:.1f} L/d vs {pool_lpd:.1f} L/d (bias {field_bias}, min ratio {min_ratio_vs_standard})")
    if people_count > 0:
        notes.append(f"Occupants: {people_count} → {occupant_lpd:.1f} L/day")
    if pool_area_m2 > 0:
        notes.append(
            f"Pool: {pool_area_m2} m², water {water_temp_c if water_temp_c is not None else 28.0}°C → {pool_lpd:.1f} L/day"
        )
    if other_lpd > 0:
        notes.append(f"Additional loads: {other_lpd:.1f} L/day")

    return {
        "inputs": {
            "current_rh": current_rh,
            "target_rh": target_rh,
            "indoor_temp_c": indoor_temp,
            "length": dims["length"],
            "width": dims["width"],
            "height": dims["height"],
            "volume_m3": volume,
            "ach": ach,
            "people_count": people_count,
            "pool_area_m2": pool_area_m2,
            "water_temp_c": water_temp_c if water_temp_c is not None else 28.0,
            "pool_activity": pool_activity,
            "vent_factor": vent_factor,
            "additional_loads_lpd": other_lpd,
            "air_velocity_mps": air_velocity_mps,
        },
        "derived": {
            "room_area_m2": round(room_area_m2, 1) if room_area_m2 > 0 else None,
            "air_density": round(air_density(indoor_temp), 3),
        },
        "components": {
            "infiltration_lpd": round(infiltration_lpd, 1),
            "occupant_lpd": round(occupant_lpd, 1),
            "pool_lpd": round(pool_lpd, 1),
            "additional_lpd": round(other_lpd, 1),
        },
        "total_lpd": steady_total_lpd,
        "steady_latent_kw": latent_kw,
        "pulldown_air_l": pulldown_l,
        "plot_data": {
            "components": components,
            "load_vs_ach": load_vs_ach,
        },
        "notes": notes,
    }


