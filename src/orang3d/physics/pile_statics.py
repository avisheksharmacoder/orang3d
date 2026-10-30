"""
Bored Floating Pile Statics & Lateral Resistance Engine (Phase 3).
Implements Broms' (1964) method and IS 2911 (Part 1/Sec 2: 2010) lateral load capacity
in c-phi hill soils without a rock socket.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple, Optional
import numpy as np

from ..models.advanced_wall_params import PierAndPileGeometry
from ..models.wall_params import SoilProperties


@dataclass
class PileCapacityResult:
    """
    Lateral resistance and structural demand results for bored cast-in-situ floating piles.
    """
    embedment_length: float              # L_pile: Pile embedment length into hill soil (m)
    pile_diameter: float                 # D_p: Pile diameter (m)
    stiffness_factor_t: float            # T: Characteristic flexural stiffness factor (m)
    pile_classification: str             # "Rigid (Short)", "Intermediate", or "Flexible (Long)"
    depth_of_fixity: float               # z_f: Virtual depth of fixity per IS 2911 (m)
    ultimate_lateral_capacity: float     # H_ult: Ultimate lateral capacity per pile per Broms (kN)
    allowable_lateral_capacity: float    # H_allow = H_ult / 1.5 (kN)
    applied_lateral_load_per_pile: float # V_pile: Factored lateral shear demand per pile (kN)
    factor_of_safety_lateral: float      # FS_lateral = H_ult / V_pile (>= 1.5 required)
    status: str                          # "PASS" if FS_lateral >= 1.5 else "FAIL"
    max_pile_bending_moment: float       # M_pile,max: Maximum moment at depth of fixity (kNm)


def compute_broms_lateral_capacity(
    pier_pile: PierAndPileGeometry,
    soil: SoilProperties,
    applied_shear_per_pier: float,
    concrete_elastic_modulus: float = 30.0e6, # 30 GPa = 30,000,000 kPa
) -> PileCapacityResult:
    """
    Evaluates Broms' (1964) ultimate lateral resistance and IS 2911 depth of fixity
    for bored cast-in-situ piles embedded in c-phi soil under restrained head conditions.
    """
    if applied_shear_per_pier < 0:
        raise ValueError(f"applied_shear_per_pier cannot be negative, got {applied_shear_per_pier}")

    dp = pier_pile.pile_diameter
    lp = pier_pile.pile_length
    n_piles = pier_pile.num_piles_per_pier

    gamma = soil.foundation_unit_weight
    phi = soil.foundation_friction_angle
    c = soil.foundation_cohesion

    # 1. Structural pile properties
    # Moment of inertia for circular section: I_p = pi * D_p^4 / 64
    i_p = (math.pi * (dp ** 4)) / 64.0
    ep = concrete_elastic_modulus

    # Subgrade modulus nh per IS 2911: typically 5000 to 15000 kN/m^3 for medium/stiff soil
    # Correlated with soil friction angle
    nh = 400.0 * phi # kN/m^3

    # Characteristic stiffness factor T = (E_p * I_p / n_h)^(1/5) (meters)
    stiffness_t = ((ep * i_p) / nh) ** 0.2

    # Classification per IS 2911:
    if lp <= 2.0 * stiffness_t:
        classification = "Rigid (Short)"
    elif lp >= 4.0 * stiffness_t:
        classification = "Flexible (Long)"
    else:
        classification = "Intermediate"

    # Depth of fixity z_f per IS 2911 Table 2 (for restrained head pile in pile cap)
    depth_fixity = 2.0 * stiffness_t

    # 2. Broms' Ultimate Lateral Resistance in c-phi soil
    # Rankine passive earth pressure coefficient: K_p = tan^2(45 + phi/2)
    kp = math.tan(math.radians(45.0 + phi / 2.0)) ** 2

    # For restrained head pile in c-phi soil:
    # Frictional passive resistance: H_friction = 1.5 * K_p * gamma * D_p * L^2
    # Cohesive passive resistance: H_cohesion = 2.0 * c * sqrt(K_p) * D_p * L
    h_friction = 1.5 * kp * gamma * dp * (lp ** 2)
    h_cohesion = 2.0 * c * math.sqrt(kp) * dp * lp
    h_ult = h_friction + h_cohesion

    # Allowable lateral capacity (with code factor of safety 1.5 per IS 2911)
    h_allow = h_ult / 1.5

    # Demand per pile
    v_pile = applied_shear_per_pier / n_piles

    if v_pile > 1e-4:
        fs_lateral = h_ult / v_pile
    else:
        fs_lateral = 100.0

    status = "PASS" if fs_lateral >= 1.5 else "FAIL"

    # 3. Maximum bending moment in pile at depth of fixity (restrained head)
    # M_max = V_pile * z_f / 2
    m_max = (v_pile * depth_fixity) / 2.0

    return PileCapacityResult(
        embedment_length=lp,
        pile_diameter=dp,
        stiffness_factor_t=stiffness_t,
        pile_classification=classification,
        depth_of_fixity=depth_fixity,
        ultimate_lateral_capacity=h_ult,
        allowable_lateral_capacity=h_allow,
        applied_lateral_load_per_pile=v_pile,
        factor_of_safety_lateral=fs_lateral,
        status=status,
        max_pile_bending_moment=m_max,
    )


def calculate_minimum_pile_embedment(
    pier_pile: PierAndPileGeometry,
    soil: SoilProperties,
    applied_shear_per_pier: float,
    target_fs: float = 1.5,
) -> float:
    """
    Computes the exact closed-form minimum pile embedment length L_min required
    to achieve FS_lateral >= target_fs in c-phi soil:
        target_fs * V_pile = 1.5 * K_p * gamma * D_p * L^2 + 2 * c * sqrt(K_p) * D_p * L
        A * L^2 + B * L - C = 0
    """
    if applied_shear_per_pier <= 0:
        return 2.0 # Minimum nominal embedment

    dp = pier_pile.pile_diameter
    n_piles = pier_pile.num_piles_per_pier
    v_pile = applied_shear_per_pier / n_piles

    gamma = soil.foundation_unit_weight
    phi = soil.foundation_friction_angle
    c = soil.foundation_cohesion

    kp = math.tan(math.radians(45.0 + phi / 2.0)) ** 2

    # Quadratic equation: A * L^2 + B * L - C = 0
    A = 1.5 * kp * gamma * dp
    B = 2.0 * c * math.sqrt(kp) * dp
    C = target_fs * v_pile

    discriminant = (B ** 2) - (4.0 * A * (-C))
    l_min = (-B + math.sqrt(discriminant)) / (2.0 * A)

    # Minimum practical pile embedment is 3.0 m
    return max(float(l_min), 3.0)
