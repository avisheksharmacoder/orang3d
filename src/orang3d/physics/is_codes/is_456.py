"""
IS 456:2000 Plain and Reinforced Concrete - Code of Practice.
Limit State Design of RC Shell Panels, Piers, and Retaining Walls in Flexure,
Shear, Cracking, and Detailing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple, Optional, Any, Dict
import numpy as np


# Neutral axis depth ratio limits (IS 456:2000 Cl. 38.1 Note)
XU_MAX_D_RATIOS: dict[float, float] = {
    250.0: 0.53,
    415.0: 0.48,
    500.0: 0.46,
    550.0: 0.44,
}


def get_xu_max_ratio(f_y: float) -> float:
    """Returns xu_max / d per IS 456:2000 Clause 38.1 Note."""
    if f_y <= 250.0:
        return 0.53
    elif f_y <= 415.0:
        # Linear interpolation between 250 and 415
        return 0.53 - (f_y - 250.0) / (415.0 - 250.0) * (0.53 - 0.48)
    elif f_y <= 500.0:
        # Linear interpolation between 415 and 500
        return 0.48 - (f_y - 415.0) / (500.0 - 415.0) * (0.48 - 0.46)
    elif f_y <= 550.0:
        # Linear interpolation between 500 and 550
        return 0.46 - (f_y - 500.0) / (550.0 - 500.0) * (0.46 - 0.44)
    else:
        return 0.44


@dataclass
class IS456FlexuralDesign:
    """Summary results of Limit State flexural design per IS 456:2000."""
    m_u_applied: float            # Factored design bending moment (kNm)
    m_u_lim: float                # Limiting moment of resistance (kNm)
    is_doubly_reinforced: bool    # True if Mu > Mu_lim
    a_st_required: float          # Required tensile steel area (mm2)
    a_st_provided: float          # Provided tensile steel area (mm2)
    a_sc_required: float          # Required compression steel area (mm2, for doubly reinforced)
    pt_percentage: float          # Tension reinforcement percentage pt = 100 * Ast / (b * d) (%)
    x_u: float                    # Actual depth of neutral axis (mm)
    x_u_max: float                # Maximum limiting depth of neutral axis (mm)
    lever_arm: float              # Lever arm z = d - 0.42 * x_u (mm)
    bar_callout: str              # Professional detailing callout (e.g. '2-layer T16 @ 125 mm c/c')
    unity_ratio: float            # Demand-to-capacity ratio Mu / Mu_cap
    status: str                   # 'PASS', 'WARNING', or 'FAIL'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "m_u_applied_kNm": self.m_u_applied,
            "m_u_lim_kNm": self.m_u_lim,
            "is_doubly_reinforced": self.is_doubly_reinforced,
            "a_st_required_mm2": self.a_st_required,
            "a_st_provided_mm2": self.a_st_provided,
            "a_sc_required_mm2": self.a_sc_required,
            "pt_percentage": self.pt_percentage,
            "x_u_mm": self.x_u,
            "x_u_max_mm": self.x_u_max,
            "lever_arm_mm": self.lever_arm,
            "bar_callout": self.bar_callout,
            "unity_ratio": self.unity_ratio,
            "status": self.status,
        }


@dataclass
class IS456ShearDesign:
    """Summary results of Limit State shear design per IS 456:2000 Cl. 40."""
    v_u_applied: float            # Factored shear force (kN)
    tau_v: float                  # Nominal shear stress = Vu / (b * d) (MPa)
    tau_c: float                  # Design shear strength of concrete from Table 19 (MPa)
    tau_c_max: float              # Maximum shear stress from Table 20 = 0.62 * sqrt(fck) (MPa)
    shear_rebar_required: bool    # True if tau_v > tau_c
    a_sv_per_meter: float         # Required shear stirrup area per meter spacing (mm2/m)
    stirrup_callout: str          # Stirrup detailing callout (e.g. '2-legged T10 @ 150 mm c/c')
    unity_ratio: float            # Demand-to-capacity ratio tau_v / tau_c_max or tau_v / tau_c
    status: str                   # 'PASS', 'WARNING', or 'FAIL'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "v_u_applied_kN": self.v_u_applied,
            "tau_v_MPa": self.tau_v,
            "tau_c_MPa": self.tau_c,
            "tau_c_max_MPa": self.tau_c_max,
            "shear_rebar_required": self.shear_rebar_required,
            "a_sv_per_meter_mm2_m": self.a_sv_per_meter,
            "stirrup_callout": self.stirrup_callout,
            "unity_ratio": self.unity_ratio,
            "status": self.status,
        }


@dataclass
class IS456CrackWidthResult:
    """Crack width and serviceability check per IS 456 Annex F / Cl. 35.3.2."""
    calculated_crack_width: float # Estimated surface crack width (mm)
    allowable_crack_width: float  # Maximum permissible crack width (mm) (0.2 mm for aggressive/retaining)
    bar_spacing: float            # Actual bar spacing provided (mm)
    max_allowable_spacing: float  # Max allowable spacing per Table 15 (mm)
    unity_ratio: float            # w_cr / w_allow
    status: str                   # 'PASS' or 'FAIL'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calculated_crack_width_mm": self.calculated_crack_width,
            "allowable_crack_width_mm": self.allowable_crack_width,
            "bar_spacing_mm": self.bar_spacing,
            "max_allowable_spacing_mm": self.max_allowable_spacing,
            "unity_ratio": self.unity_ratio,
            "status": self.status,
        }


def calculate_is456_limiting_moment(
    b_mm: float,
    d_mm: float,
    f_ck: float,
    f_y: float,
) -> Tuple[float, float]:
    """
    Computes limiting moment of resistance Mu_lim (kNm) and limiting depth of neutral axis
    xu_max (mm) per IS 456:2000 Cl. 38.1 and Annex G:
        Mu_lim = 0.36 * (xu_max / d) * (1 - 0.42 * (xu_max / d)) * f_ck * b * d^2
    """
    xu_d = get_xu_max_ratio(f_y)
    xu_max = xu_d * d_mm
    r_u_lim = 0.36 * xu_d * (1.0 - 0.42 * xu_d)
    m_u_lim_Nmm = r_u_lim * f_ck * b_mm * (d_mm ** 2)
    m_u_lim_kNm = m_u_lim_Nmm / 1e6
    return m_u_lim_kNm, xu_max


def calculate_is456_tau_c(f_ck: float, pt_percent: float) -> float:
    """
    Evaluates design shear strength of concrete tau_c (MPa) per IS 456:2000 Table 19.
    Uses the analytical formula adopted by the IS 456 code committee:
        beta = 0.8 * f_ck / (6.89 * pt)
        tau_c = 0.85 * sqrt(0.8 * f_ck) * (sqrt(1 + 5 * beta) - 1) / (6 * beta)
    Clamped to pt >= 0.15% and maximum shear stress tau_c_max = 0.62 * sqrt(fck).
    """
    pt = max(0.15, min(pt_percent, 3.0)) # Clamped within standard Table 19 range [0.15%, 3.0%]
    fck = max(15.0, min(f_ck, 40.0))    # Table 19 defined up to M40

    beta = (0.8 * fck) / (6.89 * pt)
    tau_c = (0.85 * math.sqrt(0.8 * fck) * (math.sqrt(1.0 + 5.0 * beta) - 1.0)) / (6.0 * beta)
    
    # Check max limit tau_c_max
    tau_c_max = 0.62 * math.sqrt(f_ck)
    return float(min(tau_c, tau_c_max))


def calculate_is456_tau_c_max(f_ck: float) -> float:
    """
    Maximum shear stress in concrete tau_c_max (MPa) per IS 456:2000 Table 20:
        tau_c_max = 0.62 * sqrt(f_ck)
    """
    table_20 = {
        20.0: 2.8,
        25.0: 3.1,
        30.0: 3.5,
        35.0: 3.7,
        40.0: 4.0,
    }
    if f_ck in table_20:
        return table_20[f_ck]
    return 0.62 * math.sqrt(f_ck)


def generate_is456_bar_callout(
    a_st_req_mm2: float,
    b_mm: float = 1000.0,
    max_spacing_mm: float = 300.0,
    preferred_dia_mm: int = 16,
    two_layers: bool = True,
) -> Tuple[str, float]:
    """
    Selects standard reinforcing bar diameter and spacing to meet or exceed Ast_req.
    Rounds spacing down to 25 mm increments (e.g., 100, 125, 150, 175, 200 mm).
    Returns (callout_str, a_st_provided_mm2).
    """
    standard_diameters = [preferred_dia_mm, 12, 16, 20, 25, 32]
    # Remove duplicates preserving order
    seen = set()
    candidate_dias = [d for d in standard_diameters if not (d in seen or seen.add(d))]

    layers = 2 if two_layers else 1
    # Ast required per layer / face
    ast_per_layer = a_st_req_mm2 / float(layers)

    for dia in candidate_dias:
        bar_area = (math.pi / 4.0) * (dia ** 2)
        # Required spacing s = (b * bar_area) / ast_per_layer
        if ast_per_layer <= 0:
            calc_spacing = max_spacing_mm
        else:
            calc_spacing = (b_mm * bar_area) / ast_per_layer

        # Round down to nearest 25 mm
        spacing = math.floor(calc_spacing / 25.0) * 25.0
        spacing = max(75.0, min(spacing, max_spacing_mm))

        provided_per_layer = (b_mm / spacing) * bar_area
        total_provided = provided_per_layer * float(layers)

        if total_provided >= a_st_req_mm2 * 0.999:
            prefix = f"{layers}-layer " if layers > 1 else ""
            suffix = " each face" if layers > 1 else ""
            callout = f"{prefix}T{dia} @ {int(spacing)} mm c/c{suffix}"
            return callout, float(total_provided)

    # Fallback to T25 closely spaced
    dia = 25
    bar_area = (math.pi / 4.0) * (dia ** 2)
    spacing = 75.0
    total_provided = (b_mm / spacing) * bar_area * float(layers)
    prefix = f"{layers}-layer " if layers > 1 else ""
    suffix = " each face" if layers > 1 else ""
    return f"{prefix}T{dia} @ {int(spacing)} mm c/c{suffix}", float(total_provided)


def design_is456_flexure(
    m_u_kNm: float,
    b_mm: float,
    d_mm: float,
    D_mm: float,
    f_ck: float,
    f_y: float,
    cover_mm: float = 50.0,
    is_slab: bool = True,
    preferred_dia_mm: int = 16,
) -> IS456FlexuralDesign:
    """
    Performs Limit State flexural design per IS 456:2000 Cl. 38 and Annex G.
    Determines required steel area, checks minimum/maximum reinforcement,
    and produces professional detailing callouts.
    """
    if b_mm <= 0 or d_mm <= 0 or D_mm <= 0:
        raise ValueError(f"Section dimensions must be positive, got b={b_mm}, d={d_mm}, D={D_mm}")
    if f_ck < 15.0:
        raise ValueError(f"f_ck must be >= 15 MPa per IS 456, got {f_ck}")
    if f_y < 250.0:
        raise ValueError(f"f_y must be >= 250 MPa, got {f_y}")

    m_u = abs(m_u_kNm)
    m_u_lim, xu_max = calculate_is456_limiting_moment(b_mm, d_mm, f_ck, f_y)

    # Minimum reinforcement (Cl. 26.5.2.1 for slabs/walls: 0.12% for HYSD, 0.15% for mild steel)
    min_pt_ratio = 0.0012 if f_y >= 415.0 else 0.0015
    if not is_slab:
        # Beam / pier minimum Ast = 0.85 * b * d / fy (Cl. 26.5.1.1)
        a_st_min = (0.85 * b_mm * d_mm) / f_y
    else:
        a_st_min = min_pt_ratio * b_mm * D_mm

    # Maximum reinforcement: 4% of gross area (Cl. 26.5.1.1)
    a_st_max = 0.04 * b_mm * D_mm

    is_doubly = m_u > m_u_lim
    a_sc_req = 0.0

    if not is_doubly:
        # Singly reinforced section
        m_u_Nmm = m_u * 1e6
        # Ast = 0.5 * fck / fy * [1 - sqrt(1 - 4.6 * Mu / (fck * b * d^2))] * b * d
        discriminant = 1.0 - (4.6 * m_u_Nmm) / (f_ck * b_mm * (d_mm ** 2))
        discriminant = max(0.0, discriminant)
        a_st_calc = (0.5 * f_ck / f_y) * (1.0 - math.sqrt(discriminant)) * b_mm * d_mm
        a_st_req = max(a_st_calc, a_st_min)

        # Actual neutral axis depth xu = 0.87 * fy * Ast / (0.36 * fck * b)
        x_u = (0.87 * f_y * a_st_req) / (0.36 * f_ck * b_mm)
        lever_arm = d_mm - 0.42 * x_u
        unity_ratio = m_u / max(m_u_lim, 1e-4)
    else:
        # Doubly reinforced section
        # Ast1 for limiting moment
        r_u_lim = 0.36 * (xu_max / d_mm) * (1.0 - 0.42 * (xu_max / d_mm))
        a_st1 = (0.36 * f_ck * b_mm * xu_max) / (0.87 * f_y)
        
        # Remaining moment Mu2
        m_u2 = (m_u - m_u_lim) * 1e6 # Nmm
        d_prime = cover_mm
        
        # Design stress in compression steel f_sc (approx 0.87 * fy)
        f_sc = 0.87 * f_y
        f_cc = 0.446 * f_ck
        a_sc_req = m_u2 / ((f_sc - f_cc) * (d_mm - d_prime))
        a_st2 = m_u2 / (0.87 * f_y * (d_mm - d_prime))
        a_st_req = a_st1 + a_st2
        x_u = xu_max
        lever_arm = d_mm - 0.42 * x_u
        
        # Maximum permissible moment capacity with 4% steel limit
        a_sc_max = max(0.0, 0.5 * (a_st_max - a_st1))
        m_u2_max = ((f_sc - f_cc) * a_sc_max * (d_mm - d_prime)) / 1e6
        m_u_cap_max = m_u_lim + m_u2_max
        unity_ratio = max(m_u / max(m_u_cap_max, 1e-4), (a_st_req + a_sc_req) / a_st_max)

    # Verify maximum steel limit
    if (a_st_req + a_sc_req) > a_st_max or unity_ratio > 1.0:
        status = "FAIL"
    elif unity_ratio >= 0.90:
        status = "WARNING"
    else:
        status = "PASS"

    pt_calc = (100.0 * a_st_req) / (b_mm * d_mm)

    # Detailing callout
    max_spacing = min(3.0 * d_mm, 300.0) if is_slab else 300.0
    callout, a_st_prov = generate_is456_bar_callout(
        a_st_req_mm2=a_st_req,
        b_mm=b_mm,
        max_spacing_mm=max_spacing,
        preferred_dia_mm=preferred_dia_mm,
        two_layers=is_slab,
    )

    return IS456FlexuralDesign(
        m_u_applied=m_u,
        m_u_lim=m_u_lim,
        is_doubly_reinforced=is_doubly,
        a_st_required=float(a_st_req),
        a_st_provided=float(a_st_prov),
        a_sc_required=float(a_sc_req),
        pt_percentage=float(pt_calc),
        x_u=float(x_u),
        x_u_max=float(xu_max),
        lever_arm=float(lever_arm),
        bar_callout=callout,
        unity_ratio=float(unity_ratio),
        status=status,
    )


def design_is456_shear(
    v_u_kN: float,
    b_mm: float,
    d_mm: float,
    f_ck: float,
    f_y: float,
    a_st_provided_mm2: float,
    is_slab: bool = True,
    D_mm: Optional[float] = None,
) -> IS456ShearDesign:
    """
    Performs Limit State shear design per IS 456:2000 Cl. 40 and Table 19.
    Evaluates nominal shear stress tau_v, concrete shear capacity tau_c,
    and sizes shear reinforcement if required.
    """
    if b_mm <= 0 or d_mm <= 0:
        raise ValueError(f"Dimensions must be positive, got b={b_mm}, d={d_mm}")

    v_u = abs(v_u_kN)
    v_u_N = v_u * 1000.0

    # Nominal shear stress tau_v = Vu / (b * d)
    tau_v = v_u_N / (b_mm * d_mm)

    # Steel percentage pt = 100 * Ast / (b * d)
    pt = (100.0 * a_st_provided_mm2) / (b_mm * d_mm)
    tau_c_base = calculate_is456_tau_c(f_ck, pt)

    # Thickness modification factor k for slabs (Cl. 40.2.1.1)
    if is_slab and D_mm is not None:
        if D_mm <= 150.0:
            k = 1.30
        elif D_mm >= 300.0:
            k = 1.00
        else:
            k = 1.30 - (D_mm - 150.0) / (300.0 - 150.0) * (1.30 - 1.00)
    else:
        k = 1.0

    tau_c = tau_c_base * k
    tau_c_max = calculate_is456_tau_c_max(f_ck)

    # Shear rebar sizing
    if tau_v > tau_c_max:
        # Inadequate section dimensions
        status = "FAIL"
        shear_rebar_req = True
        a_sv_per_meter = 0.0
        stirrup_callout = "SECTION INADEQUATE: Increase concrete section depth"
        unity_ratio = tau_v / tau_c_max
    elif tau_v > tau_c:
        # Shear reinforcement required to carry excess shear Vus = Vu - tau_c * b * d
        v_uc_N = tau_c * b_mm * d_mm
        v_us_N = max(0.0, v_u_N - v_uc_N)
        
        # Asv / sv = Vus / (0.87 * fy * d)
        asv_sv = v_us_N / (0.87 * f_y * d_mm) # mm2 / mm
        # Minimum shear rebar: Asv / (b * sv) >= 0.4 / (0.87 * fy)
        asv_sv_min = (0.4 * b_mm) / (0.87 * f_y)
        asv_sv = max(asv_sv, asv_sv_min)
        
        a_sv_per_meter = asv_sv * 1000.0 # mm2/m
        
        # Size stirrups (e.g. 2-legged 10 mm bar)
        dia_stirrup = 10
        area_2leg = 2.0 * (math.pi / 4.0) * (dia_stirrup ** 2)
        calc_spacing = area_2leg / asv_sv
        max_spacing = min(0.75 * d_mm, 300.0)
        spacing = math.floor(min(calc_spacing, max_spacing) / 25.0) * 25.0
        spacing = max(75.0, spacing)

        stirrup_callout = f"2-legged T{dia_stirrup} @ {int(spacing)} mm c/c"
        shear_rebar_req = True
        unity_ratio = tau_v / tau_c_max
        status = "PASS" if unity_ratio <= 1.0 else "FAIL"
    else:
        # Nominal shear adequate
        shear_rebar_req = False
        # Minimum nominal stirrups for beams/piers
        if not is_slab:
            asv_sv_min = (0.4 * b_mm) / (0.87 * f_y)
            a_sv_per_meter = asv_sv_min * 1000.0
            dia_stirrup = 8
            area_2leg = 2.0 * (math.pi / 4.0) * (dia_stirrup ** 2)
            calc_spacing = area_2leg / asv_sv_min
            max_spacing = min(0.75 * d_mm, 300.0)
            spacing = math.floor(min(calc_spacing, max_spacing) / 25.0) * 25.0
            spacing = max(100.0, spacing)
            stirrup_callout = f"Nominal 2-legged T{dia_stirrup} @ {int(spacing)} mm c/c"
        else:
            a_sv_per_meter = 0.0
            stirrup_callout = "None required (Concrete shear capacity tau_c > tau_v)"
        
        unity_ratio = tau_v / max(tau_c, 1e-4)
        status = "PASS" if unity_ratio <= 1.0 else "WARNING"

    return IS456ShearDesign(
        v_u_applied=v_u,
        tau_v=float(tau_v),
        tau_c=float(tau_c),
        tau_c_max=float(tau_c_max),
        shear_rebar_required=shear_rebar_req,
        a_sv_per_meter=float(a_sv_per_meter),
        stirrup_callout=stirrup_callout,
        unity_ratio=float(unity_ratio),
        status=status,
    )


def check_is456_crack_width(
    m_service_kNm: float,
    b_mm: float,
    d_mm: float,
    D_mm: float,
    a_st_provided_mm2: float,
    bar_dia_mm: float,
    bar_spacing_mm: float,
    cover_mm: float = 50.0,
    aggressive_environment: bool = True,
) -> IS456CrackWidthResult:
    """
    Evaluates flexural crack width at tension surface per IS 456 Annex F / Cl. 35.3.2.
    Allowable crack width: 0.2 mm for aggressive/earth-retaining, 0.3 mm for mild.
    """
    allowable_wcr = 0.20 if aggressive_environment else 0.30

    # Service moment stress in steel
    # Approx lever arm z ~ 0.9 * d
    z = 0.90 * d_mm
    m_ser_Nmm = abs(m_service_kNm) * 1e6
    f_s = m_ser_Nmm / (a_st_provided_mm2 * z)

    # Annex F strain formula: epsilon_1 = (f_s / E_s) * (D - x) / (d - x)
    # Neutral axis depth x_elastic ~ sqrt(2 * m * pt) * d
    m_modular = 280.0 / (3.0 * 30.0) # approx modular ratio for M30
    pt = a_st_provided_mm2 / (b_mm * d_mm)
    rho = pt
    k_el = math.sqrt((rho * m_modular) ** 2 + 2.0 * rho * m_modular) - (rho * m_modular)
    x_el = k_el * d_mm

    e_s = 2.0e5 # MPa
    eps_1 = (f_s / e_s) * max((D_mm - x_el) / max(d_mm - x_el, 1.0), 0.1)

    # Tension stiffening reduction per IS 456 Cl. F-1.2:
    # eps_m = eps_1 - [b * (D - x)^2 / (3 * Es * Ast * (d - x))]
    eps_stiff = (b_mm * ((D_mm - x_el) ** 2)) / (3.0 * e_s * a_st_provided_mm2 * max(d_mm - x_el, 1.0))
    eps_m = max(0.0, eps_1 - eps_stiff)

    # Distance acr from surface point to nearest rebar corner
    # acr = sqrt((spacing / 2)^2 + cover^2) - bar_dia / 2
    a_cr = math.sqrt((bar_spacing_mm / 2.0) ** 2 + cover_mm ** 2) - bar_dia_mm / 2.0

    # Crack width formula (Annex F):
    # w_cr = 3 * a_cr * eps_m / (1 + 2 * (a_cr - c_min) / (D - x))
    c_min = cover_mm
    denom = 1.0 + 2.0 * max(0.0, a_cr - c_min) / max(D_mm - x_el, 1.0)
    w_cr = (3.0 * a_cr * eps_m) / denom

    max_spacing_table15 = 150.0 if aggressive_environment else 180.0
    unity_ratio = w_cr / allowable_wcr

    status = "PASS" if unity_ratio <= 1.0 else "FAIL"

    return IS456CrackWidthResult(
        calculated_crack_width=float(w_cr),
        allowable_crack_width=float(allowable_wcr),
        bar_spacing=float(bar_spacing_mm),
        max_allowable_spacing=float(max_spacing_table15),
        unity_ratio=float(unity_ratio),
        status=status,
    )
