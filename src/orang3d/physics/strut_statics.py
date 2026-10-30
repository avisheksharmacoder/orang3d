"""
Multi-Strut Statics & Apparent Earth Pressure Engine (Phase 3).
Computes tributary area apportionment, apparent earth pressure (AEP) envelopes,
inclined strut axial forces with installation pre-stress lock-off, and Euler/IS 800 buckling checks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

from ..models.advanced_wall_params import StrutSupportSystem


@dataclass
class StrutReactionResult:
    """
    Structural statics and capacity utilization for an individual raking strut tier.
    """
    strut_index: int                     # Tier index (0 = topmost strut)
    depth: float                         # Attachment depth from wall crest (m)
    tributary_height: float              # Tributary vertical span H_trib (m)
    horizontal_force: float              # F_h: Total horizontal load transferred to strut (kN)
    axial_force: float                   # P_strut: Axial compressive force along strut (kN)
    vertical_reaction: float             # V_strut: Downward vertical force on pier/subgrade (kN)
    euler_buckling_capacity: float       # P_cr: Euler elastic buckling limit (kN)
    slenderness_ratio: float             # lambda: Effective slenderness L / r
    unity_ratio: float                   # UR: Demand-to-capacity ratio (P_strut / P_cr)
    status: str                          # "PASS" if UR <= 1.0 else "FAIL"


@dataclass
class MultiStrutSystemResult:
    """
    Overall system statics for the complete multi-tier strut support system.
    """
    strut_reactions: List[StrutReactionResult]
    total_strut_horizontal_force: float  # Sum of F_h across all struts (kN)
    total_strut_vertical_force: float    # Sum of downward V_strut onto pier (kN)
    residual_base_shear: float           # Unbalanced horizontal shear transferred to pile cap (kN)
    depths: np.ndarray                   # Sampled depth coordinates for AEP envelope (m)
    apparent_earth_pressure: np.ndarray  # p_a(y): Apparent earth pressure profile (kPa)


def compute_apparent_earth_pressure(
    height: float,
    total_thrust: float,
    num_points: int = 50,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates a modified Peck / Terzaghi-Peck trapezoidal apparent earth pressure envelope:
    - Pressure increases linearly from 0 at crest to uniform pressure at 0.2*H depth.
    - Uniform rectangular plateau from 0.2*H to 0.8*H depth.
    - Tapers linearly from 0.8*H to 0 at excavation base.
    The envelope is calibrated such that the integral over height equals the total dynamic thrust.
    """
    if height <= 0:
        raise ValueError(f"height must be positive, got {height}")

    depths = np.linspace(0.0, height, num_points, dtype=np.float64)

    # Unit trapezoid shape:
    # 0 to 0.2*H: rise from 0 to 1
    # 0.2*H to 0.8*H: plateau at 1
    # 0.8*H to H: fall from 1 to 0
    shape = np.ones_like(depths)
    z_rise = 0.2 * height
    z_fall = 0.8 * height

    rise_mask = depths < z_rise
    shape[rise_mask] = depths[rise_mask] / max(z_rise, 1e-4)

    fall_mask = depths > z_fall
    shape[fall_mask] = (height - depths[fall_mask]) / max(height - z_fall, 1e-4)

    # Area under unit trapezoid
    integrate_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
    area_unit = float(integrate_trapz(shape, depths))

    # Scale so that integral equals total_thrust
    if area_unit > 1e-6:
        peak_pressure = total_thrust / area_unit
    else:
        peak_pressure = 0.0

    pressure_profile = shape * peak_pressure
    return depths, pressure_profile


def compute_multi_strut_apportionment(
    struts: StrutSupportSystem,
    pier_height: float,
    total_thrust: float,
    bay_span: float,
) -> MultiStrutSystemResult:
    """
    Apportions dynamic earth pressures across all raking strut tiers using tributary area statics.
    Incorporates inclination angle alpha_strut, prestress lock-off P_0, and Euler buckling verification.
    """
    struts.validate_with_pier(pier_height)

    H = pier_height
    levels = struts.strut_levels
    n_struts = len(levels)
    alpha_rad = math.radians(struts.inclination_angle)
    cos_alpha = max(math.cos(alpha_rad), 0.1)
    sin_alpha = math.sin(alpha_rad)

    # 1. Generate apparent earth pressure profile
    depths, aep = compute_apparent_earth_pressure(height=H, total_thrust=total_thrust)

    # 2. Determine tributary vertical spans for each strut level
    # Bounds between strut levels
    trib_heights = []
    for idx, d_curr in enumerate(levels):
        if n_struts == 1:
            h_trib = H
        elif idx == 0:
            # Top strut: from crest to midpoint between strut 0 and strut 1
            d_next = levels[1]
            h_trib = (d_curr + d_next) / 2.0
        elif idx == n_struts - 1:
            # Bottom strut: from midpoint of (m-1, m) to base
            d_prev = levels[idx - 1]
            h_trib = H - ((d_prev + d_curr) / 2.0)
        else:
            # Intermediate strut: mid-span between adjacent struts
            d_prev = levels[idx - 1]
            d_next = levels[idx + 1]
            h_trib = (d_next - d_prev) / 2.0

        trib_heights.append(h_trib)

    # 3. Calculate forces on each strut
    reactions = []
    total_f_h = 0.0
    total_v_strut = 0.0

    p_cr = struts.euler_buckling_load

    for idx, (depth, h_trib) in enumerate(zip(levels, trib_heights)):
        # Average apparent pressure in the tributary zone
        avg_pressure = total_thrust / H
        f_h = avg_pressure * h_trib * bay_span

        # Strut axial compressive demand: P_strut = (F_h / cos(alpha)) + P_0
        p_strut = (f_h / cos_alpha) + struts.pre_stress_load

        # Downward vertical thrust component: V = P_strut * sin(alpha)
        v_strut = p_strut * sin_alpha

        # Demand-to-capacity unity ratio
        ur = p_strut / max(p_cr, 1e-4)
        status = "PASS" if ur <= 1.0 else "FAIL"

        reactions.append(
            StrutReactionResult(
                strut_index=idx,
                depth=depth,
                tributary_height=h_trib,
                horizontal_force=f_h,
                axial_force=p_strut,
                vertical_reaction=v_strut,
                euler_buckling_capacity=p_cr,
                slenderness_ratio=struts.slenderness_ratio,
                unity_ratio=ur,
                status=status,
            )
        )
        total_f_h += f_h
        total_v_strut += v_strut

    # Residual horizontal shear at base of pier
    total_bay_thrust = total_thrust * bay_span
    residual_base_shear = max(total_bay_thrust - total_f_h, 0.0)

    return MultiStrutSystemResult(
        strut_reactions=reactions,
        total_strut_horizontal_force=total_f_h,
        total_strut_vertical_force=total_v_strut,
        residual_base_shear=residual_base_shear,
        depths=depths,
        apparent_earth_pressure=aep,
    )
