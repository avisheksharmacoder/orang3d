"""
Global Geotechnical Stability Solver for Retaining Walls (Phase 3).
Evaluates Factors of Safety (Sliding, Overturning, Bearing) under combined Static + Seismic loads.
Includes Meyerhof, Hansen, and Vesic ultimate bearing capacity and passive key resistance.
"""

import numpy as np
from typing import Tuple
from ..models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
)
from .mononobe_okabe import (
    compute_mononobe_okabe,
    compute_lateral_thrusts,
    compute_rankine_earth_pressures,
)


def compute_bearing_capacity_factors(phi_deg: float) -> Tuple[float, float, float]:
    """
    Computes bearing capacity factors Nc, Nq, Ngamma using the standard
    Prandtl (1921), Reissner (1924), and Vesic (1973) formulations.
    """
    if phi_deg <= 1e-4:
        return 5.14, 1.0, 0.0

    phi_rad = np.radians(phi_deg)
    # Nq = exp(pi * tan(phi)) * tan^2(45 + phi/2)
    n_q = float(np.exp(np.pi * np.tan(phi_rad)) * (np.tan(np.pi / 4.0 + phi_rad / 2.0) ** 2))
    # Nc = (Nq - 1) / tan(phi)
    n_c = float((n_q - 1.0) / np.tan(phi_rad))
    # Ngamma (Vesic 1973) = 2 * (Nq + 1) * tan(phi)
    n_gamma = float(2.0 * (n_q + 1.0) * np.tan(phi_rad))

    return n_c, n_q, n_gamma


def compute_ultimate_bearing_capacity(
    base_width: float,
    vertical_load: float,
    horizontal_load: float,
    eccentricity: float,
    embedment_depth: float,
    foundation_phi: float,
    foundation_cohesion: float,
    foundation_unit_weight: float,
) -> Tuple[float, float]:
    """
    Calculates ultimate bearing capacity (q_ult in kPa) and factor of safety
    incorporating effective width B', load inclination (Meyerhof), and depth factors.
    Returns: (q_ult, fs_bearing)
    """
    # 1. Effective width accounting for load eccentricity (Meyerhof)
    b_eff = max(0.1, base_width - 2.0 * abs(eccentricity))

    # 2. Bearing capacity factors
    nc, nq, n_gamma = compute_bearing_capacity_factors(foundation_phi)

    # 3. Overburden surcharge pressure at base level
    q_surcharge = foundation_unit_weight * max(0.0, embedment_depth)

    # 4. Load inclination factors (Meyerhof 1963)
    # theta_load in degrees
    psi_deg = float(np.degrees(np.arctan(abs(horizontal_load) / max(1e-3, vertical_load))))
    iq = max(0.0, (1.0 - psi_deg / 90.0) ** 2)
    if foundation_phi > 1e-3:
        igamma = max(0.0, (1.0 - psi_deg / foundation_phi) ** 2)
        ic = iq - (1.0 - iq) / max(1e-3, nc * np.tan(np.radians(foundation_phi)))
    else:
        igamma = 0.0
        ic = max(0.0, 1.0 - (2.0 * psi_deg) / (180.0 + 90.0 * (np.pi - 2.0)))

    # 5. Depth factors (Hansen)
    df_over_b = embedment_depth / b_eff
    if foundation_phi > 1e-3:
        phi_rad = np.radians(foundation_phi)
        dq = 1.0 + 2.0 * np.tan(phi_rad) * ((1.0 - np.sin(phi_rad)) ** 2) * min(1.0, df_over_b)
        dc = dq - (1.0 - dq) / (nc * np.tan(phi_rad))
    else:
        dq = 1.0
        dc = 1.0 + 0.4 * min(1.0, df_over_b)
    dgamma = 1.0

    # 6. Ultimate bearing capacity q_ult
    # q_ult = c * Nc * dc * ic + q * Nq * dq * iq + 0.5 * gamma * B' * Ngamma * dgamma * igamma
    term_c = foundation_cohesion * nc * dc * ic
    term_q = q_surcharge * nq * dq * iq
    term_gamma = 0.5 * foundation_unit_weight * b_eff * n_gamma * dgamma * igamma

    q_ult = float(term_c + term_q + term_gamma)

    # Effective average bearing demand
    q_demand = vertical_load / b_eff
    fs_bearing = float(q_ult / max(1e-3, q_demand))

    return q_ult, fs_bearing


