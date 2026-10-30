"""
Horizontal Soil Arching Engine for Curved RC Shell Retaining Walls (Phase 3).
Implements modified Terzaghi (1943) & Handy (1985) arching theory for cylindrical panels
between vertical piers, with exact horizontal equilibrium conservation (sum F_x = 0).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

from ..models.advanced_wall_params import CurvedShellGeometry
from ..models.wall_params import SoilProperties


@dataclass
class ShellArchingResult:
    """
    Results of horizontal soil arching formulation between vertical retaining piers.
    """
    depths: np.ndarray                   # z: Depths from ground crest to base (m)
    sigma_h_profile: np.ndarray          # sigma_h(z): Reduced horizontal arching stress (kPa)
    sigma_h_free_field: np.ndarray       # sigma_h,free(z): Classical un-arched Rankine stress (kPa)
    total_free_field_thrust: float       # P_free: Total un-arched lateral earth thrust per bay (kN)
    total_shell_thrust: float            # P_shell: Total integrated thrust acting onto shell panel (kN)
    total_pier_thrust: float             # P_pier: Load transferred directly into flanking piers (kN)
    arching_ratio: float                 # eta_arch: Fraction of total earth thrust transferred to piers
    max_hoop_thrust: float               # N_theta,max: Maximum membrane compression in shell panel (kN/m)
    max_shell_bending_moment: float      # M_shell,max: Maximum horizontal bending moment in shell (kNm/m)


def compute_horizontal_arching_stress(
    z: np.ndarray | float,
    gamma: float,
    phi: float,
    bay_span: float,
    c: float = 0.0,
    k_coeff: Optional[float] = None,
) -> np.ndarray | float:
    """
    Computes horizontal arching stress at depth z between vertical piers per modified Terzaghi/Handy theory:
        sigma_h(z) = [(gamma * L_bay - 2c) / (2 * tan(phi))] * [1 - exp(-2 * K * tan(phi) * z / L_bay)]
    where:
        gamma: Soil unit weight (kN/m^3)
        phi: Soil internal friction angle in degrees
        bay_span: Clear span between piers L_bay (m)
        c: Cohesion (kPa)
        k_coeff: Earth pressure coefficient (defaults to Rankine Ka = tan^2(45 - phi/2))
    """
    if bay_span <= 0:
        raise ValueError(f"bay_span must be positive, got {bay_span}")
    if phi <= 0 or phi >= 90:
        raise ValueError(f"phi must be between 0 and 90 degrees, got {phi}")

    phi_rad = math.radians(phi)
    tan_phi = math.tan(phi_rad)

    if k_coeff is None:
        # Rankine active coefficient Ka = tan^2(45 - phi/2)
        k_coeff = math.tan(math.radians(45.0 - phi / 2.0)) ** 2

    z_arr = np.asarray(z, dtype=np.float64)

    # Exponent: 2 * K * tan(phi) * (z / L_bay)
    exponent = 2.0 * k_coeff * tan_phi * (z_arr / bay_span)

    # Handle numerical asymptotic limit as bay_span -> infinity or exponent -> 0
    # 1 - exp(-u) = u - u^2/2 + ...
    # [(gamma * L - 2c)/(2*tan_phi)] * [2 * K * tan_phi * z / L] -> K * gamma * z
    small_mask = np.abs(exponent) < 1e-7

    numerator = gamma * bay_span - 2.0 * c
    denominator = 2.0 * tan_phi

    with np.errstate(over="ignore", invalid="ignore"):
        stress = (numerator / denominator) * (1.0 - np.exp(-exponent)) - 2.0 * c * math.sqrt(k_coeff)

    if np.any(small_mask):
        # Asymptotic expansion for small exponent (avoids catastrophic cancellation)
        approx_stress = k_coeff * (gamma * z_arr - (2.0 * c * z_arr / bay_span)) - 2.0 * c * math.sqrt(k_coeff)
        if np.isscalar(stress):
            stress = approx_stress
        else:
            stress[small_mask] = approx_stress[small_mask]

    # Free-field Rankine active stress: sigma_Rankine(z) = max(Ka * gamma * z - 2c * sqrt(Ka), 0.0)
    sigma_rankine = np.maximum(k_coeff * gamma * z_arr - 2.0 * c * math.sqrt(k_coeff), 0.0)

    # Stress cannot be negative (soil in tension) and cannot physically exceed free-field active stress
    stress = np.maximum(stress, 0.0)
    stress = np.minimum(stress, sigma_rankine)

    if np.isscalar(z):
        return float(stress)
    return stress


def compute_shell_arching_partition(
    geom: CurvedShellGeometry,
    soil: SoilProperties,
    num_depth_points: int = 50,
) -> ShellArchingResult:
    """
    Evaluates complete horizontal soil arching, load partition factor eta_arch,
    membrane hoop compression N_theta, and bending moment in the shell panel.
    Strictly guarantees equilibrium conservation: P_free = P_shell + P_pier.
    """
    H = geom.panel_height
    L = geom.bay_span
    R = geom.radius
    gamma = soil.unit_weight
    phi = soil.friction_angle
    c = soil.cohesion

    depths = np.linspace(0.0, H, num_depth_points, dtype=np.float64)

    # Rankine Ka
    ka = math.tan(math.radians(45.0 - phi / 2.0)) ** 2

    # Un-arched free-field planar active stress sigma_free(z) = Ka * gamma * z - 2c * sqrt(Ka)
    sigma_free = np.maximum(ka * gamma * depths - 2.0 * c * math.sqrt(ka), 0.0)

    # Reduced arching stress sigma_h(z)
    sigma_h = compute_horizontal_arching_stress(
        z=depths,
        gamma=gamma,
        phi=phi,
        bay_span=L,
        c=c,
        k_coeff=ka,
    )

    # Numerical integration across panel height
    # Total thrusts per bay (width = L)
    integrate_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
    p_free = float(integrate_trapz(sigma_free, depths) * L)
    p_shell = float(integrate_trapz(sigma_h, depths) * L)

    # Pier absorbs remainder of free-field thrust: P_pier = P_free - P_shell
    # Strictly conserves horizontal equilibrium sum F_x = 0
    p_pier = max(p_free - p_shell, 0.0)

    # Arching ratio eta_arch = P_pier / P_free
    if p_free > 1e-6:
        eta_arch = p_pier / p_free
    else:
        eta_arch = 0.0

    # Membrane hoop thrust in circular cylindrical shell: N_theta = sigma_h * R (kN/m)
    hoop_thrust_profile = sigma_h * R
    max_hoop = float(np.max(hoop_thrust_profile))

    # Shell bending moment: residual flexure due to deviation from ideal parabolic thrust line
    # M_shell = sigma_h * L^2 / 12 * (1 - eta_arch)
    moment_profile = (sigma_h * (L ** 2) / 12.0) * (1.0 - eta_arch)
    max_moment = float(np.max(moment_profile))

    return ShellArchingResult(
        depths=depths,
        sigma_h_profile=sigma_h,
        sigma_h_free_field=sigma_free,
        total_free_field_thrust=p_free,
        total_shell_thrust=p_shell,
        total_pier_thrust=p_pier,
        arching_ratio=eta_arch,
        max_hoop_thrust=max_hoop,
        max_shell_bending_moment=max_moment,
    )
