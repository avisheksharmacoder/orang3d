"""
IS 875 (Part 3): 2015 and IS 802 Wind Load Engine for High-Voltage Transmission Towers.
Calculates height-dependent design wind velocity V_z, design wind pressure p_z,
force coefficients C_f for lattice tower frameworks, conductor aerodynamic drag,
and total multi-hazard base shear and overturning moments.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


@dataclass
class IS875WindParameters:
    """
    Input parameters for wind load calculation per IS 875 (Part 3): 2015
    and IS 802 (Part 1/Sec 1): 1995.
    """
    basic_wind_speed: float = 47.0        # V_b: Basic wind speed in m/s (Zone 4 default for hill regions)
    terrain_category: int = 2             # Category 1 (open sea/plain), 2 (scattered trees), 3 (towns)
    risk_coefficient_k1: float = 1.06     # k1: Probability factor (1.06 for 100-year design life of EHV line)
    topography_factor_k3: float = 1.15    # k3: Topographic crest amplification factor (slope > 3°)
    cyclone_factor_k4: float = 1.0        # k4: Cyclonic factor (1.0 for non-coastal inland hills)
    solidity_ratio: float = 0.20          # phi_s = A_solid / A_gross for square lattice tower
    conductor_diameter: float = 0.0286    # d_cond: Diameter of phase conductor in meters (e.g. Moose ACSR)
    wind_span: float = 350.0              # L_span: Wind span distance between adjacent towers (m)
    num_conductors: int = 6               # Total number of phase conductors (double-circuit 3-phase = 6)
    num_ground_wires: int = 1             # Number of earth/shield wires at tower peak
    ground_wire_diameter: float = 0.011   # d_gw: Shield wire diameter (m)
    conductor_drag_coeff: float = 1.0     # C_dc: Aerodynamic drag coefficient for circular cables
    gust_response_factor: float = 1.10    # G_t: Dynamic gust factor for transmission towers

    def __post_init__(self):
        if self.basic_wind_speed <= 0:
            raise ValueError(f"basic_wind_speed must be positive, got {self.basic_wind_speed}")
        if self.terrain_category not in (1, 2, 3, 4):
            raise ValueError(f"terrain_category must be 1, 2, 3, or 4, got {self.terrain_category}")
        if self.risk_coefficient_k1 <= 0:
            raise ValueError(f"risk_coefficient_k1 must be positive, got {self.risk_coefficient_k1}")
        if self.topography_factor_k3 < 1.0:
            raise ValueError(f"topography_factor_k3 must be >= 1.0, got {self.topography_factor_k3}")
        if not (0.05 <= self.solidity_ratio <= 0.60):
            raise ValueError(f"solidity_ratio must be between 0.05 and 0.60, got {self.solidity_ratio}")
        if self.wind_span <= 0:
            raise ValueError(f"wind_span must be positive, got {self.wind_span}")
        if self.conductor_diameter <= 0:
            raise ValueError(f"conductor_diameter must be positive, got {self.conductor_diameter}")


@dataclass
class TowerWindProfileResult:
    """
    Height-dependent wind velocity, pressure, and aerodynamic drag profile.
    """
    heights: List[float]                  # z elevations above ground (m)
    k2_factors: List[float]               # Terrain and height factors k2(z)
    design_velocities: List[float]        # V_z design wind speeds (m/s)
    wind_pressures: List[float]           # p_z design wind pressures (kN/m^2)
    tower_drag_forces: List[float]        # Aerodynamic drag per height segment (kN)
    total_tower_body_shear: float         # Net horizontal drag on lattice tower framework (kN)
    conductor_drag_shear: float           # Horizontal drag on phase conductors (kN)
    ground_wire_drag_shear: float         # Horizontal drag on ground/shield wires (kN)
    total_base_wind_shear: float          # V_wind_total = Tower + Conductors + Shield (kN)
    base_overturning_moment: float        # M_wind_total about ground base (kNm)
    effective_wind_thrust_height: float   # z_eff = M_wind_total / V_wind_total (m)


def compute_k2_factor(height_z: float, terrain_category: int = 2) -> float:
    """
    Computes terrain and height factor k2 per IS 875 (Part 3): 2015, Table 2.
    Uses continuous logarithmic/power-law interpolation matching standard table points:
    Cat 1: 10m -> 1.05, 15m -> 1.09, 20m -> 1.12, 30m -> 1.17, 50m -> 1.24
    Cat 2: 10m -> 1.00, 15m -> 1.05, 20m -> 1.07, 30m -> 1.12, 50m -> 1.17
    Cat 3: 10m -> 0.91, 15m -> 0.97, 20m -> 1.01, 30m -> 1.06, 50m -> 1.12
    Cat 4: 10m -> 0.80, 15m -> 0.80, 20m -> 0.80, 30m -> 0.88, 50m -> 0.99
    """
    z_clamped = max(10.0, min(height_z, 150.0))

    if terrain_category == 1:
        # Power law alpha = 0.09
        return 1.05 * ((z_clamped / 10.0) ** 0.10)
    elif terrain_category == 2:
        # Standard open country alpha = 0.10
        return 1.00 * ((z_clamped / 10.0) ** 0.10)
    elif terrain_category == 3:
        # Suburban / small trees alpha = 0.14
        return 0.91 * ((z_clamped / 10.0) ** 0.13)
    else: # Category 4
        if z_clamped <= 20.0:
            return 0.80
        return 0.80 * ((z_clamped / 20.0) ** 0.20)


def compute_lattice_force_coefficient(solidity_ratio: float) -> float:
    """
    Calculates overall force coefficient C_f for square-plan lattice towers
    with flat-sided structural angle members per IS 875 (Part 3) Table 29:
    phi_s <= 0.1: C_f = 3.6
    phi_s = 0.2: C_f = 2.8
    phi_s = 0.3: C_f = 2.3
    phi_s = 0.4: C_f = 2.1
    phi_s >= 0.5: C_f = 2.0
    """
    phi = max(0.05, min(solidity_ratio, 0.60))
    if phi <= 0.20:
        # Linear between (0.1, 3.6) and (0.2, 2.8)
        return 3.6 - (phi - 0.10) * 8.0
    elif phi <= 0.40:
        # Linear between (0.2, 2.8) and (0.4, 2.1)
        return 2.8 - (phi - 0.20) * 3.5
    else:
        # Asymptote to 2.0
        return max(2.0, 2.1 - (phi - 0.40) * 0.5)


def calculate_transmission_tower_wind_loads(
    tower_height: float,
    base_width: float,
    top_width: float,
    wind_params: Optional[IS875WindParameters] = None,
    num_panels: int = 5,
) -> TowerWindProfileResult:
    """
    Calculates the full-height aerodynamic wind profile and resultant base reactions
    for a lattice transmission tower per IS 875 (Part 3) and IS 802.

    Parameters:
    - tower_height: Total tower height H_tower (m)
    - base_width: Base width B_tower (m)
    - top_width: Waist / peak width B_top (m)
    - wind_params: Wind design coefficients and conductor specs
    - num_panels: Number of discrete vertical panels for profile integration
    """
    if wind_params is None:
        wind_params = IS875WindParameters()

    if tower_height <= 0:
        raise ValueError(f"tower_height must be positive, got {tower_height}")
    if base_width <= 0:
        raise ValueError(f"base_width must be positive, got {base_width}")
    if top_width <= 0 or top_width > base_width:
        raise ValueError(f"top_width must be positive and <= base_width ({base_width}), got {top_width}")
    if num_panels < 2:
        raise ValueError(f"num_panels must be >= 2, got {num_panels}")

    # Panel vertical division
    z_edges = np.linspace(0.0, tower_height, num_panels + 1)
    heights: List[float] = []
    k2_factors: List[float] = []
    design_velocities: List[float] = []
    wind_pressures: List[float] = []
    tower_drag_forces: List[float] = []

    c_f = compute_lattice_force_coefficient(wind_params.solidity_ratio)
    total_tower_drag = 0.0
    tower_overturning_moment = 0.0

    for i in range(num_panels):
        z_bot = z_edges[i]
        z_top = z_edges[i + 1]
        z_mid = 0.5 * (z_bot + z_top)
        dz = z_top - z_bot

        # Width at panel midpoint (linear taper)
        b_mid = base_width - (base_width - top_width) * (z_mid / tower_height)

        # IS 875 wind velocity V_z = V_b * k1 * k2 * k3 * k4
        k2 = compute_k2_factor(z_mid, wind_params.terrain_category)
        v_z = (
            wind_params.basic_wind_speed
            * wind_params.risk_coefficient_k1
            * k2
            * wind_params.topography_factor_k3
            * wind_params.cyclone_factor_k4
        )

        # Wind pressure p_z = 0.6 * V_z^2 (N/m^2) -> kN/m^2 (divide by 1000)
        p_z = 0.0006 * (v_z ** 2)

        # Effective frontal projected area of lattice panel
        gross_panel_area = b_mid * dz
        solid_panel_area = gross_panel_area * wind_params.solidity_ratio

        # Drag on panel framework: F = C_f * A_e * p_z * G_t (kN)
        f_panel = c_f * solid_panel_area * p_z * wind_params.gust_response_factor

        heights.append(round(float(z_mid), 2))
        k2_factors.append(round(float(k2), 3))
        design_velocities.append(round(float(v_z), 2))
        wind_pressures.append(round(float(p_z), 3))
        tower_drag_forces.append(round(float(f_panel), 2))

        total_tower_drag += f_panel
        tower_overturning_moment += f_panel * z_mid

    # Conductor aerodynamic wind load (acts at cross-arm level ~ 0.85 * H_tower)
    z_cross_arm = 0.85 * tower_height
    k2_arm = compute_k2_factor(z_cross_arm, wind_params.terrain_category)
    v_z_arm = (
        wind_params.basic_wind_speed
        * wind_params.risk_coefficient_k1
        * k2_arm
        * wind_params.topography_factor_k3
        * wind_params.cyclone_factor_k4
    )
    p_z_arm = 0.0006 * (v_z_arm ** 2)

    # Conductor projected wind area per phase
    conductor_area_per_cable = wind_params.conductor_diameter * wind_params.wind_span
    conductor_drag = (
        wind_params.num_conductors
        * conductor_area_per_cable
        * p_z_arm
        * wind_params.conductor_drag_coeff
        * wind_params.gust_response_factor
    )

    # Ground/shield wire wind load (acts at tower peak z = H_tower)
    k2_peak = compute_k2_factor(tower_height, wind_params.terrain_category)
    v_z_peak = (
        wind_params.basic_wind_speed
        * wind_params.risk_coefficient_k1
        * k2_peak
        * wind_params.topography_factor_k3
        * wind_params.cyclone_factor_k4
    )
    p_z_peak = 0.0006 * (v_z_peak ** 2)

    gw_area_per_cable = wind_params.ground_wire_diameter * wind_params.wind_span
    ground_wire_drag = (
        wind_params.num_ground_wires
        * gw_area_per_cable
        * p_z_peak
        * wind_params.conductor_drag_coeff
        * wind_params.gust_response_factor
    )

    # Net overturning moment and base shear
    conductors_overturning = conductor_drag * z_cross_arm + ground_wire_drag * tower_height
    total_overturning_moment = tower_overturning_moment + conductors_overturning
    total_base_shear = total_tower_drag + conductor_drag + ground_wire_drag

    z_eff = total_overturning_moment / total_base_shear if total_base_shear > 0 else 0.5 * tower_height

    return TowerWindProfileResult(
        heights=heights,
        k2_factors=k2_factors,
        design_velocities=design_velocities,
        wind_pressures=wind_pressures,
        tower_drag_forces=tower_drag_forces,
        total_tower_body_shear=round(float(total_tower_drag), 2),
        conductor_drag_shear=round(float(conductor_drag), 2),
        ground_wire_drag_shear=round(float(ground_wire_drag), 2),
        total_base_wind_shear=round(float(total_base_shear), 2),
        base_overturning_moment=round(float(total_overturning_moment), 2),
        effective_wind_thrust_height=round(float(z_eff), 2),
    )
