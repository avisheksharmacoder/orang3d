"""
Advanced data contracts and validation schemas for pile-supported multi-strut
curved shell retaining walls on seismic hill slopes (Phase 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import math
from typing import Any


@dataclass
class CurvedShellGeometry:
    """
    Parametric geometry for a 3D Reinforced Concrete Curved Shell Retaining Panel
    spanning horizontally between discrete vertical piers.
    Units: meters (m), degrees (°), kN, kN/m^3.
    """
    radius: float = 4.0                  # R: Radius of shell cylindrical curvature (m)
    subtended_angle: float = 60.0        # 2*theta: Subtended arc angle in degrees (0 < 2*theta < 180)
    thickness: float = 0.25              # t_s: Shell panel thickness (m, must be > 0.05 m)
    crown_to_backfill: bool = True       # Orientation: True = convex toward backfill (arching in compression)
    bay_span: float = 4.0                # L_bay: Clear/center span between vertical piers (m)
    panel_height: float = 6.0            # H_p: Vertical panel height (m)
    concrete_grade: str = "M30"          # Concrete designation per IS 456
    concrete_unit_weight: float = 25.0   # Unit weight of reinforced concrete (kN/m^3)

    def __post_init__(self):
        if self.radius <= 0:
            raise ValueError(f"radius must be positive, got {self.radius}")
        if not (0.0 < self.subtended_angle < 180.0):
            raise ValueError(
                f"subtended_angle must be strictly between 0 and 180 degrees, got {self.subtended_angle}"
            )
        if self.thickness <= 0.05:
            raise ValueError(
                f"thickness must be > 0.05 m (50 mm minimum structural shell thickness), got {self.thickness}"
            )
        if self.bay_span <= 0:
            raise ValueError(f"bay_span must be positive, got {self.bay_span}")
        if self.panel_height <= 0:
            raise ValueError(f"panel_height must be positive, got {self.panel_height}")
        if self.concrete_unit_weight <= 0:
            raise ValueError(
                f"concrete_unit_weight must be positive, got {self.concrete_unit_weight}"
            )
        if self.bay_span > 2.0 * self.radius:
            raise ValueError(
                f"bay_span ({self.bay_span}) cannot exceed cylinder diameter 2*R ({2.0 * self.radius})"
            )

    @property
    def half_angle_rad(self) -> float:
        """Half of the subtended arc angle theta in radians."""
        return math.radians(self.subtended_angle / 2.0)

    @property
    def arc_length(self) -> float:
        """Arc perimeter length along the shell curved profile S = R * (2*theta_rad)."""
        return self.radius * math.radians(self.subtended_angle)

    @property
    def chord_length(self) -> float:
        """Geometric straight chord length spanning between panel ends C = 2 * R * sin(theta)."""
        return 2.0 * self.radius * math.sin(self.half_angle_rad)

    @property
    def crown_sagitta(self) -> float:
        """Crown arching rise / sagitta f = R * (1 - cos(theta))."""
        return self.radius * (1.0 - math.cos(self.half_angle_rad))

    @property
    def surface_area(self) -> float:
        """Curved surface area of the shell facing (m^2)."""
        return self.arc_length * self.panel_height

    @property
    def concrete_volume(self) -> float:
        """Total concrete volume of one shell panel (m^3)."""
        return self.surface_area * self.thickness

    @property
    def total_weight(self) -> float:
        """Total dead load weight of one shell panel (kN)."""
        return self.concrete_volume * self.concrete_unit_weight

    def to_dict(self) -> dict[str, Any]:
        """Serialize dataclass to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CurvedShellGeometry:
        """Construct dataclass instance from dictionary."""
        return cls(**data)


