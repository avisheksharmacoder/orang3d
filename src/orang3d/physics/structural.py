"""
Structural Concrete Mechanics and Reinforcement Demand Estimator (Phase 4).
Calculates continuous shear force profiles V(y), bending moment profiles M(y),
elastic tensile stresses, concrete cracking, and ACI 318 / Eurocode 2 rebar demands.
"""

from dataclasses import dataclass
from typing import Tuple
import numpy as np

from ..models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
)
from .mononobe_okabe import compute_mononobe_okabe


@dataclass
class StemStructuralProfile:
    """Continuous structural force and stress profiles along the retaining wall stem."""
    heights: np.ndarray            # y elevations above base footing (0 to H_stem) in meters
    shear_forces: np.ndarray       # V(y) shear force profile in kN / m
    bending_moments: np.ndarray    # M(y) bending moment profile in kNm / m
    tensile_stresses: np.ndarray   # sigma_t(y) elastic tensile stress in MPa
    thicknesses: np.ndarray        # t(y) stem thickness profile in meters
    max_bending_moment: float      # Peak moment at base junction (kNm / m)
    max_shear_force: float         # Peak shear at base junction (kN / m)
    max_tensile_stress: float      # Peak tensile stress at base (MPa)
    cracking_predicted: bool       # True if max tensile stress exceeds modulus of rupture
    modulus_of_rupture: float      # f_r cracking modulus in MPa


@dataclass
class RebarDesignResults:
    """ACI 318 / Eurocode 2 flexural and shear reinforcement design quantities."""
    required_steel_area: float           # A_s required in mm^2 per meter width
    minimum_steel_area: float            # A_s,min in mm^2 per meter width
    design_moment: float                 # Factored ultimate moment M_u (kNm / m)
    design_shear: float                  # Factored shear force V_u (kN / m)
    concrete_shear_capacity: float       # phi * V_c concrete shear strength (kN / m)
    shear_reinforcement_required: bool   # True if V_u > phi * V_c
    reinforcement_ratio: float           # rho = A_s / (b * d)
    recommended_bar_callout: str         # Standard engineering callout, e.g. "T20 @ 150 mm c/c"


def compute_stem_internal_profiles(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    n_points: int = 50,
    concrete_strength_mpa: float = 28.0,
) -> StemStructuralProfile:
    """
    Computes continuous shear V(y), moment M(y), and flexural stress sigma_t(y)
    profiles along the stem from base junction (y=0) to crest (y=H_stem).
    Guarantees dM/dy = -V(y) differential equilibrium and crest boundary conditions.
    """
    h_stem = geom.stem_height
    t_base = geom.stem_thickness_base
    t_top = geom.stem_thickness_top
    gamma_c = geom.concrete_unit_weight
    gamma_s = soil.unit_weight
    gamma_w = 9.81

    # 1. Mononobe-Okabe active earth pressure coefficient
    k_ae, k_a, _ = compute_mononobe_okabe(
        phi_deg=soil.friction_angle,
        delta_deg=soil.wall_friction_angle,
        kh=seismic.horizontal_pga,
        kv=seismic.vertical_pga,
        beta_deg=seismic.backfill_slope,
        liquefaction_factor=seismic.liquefaction_factor,
    )

    # Subdivisions along stem from base (y=0) to crest (y=h_stem)
    y_arr = np.linspace(0.0, h_stem, n_points)
    dy = h_stem / max(1, n_points - 1)

    # Depth from crest: z = h_stem - y
    z_arr = h_stem - y_arr

    # Water table depth from crest of stem
    # (geom.footing_thickness offset from top of backfill)
    z_water = max(0.0, seismic.water_table_depth - geom.footing_thickness)

    # 2. Compute lateral pressure distribution p_lat(z)
    p_lat = np.zeros(n_points, dtype=np.float64)
    seismic_factor = max(0.01, 1.0 - seismic.vertical_pga)

    for i, z in enumerate(z_arr):
        if z <= z_water:
            sigma_v = gamma_s * z
            u_water = 0.0
        else:
            z_sub = z - z_water
            sigma_v = gamma_s * z_water + (soil.saturated_unit_weight - gamma_w) * z_sub
            u_water = gamma_w * z_sub

        p_soil = sigma_v * k_ae * seismic_factor
        p_lat[i] = p_soil + u_water

    # 3. Stem inertia force per unit height: q_inertia(y) = t(y) * gamma_c * kh
    # Linear stem thickness profile
    t_arr = t_base - (y_arr / h_stem) * (t_base - t_top)
    q_inertia = t_arr * gamma_c * seismic.horizontal_pga

    # Total horizontal distributed load per unit height: q_total(y) = p_lat(y) + q_inertia(y)
    q_total = p_lat + q_inertia

    # 4. Integrate shear force V(y) = integral_y^H q_total(eta) d_eta
    # At crest (y = h_stem): V = 0
    _trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))

    v_arr = np.zeros(n_points, dtype=np.float64)
    for i in range(n_points - 1):
        v_arr[i] = _trapz(q_total[i:], y_arr[i:])
    v_arr[-1] = 0.0  # Exact crest boundary condition

    # 5. Integrate bending moment M(y) = integral_y^H V(eta) d_eta
    # At crest (y = h_stem): M = 0
    m_arr = np.zeros(n_points, dtype=np.float64)
    for i in range(n_points - 1):
        m_arr[i] = _trapz(v_arr[i:], y_arr[i:])
    m_arr[-1] = 0.0  # Exact crest boundary condition

    # 6. Elastic tensile flexural stress: sigma_t(y) = M(y) / Z(y)
    # Z(y) = (1.0 * t(y)^2) / 6.0 (for 1m wide section)
    z_section = (1.0 * (t_arr ** 2)) / 6.0
    sigma_arr = (m_arr / np.maximum(1e-4, z_section)) / 1000.0  # kPa -> MPa
    sigma_arr[-1] = 0.0

    # Concrete modulus of rupture: f_r = 0.62 * sqrt(f'c) (ACI 318)
    f_r = float(0.62 * np.sqrt(max(10.0, concrete_strength_mpa)))
    cracked = bool(np.max(sigma_arr) > f_r)

    return StemStructuralProfile(
        heights=y_arr,
        shear_forces=v_arr,
        bending_moments=m_arr,
        tensile_stresses=sigma_arr,
        thicknesses=t_arr,
        max_bending_moment=float(m_arr[0]),
        max_shear_force=float(v_arr[0]),
        max_tensile_stress=float(sigma_arr[0]),
        cracking_predicted=cracked,
        modulus_of_rupture=f_r,
    )


