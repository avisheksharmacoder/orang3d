"""
Dynamic Earth Pressure Engine per IS 1893 (Part 3: 2014 / Part 1: 2016).
Implements Mononobe-Okabe formulation for seismic Zone V conditions with tension cracks
in c-phi hill soils and Seed & Whitman dynamic increment partition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple, Optional
import numpy as np

from ..models.is_code_params import IndianDesignStandards
from ..models.advanced_wall_params import CurvedShellGeometry
from ..models.wall_params import SoilProperties


@dataclass
class IS1893SeismicDemand:
    """
    Seismic dynamic earth pressure demand and resultant forces per IS 1893 (Part 3).
    """
    zone_factor: float                   # Z: Seismic zone factor (e.g. 0.36 for Zone V)
    horizontal_coefficient: float        # A_h: Design horizontal seismic coefficient
    vertical_coefficient: float          # A_v: Design vertical seismic coefficient (2/3 A_h)
    seismic_inertia_angle: float         # theta: Dynamic seismic angle in degrees
    k_ae: float                          # K_ae: Dynamic active earth pressure coefficient (M-O)
    k_a_static: float                    # K_a: Static active earth pressure coefficient
    delta_k_ae: float                    # Delta K_ae: Dynamic seismic increment (K_ae - K_a)
    total_dynamic_thrust: float          # P_ae: Total dynamic lateral thrust per meter width (kN/m)
    static_thrust: float                 # P_a: Static lateral earth thrust (kN/m)
    dynamic_thrust_increment: float      # Delta P_ae: Dynamic seismic force increment (kN/m)
    thrust_centroid_height: float        # y_res: Resultant centroid height above wall base (m)
    tension_crack_depth: float           # z_c: Depth of tensile cracking in c-phi soil (m)


def calculate_is1893_seismic_coefficients(
    standards: IndianDesignStandards,
    time_period: float = 0.5,
) -> Tuple[float, float]:
    """
    Computes horizontal (A_h) and vertical (A_v) seismic coefficients per IS 1893 (Part 1/Part 3):
        A_h = (Z / 2) * (I / R) * (Sa / g)
        A_v = (2 / 3) * A_h
    """
    a_h = standards.compute_horizontal_seismic_coefficient(time_period)
    a_v = standards.compute_vertical_seismic_coefficient(time_period)
    return a_h, a_v


def compute_mononobe_okabe_kae(
    phi: float,
    delta: float,
    theta: float,
    beta: float = 0.0,
    alpha: float = 0.0,
) -> float:
    """
    Computes Mononobe-Okabe dynamic active earth pressure coefficient K_ae:
        K_ae = [cos^2(phi - theta - alpha)] / [cos(theta) * cos^2(alpha) * cos(delta + alpha + theta) * (1 + sqrt(term))^2]
    where:
        phi: Soil friction angle (deg)
        delta: Wall-soil interface friction angle (deg)
        theta: Seismic inertia angle tan(theta) = A_h / (1 - A_v) (deg)
        beta: Backfill slope angle (deg)
        alpha: Batter of back face from vertical (deg, 0 for vertical wall)
    """
    phi_rad = math.radians(phi)
    delta_rad = math.radians(delta)
    theta_rad = math.radians(theta)
    beta_rad = math.radians(beta)
    alpha_rad = math.radians(alpha)

    # Physical validity: (phi - theta - beta) must be >= 0
    if phi_rad - theta_rad - beta_rad < 0:
        # Extreme shaking / steep slope: soil mass unstable; return asymptotic upper bound
        return 1.5

    num = math.cos(phi_rad - theta_rad - alpha_rad) ** 2

    den_base = (
        math.cos(theta_rad)
        * (math.cos(alpha_rad) ** 2)
        * math.cos(delta_rad + alpha_rad + theta_rad)
    )

    if den_base <= 0:
        return 1.5

    # Radical term
    rad_num = math.sin(phi_rad + delta_rad) * math.sin(phi_rad - theta_rad - beta_rad)
    rad_den = math.cos(delta_rad + alpha_rad + theta_rad) * math.cos(beta_rad - alpha_rad)

    if rad_den <= 0 or rad_num < 0:
        radical = 0.0
    else:
        radical = math.sqrt(rad_num / rad_den)

    k_ae = num / (den_base * ((1.0 + radical) ** 2))
    return float(k_ae)


def calculate_is1893_dynamic_earth_pressure(
    geom: CurvedShellGeometry,
    soil: SoilProperties,
    standards: IndianDesignStandards,
    time_period: float = 0.5,
    backfill_slope: float = 0.0,
) -> IS1893SeismicDemand:
    """
    Evaluates seismic active earth pressures, dynamic increment partition,
    and tension crack depth per IS 1893 (Part 3: 2014 Annex B).
    """
    H = geom.panel_height
    gamma = soil.unit_weight
    phi = soil.friction_angle
    c = soil.cohesion
    delta = soil.wall_friction_angle

    # 1. Seismic coefficients
    a_h, a_v = calculate_is1893_seismic_coefficients(standards, time_period)

    # 2. Seismic inertia angle theta = atan(A_h / (1 - A_v))
    denom_v = max(1.0 - a_v, 0.05)
    theta_rad = math.atan(a_h / denom_v)
    theta_deg = math.degrees(theta_rad)

    # 3. Dynamic active coefficient K_ae & Static active coefficient K_a
    k_ae = compute_mononobe_okabe_kae(phi=phi, delta=delta, theta=theta_deg, beta=backfill_slope)
    k_a = compute_mononobe_okabe_kae(phi=phi, delta=delta, theta=0.0, beta=backfill_slope)

    delta_k_ae = max(k_ae - k_a, 0.0)

    # 4. Tension crack depth z_c in c-phi soil per IS 1893:
    # z_c = 2*c / (gamma * sqrt(Ka))
    if c > 0 and k_a > 0:
        z_c = (2.0 * c) / (gamma * math.sqrt(k_a))
        z_c = min(z_c, 0.5 * H) # Clamped to half wall height per standard engineering practice
    else:
        z_c = 0.0

    eff_h = max(H - z_c, 0.1)

    # 5. Static thrust P_a and Total Dynamic thrust P_ae per meter width
    # P_a = 0.5 * gamma * H'^2 * K_a
    # P_ae = 0.5 * gamma * H'^2 * (1 - A_v) * K_ae
    p_a = 0.5 * gamma * (eff_h ** 2) * k_a
    p_ae = 0.5 * gamma * (eff_h ** 2) * (1.0 - a_v) * k_ae
    p_ae = max(p_ae, p_a)

    delta_p_ae = max(p_ae - p_a, 0.0)

    # 6. Combined Resultant Centroid Height y_res (m above base):
    # Static component acts at H'/3, Dynamic increment acts at 0.6 H' per IS 1893 / Seed & Whitman (1970)
    if p_ae > 1e-6:
        y_res = (p_a * (eff_h / 3.0) + delta_p_ae * (0.6 * eff_h)) / p_ae
    else:
        y_res = eff_h / 3.0

    return IS1893SeismicDemand(
        zone_factor=standards.zone_factor,
        horizontal_coefficient=a_h,
        vertical_coefficient=a_v,
        seismic_inertia_angle=theta_deg,
        k_ae=k_ae,
        k_a_static=k_a,
        delta_k_ae=delta_k_ae,
        total_dynamic_thrust=p_ae,
        static_thrust=p_a,
        dynamic_thrust_increment=delta_p_ae,
        thrust_centroid_height=y_res,
        tension_crack_depth=z_c,
    )
