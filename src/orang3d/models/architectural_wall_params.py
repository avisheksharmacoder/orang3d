"""
Parametric Data Contracts for Architectural Retaining Wall Morphologies (Phase 7).

Supports five architectural/urban retaining systems:
  1. Stepped / Terraced Retaining Walls (2 to 4 tiers, bench width W_bench, tier heights H_i)
  2. L-Corner & Angled Wingwall Junctions (corner angle 60°..150°, 3D corner stiffener)
  3. Counterfort / Buttress Walls (spacing s_cf, thickness t_cf, rear counterfort or front buttress)
  4. Curved Plan-View Walls (plan radius R_plan, sweep angle, concave or convex toward backfill)
  5. MSE / Gabion / Crib Modular Walls (geogrid reinforcement, gabion baskets, or timber/RC cribs)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Optional, Tuple


class ArchWallMorphology(str, Enum):
    """Supported architectural retaining wall typologies."""

    STEPPED_TERRACED = "stepped_terraced"
    CORNER_WINGWALL = "corner_wingwall"
    COUNTERFORT = "counterfort"
    CURVED_PLAN = "curved_plan"
    MSE_GABION_CRIB = "mse_gabion_crib"


@dataclass
class SteppedTerracedWallParams:
    """2-to-4 tier stepped / terraced cantilever retaining system."""

    num_tiers: int = 3
    tier_height: float = 2.5
    tier_heights: Optional[Tuple[float, ...]] = None
    bench_width: float = 1.8
    wall_length: float = 10.0
    stem_thickness_top: float = 0.28
    stem_thickness_base: float = 0.42
    footing_thickness: float = 0.45
    toe_length: float = 0.55
    heel_length: float = 1.25
    concrete_unit_weight: float = 25.0

    def __post_init__(self) -> None:
        if not (2 <= int(self.num_tiers) <= 4):
            raise ValueError(f"num_tiers must be between 2 and 4, got {self.num_tiers}")
        self.num_tiers = int(self.num_tiers)
        if self.tier_height <= 0.0:
            raise ValueError(f"tier_height must be positive, got {self.tier_height}")
        if self.tier_heights is not None:
            self.tier_heights = tuple(float(h) for h in self.tier_heights)
            if len(self.tier_heights) != self.num_tiers:
                raise ValueError(
                    f"len(tier_heights)={len(self.tier_heights)} must match num_tiers={self.num_tiers}"
                )
            if any(h <= 0.0 for h in self.tier_heights):
                raise ValueError("All tier_heights must be positive")
        if self.bench_width < 0.2:
            raise ValueError(f"bench_width must be >= 0.2 m, got {self.bench_width}")
        if self.wall_length <= 0.0:
            raise ValueError(f"wall_length must be positive, got {self.wall_length}")
        if self.stem_thickness_top <= 0.0 or self.stem_thickness_base < self.stem_thickness_top:
            raise ValueError("stem_thickness_base must be >= stem_thickness_top > 0")
        if self.footing_thickness <= 0.0:
            raise ValueError("footing_thickness must be positive")

    @property
    def resolved_tier_heights(self) -> Tuple[float, ...]:
        """Returns per-tier stem heights from bottom tier (0) to top tier (n-1)."""
        if self.tier_heights is not None:
            return self.tier_heights
        return tuple(self.tier_height for _ in range(self.num_tiers))

    @property
    def total_retained_height(self) -> float:
        """Cumulative vertical elevation rise across all terraced tiers (m)."""
        return float(sum(self.resolved_tier_heights) + self.footing_thickness)


@dataclass
class CornerWingwallParams:
    """L-Corner or angled wingwall junction with corner haunch/stiffener."""

    corner_angle_deg: float = 90.0
    primary_length: float = 6.5
    wing_length: float = 5.0
    stem_height: float = 5.0
    stem_thickness_top: float = 0.30
    stem_thickness_base: float = 0.48
    footing_thickness: float = 0.55
    toe_length: float = 0.75
    heel_length: float = 1.90
    stiffener_fillet_width: float = 0.85
    concrete_grade: str = "M30"
    concrete_unit_weight: float = 25.0

    def __post_init__(self) -> None:
        if not (60.0 <= self.corner_angle_deg <= 150.0):
            raise ValueError(
                f"corner_angle_deg must be in [60, 150] deg, got {self.corner_angle_deg}"
            )
        if self.primary_length <= 1.0 or self.wing_length <= 1.0:
            raise ValueError("primary_length and wing_length must be > 1.0 m")
        if self.stem_height <= 0.0 or self.footing_thickness <= 0.0:
            raise ValueError("stem_height and footing_thickness must be positive")
        if self.stiffener_fillet_width < 0.0:
            raise ValueError("stiffener_fillet_width must be >= 0")


@dataclass
class CounterfortWallParams:
    """Counterfort (rear tension) or buttress (front compression) retaining wall."""

    wall_height: float = 7.5
    wall_length: float = 12.0
    counterfort_spacing: float = 3.2
    counterfort_thickness: float = 0.38
    counterfort_top_offset: float = 0.35
    is_buttress: bool = False
    stem_thickness: float = 0.35
    footing_thickness: float = 0.65
    toe_length: float = 1.1
    heel_length: float = 3.2
    concrete_grade: str = "M30"
    concrete_unit_weight: float = 25.0

    def __post_init__(self) -> None:
        if self.wall_height <= 0.0 or self.wall_length <= 0.0:
            raise ValueError("wall_height and wall_length must be positive")
        if self.counterfort_spacing <= self.counterfort_thickness:
            raise ValueError("counterfort_spacing must exceed counterfort_thickness")
        if self.counterfort_thickness <= 0.1 or self.stem_thickness <= 0.1:
            raise ValueError("thicknesses must be > 0.1 m")
        if self.footing_thickness <= 0.0:
            raise ValueError("footing_thickness must be positive")

    @property
    def num_bays(self) -> int:
        """Number of clear slab bays spanned between counterforts."""
        return max(1, int(round(self.wall_length / self.counterfort_spacing)))

    @property
    def clear_span(self) -> float:
        """Clear center-to-center counterfort slab span s_cf - t_cf (m)."""
        return max(0.3, self.counterfort_spacing - self.counterfort_thickness)


@dataclass
class CurvedPlanWallParams:
    """Architectural retaining wall curved smoothly in horizontal plan view."""

    plan_radius: float = 12.0
    sweep_angle_deg: float = 65.0
    concave_to_backfill: bool = True
    stem_height: float = 5.0
    stem_thickness_top: float = 0.30
    stem_thickness_base: float = 0.48
    footing_thickness: float = 0.55
    toe_length: float = 0.70
    heel_length: float = 1.80
    concrete_unit_weight: float = 25.0

    def __post_init__(self) -> None:
        if self.plan_radius < 2.0:
            raise ValueError(f"plan_radius must be >= 2.0 m, got {self.plan_radius}")
        if not (10.0 <= self.sweep_angle_deg <= 150.0):
            raise ValueError(
                f"sweep_angle_deg must be in [10, 150] deg, got {self.sweep_angle_deg}"
            )
        if self.stem_height <= 0.0 or self.footing_thickness <= 0.0:
            raise ValueError("stem_height and footing_thickness must be positive")
        if self.plan_radius <= self.toe_length + self.heel_length + self.stem_thickness_base:
            raise ValueError("plan_radius must exceed total footing width to avoid self-intersection")

    @property
    def arc_length(self) -> float:
        """Plan centerline arc length R_plan * sweep_rad (m)."""
        return self.plan_radius * math.radians(self.sweep_angle_deg)


@dataclass
class MSEGabionWallParams:
    """Modular MSE / Gabion / Crib landscape retaining wall system."""

    wall_subtype: str = "mse_geogrid"  # "mse_geogrid", "gabion", "crib"
    num_courses: int = 6
    course_height: float = 0.85
    block_depth: float = 1.05
    wall_length: float = 10.0
    batter_deg: float = 6.0
    reinforcement_length: float = 4.2
    vertical_spacing: float = 0.85
    tensile_capacity_kn_per_m: float = 45.0
    pullout_friction_factor: float = 0.80
    infill_unit_weight: float = 21.0

    def __post_init__(self) -> None:
        if self.wall_subtype not in ("mse_geogrid", "gabion", "crib"):
            raise ValueError(f"Unsupported wall_subtype: {self.wall_subtype}")
        if not (2 <= int(self.num_courses) <= 20):
            raise ValueError(f"num_courses must be in [2, 20], got {self.num_courses}")
        self.num_courses = int(self.num_courses)
        if self.course_height <= 0.0 or self.block_depth <= 0.0 or self.wall_length <= 0.0:
            raise ValueError("course_height, block_depth, and wall_length must be positive")
        if not (0.0 <= self.batter_deg <= 20.0):
            raise ValueError(f"batter_deg must be in [0, 20] deg, got {self.batter_deg}")
        if self.reinforcement_length <= 0.0 or self.tensile_capacity_kn_per_m <= 0.0:
            raise ValueError("reinforcement_length and tensile_capacity must be positive")

    @property
    def total_height(self) -> float:
        """Total stacked facing height (m)."""
        return self.num_courses * self.course_height


@dataclass
class ArchitecturalWallSpec:
    """Unified architectural retaining structure bundle across all 5 morphologies."""

    morphology: ArchWallMorphology = ArchWallMorphology.STEPPED_TERRACED
    stepped: SteppedTerracedWallParams = field(default_factory=SteppedTerracedWallParams)
    corner: CornerWingwallParams = field(default_factory=CornerWingwallParams)
    counterfort: CounterfortWallParams = field(default_factory=CounterfortWallParams)
    curved_plan: CurvedPlanWallParams = field(default_factory=CurvedPlanWallParams)
    mse: MSEGabionWallParams = field(default_factory=MSEGabionWallParams)

    def to_dict(self) -> dict[str, Any]:
        """Serializes architectural wall configuration to plain dictionary."""
        data = asdict(self)
        data["morphology"] = self.morphology.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchitecturalWallSpec:
        """Reconstructs ArchitecturalWallSpec from dictionary."""
        return cls(
            morphology=ArchWallMorphology(data.get("morphology", ArchWallMorphology.STEPPED_TERRACED)),
            stepped=SteppedTerracedWallParams(**data.get("stepped", {})),
            corner=CornerWingwallParams(**data.get("corner", {})),
            counterfort=CounterfortWallParams(**data.get("counterfort", {})),
            curved_plan=CurvedPlanWallParams(**data.get("curved_plan", {})),
            mse=MSEGabionWallParams(**data.get("mse", {})),
        )

