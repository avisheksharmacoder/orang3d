"""
Data contracts and parameters for Indian Standard (IS) Design Codes (Phase 1):
IS 1893 (Part 1/Part 3), IS 456, IS 2911, and IS 800.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
import math
from typing import Any


class SeismicZone(str, Enum):
    """Seismic Zones defined in IS 1893 (Part 1/Part 3): 2016."""
    ZONE_II = "Zone II"
    ZONE_III = "Zone III"
    ZONE_IV = "Zone IV"
    ZONE_V = "Zone V"


class FoundationSoilType(str, Enum):
    """Foundation soil classification per IS 1893 (Part 1): 2016 Table 2."""
    TYPE_I = "Type I"     # Rock or Hard Soils
    TYPE_II = "Type II"   # Medium or Stiff Soils
    TYPE_III = "Type III" # Soft Soils


# Seismic Zone Factors (Z) per IS 1893 Table 3
SEISMIC_ZONE_FACTORS: dict[str, float] = {
    SeismicZone.ZONE_II.value: 0.10,
    SeismicZone.ZONE_III.value: 0.16,
    SeismicZone.ZONE_IV.value: 0.24,
    SeismicZone.ZONE_V.value: 0.36,
    "Zone II": 0.10,
    "Zone III": 0.16,
    "Zone IV": 0.24,
    "Zone V": 0.36,
}


@dataclass
class IndianDesignStandards:
    """
    Design parameters conforming to Indian Standards for earthquake-resistant
    and structural retaining wall engineering:
    - IS 1893 (Part 1: 2016 / Part 3: 2014): Seismic Criteria
    - IS 456: 2000: Plain and Reinforced Concrete
    - IS 2911 (Part 1/Sec 2: 2010): Bored Cast-in-Situ Piles
    - IS 800: 2007: General Construction in Steel
    """
    seismic_zone: str = "Zone V"
    importance_factor: float = 1.5           # I: 1.0 (general), 1.2 (community), 1.5 (critical / lifeline)
    response_reduction_factor: float = 3.0   # R: 3.0 (OMRF / Gravity), 5.0 (SMRF ductile frame)
    soil_type: str = "Type II"               # Foundation Soil Type I, II, or III
    damping_ratio: float = 0.05              # xi: 5% critical damping for RC structures
    concrete_grade: str = "M30"              # Concrete compressive grade (>= M25 for retaining walls)
    steel_grade: str = "Fe500"               # Reinforcing steel grade (Fe415, Fe500, Fe550, Fe500D)
    partial_safety_factor_concrete: float = 1.5  # gamma_mc per IS 456 Clause 36.4.2.1
    partial_safety_factor_steel: float = 1.15    # gamma_ms per IS 456 Clause 36.4.2.1

    def __post_init__(self):
        if self.seismic_zone not in SEISMIC_ZONE_FACTORS:
            raise ValueError(
                f"Invalid seismic_zone '{self.seismic_zone}'. Must be one of {list(SEISMIC_ZONE_FACTORS.keys())}"
            )
        valid_soils = [st.value for st in FoundationSoilType] + ["Type I", "Type II", "Type III"]
        if self.soil_type not in valid_soils:
            raise ValueError(
                f"Invalid soil_type '{self.soil_type}'. Must be one of {valid_soils}"
            )
        if self.importance_factor < 1.0:
            raise ValueError(
                f"importance_factor must be >= 1.0, got {self.importance_factor}"
            )
        if self.response_reduction_factor < 1.0:
            raise ValueError(
                f"response_reduction_factor must be >= 1.0, got {self.response_reduction_factor}"
            )
        if not (0.0 < self.damping_ratio <= 0.20):
            raise ValueError(
                f"damping_ratio must be between 0.0 and 0.20, got {self.damping_ratio}"
            )
        if self.partial_safety_factor_concrete <= 1.0:
            raise ValueError(
                f"partial_safety_factor_concrete must be > 1.0, got {self.partial_safety_factor_concrete}"
            )
        if self.partial_safety_factor_steel <= 1.0:
            raise ValueError(
                f"partial_safety_factor_steel must be > 1.0, got {self.partial_safety_factor_steel}"
            )

        # Validate concrete grade
        if not self.concrete_grade.startswith("M") or self.f_ck < 25.0:
            raise ValueError(
                f"concrete_grade must be at least M25 for retaining structures per IS 456, got '{self.concrete_grade}'"
            )

        # Validate steel grade
        valid_steel = {"Fe415", "Fe500", "Fe550", "Fe500D"}
        if self.steel_grade not in valid_steel:
            raise ValueError(
                f"steel_grade must be one of {valid_steel}, got '{self.steel_grade}'"
            )

    @property
    def zone_factor(self) -> float:
        """Seismic Zone Factor Z per IS 1893 Table 3."""
        return SEISMIC_ZONE_FACTORS[self.seismic_zone]

    @property
    def f_ck(self) -> float:
        """Characteristic compressive cube strength of concrete in MPa (IS 456)."""
        numeric_part = self.concrete_grade[1:] if self.concrete_grade.startswith("M") else self.concrete_grade
        try:
            return float(numeric_part)
        except ValueError:
            raise ValueError(f"Cannot parse characteristic strength from grade '{self.concrete_grade}'")

    @property
    def f_y(self) -> float:
        """Characteristic yield strength of steel in MPa (IS 456 / IS 1786)."""
        yield_map = {
            "Fe415": 415.0,
            "Fe500": 500.0,
            "Fe550": 550.0,
            "Fe500D": 500.0,
        }
        if self.steel_grade in yield_map:
            return yield_map[self.steel_grade]
        clean = self.steel_grade.lstrip("Fe").rstrip("D")
        try:
            return float(clean)
        except ValueError:
            raise ValueError(f"Cannot parse yield strength from grade '{self.steel_grade}'")

    def damping_multiplying_factor(self) -> float:
        """
        Damping factor eta per IS 1893 Table 3 for damping other than 5%:
        eta = sqrt(10 / (5 + 100 * xi))
        """
        return math.sqrt(10.0 / (5.0 + 100.0 * self.damping_ratio))

    def spectral_acceleration_ratio(self, time_period: float) -> float:
        """
        Normalized design spectral acceleration (Sa / g) per IS 1893 (Part 1): 2016 Clause 6.4.2
        for 5% damping, adjusted by damping multiplying factor.
        """
        if time_period < 0:
            raise ValueError(f"time_period must be non-negative, got {time_period}")

        t = max(time_period, 1e-4)
        soil = self.soil_type

        # 5% Damping curves
        if soil == FoundationSoilType.TYPE_I.value or soil == "Type I":
            if t <= 0.10:
                sa_g_5 = 1.0 + 15.0 * t
            elif t <= 0.40:
                sa_g_5 = 2.50
            else:
                sa_g_5 = min(2.50, 1.00 / t)
        elif soil == FoundationSoilType.TYPE_II.value or soil == "Type II":
            if t <= 0.10:
                sa_g_5 = 1.0 + 15.0 * t
            elif t <= 0.55:
                sa_g_5 = 2.50
            else:
                sa_g_5 = min(2.50, 1.36 / t)
        else: # Type III Soft
            if t <= 0.10:
                sa_g_5 = 1.0 + 15.0 * t
            elif t <= 0.67:
                sa_g_5 = 2.50
            else:
                sa_g_5 = min(2.50, 1.67 / t)

        # Apply damping correction
        eta = self.damping_multiplying_factor()
        return sa_g_5 * eta

    def compute_horizontal_seismic_coefficient(self, time_period: float = 0.5) -> float:
        """
        Design horizontal seismic coefficient A_h per IS 1893 (Part 1) Clause 6.4.2:
        A_h = (Z / 2) * (I / R) * (Sa / g)
        """
        sa_g = self.spectral_acceleration_ratio(time_period)
        return (self.zone_factor / 2.0) * (self.importance_factor / self.response_reduction_factor) * sa_g

    def compute_vertical_seismic_coefficient(self, time_period: float = 0.5) -> float:
        """
        Design vertical seismic coefficient A_v per IS 1893 (Part 1) Clause 6.4.6:
        A_v = (2 / 3) * A_h
        """
        a_h = self.compute_horizontal_seismic_coefficient(time_period)
        return (2.0 / 3.0) * a_h

    def to_dict(self) -> dict[str, Any]:
        """Serialize dataclass to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IndianDesignStandards:
        """Construct dataclass instance from dictionary."""
        return cls(**data)
