"""
Mononobe-Okabe (M-O) dynamic earth pressure solver and hydrodynamic thrust (Phase 3).
Reference: Seed & Whitman (1970), Kramer (1996) Geotechnical Earthquake Engineering,
Rankine (1857), Coulomb (1776).
"""

import numpy as np
from typing import Tuple


def compute_rankine_earth_pressures(phi_deg: float, c: float = 0.0) -> Tuple[float, float]:
    """
    Computes Rankine static active (Ka) and passive (Kp) earth pressure coefficients.
    Ka = (1 - sin(phi)) / (1 + sin(phi)) = tan^2(45 - phi/2)
    Kp = (1 + sin(phi)) / (1 - sin(phi)) = tan^2(45 + phi/2)
    """
    phi_rad = np.radians(phi_deg)
    sin_phi = np.sin(phi_rad)
    denom = max(1e-6, 1.0 + sin_phi)
    k_a = (1.0 - sin_phi) / denom
    k_p = (1.0 + sin_phi) / max(1e-6, 1.0 - sin_phi)
    return float(k_a), float(k_p)


def compute_coulomb_earth_pressures(
    phi_deg: float,
    delta_deg: float,
    beta_deg: float = 0.0,
    theta_deg: float = 0.0,
) -> Tuple[float, float]:
    """
    Computes Coulomb static active (Ka) and passive (Kp) earth pressure coefficients.
    theta: Angle of wall backface from vertical (0 = vertical)
    beta: Backfill slope angle from horizontal
    delta: Interface wall friction angle
    """
    phi = np.radians(phi_deg)
    delta = np.radians(delta_deg)
    beta = np.radians(beta_deg)
    theta = np.radians(theta_deg)

    # Active coefficient Ka
    num_a = np.cos(phi - theta) ** 2
    denom_a_base = np.cos(theta) ** 2 * np.cos(delta + theta)
    inner_root_a = (np.sin(phi + delta) * np.sin(phi - beta)) / max(
        1e-6, np.cos(delta + theta) * np.cos(beta - theta)
    )
    if inner_root_a < 0:
        k_a = 1.0
    else:
        k_a = num_a / (denom_a_base * ((1.0 + np.sqrt(inner_root_a)) ** 2))

    # Passive coefficient Kp
    num_p = np.cos(phi + theta) ** 2
    denom_p_base = np.cos(theta) ** 2 * np.cos(delta - theta)
    inner_root_p = (np.sin(phi + delta) * np.sin(phi + beta)) / max(
        1e-6, np.cos(delta - theta) * np.cos(beta - theta)
    )
    if inner_root_p < 0 or (1.0 - np.sqrt(inner_root_p)) <= 1e-4:
        # High friction angle cap
        k_p = 1.0 / max(1e-4, k_a)
    else:
        k_p = num_p / (denom_p_base * ((1.0 - np.sqrt(inner_root_p)) ** 2))

    return float(k_a), float(k_p)


def compute_liquefaction_degradation(
    phi_deg: float,
    cohesion: float,
    r_u: float,
) -> Tuple[float, float]:
    """
    Non-linear degradation of effective soil shear strength parameters
    as excess pore water pressure ratio r_u -> 1.0.
    tan(phi') = (1 - r_u) * tan(phi)
    c' = (1 - r_u) * c
    """
    ru_clamped = float(np.clip(r_u, 0.0, 1.0))
    phi_rad = np.radians(phi_deg)
    tan_phi_eff = (1.0 - ru_clamped) * np.tan(phi_rad)
    phi_eff_deg = float(np.degrees(np.arctan(max(0.0, tan_phi_eff))))
    c_eff = float(max(0.0, (1.0 - ru_clamped) * cohesion))
    return phi_eff_deg, c_eff