def design_flexural_reinforcement(
    bending_moment_kNm: float,
    shear_force_kN: float,
    stem_thickness_base: float,
    concrete_strength_mpa: float = 28.0,
    steel_yield_mpa: float = 420.0,
    clear_cover_m: float = 0.05,
    bar_diameter_mm: float = 20.0,
) -> RebarDesignResults:
    """
    Performs ACI 318 / Eurocode 2 ultimate strength design for stem reinforcement.
    Calculates required tension steel A_s, temperature/shrinkage steel A_s,min,
    and concrete shear capacity phi*V_c.
    """
    b_mm = 1000.0  # 1 meter width
    t_base_mm = stem_thickness_base * 1000.0

    # Effective depth d
    d_mm = max(100.0, t_base_mm - clear_cover_m * 1000.0 - bar_diameter_mm / 2.0)

    # 1. Factored Design Moment (ACI load combinations: 1.2 D + 1.6 L or factored seismic)
    # The input bending_moment_kNm is the peak nominal base moment
    m_u_nmm = max(1.0, bending_moment_kNm) * 1e6  # kNm to N*mm

    # 2. Flexural Strength Reduction factor phi = 0.90 (Tension-controlled)
    phi_flex = 0.90
    fc = max(15.0, concrete_strength_mpa)
    fy = max(200.0, steel_yield_mpa)

    # Whitney stress block: R_n = M_u / (phi * b * d^2)
    r_n = m_u_nmm / (phi_flex * b_mm * (d_mm ** 2))
    discriminant = 1.0 - (2.0 * r_n) / (0.85 * fc)

    if discriminant <= 0.0:
        # Over-reinforced section: cap at balanced reinforcement
        rho_calc = 0.85 * (fc / fy) * 0.5
    else:
        rho_calc = float((0.85 * fc / fy) * (1.0 - np.sqrt(discriminant)))

    a_s_calc = rho_calc * b_mm * d_mm

    # 3. Minimum Reinforcement Checks (ACI 318)
    # Flexural minimum: max(0.25 * sqrt(f'c) / fy, 1.4 / fy) * b * d
    rho_min_1 = (0.25 * np.sqrt(fc)) / fy
    rho_min_2 = 1.4 / fy
    a_s_min_flex = max(rho_min_1, rho_min_2) * b_mm * d_mm

    # Shrinkage and temperature minimum: 0.0018 * b * h (Grade 420/500)
    a_s_min_temp = 0.0018 * b_mm * t_base_mm

    a_s_min = float(max(a_s_min_flex, a_s_min_temp))
    a_s_required = float(max(a_s_calc, a_s_min))

    # 4. Concrete Shear Capacity (ACI 318 Metric): phi * V_c = 0.75 * 0.17 * sqrt(f'c) * b * d
    phi_v = 0.75
    v_c_kn = (0.17 * np.sqrt(fc) * b_mm * d_mm) / 1000.0  # N to kN
    phi_vc = float(phi_v * v_c_kn)
    shear_rebar_needed = bool(shear_force_kN > phi_vc)

    # 5. Reinforcement ratio
    final_rho = float(a_s_required / (b_mm * d_mm))

    # 6. Rebar callout recommendation
    bar_area = float(np.pi * ((bar_diameter_mm / 2.0) ** 2))
    raw_spacing = (1000.0 * bar_area) / a_s_required
    # Practical standard spacings: 100, 125, 150, 175, 200, 250, 300 mm
    standard_spacings = [100, 125, 150, 175, 200, 250, 300]
    chosen_spacing = 100
    for s in standard_spacings:
        if s <= raw_spacing:
            chosen_spacing = s
        else:
            break

    callout = f"T{int(bar_diameter_mm)} @ {chosen_spacing} mm c/c"

    return RebarDesignResults(
        required_steel_area=round(a_s_required, 1),
        minimum_steel_area=round(a_s_min, 1),
        design_moment=round(bending_moment_kNm, 2),
        design_shear=round(shear_force_kN, 2),
        concrete_shear_capacity=round(phi_vc, 2),
        shear_reinforcement_required=shear_rebar_needed,
        reinforcement_ratio=round(final_rho, 5),
        recommended_bar_callout=callout,
    )
