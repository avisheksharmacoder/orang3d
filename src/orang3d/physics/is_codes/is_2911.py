"""
IS 2911 (Part 1/Sec 2: 2010): Design and Construction of Pile Foundations - Bored Cast-in-Situ Concrete Piles.
Geotechnical Axial Load Capacity (Appendix B), Lateral Capacity and Depth of Fixity (Appendix C),
and Structural Rebar Detailing (Clause 6.11).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple, Optional, Any, Dict
import numpy as np


# IS 2911 Table 1: Bearing Capacity Factors for Deep Foundations (Berezantsev / Meyerhof)
IS2911_BEARING_FACTORS: list[tuple[float, float, float]] = [
    # phi (deg), N_q, N_gamma
    (20.0, 4.4, 2.0),
    (25.0, 8.5, 6.0),
    (28.0, 12.5, 10.0),
    (30.0, 16.5, 15.0),
    (32.0, 22.0, 22.0),
    (35.0, 31.0, 35.0),
    (38.0, 48.0, 58.0),
    (40.0, 65.0, 80.0),
]


def interpolate_is2911_factors(phi_deg: float) -> Tuple[float, float, float]:
    """
    Interpolates deep foundation bearing capacity factors N_c, N_q, N_gamma per IS 2911 Table 1.
    For phi=0, returns (9.0, 1.0, 0.0) per IS 2911 Appendix B.
    """
    if phi_deg <= 0.0:
        return 9.0, 1.0, 0.0

    phi_clamped = max(20.0, min(phi_deg, 40.0))
    phis = [row[0] for row in IS2911_BEARING_FACTORS]
    nqs = [row[1] for row in IS2911_BEARING_FACTORS]
    ngammas = [row[2] for row in IS2911_BEARING_FACTORS]

    nq = float(np.interp(phi_clamped, phis, nqs))
    ngamma = float(np.interp(phi_clamped, phis, ngammas))

    # Nc from Prandtl / Meyerhof relation for deep foundation: Nc = (Nq - 1) * cot(phi)
    phi_rad = math.radians(phi_clamped)
    nc = (nq - 1.0) / math.tan(phi_rad)
    return nc, nq, ngamma


def get_is2911_adhesion_factor(c_u_kPa: float) -> float:
    """
    Evaluates shaft adhesion factor alpha for cohesive soils per IS 2911 Table 2:
    cu <= 25 kPa -> alpha = 0.70
    cu = 50 kPa  -> alpha = 0.50
    cu = 75 kPa  -> alpha = 0.40
    cu = 100 kPa -> alpha = 0.35
    cu >= 150 kPa -> alpha = 0.30
    """
    c_pts = [0.0, 25.0, 50.0, 75.0, 100.0, 150.0]
    alpha_pts = [0.70, 0.70, 0.50, 0.40, 0.35, 0.30]
    return float(np.interp(c_u_kPa, c_pts, alpha_pts))


@dataclass
class IS2911AxialCapacityResult:
    """Vertical axial geotechnical capacity per IS 2911 (Part 1/Sec 2) Appendix B."""
    ultimate_end_bearing: float    # Q_b: Ultimate tip end-bearing capacity (kN)
    ultimate_skin_friction: float  # Q_s: Ultimate shaft skin friction (kN)
    ultimate_capacity: float       # Q_u = Q_b + Q_s (kN)
    safe_capacity: float           # Q_safe = Q_u / FS (kN)
    factor_of_safety: float        # Applied factor of safety (2.5 static, 2.0 seismic)
    applied_axial_load: float      # Factored/service design axial load P (kN)
    end_bearing_stress: float      # q_b = Q_b / A_p (kPa)
    avg_skin_friction: float       # f_s = Q_s / A_s (kPa)
    unity_ratio: float             # P / Q_safe
    status: str                    # 'PASS' or 'FAIL'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ultimate_end_bearing_kN": self.ultimate_end_bearing,
            "ultimate_skin_friction_kN": self.ultimate_skin_friction,
            "ultimate_capacity_kN": self.ultimate_capacity,
            "safe_capacity_kN": self.safe_capacity,
            "factor_of_safety": self.factor_of_safety,
            "applied_axial_load_kN": self.applied_axial_load,
            "end_bearing_stress_kPa": self.end_bearing_stress,
            "avg_skin_friction_kPa": self.avg_skin_friction,
            "unity_ratio": self.unity_ratio,
            "status": self.status,
        }


@dataclass
class IS2911LateralCapacityResult:
    """Lateral load capacity and depth of fixity per IS 2911 Appendix C."""
    stiffness_factor_T: float      # T (m) for sand / NC clay, or R (m) for preloaded clay
    depth_of_fixity_zf: float      # Depth of virtual fixity below ground level z_f (m)
    safe_lateral_capacity: float   # Safe permissible lateral shear H_safe (kN)
    applied_lateral_shear: float   # Applied design lateral load H (kN)
    allowable_deflection: float    # Permissible lateral deflection at pile head (m, 0.005 m = 5 mm)
    estimated_deflection: float    # Predicted lateral deflection under applied H (m)
    unity_ratio: float             # H / H_safe
    status: str                    # 'PASS' or 'FAIL'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stiffness_factor_T_m": self.stiffness_factor_T,
            "depth_of_fixity_zf_m": self.depth_of_fixity_zf,
            "safe_lateral_capacity_kN": self.safe_lateral_capacity,
            "applied_lateral_shear_kN": self.applied_lateral_shear,
            "allowable_deflection_mm": self.allowable_deflection * 1000.0,
            "estimated_deflection_mm": self.estimated_deflection * 1000.0,
            "unity_ratio": self.unity_ratio,
            "status": self.status,
        }


@dataclass
class IS2911StructuralPileDesign:
    """Structural concrete and reinforcement cage detailing per IS 2911 Clause 6.11."""
    pile_diameter_mm: float
    pile_length_m: float
    concrete_grade: str
    steel_grade: str
    gross_area_mm2: float
    a_st_min_mm2: float            # 0.4% minimum longitudinal steel
    a_st_provided_mm2: float       # Provided longitudinal rebar area
    longitudinal_ratio_percent: float # Ast / Ag (%)
    rebar_cage_callout: str        # e.g. '12-T25 bars uniformly distributed'
    helical_binder_callout: str    # e.g. 'T10 helical binder @ 100 mm pitch'
    axial_structural_capacity_kN: float # Factored axial capacity Puz
    unity_ratio: float             # Applied P / Puz
    status: str                    # 'PASS' or 'FAIL'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pile_diameter_mm": self.pile_diameter_mm,
            "pile_length_m": self.pile_length_m,
            "concrete_grade": self.concrete_grade,
            "steel_grade": self.steel_grade,
            "gross_area_mm2": self.gross_area_mm2,
            "a_st_min_mm2": self.a_st_min_mm2,
            "a_st_provided_mm2": self.a_st_provided_mm2,
            "longitudinal_ratio_percent": self.longitudinal_ratio_percent,
            "rebar_cage_callout": self.rebar_cage_callout,
            "helical_binder_callout": self.helical_binder_callout,
            "axial_structural_capacity_kN": self.axial_structural_capacity_kN,
            "unity_ratio": self.unity_ratio,
            "status": self.status,
        }


def calculate_is2911_axial_capacity(
    pile_diameter_m: float,
    pile_length_m: float,
    cohesion_kPa: float,
    friction_angle_deg: float,
    unit_weight_kNm3: float,
    applied_axial_kN: float = 0.0,
    k_earth_pressure: float = 1.0,
    is_seismic: bool = False,
    critical_depth_ratio: float = 15.0,
) -> IS2911AxialCapacityResult:
    """
    Computes ultimate and safe vertical axial load capacity for bored cast-in-situ piles
    in c-phi soil per IS 2911 (Part 1/Sec 2: 2010 Appendix B):
        Qu = Qb + Qs
        Qb = Ap * (c * Nc + sigma'_v * Nq + 0.5 * gamma * Dp * N_gamma)
        Qs = sum [ (alpha * c_i + K * sigma'_vi * tan(delta)) * As_i ]
    """
    d_p = pile_diameter_m
    l_p = pile_length_m
    gamma = unit_weight_kNm3
    c = cohesion_kPa
    phi = friction_angle_deg

    if d_p <= 0 or l_p <= 0:
        raise ValueError(f"Pile dimensions must be positive, got Dp={d_p}, Lp={l_p}")

    # Pile geometry
    a_p = (math.pi / 4.0) * (d_p ** 2) # Base tip area (m2)
    perimeter = math.pi * d_p          # Shaft perimeter (m)
    a_s = perimeter * l_p              # Total shaft surface area (m2)

    # Critical depth for overburden stress: z_cr = 15 * Dp (IS 2911 Cl. B-1.2)
    z_cr = min(critical_depth_ratio * d_p, l_p)
    sigma_v_tip = gamma * z_cr

    # Bearing capacity factors
    nc, nq, ngamma = interpolate_is2911_factors(phi)

    # 1. End Bearing Qb
    # For bored piles in sand, IS 2911 limits tip resistance stress or uses conservative Nq
    if phi == 0.0:
        q_b_stress = 9.0 * c # 9 * cu
    else:
        q_b_stress = c * nc + sigma_v_tip * nq + 0.5 * gamma * d_p * ngamma
    
    q_b = a_p * q_b_stress # kN

    # 2. Shaft Skin Friction Qs
    # Discretize shaft into depth slices to integrate overburden
    n_slices = 20
    dz = l_p / float(n_slices)
    q_s = 0.0
    delta_rad = math.radians(0.75 * phi) if phi > 0 else 0.0
    alpha = get_is2911_adhesion_factor(c) if c > 0 else 0.0

    for i in range(n_slices):
        z_mid = (i + 0.5) * dz
        z_eff = min(z_mid, z_cr)
        sigma_v_mid = gamma * z_eff
        
        # Skin friction stress f_si = alpha * c + K * sigma_vi * tan(delta)
        f_si = alpha * c + k_earth_pressure * sigma_v_mid * math.tan(delta_rad)
        # Cap skin friction for bored piles in sand per standard practice (e.g. 100-120 kPa)
        f_si = min(f_si, 120.0)
        
        area_slice = perimeter * dz
        q_s += f_si * area_slice

    q_u = q_b + q_s

    # Factor of Safety: 2.5 for static, 2.0 for seismic (IS 2911 Cl. 6.1)
    fs = 2.0 if is_seismic else 2.5
    q_safe = q_u / fs

    p_applied = abs(applied_axial_kN)
    unity_ratio = p_applied / max(q_safe, 1e-3)
    status = "PASS" if unity_ratio <= 1.0 else "FAIL"

    return IS2911AxialCapacityResult(
        ultimate_end_bearing=float(q_b),
        ultimate_skin_friction=float(q_s),
        ultimate_capacity=float(q_u),
        safe_capacity=float(q_safe),
        factor_of_safety=float(fs),
        applied_axial_load=float(p_applied),
        end_bearing_stress=float(q_b_stress),
        avg_skin_friction=float(q_s / max(a_s, 1e-4)),
        unity_ratio=float(unity_ratio),
        status=status,
    )


def calculate_is2911_lateral_capacity(
    pile_diameter_m: float,
    pile_length_m: float,
    f_ck: float,
    subgrade_modulus_nh_kNm3: float = 6000.0,
    applied_lateral_kN: float = 0.0,
    cantilever_length_m: float = 0.0,
    allowable_deflection_m: float = 0.005,
    fixed_head: bool = True,
) -> IS2911LateralCapacityResult:
    """
    Computes lateral pile capacity and depth of fixity per IS 2911 Appendix C:
        Stiffness factor T = (Ep * Ip / eta_h)^(1/5)
        Depth of fixity z_f = 2.0 * T to 2.2 * T for fixed head in sand/NC clay
        Allowable lateral shear H_safe = 12 * Ep * Ip * y_allow / (z_f + e1)^3
    """
    d_p = pile_diameter_m
    l_p = pile_length_m

    # Concrete modulus Ep = 5000 * sqrt(fck) in MPa -> convert to kN/m2 (* 1000)
    e_p_kN_m2 = 5000.0 * math.sqrt(f_ck) * 1000.0
    i_p = (math.pi * (d_p ** 4)) / 64.0 # m4
    ep_ip = e_p_kN_m2 * i_p # kNm2

    eta_h = max(subgrade_modulus_nh_kNm3, 100.0) # kN/m3
    # Stiffness factor T = (Ep * Ip / eta_h)^0.2
    t_m = (ep_ip / eta_h) ** 0.2

    # Depth of fixity z_f per IS 2911 Table 2 / Fig. 2
    # For fixed-head pile in sand: z_f = 2.0 * T
    # For free-head pile: z_f = 2.2 * T
    multiplier = 2.0 if fixed_head else 2.2
    z_f = min(multiplier * t_m, l_p)

    # Effective length L_eff = z_f + e1
    l_eff = z_f + cantilever_length_m

    # For fixed-head pile: Deflection y = H * L_eff^3 / (12 * Ep * Ip)
    # H_safe = 12 * Ep * Ip * y_allow / L_eff^3
    coeff = 12.0 if fixed_head else 3.0
    h_safe = (coeff * ep_ip * allowable_deflection_m) / (l_eff ** 3)

    h_applied = abs(applied_lateral_kN)
    y_est = (h_applied * (l_eff ** 3)) / (coeff * ep_ip)

    unity_ratio = h_applied / max(h_safe, 1e-4)
    status = "PASS" if unity_ratio <= 1.0 else "FAIL"

    return IS2911LateralCapacityResult(
        stiffness_factor_T=float(t_m),
        depth_of_fixity_zf=float(z_f),
        safe_lateral_capacity=float(h_safe),
        applied_lateral_shear=float(h_applied),
        allowable_deflection=float(allowable_deflection_m),
        estimated_deflection=float(y_est),
        unity_ratio=float(unity_ratio),
        status=status,
    )


def design_is2911_structural_pile(
    pile_diameter_m: float,
    pile_length_m: float,
    f_ck: float,
    f_y: float,
    applied_axial_kN: float,
    min_longitudinal_ratio: float = 0.004,
) -> IS2911StructuralPileDesign:
    """
    Designs structural reinforcement cage for bored cast-in-situ pile per IS 2911 Cl. 6.11:
    - Minimum longitudinal reinforcement: 0.4% of gross area
    - Maximum longitudinal reinforcement: 1.25% to prevent tremie pipe blockage
    - Helical binder: >= 8 mm bar at <= 150 mm pitch (100 mm in top zone)
    - Factored axial structural capacity: Puz = 0.4 * fck * Ac + 0.67 * fy * Asc
    """
    d_p_mm = pile_diameter_m * 1000.0
    a_gross = (math.pi / 4.0) * (d_p_mm ** 2)

    # Ast min = 0.4% of Ag (Cl. 6.11.2)
    a_st_min = min_longitudinal_ratio * a_gross

    # Bar selection: try 16, 20, 25, 32 mm bars
    target_ast = a_st_min
    selected_dia = 25
    selected_num = 8
    best_ast = (math.pi / 4.0) * (selected_dia ** 2) * selected_num

    for dia in [16, 20, 25, 32]:
        single_bar = (math.pi / 4.0) * (dia ** 2)
        n_bars = math.ceil(target_ast / single_bar)
        # Minimum 6 bars for circular pile (IS 456 Cl. 26.5.3.1)
        n_bars = max(n_bars, 6)
        if n_bars % 2 != 0:
            n_bars += 1 # Prefer even number of bars for symmetric detailing
        
        prov_ast = n_bars * single_bar
        pt = prov_ast / a_gross
        if pt <= 0.0125: # Within 1.25% tremie placement limit
            selected_dia = dia
            selected_num = n_bars
            best_ast = prov_ast
            break

    rebar_callout = f"{selected_num}-T{selected_dia} bars uniformly distributed"
    helical_callout = "T10 helical binder @ 100 mm pitch (top 3D zone) / 150 mm pitch (rest)"

    # Factored axial structural compression capacity:
    # Puz = 0.40 * fck * (Ag - Asc) + 0.67 * fy * Asc (IS 456 Cl. 39.3 for short column)
    a_c = a_gross - best_ast
    p_uz_N = 0.40 * f_ck * a_c + 0.67 * f_y * best_ast
    p_uz_kN = p_uz_N / 1000.0

    p_applied = abs(applied_axial_kN)
    unity_ratio = p_applied / max(p_uz_kN, 1.0)
    status = "PASS" if unity_ratio <= 1.0 else "FAIL"

    return IS2911StructuralPileDesign(
        pile_diameter_mm=float(d_p_mm),
        pile_length_m=float(pile_length_m),
        concrete_grade=f"M{int(f_ck)}",
        steel_grade=f"Fe{int(f_y)}",
        gross_area_mm2=float(a_gross),
        a_st_min_mm2=float(a_st_min),
        a_st_provided_mm2=float(best_ast),
        longitudinal_ratio_percent=float((best_ast / a_gross) * 100.0),
        rebar_cage_callout=rebar_callout,
        helical_binder_callout=helical_callout,
        axial_structural_capacity_kN=float(p_uz_kN),
        unity_ratio=float(unity_ratio),
        status=status,
    )