def compute_mononobe_okabe(
    phi_deg: float,
    delta_deg: float,
    kh: float,
    kv: float,
    beta_deg: float = 0.0,
    wall_slope_deg: float = 0.0,
    liquefaction_factor: float = 0.0,
) -> Tuple[float, float, float]:
    """
    Computes:
    - K_ae: Dynamic active earth pressure coefficient
    - K_a: Static active earth pressure coefficient
    - delta_K_ae: Seismic active pressure increment (K_ae - K_a)
    """
    # Degrade friction angle under liquefaction
    effective_phi_deg, _ = compute_liquefaction_degradation(phi_deg, 0.0, liquefaction_factor)
    effective_delta_deg = min(delta_deg, effective_phi_deg * (2.0 / 3.0))

    phi = np.radians(max(1.0, effective_phi_deg))
    delta = np.radians(effective_delta_deg)
    beta = np.radians(beta_deg)
    theta = np.radians(wall_slope_deg)  # Vertical wall = 0

    # Seismic inertia angle: theta_e = arctan(kh / (1 - kv))
    denom_inertia = max(0.01, 1.0 - kv)
    theta_e = np.arctan(kh / denom_inertia)

    def calc_mo(t_e: float) -> float:
        num = np.cos(phi - t_e - theta) ** 2
        term1 = np.cos(t_e) * (np.cos(theta) ** 2) * np.cos(delta + theta + t_e)

        sin_part1 = np.sin(phi + delta)
        sin_part2 = np.sin(phi - t_e - beta)
        cos_part1 = np.cos(delta + theta + t_e)
        cos_part2 = np.cos(beta - theta)

        inner_root = (sin_part1 * sin_part2) / max(1e-6, (cos_part1 * cos_part2))

        if inner_root < 0:
            return 1.8  # Physical limit reached: severe plastic soil failure

        denom = term1 * ((1.0 + np.sqrt(inner_root)) ** 2)
        if denom <= 1e-6:
            return 1.8

        return float(np.clip(num / denom, 0.1, 2.5))

    k_ae = calc_mo(theta_e)
    k_a = calc_mo(0.0)
    delta_k_ae = max(0.0, k_ae - k_a)

    return float(k_ae), float(k_a), float(delta_k_ae)


def compute_lateral_thrusts(
    wall_height: float,
    gamma: float,
    gamma_sat: float,
    k_ae: float,
    k_a: float,
    water_table_depth: float,
    kv: float = 0.0,
    gamma_water: float = 9.81,
) -> Tuple[float, float, float, float]:
    """
    Computes total dynamic soil thrust and hydrostatic water pressure.
    Returns:
    - total_thrust: P_ae (kN per m width)
    - thrust_height: Height of resultant thrust above base of wall (m)
    - water_thrust: P_w hydrostatic thrust (kN/m)
    - water_height: Height of water resultant above base (m)
    """
    H = wall_height
    H_w_depth = np.clip(water_table_depth, 0.0, H)
    h_submerged = H - H_w_depth  # Height of water column behind wall

    effective_unit_weight = (
        gamma
        if h_submerged <= 0.0
        else (gamma * (H_w_depth / H) + (gamma_sat - gamma_water) * (h_submerged / H))
    )

    seismic_factor = max(0.01, 1.0 - kv)
    p_a_static = 0.5 * effective_unit_weight * (H ** 2) * k_a
    delta_p_ae = 0.5 * effective_unit_weight * (H ** 2) * max(0.0, k_ae - k_a) * seismic_factor

    # Hydrostatic water thrust
    p_water = 0.5 * gamma_water * (h_submerged ** 2)
    h_water_resultant = h_submerged / 3.0

    # Seed & Whitman resultant height:
    # Static component acts at H/3
    # Dynamic increment acts at 0.6 * H
    total_soil_thrust = p_a_static + delta_p_ae
    if total_soil_thrust > 1e-3:
        h_soil_resultant = (p_a_static * (H / 3.0) + delta_p_ae * (0.6 * H)) / total_soil_thrust
    else:
        h_soil_resultant = H / 3.0

    total_combined_thrust = total_soil_thrust + p_water
    if total_combined_thrust > 1e-3:
        overall_height = (
            total_soil_thrust * h_soil_resultant + p_water * h_water_resultant
        ) / total_combined_thrust
    else:
        overall_height = H / 3.0

    return (
        float(total_combined_thrust),
        float(overall_height),
        float(p_water),
        float(h_water_resultant),
    )
