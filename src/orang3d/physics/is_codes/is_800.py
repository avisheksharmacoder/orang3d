"""
IS 800:2007 General Construction in Steel - Code of Practice (Limit State Method).
Design of Structural Steel Struts, Walers, and Retaining Wall Braces in Axial Compression,
Tension Load Reversal, Biaxial Bending, and Connection Detailing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple, Optional, Any, Dict
from enum import Enum
import numpy as np


class BucklingCurve(str, Enum):
    """IS 800:2007 Table 7 Imperfection Factors for Buckling Curves."""
    CURVE_A = "a" # alpha_b = 0.21 (hot-rolled I-sections, major axis)
    CURVE_B = "b" # alpha_b = 0.34 (hot-rolled I-sections minor axis, welded I-sections)
    CURVE_C = "c" # alpha_b = 0.49 (CHS / SHS tubular struts, built-up struts, channels)
    CURVE_D = "d" # alpha_b = 0.76 (thick plates > 40 mm, built-up members)


IMPERFECTION_FACTORS: dict[str, float] = {
    BucklingCurve.CURVE_A.value: 0.21,
    BucklingCurve.CURVE_B.value: 0.34,
    BucklingCurve.CURVE_C.value: 0.49,
    BucklingCurve.CURVE_D.value: 0.76,
    "a": 0.21,
    "b": 0.34,
    "c": 0.49,
    "d": 0.76,
}


@dataclass
class IS800StrutCompressionResult:
    """Design compressive strength per IS 800:2007 Cl. 7.1.2."""
    slenderness_ratio: float       # KL / r
    euler_stress_fcc: float        # fcc = pi^2 * E / (KL/r)^2 (MPa)
    non_dim_slenderness_lambda: float # lambda = sqrt(fy / fcc)
    imperfection_factor: float     # alpha_b (0.49 for Curve c)
    stress_reduction_factor: float # chi
    design_compressive_stress_fcd: float # fcd = chi * fy / gamma_m0 (MPa)
    design_compressive_strength_pd: float # Pd = Ae * fcd (kN)
    applied_compression_force: float # Factored compressive demand P (kN)
    max_slenderness_limit: float   # 180 (gravity) or 250 (seismic) per Table 3
    slenderness_status: str        # 'PASS' or 'FAIL'
    unity_ratio: float             # P / Pd
    status: str                    # 'PASS', 'WARNING', or 'FAIL'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slenderness_ratio": self.slenderness_ratio,
            "euler_stress_fcc_MPa": self.euler_stress_fcc,
            "non_dim_slenderness_lambda": self.non_dim_slenderness_lambda,
            "imperfection_factor": self.imperfection_factor,
            "stress_reduction_factor": self.stress_reduction_factor,
            "design_compressive_stress_fcd_MPa": self.design_compressive_stress_fcd,
            "design_compressive_strength_pd_kN": self.design_compressive_strength_pd,
            "applied_compression_force_kN": self.applied_compression_force,
            "max_slenderness_limit": self.max_slenderness_limit,
            "slenderness_status": self.slenderness_status,
            "unity_ratio": self.unity_ratio,
            "status": self.status,
        }


@dataclass
class IS800StrutTensionResult:
    """Design tensile strength per IS 800:2007 Cl. 6.2 (seismic load reversal)."""
    gross_yielding_capacity_tdg: float # Tdg = Ag * fy / gamma_m0 (kN)
    net_rupture_capacity_tdn: float    # Tdn = 0.9 * Anet * fu / gamma_m1 (kN)
    design_tension_capacity_td: float  # Td = min(Tdg, Tdn) (kN)
    applied_tension_demand: float      # Factored reversal tension T (kN)
    unity_ratio: float                 # T / Td
    status: str                        # 'PASS' or 'FAIL'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gross_yielding_capacity_tdg_kN": self.gross_yielding_capacity_tdg,
            "net_rupture_capacity_tdn_kN": self.net_rupture_capacity_tdn,
            "design_tension_capacity_td_kN": self.design_tension_capacity_td,
            "applied_tension_demand_kN": self.applied_tension_demand,
            "unity_ratio": self.unity_ratio,
            "status": self.status,
        }


@dataclass
class IS800ConnectionResult:
    """Strut end connection design per IS 800:2007 Section 10."""
    connection_type: str          # 'BOLTED' or 'WELDED'
    bolt_diameter_mm: float       # e.g. 24 mm Grade 8.8 / 4.6
    num_bolts_required: int       # Number of bolts
    bolt_shear_capacity_kN: float # Vdsb
    bolt_bearing_capacity_kN: float # Vdpb
    weld_size_mm: float           # Leg size of fillet weld s (mm)
    weld_length_required_mm: float # Required length Lw (mm)
    connection_capacity_kN: float # Design capacity of connection
    applied_load_kN: float        # Applied factored load
    unity_ratio: float            # P / Connection Capacity
    status: str                   # 'PASS' or 'FAIL'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_type": self.connection_type,
            "bolt_diameter_mm": self.bolt_diameter_mm,
            "num_bolts_required": self.num_bolts_required,
            "bolt_shear_capacity_kN": self.bolt_shear_capacity_kN,
            "bolt_bearing_capacity_kN": self.bolt_bearing_capacity_kN,
            "weld_size_mm": self.weld_size_mm,
            "weld_length_required_mm": self.weld_length_required_mm,
            "connection_capacity_kN": self.connection_capacity_kN,
            "applied_load_kN": self.applied_load_kN,
            "unity_ratio": self.unity_ratio,
            "status": self.status,
        }


@dataclass
class IS800StrutDesignReport:
    """Unified structural steel strut verification report per IS 800:2007."""
    section_name: str
    effective_length_m: float
    effective_area_mm2: float
    radius_of_gyration_mm: float
    compression_result: IS800StrutCompressionResult
    tension_result: IS800StrutTensionResult
    connection_result: IS800ConnectionResult
    combined_axial_bending_ratio: float
    max_unity_ratio: float
    overall_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_name": self.section_name,
            "effective_length_m": self.effective_length_m,
            "effective_area_mm2": self.effective_area_mm2,
            "radius_of_gyration_mm": self.radius_of_gyration_mm,
            "compression": self.compression_result.to_dict(),
            "tension": self.tension_result.to_dict(),
            "connection": self.connection_result.to_dict(),
            "combined_axial_bending_ratio": self.combined_axial_bending_ratio,
            "max_unity_ratio": self.max_unity_ratio,
            "overall_status": self.overall_status,
        }


def calculate_is800_design_compressive_stress(
    slenderness_kl_r: float,
    f_y: float = 250.0,
    buckling_curve: str = "c",
    gamma_m0: float = 1.10,
    e_steel: float = 2.0e5,
) -> Tuple[float, float, float]:
    """
    Computes design compressive stress f_cd (MPa) per IS 800:2007 Clause 7.1.2.1:
        f_cd = (f_y / gamma_m0) / [phi + sqrt(phi^2 - lambda^2)] = chi * f_y / gamma_m0
        where:
        phi = 0.5 * [1 + alpha * (lambda - 0.2) + lambda^2]
        lambda = sqrt(f_y / f_cc) = (KL / r) / [pi * sqrt(E / f_y)]
        f_cc = pi^2 * E / (KL / r)^2
    Returns (f_cd, lambda, chi).
    """
    if slenderness_kl_r <= 0:
        raise ValueError(f"Slenderness ratio must be positive, got {slenderness_kl_r}")
    if f_y <= 0:
        raise ValueError(f"Yield stress must be positive, got {f_y}")

    alpha_b = IMPERFECTION_FACTORS.get(buckling_curve, 0.49)

    # Euler buckling stress fcc
    f_cc = (math.pi ** 2 * e_steel) / (slenderness_kl_r ** 2)

    # Non-dimensional slenderness lambda = sqrt(fy / fcc)
    lam = math.sqrt(f_y / f_cc)

    # Auxiliary parameter phi_b
    phi_b = 0.5 * (1.0 + alpha_b * (lam - 0.2) + (lam ** 2))

    # Stress reduction factor chi
    discriminant = max(0.0, (phi_b ** 2) - (lam ** 2))
    chi = 1.0 / (phi_b + math.sqrt(discriminant))
    chi = min(1.0, max(0.0, chi))

    f_cd = (chi * f_y) / gamma_m0
    return float(f_cd), float(lam), float(chi)


def design_is800_steel_strut(
    applied_compression_kN: float,
    effective_length_m: float,
    section_area_mm2: float,
    radius_of_gyration_mm: float,
    f_y: float = 250.0,
    f_u: float = 410.0,
    applied_tension_reversal_kN: float = 0.0,
    applied_bending_moment_kNm: float = 0.0,
    elastic_section_modulus_z_cm3: float = 1000.0,
    buckling_curve: str = "c",
    is_seismic: bool = False,
    section_name: str = "CHS 355.6x12.5 Strut",
    bolt_dia_mm: float = 24.0,
) -> IS800StrutDesignReport:
    """
    Executes comprehensive structural steel strut design per IS 800:2007 (LSM):
    - Slenderness limit check (Table 3: 180 gravity, 250 seismic)
    - Compressive buckling capacity (Cl. 7.1.2)
    - Tension reversal capacity (Cl. 6.2)
    - Combined axial compression + bending interaction (Cl. 9.3)
    - End connection bolt/weld detailing (Section 10)
    """
    gamma_m0 = 1.10
    gamma_m1 = 1.25
    gamma_mb = 1.25

    kl_mm = effective_length_m * 1000.0
    r_mm = max(radius_of_gyration_mm, 1.0)
    kl_r = kl_mm / r_mm

    # 1. Slenderness check per IS 800 Table 3
    max_kl_r = 250.0 if is_seismic else 180.0
    slenderness_status = "PASS" if kl_r <= max_kl_r else "FAIL"

    # 2. Design compressive stress and strength
    f_cd, lam, chi = calculate_is800_design_compressive_stress(
        slenderness_kl_r=kl_r,
        f_y=f_y,
        buckling_curve=buckling_curve,
        gamma_m0=gamma_m0,
    )
    f_cc = (math.pi ** 2 * 2.0e5) / (kl_r ** 2)

    # Design compressive capacity Pd = Ae * fcd (kN)
    p_d_N = section_area_mm2 * f_cd
    p_d_kN = p_d_N / 1000.0

    p_app = abs(applied_compression_kN)
    ur_comp = p_app / max(p_d_kN, 1e-3)
    status_comp = "FAIL" if (ur_comp > 1.0 or slenderness_status == "FAIL") else ("WARNING" if ur_comp >= 0.90 else "PASS")

    comp_result = IS800StrutCompressionResult(
        slenderness_ratio=float(kl_r),
        euler_stress_fcc=float(f_cc),
        non_dim_slenderness_lambda=float(lam),
        imperfection_factor=IMPERFECTION_FACTORS.get(buckling_curve, 0.49),
        stress_reduction_factor=float(chi),
        design_compressive_stress_fcd=float(f_cd),
        design_compressive_strength_pd=float(p_d_kN),
        applied_compression_force=float(p_app),
        max_slenderness_limit=float(max_kl_r),
        slenderness_status=slenderness_status,
        unity_ratio=float(ur_comp),
        status=status_comp,
    )

    # 3. Tension reversal capacity (Cl. 6.2)
    # Tdg = Ag * fy / gamma_m0
    t_dg = (section_area_mm2 * f_y / gamma_m0) / 1000.0
    # Net area ~ 0.85 * Ag for bolted connection holes
    a_net = 0.85 * section_area_mm2
    t_dn = (0.9 * a_net * f_u / gamma_m1) / 1000.0
    t_d = min(t_dg, t_dn)

    t_app = abs(applied_tension_reversal_kN)
    ur_tension = t_app / max(t_d, 1e-3)
    status_tension = "PASS" if ur_tension <= 1.0 else "FAIL"

    tension_result = IS800StrutTensionResult(
        gross_yielding_capacity_tdg=float(t_dg),
        net_rupture_capacity_tdn=float(t_dn),
        design_tension_capacity_td=float(t_d),
        applied_tension_demand=float(t_app),
        unity_ratio=float(ur_tension),
        status=status_tension,
    )

    # 4. Connection design (Bolted flange/cleat per Cl. 10.3)
    # Grade 8.8 bolts: fub = 800 MPa, Grade 4.6 bolts: fub = 400 MPa
    f_ub = 800.0 if bolt_dia_mm >= 20.0 else 400.0
    # Nominal shank/net area: Anb ~ 0.78 * (pi/4 * d^2)
    a_nb = 0.78 * (math.pi / 4.0) * (bolt_dia_mm ** 2)
    
    # Shear capacity per bolt Vdsb = fub / (sqrt(3) * gamma_mb) * Anb
    v_dsb_N = (f_ub / (math.sqrt(3.0) * gamma_mb)) * a_nb
    v_dsb_kN = v_dsb_N / 1000.0

    # Bearing capacity per bolt Vdpb = 2.5 * kb * d * t * fu / gamma_mb (assume kb=0.5, t=16 mm)
    t_conn_plate = 16.0
    k_b = 0.50
    v_dpb_N = (2.5 * k_b * bolt_dia_mm * t_conn_plate * f_u) / gamma_mb
    v_dpb_kN = v_dpb_N / 1000.0

    v_bolt_kN = min(v_dsb_kN, v_dpb_kN)
    governing_load = max(p_app, t_app)
    n_bolts = math.ceil(governing_load / max(v_bolt_kN, 1.0))
    n_bolts = max(n_bolts, 4) # Minimum 4 bolts for strut joint stability
    if n_bolts % 2 != 0:
        n_bolts += 1

    conn_capacity = n_bolts * v_bolt_kN
    ur_conn = governing_load / max(conn_capacity, 1e-3)
    status_conn = "PASS" if ur_conn <= 1.0 else "FAIL"

    # Weld alternative
    weld_size = 10.0 # mm
    t_throat = 0.707 * weld_size
    f_wd = f_u / (math.sqrt(3.0) * 1.25) # MPa
    req_weld_len_mm = (governing_load * 1000.0) / (t_throat * f_wd) if governing_load > 0 else 100.0

    conn_result = IS800ConnectionResult(
        connection_type="BOLTED",
        bolt_diameter_mm=float(bolt_dia_mm),
        num_bolts_required=int(n_bolts),
        bolt_shear_capacity_kN=float(v_dsb_kN),
        bolt_bearing_capacity_kN=float(v_dpb_kN),
        weld_size_mm=float(weld_size),
        weld_length_required_mm=float(req_weld_len_mm),
        connection_capacity_kN=float(conn_capacity),
        applied_load_kN=float(governing_load),
        unity_ratio=float(ur_conn),
        status=status_conn,
    )

    # 5. Combined axial compression + bending interaction (Cl. 9.3.1.1)
    # P / Pd + My / Mdy <= 1.0
    # Mdy = Z_p * fy / gamma_m0
    z_cm3 = elastic_section_modulus_z_cm3
    z_mm3 = z_cm3 * 1000.0
    m_dy_kNm = (z_mm3 * f_y / gamma_m0) / 1e6

    m_app = abs(applied_bending_moment_kNm)
    combined_ratio = (p_app / max(p_d_kN, 1e-3)) + (m_app / max(m_dy_kNm, 1e-3))

    max_ur = max(ur_comp, ur_tension, ur_conn, combined_ratio)
    overall_status = "FAIL" if (max_ur > 1.0 or slenderness_status == "FAIL") else ("WARNING" if max_ur >= 0.90 else "PASS")

    return IS800StrutDesignReport(
        section_name=section_name,
        effective_length_m=float(effective_length_m),
        effective_area_mm2=float(section_area_mm2),
        radius_of_gyration_mm=float(radius_of_gyration_mm),
        compression_result=comp_result,
        tension_result=tension_result,
        connection_result=conn_result,
        combined_axial_bending_ratio=float(combined_ratio),
        max_unity_ratio=float(max_ur),
        overall_status=overall_status,
    )
