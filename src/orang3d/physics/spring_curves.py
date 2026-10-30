"""
Nonlinear Geotechnical Soil Spring Formulations (p-y, t-z, q-z) and Radiation Damping
for Beam on Nonlinear Winkler Foundation (BNWF) Analysis.

References:
- API RP 2A-WSD (2000): Recommended Practice for Planning, Designing and Constructing Fixed Offshore Platforms.
- Reese, L. C., Cox, W. R., and Koop, F. D. (1974): Analysis of laterally loaded piles in sand. OTC 2080.
- Matlock, H. (1970): Correlations for design of laterally loaded piles in soft clay. OTC 1204.
- Mosher, R. L. (1984): Load-transfer criteria for numerical analysis of axially loaded piles in sand.
- Meyerhof, G. G. (1976): Bearing capacity and settlement of pile foundations.
- Berger, E. et al. (1977) & Gazetas, G. and Dobry, R. (1984): Radiation damping dashpots in Winkler soil.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np

from ..models.advanced_wall_params import PierAndPileGeometry
from ..models.wall_params import SoilProperties


@dataclass
class PySpringParams:
    """Parameters for OpenSees PySimple1 lateral soil spring."""
    depth: float            # z: Depth below mudline / dredge line (m)
    p_ult: float            # p_ult: Ultimate lateral resistance per unit length (kN/m)
    p_ult_integrated: float # P_ult: Integrated force for tributary length = p_ult * dz (kN)
    y_50: float             # y_50: Displacement at 50% ultimate capacity (m)
    cd: float               # cd: Drag coefficient in PySimple1 (0.0 to 0.3)
    c_dashpot: float        # c_dashpot: Parallel radiation damping coefficient (kN*s/m)
    mat_type: int           # 1 for sand (Reese/API), 2 for clay (Matlock)


@dataclass
class TzSpringParams:
    """Parameters for OpenSees TzSimple1 vertical skin friction spring."""
    depth: float            # z: Depth below mudline (m)
    t_ult: float            # t_ult: Ultimate skin friction per unit length (kN/m)
    t_ult_integrated: float # T_ult: Integrated force = t_ult * dz (kN)
    z_50: float             # z_50: Displacement at 50% skin friction capacity (m)
    c_dashpot: float        # c_dashpot: Vertical radiation damping coefficient (kN*s/m)


@dataclass
class QzSpringParams:
    """Parameters for OpenSees QzSimple1 pile tip end-bearing spring."""
    q_ult: float            # Q_ult: Total ultimate tip resistance (kN)
    z_50: float             # z_50: Displacement at 50% ultimate tip capacity (m)
    c_dashpot: float        # c_dashpot: Tip radiation damping coefficient (kN*s/m)


@dataclass
class SoilSpringProfile:
    """Complete profile of Winkler springs along a pile length."""
    pile_length: float
    depths: np.ndarray
    tributary_lengths: np.ndarray
    py_springs: List[PySpringParams]
    tz_springs: List[TzSpringParams]
    qz_spring: QzSpringParams


def compute_py_sand_parameters(
    depth: float,
    gamma: float,
    phi: float,
    diameter: float,
    tributary_length: float,
    slope_angle: float = 0.0,
    water_table_depth: float = 100.0,
) -> PySpringParams:
    """
    Computes API RP 2A / Reese et al. (1974) lateral p-y spring parameters for sand.
    Includes sloping ground reduction factor: (1 - tan(beta_slope)).
    """
    if diameter <= 0:
        raise ValueError(f"diameter must be positive, got {diameter}")
    if tributary_length <= 0:
        raise ValueError(f"tributary_length must be positive, got {tributary_length}")
    if depth < 0:
        raise ValueError(f"depth cannot be negative, got {depth}")

    phi_deg = max(min(phi, 50.0), 15.0)
    phi_rad = math.radians(phi_deg)
    beta_rad = math.radians(abs(slope_angle))

    # Effective vertical overburden stress sigma_v'
    eff_gamma = gamma
    if depth > water_table_depth:
        eff_gamma = max(gamma - 9.81, 8.0)
    sigma_v = eff_gamma * depth

    # API RP 2A coefficients C1, C2, C3 as functions of friction angle
    # C1 = tan(45 - phi/2) * [tan(phi)*tan(45+phi/2) + tan^2(45+phi/2) - 1] (simplified polynomial)
    c1 = (phi_deg / 10.0) ** 1.35
    c2 = (phi_deg / 15.0) ** 1.1
    c3 = (phi_deg / 5.0) ** 1.4

    # Shallow wedge failure vs deep flow failure
    # p_us = (C1 * z + C2 * D) * sigma_v
    # p_ud = C3 * D * sigma_v
    # Protect against depth = 0
    z_eff = max(depth, 0.1)
    p_us = (c1 * z_eff + c2 * diameter) * (eff_gamma * z_eff)
    p_ud = c3 * diameter * (eff_gamma * z_eff)
    p_ult_level = min(p_us, p_ud)

    # Sloping ground reduction factor (Georgiadis 1991 / Reese)
    # Downslope loading on hill slope reduces ultimate capacity
    slope_factor = max(1.0 - math.tan(beta_rad), 0.25)
    p_ult = max(p_ult_level * slope_factor, 1.0) # kN/m

    # Initial subgrade reaction modulus rate k_h (kN/m^3) per API
    # Ranges from 5,000 (loose) to 35,000 (dense)
    k_h = 500.0 * (phi_deg ** 1.2) # kN/m^3
    a_factor = max(0.9, 3.0 - 0.8 * (z_eff / diameter))

    # y50: displacement at 0.5 * P_ult
    # p = A * p_ult * tanh(k * z / (A * p_ult) * y)
    # At p = 0.5 * p_ult, y50 = (A * p_ult / (k * z)) * arctanh(0.5 / A)
    ratio = min(0.5 / a_factor, 0.95)
    y_50 = (a_factor * p_ult / (k_h * z_eff)) * math.atanh(ratio)
    y_50 = max(min(y_50, 0.1 * diameter), 0.001)

    p_ult_int = p_ult * tributary_length

    # Berger radiation damping: c_dash = 2 * D * rho * V_s
    rho_soil = gamma / 9.81 # t/m^3
    vs = 100.0 + 3.0 * phi_deg # Approximate shear wave velocity (m/s)
    c_dash = 2.0 * diameter * rho_soil * vs * tributary_length

    return PySpringParams(
        depth=depth,
        p_ult=p_ult,
        p_ult_integrated=p_ult_int,
        y_50=y_50,
        cd=0.1,
        c_dashpot=c_dash,
        mat_type=1, # Sand
    )


def compute_py_clay_parameters(
    depth: float,
    gamma: float,
    cu: float,
    diameter: float,
    tributary_length: float,
    slope_angle: float = 0.0,
) -> PySpringParams:
    """
    Computes Matlock (1970) lateral p-y spring parameters for cohesive soil.
    """
    if diameter <= 0:
        raise ValueError(f"diameter must be positive, got {diameter}")
    if tributary_length <= 0:
        raise ValueError(f"tributary_length must be positive, got {tributary_length}")
    if depth < 0:
        raise ValueError(f"depth cannot be negative, got {depth}")

    cu_eff = max(cu, 10.0) # kPa
    beta_rad = math.radians(abs(slope_angle))

    # Matlock ultimate lateral capacity:
    # Shallow: p_us = (3 + gamma'*z / cu + J * z / D) * cu * D
    # Deep: p_ud = 9 * cu * D
    j_coeff = 0.5
    z_eff = max(depth, 0.1)
    p_us = (3.0 + (gamma * z_eff / cu_eff) + (j_coeff * z_eff / diameter)) * cu_eff * diameter
    p_ud = 9.0 * cu_eff * diameter
    p_ult_level = min(p_us, p_ud)

    # Sloping ground reduction
    slope_factor = max(1.0 - math.tan(beta_rad), 0.25)
    p_ult = max(p_ult_level * slope_factor, 1.0) # kN/m
    p_ult_int = p_ult * tributary_length

    # y50 = 2.5 * eps50 * D
    eps_50 = 0.01 # Typical for medium/stiff clay
    y_50 = max(2.5 * eps_50 * diameter, 0.002)

    # Radiation damping
    rho_soil = gamma / 9.81
    vs = max(math.sqrt(max(cu_eff, 10.0) * 1000.0 / (rho_soil * 1000.0)), 80.0)
    c_dash = 2.0 * diameter * rho_soil * vs * tributary_length

    return PySpringParams(
        depth=depth,
        p_ult=p_ult,
        p_ult_integrated=p_ult_int,
        y_50=y_50,
        cd=0.2,
        c_dashpot=c_dash,
        mat_type=2, # Clay
    )


def compute_tz_parameters(
    depth: float,
    gamma: float,
    phi: float,
    cu: float,
    diameter: float,
    tributary_length: float,
) -> TzSpringParams:
    """
    Computes Mosher (1984) / API RP 2A vertical skin friction t-z spring parameters.
    """
    perimeter = math.pi * diameter
    z_eff = max(depth, 0.1)

    if cu > 5.0 and phi < 15.0:
        # Cohesive soil: alpha method: t_ult = alpha * cu * perimeter
        alpha = min(max(0.5 * (cu / 100.0) ** (-0.5), 0.35), 1.0)
        unit_friction = alpha * cu
    else:
        # Granular soil: beta method: t_ult = beta * sigma_v' * perimeter
        delta_deg = 0.75 * phi
        k_earth = 1.0 - math.sin(math.radians(phi))
        sigma_v = gamma * z_eff
        unit_friction = k_earth * sigma_v * math.tan(math.radians(delta_deg))
        # Limit unit friction to 100 kPa per API
        unit_friction = min(unit_friction, 100.0)

    t_ult = max(unit_friction * perimeter, 1.0) # kN/m
    t_ult_int = t_ult * tributary_length

    # z50 for skin friction typically 1-3 mm (0.001 - 0.003 m)
    z_50 = 0.002

    # Vertical damping
    rho_soil = gamma / 9.81
    vs = 150.0
    c_dash = math.pi * diameter * rho_soil * vs * tributary_length

    return TzSpringParams(
        depth=depth,
        t_ult=t_ult,
        t_ult_integrated=t_ult_int,
        z_50=z_50,
        c_dashpot=c_dash,
    )


def compute_qz_parameters(
    diameter: float,
    gamma: float,
    phi: float,
    cu: float,
    pile_length: float,
) -> QzSpringParams:
    """
    Computes Meyerhof (1976) / Vijayvergiya (1977) pile tip end-bearing q-z spring parameters.
    """
    tip_area = (math.pi * (diameter ** 2)) / 4.0
    z_tip = max(pile_length, 1.0)

    if cu > 5.0 and phi < 15.0:
        # Cohesive end bearing: q_ult = 9 * cu * A_tip
        q_ult = 9.0 * cu * tip_area
    else:
        # Frictional end bearing: q_ult = Nq * sigma_v' * A_tip
        phi_rad = math.radians(phi)
        nq = math.tan(math.radians(45.0 + phi / 2.0)) ** 2 * math.exp(math.pi * math.tan(phi_rad))
        sigma_v = gamma * z_tip
        q_unit = min(sigma_v * nq, 10000.0) # Clamped per Meyerhof limit
        q_ult = q_unit * tip_area

    q_ult = max(q_ult, 10.0)

    # z50 for end-bearing typically 0.01 - 0.05 D
    z_50 = 0.02 * diameter

    # Tip radiation damping
    rho_soil = gamma / 9.81
    vp = 350.0 # P-wave velocity under tip (m/s)
    c_dash = tip_area * rho_soil * vp

    return QzSpringParams(
        q_ult=q_ult,
        z_50=z_50,
        c_dashpot=c_dash,
    )


def generate_soil_spring_profile(
    pier_pile: PierAndPileGeometry,
    soil: SoilProperties,
    slope_angle: float = 0.0,
    num_pile_nodes: int = 15,
) -> SoilSpringProfile:
    """
    Discretizes a bored pile into Winkler foundation segments and generates
    corresponding p-y, t-z, and q-z springs along its entire embedment.
    """
    if num_pile_nodes < 2:
        raise ValueError(f"num_pile_nodes must be >= 2, got {num_pile_nodes}")

    lp = pier_pile.pile_length
    dp = pier_pile.pile_diameter
    gamma = soil.foundation_unit_weight
    phi = soil.foundation_friction_angle
    cu = soil.foundation_cohesion

    depths = np.linspace(0.0, lp, num_pile_nodes, dtype=np.float64)
    dz = float(depths[1] - depths[0])

    # Tributary length for each node
    tributaries = np.full(num_pile_nodes, dz, dtype=np.float64)
    tributaries[0] = 0.5 * dz
    tributaries[-1] = 0.5 * dz

    py_springs: List[PySpringParams] = []
    tz_springs: List[TzSpringParams] = []

    is_clay = cu > 10.0 and phi < 20.0

    for depth, trib_len in zip(depths, tributaries):
        if is_clay:
            py = compute_py_clay_parameters(
                depth=depth,
                gamma=gamma,
                cu=cu,
                diameter=dp,
                tributary_length=trib_len,
                slope_angle=slope_angle,
            )
        else:
            py = compute_py_sand_parameters(
                depth=depth,
                gamma=gamma,
                phi=phi,
                diameter=dp,
                tributary_length=trib_len,
                slope_angle=slope_angle,
            )
        tz = compute_tz_parameters(
            depth=depth,
            gamma=gamma,
            phi=phi,
            cu=cu,
            diameter=dp,
            tributary_length=trib_len,
        )
        py_springs.append(py)
        tz_springs.append(tz)

    qz = compute_qz_parameters(
        diameter=dp,
        gamma=gamma,
        phi=phi,
        cu=cu,
        pile_length=lp,
    )

    return SoilSpringProfile(
        pile_length=lp,
        depths=depths,
        tributary_lengths=tributaries,
        py_springs=py_springs,
        tz_springs=tz_springs,
        qz_spring=qz,
    )


def reese_matlock_theoretical_displacement(
    lateral_shear: float,
    moment: float,
    elastic_modulus: float,
    moment_of_inertia: float,
    subgrade_rate_nh: float,
) -> float:
    """
    Computes theoretical closed-form pile head lateral deflection for a free/restrained
    pile in linear subgrade (Reese & Matlock 1956, Broms 1964):
        T = (E_p * I_p / n_h)^(1/5)
        y_head = A_y * (H * T^3 / (E_p * I_p)) + B_y * (M * T^2 / (E_p * I_p))
    For a fixed/restrained head pile: A_y ~ 0.93, B_y ~ -0.93.
    """
    if subgrade_rate_nh <= 0:
        raise ValueError(f"subgrade_rate_nh must be positive, got {subgrade_rate_nh}")
    ep_ip = elastic_modulus * moment_of_inertia
    if ep_ip <= 0:
        raise ValueError(f"E*I must be positive, got {ep_ip}")

    stiffness_t = (ep_ip / subgrade_rate_nh) ** 0.2
    # Reese & Matlock influence coefficients for long pile (L >= 4T)
    a_y = 2.43 # Free head shear influence factor
    b_y = 1.62 # Free head moment influence factor

    y_disp = (a_y * lateral_shear * (stiffness_t ** 3) + b_y * moment * (stiffness_t ** 2)) / ep_ip
    return float(y_disp)
