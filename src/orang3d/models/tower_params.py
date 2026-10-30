"""
Data contracts for uphill high-voltage transmission tower superstructures
and coupled foundation interactions under multi-hazard loads (Phase 1).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class TransmissionTowerParams:
    """
    Parametric specifications for an uphill high-voltage lattice transmission tower
    subjected to combined wind (IS 875 Pt 3), broken-wire conditions (IS 802),
    and earthquake ground motion.
    Units: meters (m), kN, kNm, degrees (°).
    """
    base_width: float = 6.0              # B_tower: Transverse base footprint dimension (m)
    base_length: float = 6.0             # L_tower: Longitudinal base footprint dimension (m)
    total_height: float = 35.0           # H_tower: Total vertical height of tower structure (m)
    crest_offset: float = 8.0            # X_offset: Distance from wall crest to nearest tower legs (m)
    vertical_load_per_leg: float = 250.0 # P_leg: Dead + live vertical compression reaction per leg (kN)
    wind_shear_per_leg: float = 45.0     # V_wind: Horizontal wind shear force per leg per IS 875 (kN)
    broken_wire_tension: float = 80.0    # T_bw: Longitudinal unbalanced tension pull per IS 802 (kN)
    seismic_mass_ratio: float = 0.15     # Dynamic effective mass ratio participating in inertial shear
    steel_grade: str = "E250"            # Structural steel grade per IS 2062 / IS 802

    def __post_init__(self):
        if self.base_width <= 0:
            raise ValueError(f"base_width must be positive, got {self.base_width}")
        if self.base_length <= 0:
            raise ValueError(f"base_length must be positive, got {self.base_length}")
        if self.total_height <= 0:
            raise ValueError(f"total_height must be positive, got {self.total_height}")
        if self.crest_offset < 0:
            raise ValueError(f"crest_offset cannot be negative, got {self.crest_offset}")
        if self.vertical_load_per_leg <= 0:
            raise ValueError(
                f"vertical_load_per_leg must be positive, got {self.vertical_load_per_leg}"
            )
        if self.wind_shear_per_leg < 0:
            raise ValueError(
                f"wind_shear_per_leg cannot be negative, got {self.wind_shear_per_leg}"
            )
        if self.broken_wire_tension < 0:
            raise ValueError(
                f"broken_wire_tension cannot be negative, got {self.broken_wire_tension}"
            )
        if not (0.0 <= self.seismic_mass_ratio <= 1.0):
            raise ValueError(
                f"seismic_mass_ratio must be between 0.0 and 1.0, got {self.seismic_mass_ratio}"
            )

    @property
    def total_vertical_load(self) -> float:
        """Total vertical dead + live weight across all 4 legs (kN)."""
        return 4.0 * self.vertical_load_per_leg

    @property
    def total_wind_shear(self) -> float:
        """Total horizontal wind shear across all 4 legs (kN)."""
        return 4.0 * self.wind_shear_per_leg

    @property
    def wind_overturning_moment(self) -> float:
        """
        Overturning moment about base due to wind acting at mid-height (kNm).
        M_wind = V_wind_total * (H_tower / 2)
        """
        return self.total_wind_shear * (self.total_height / 2.0)

    @property
    def broken_wire_torsional_moment(self) -> float:
        """
        Torsional yaw moment about tower vertical axis due to broken conductor (kNm).
        T_bw acts at tower cross-arm tip (lever arm = L_tower / 2).
        """
        return self.broken_wire_tension * (self.base_length / 2.0)

    @property
    def broken_wire_overturning_moment(self) -> float:
        """
        Longitudinal overturning moment due to broken conductor tension at cross-arm (kNm).
        M_bw = T_bw * (0.85 * H_tower)
        """
        return self.broken_wire_tension * (0.85 * self.total_height)

    def compute_leg_vertical_reactions(
        self,
        include_wind: bool = True,
        include_broken_wire: bool = False,
    ) -> dict[str, float]:
        """
        Computes 4 corner leg vertical reactions (kN) accounting for overturning couples:
        Leg 1: Uphill Left
        Leg 2: Uphill Right
        Leg 3: Downhill Right (toward retaining wall)
        Leg 4: Downhill Left (toward retaining wall)

        Returns dictionary mapping leg IDs to net vertical reaction (positive = compression).
        """
        r_base = self.vertical_load_per_leg

        # Wind load acting transverse/downhill toward retaining wall:
        delta_p_wind = 0.0
        if include_wind and self.base_width > 0:
            # Overturning couple transferred to front 2 legs (+) and rear 2 legs (-)
            delta_p_wind = self.wind_overturning_moment / (2.0 * self.base_width)

        # Broken wire load acting longitudinally:
        delta_p_bw = 0.0
        if include_broken_wire and self.base_length > 0:
            delta_p_bw = self.broken_wire_overturning_moment / (2.0 * self.base_length)

        # Net reactions
        r1 = r_base - delta_p_wind - delta_p_bw # Rear left
        r2 = r_base - delta_p_wind + delta_p_bw # Rear right
        r3 = r_base + delta_p_wind + delta_p_bw # Front right (downhill)
        r4 = r_base + delta_p_wind - delta_p_bw # Front left (downhill)

        return {
            "leg_1_uphill_left": r1,
            "leg_2_uphill_right": r2,
            "leg_3_downhill_right": r3,
            "leg_4_downhill_left": r4,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize dataclass to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransmissionTowerParams:
        """Construct dataclass instance from dictionary."""
        return cls(**data)