@dataclass
class PierAndPileGeometry:
    """
    Parametric geometry for vertical reinforced concrete piers rigidly coupled
    to underlying bored cast-in-situ floating piles.
    Units: meters (m), kN, kN/m^3.
    """
    pier_width: float = 0.8              # b_p: Vertical pier face width (m)
    pier_depth: float = 1.0              # d_p: Dimension into slope / wall thickness (m)
    pier_height: float = 6.5             # H_pier: Total height of pier column (m)
    pile_diameter: float = 0.8           # D_p: Bored pile circular diameter (m)
    pile_length: float = 10.0            # L_pile: Pile embedment length into hill soil (m)
    num_piles_per_pier: int = 2          # n_pile: Number of bored piles per pier
    pile_spacing: float = 2.5            # s_p: Center-to-center pile spacing (m)
    pile_cap_width: float = 1.2          # b_cap: Pile cap transverse dimension (m)
    pile_cap_length: float = 3.5         # l_cap: Pile cap longitudinal dimension (m)
    pile_cap_depth: float = 1.0          # d_cap: Pile cap vertical thickness (m)
    concrete_grade: str = "M30"          # Concrete designation per IS 456
    concrete_unit_weight: float = 25.0   # Unit weight of reinforced concrete (kN/m^3)
    rock_socket_length: float = 1.5      # L_socket: Bored pile embedment into bedrock (m)

    def __post_init__(self):
        if self.pier_width <= 0:
            raise ValueError(f"pier_width must be positive, got {self.pier_width}")
        if self.pier_depth <= 0:
            raise ValueError(f"pier_depth must be positive, got {self.pier_depth}")
        if self.pier_height <= 0:
            raise ValueError(f"pier_height must be positive, got {self.pier_height}")
        if self.pile_diameter <= 0:
            raise ValueError(f"pile_diameter must be positive, got {self.pile_diameter}")
        if self.pile_length <= 0:
            raise ValueError(f"pile_length must be positive, got {self.pile_length}")
        if self.rock_socket_length < 0:
            raise ValueError(f"rock_socket_length cannot be negative, got {self.rock_socket_length}")
        if self.num_piles_per_pier < 1:
            raise ValueError(f"num_piles_per_pier must be >= 1, got {self.num_piles_per_pier}")

        if self.num_piles_per_pier > 1:
            min_spacing = 2.5 * self.pile_diameter
            if self.pile_spacing < min_spacing:
                raise ValueError(
                    f"pile_spacing ({self.pile_spacing} m) must be >= 2.5 * pile_diameter "
                    f"({min_spacing:.2f} m) to prevent group block shear failure per IS 2911"
                )
        else:
            if self.pile_spacing < 0:
                raise ValueError(f"pile_spacing cannot be negative, got {self.pile_spacing}")

        if self.pile_cap_width <= 0:
            raise ValueError(f"pile_cap_width must be positive, got {self.pile_cap_width}")
        if self.pile_cap_length <= 0:
            raise ValueError(f"pile_cap_length must be positive, got {self.pile_cap_length}")
        if self.pile_cap_depth <= 0:
            raise ValueError(f"pile_cap_depth must be positive, got {self.pile_cap_depth}")
        if self.concrete_unit_weight <= 0:
            raise ValueError(
                f"concrete_unit_weight must be positive, got {self.concrete_unit_weight}"
            )

    @property
    def pile_cross_sectional_area(self) -> float:
        """Cross-sectional area of a single circular bored pile (m^2)."""
        return math.pi * (self.pile_diameter / 2.0) ** 2

    @property
    def pile_perimeter(self) -> float:
        """Circumferential perimeter of a single circular bored pile (m)."""
        return math.pi * self.pile_diameter

    @property
    def total_pile_length(self) -> float:
        """Total cumulative length of all piles under this pier (m)."""
        return self.num_piles_per_pier * self.pile_length

    @property
    def pier_volume(self) -> float:
        """Volume of vertical pier above pile cap (m^3)."""
        return self.pier_width * self.pier_depth * self.pier_height

    @property
    def pile_cap_volume(self) -> float:
        """Volume of pile cap (m^3)."""
        return self.pile_cap_width * self.pile_cap_length * self.pile_cap_depth

    @property
    def total_piles_volume(self) -> float:
        """Volume of all piles under this pier (m^3)."""
        return self.num_piles_per_pier * self.pile_cross_sectional_area * self.pile_length

    @property
    def total_substructure_volume(self) -> float:
        """Total volume of pier + cap + bored piles (m^3)."""
        return self.pier_volume + self.pile_cap_volume + self.total_piles_volume

    @property
    def total_substructure_weight(self) -> float:
        """Total self-weight of pier + cap + bored piles (kN)."""
        return self.total_substructure_volume * self.concrete_unit_weight

    def to_dict(self) -> dict[str, Any]:
        """Serialize dataclass to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PierAndPileGeometry:
        """Construct dataclass instance from dictionary."""
        return cls(**data)


@dataclass
class StrutSupportSystem:
    """
    Parametric specification for multi-tier raking steel struts or prestressed anchors
    supporting vertical retaining piers.
    Units: meters (m), degrees (°), m^2, m^4, kPa, MPa, kN.
    """
    strut_levels: list[float] = field(default_factory=lambda: [2.5, 5.0])
    inclination_angle: float = 25.0      # alpha_strut: Downward inclination angle in degrees (0 - 60)
    cross_section_area: float = 0.015    # A_s: Structural steel section area (m^2)
    moment_of_inertia: float = 1.5e-4    # I_s: Moment of inertia (m^4)
    elastic_modulus: float = 2.0e8       # E_s: Steel Young's modulus in kPa (200 GPa)
    yield_strength: float = 250.0        # f_y: Steel yield strength in MPa (e.g. E250 / IS 2062)
    pre_stress_load: float = 50.0        # P_0: Installation pre-stress lock-off load per strut (kN)
    allowable_slenderness: float = 180.0 # lambda_max: Allowable compression member slenderness (IS 800)
    unbraced_length: float = 8.0         # L_strut: Effective unbraced length of strut (m)
    steel_grade: str = "E250"            # Structural steel grade per IS 2062 / IS 800
    inclination_angle_deg: Optional[float] = None

    def __post_init__(self):
        if self.inclination_angle_deg is not None:
            self.inclination_angle = self.inclination_angle_deg
        else:
            self.inclination_angle_deg = self.inclination_angle

        if not self.strut_levels:
            raise ValueError("strut_levels cannot be empty")
        for i, lvl in enumerate(self.strut_levels):
            if lvl < 0:
                raise ValueError(f"strut level at index {i} cannot be negative, got {lvl}")
        if list(sorted(self.strut_levels)) != list(self.strut_levels):
            raise ValueError("strut_levels must be strictly increasing with depth")
        if len(set(self.strut_levels)) != len(self.strut_levels):
            raise ValueError("strut_levels cannot contain duplicate depths")
        if not (0.0 <= self.inclination_angle <= 60.0):
            raise ValueError(
                f"inclination_angle must be between 0 and 60 degrees, got {self.inclination_angle}"
            )
        if self.cross_section_area <= 0:
            raise ValueError(f"cross_section_area must be positive, got {self.cross_section_area}")
        if self.moment_of_inertia <= 0:
            raise ValueError(f"moment_of_inertia must be positive, got {self.moment_of_inertia}")
        if self.elastic_modulus <= 0:
            raise ValueError(f"elastic_modulus must be positive, got {self.elastic_modulus}")
        if self.yield_strength <= 0:
            raise ValueError(f"yield_strength must be positive, got {self.yield_strength}")
        if self.pre_stress_load < 0:
            raise ValueError(f"pre_stress_load cannot be negative, got {self.pre_stress_load}")
        if self.allowable_slenderness <= 0:
            raise ValueError(
                f"allowable_slenderness must be positive, got {self.allowable_slenderness}"
            )
        if self.unbraced_length <= 0:
            raise ValueError(f"unbraced_length must be positive, got {self.unbraced_length}")

    @property
    def num_struts(self) -> int:
        """Total number of strut tiers."""
        return len(self.strut_levels)

    @property
    def radius_of_gyration(self) -> float:
        """Radius of gyration r = sqrt(I_s / A_s) (m)."""
        return math.sqrt(self.moment_of_inertia / self.cross_section_area)

    @property
    def slenderness_ratio(self) -> float:
        """Effective member slenderness ratio lambda = L_strut / r."""
        return self.unbraced_length / self.radius_of_gyration

    @property
    def euler_buckling_load(self) -> float:
        """Euler elastic critical buckling load P_cr = (pi^2 * E_s * I_s) / L^2 (kN)."""
        return (math.pi ** 2 * self.elastic_modulus * self.moment_of_inertia) / (self.unbraced_length ** 2)

    @property
    def yield_capacity(self) -> float:
        """Cross-sectional axial plastic yield capacity P_y = A_s * f_y (kN)."""
        # f_y in MPa = 1000 kPa, A_s in m^2 -> kN
        return self.cross_section_area * (self.yield_strength * 1e3)

    def validate_with_pier(self, pier_height: float) -> bool:
        """
        Validates that all strut levels fit within the pier height.
        """
        for lvl in self.strut_levels:
            if lvl >= pier_height:
                raise ValueError(
                    f"strut level ({lvl} m) must be strictly less than total pier_height ({pier_height} m)"
                )
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize dataclass to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrutSupportSystem:
        """Construct dataclass instance from dictionary."""
        return cls(**data)


@dataclass
class MultiStrutPiledWallModel:
    """
    Composite system model bundling curved shell panels, pier & pile substructure,
    and multi-tier raking struts.
    """
    shell: CurvedShellGeometry = field(default_factory=CurvedShellGeometry)
    pier_pile: PierAndPileGeometry = field(default_factory=PierAndPileGeometry)
    struts: StrutSupportSystem = field(default_factory=StrutSupportSystem)
    piers: Optional[PierAndPileGeometry] = None

    def __post_init__(self):
        if self.piers is not None:
            self.pier_pile = self.piers
        else:
            self.piers = self.pier_pile

        # Cross-validation: Struts fit within pier height
        self.struts.validate_with_pier(self.pier_pile.pier_height)
        # Cross-validation: Pier height must accommodate panel height
        if self.pier_pile.pier_height < self.shell.panel_height:
            raise ValueError(
                f"pier_height ({self.pier_pile.pier_height} m) cannot be smaller than "
                f"shell panel_height ({self.shell.panel_height} m)"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize composite model to dictionary."""
        return {
            "shell": self.shell.to_dict(),
            "pier_pile": self.pier_pile.to_dict(),
            "struts": self.struts.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MultiStrutPiledWallModel:
        """Construct composite model from dictionary."""
        return cls(
            shell=CurvedShellGeometry.from_dict(data["shell"]),
            pier_pile=PierAndPileGeometry.from_dict(data["pier_pile"]),
            struts=StrutSupportSystem.from_dict(data["struts"]),
        )