def evaluate_wall_stability(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
) -> AnalysisResults:
    """
    Evaluates complete static and seismic limit-equilibrium stability of the retaining wall.
    Returns AnalysisResults dataclass.
    """
    # 1. Mononobe-Okabe earth pressure
    k_ae, k_a, delta_k_ae = compute_mononobe_okabe(
        phi_deg=soil.friction_angle,
        delta_deg=soil.wall_friction_angle,
        kh=seismic.horizontal_pga,
        kv=seismic.vertical_pga,
        beta_deg=seismic.backfill_slope,
        liquefaction_factor=seismic.liquefaction_factor,
    )

    H_total = geom.total_height
    total_thrust, thrust_h, p_water, _ = compute_lateral_thrusts(
        wall_height=H_total,
        gamma=soil.unit_weight,
        gamma_sat=soil.saturated_unit_weight,
        k_ae=k_ae,
        k_a=k_a,
        water_table_depth=seismic.water_table_depth,
        kv=seismic.vertical_pga,
    )

    # 2. Geometric Partitioning for Weight and Moments (per meter width)
    gamma_c = geom.concrete_unit_weight
    gamma_s = soil.unit_weight

    # Component 1: Base Footing Slab
    w_footing = geom.base_width * geom.footing_thickness * gamma_c
    x_footing = geom.base_width / 2.0
    y_footing = geom.footing_thickness / 2.0

    # Component 2: Stem (Trapezoid = rectangular core + triangular batter)
    t_top = geom.stem_thickness_top
    t_base = geom.stem_thickness_base
    h_stem = geom.stem_height

    w_stem_rect = t_top * h_stem * gamma_c
    x_stem_rect = geom.toe_length + (t_base - t_top) + t_top / 2.0
    y_stem_rect = geom.footing_thickness + h_stem / 2.0

    t_diff = max(0.0, t_base - t_top)
    w_stem_tri = 0.5 * t_diff * h_stem * gamma_c
    x_stem_tri = geom.toe_length + (2.0 / 3.0) * t_diff
    y_stem_tri = geom.footing_thickness + (1.0 / 3.0) * h_stem

    # Component 3: Shear Key (if active, depth > 0)
    w_key = geom.shear_key_width * geom.shear_key_depth * gamma_c
    x_key = geom.toe_length + t_base / 2.0
    y_key = -geom.shear_key_depth / 2.0

    # Component 4: Soil block resting on the Heel slab
    w_soil_heel = geom.heel_length * h_stem * gamma_s
    x_soil_heel = geom.toe_length + t_base + geom.heel_length / 2.0
    y_soil_heel = geom.footing_thickness + h_stem / 2.0

    # Total Weights
    w_concrete = w_footing + w_stem_rect + w_stem_tri + w_key
    total_vertical_dead = w_concrete + w_soil_heel

    # Effective vertical load under vertical seismic acceleration (1 - kv)
    kv_factor = max(0.1, 1.0 - seismic.vertical_pga)
    V_effective = total_vertical_dead * kv_factor

    # Concrete Center of Gravity (for horizontal wall inertia)
    x_cg_wall = (
        w_footing * x_footing
        + w_stem_rect * x_stem_rect
        + w_stem_tri * x_stem_tri
        + w_key * x_key
    ) / max(1e-3, w_concrete)
    y_cg_wall = (
        w_footing * y_footing
        + w_stem_rect * y_stem_rect
        + w_stem_tri * y_stem_tri
        + w_key * y_key
    ) / max(1e-3, w_concrete)

    # 3. Resisting and Overturning Moments around the Toe (0, 0)
    # Resisting Moments (Clockwise around toe)
    M_R = (
        w_footing * x_footing * kv_factor
        + w_stem_rect * x_stem_rect * kv_factor
        + w_stem_tri * x_stem_tri * kv_factor
        + w_key * x_key * kv_factor
        + w_soil_heel * x_soil_heel * kv_factor
    )

    # Overturning Moments (Counter-clockwise around toe)
    M_OT_thrust = total_thrust * thrust_h
    wall_inertia_force = w_concrete * seismic.horizontal_pga
    M_OT_inertia = wall_inertia_force * y_cg_wall
    M_OT = max(1e-3, M_OT_thrust + M_OT_inertia)

    # 4. Factors of Safety
    # A. Overturning Factor of Safety
    fs_overturning = float(M_R / M_OT)

    # B. Sliding Factor of Safety
    phi_b = np.radians(soil.foundation_friction_angle * 0.75)
    f_friction = np.tan(phi_b)
    c_adhesion = soil.foundation_cohesion * 0.6
    cohesion_force = c_adhesion * geom.base_width

    # Passive resistance in front of toe & shear key (Rankine passive)
    _, kp_fund = compute_rankine_earth_pressures(soil.foundation_friction_angle)
    depth_embedded = geom.footing_thickness + geom.shear_key_depth
    p_passive = 0.5 * soil.foundation_unit_weight * (depth_embedded ** 2) * kp_fund

    # If shear key exists, adds significant passive resistance across shear key depth
    if geom.shear_key_depth > 0:
        # Passive pressure acting on key front face
        y_top_key = geom.footing_thickness
        y_bot_key = geom.footing_thickness + geom.shear_key_depth
        p_key_passive = (
            0.5 * soil.foundation_unit_weight * (y_bot_key ** 2 - y_top_key ** 2) * kp_fund
        )
        p_passive += p_key_passive

    resisting_slide = V_effective * f_friction + cohesion_force + p_passive
    driving_slide = max(1e-3, total_thrust + wall_inertia_force)
    fs_sliding = float(resisting_slide / driving_slide)

    # C. Bearing Capacity & Contact Pressure
    x_resultant = (M_R - M_OT) / max(1e-3, V_effective)
    b_base = geom.base_width
    eccentricity = (b_base / 2.0) - x_resultant

    # Contact pressures (Trapezoidal / Triangular distribution)
    if abs(eccentricity) <= b_base / 6.0:
        q_toe = (V_effective / b_base) * (1.0 + (6.0 * eccentricity / b_base))
        q_heel = (V_effective / b_base) * (1.0 - (6.0 * eccentricity / b_base))
    else:
        dist_to_toe = max(0.1, x_resultant)
        q_toe = (2.0 * V_effective) / (3.0 * dist_to_toe)
        q_heel = 0.0

    q_max = max(0.0, q_toe)
    q_min = max(0.0, q_heel)

    # Comprehensive Ultimate Bearing Capacity calculation
    q_ult, fs_bearing_calc = compute_ultimate_bearing_capacity(
        base_width=b_base,
        vertical_load=V_effective,
        horizontal_load=driving_slide,
        eccentricity=eccentricity,
        embedment_depth=geom.footing_thickness,
        foundation_phi=soil.foundation_friction_angle,
        foundation_cohesion=soil.foundation_cohesion,
        foundation_unit_weight=soil.foundation_unit_weight,
    )
    # Check against allowable capacity or ultimate capacity factor
    fs_bearing = float(min(fs_bearing_calc, soil.allowable_bearing_capacity / max(1e-3, q_max)))

    # 5. Structural Demands at Stem Base Junction
    p_stem_thrust, h_stem_thrust, _, _ = compute_lateral_thrusts(
        wall_height=h_stem,
        gamma=soil.unit_weight,
        gamma_sat=soil.saturated_unit_weight,
        k_ae=k_ae,
        k_a=k_a,
        water_table_depth=max(0.0, seismic.water_table_depth - geom.footing_thickness),
        kv=seismic.vertical_pga,
    )
    stem_inertia = (w_stem_rect + w_stem_tri) * seismic.horizontal_pga
    max_moment = (p_stem_thrust * h_stem_thrust) + (stem_inertia * (h_stem / 3.0))
    max_shear = p_stem_thrust + stem_inertia

    # Elastic flexural tensile stress at stem base: sigma = M / Z
    section_modulus = (1.0 * (t_base ** 2)) / 6.0
    sigma_tension = (max_moment / max(1e-3, section_modulus)) / 1000.0  # Convert kPa to MPa
    cracked = sigma_tension > 2.8

    return AnalysisResults(
        k_ae=round(k_ae, 4),
        k_a_static=round(k_a, 4),
        delta_k_ae=round(delta_k_ae, 4),
        total_thrust=round(total_thrust, 2),
        thrust_height=round(thrust_h, 2),
        water_thrust=round(p_water, 2),
        fs_sliding=round(fs_sliding, 3),
        fs_overturning=round(fs_overturning, 3),
        fs_bearing=round(fs_bearing, 3),
        max_bearing_pressure=round(q_max, 1),
        min_bearing_pressure=round(q_min, 1),
        eccentricity=round(eccentricity, 3),
        max_bending_moment=round(max_moment, 2),
        max_shear_force=round(max_shear, 2),
        concrete_tensile_stress=round(sigma_tension, 2),
        cracking_predicted=cracked,
    )
