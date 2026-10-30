"""
Data classes defining retaining wall geometry, soil properties, and seismic disaster parameters.
Enforces engineering validity bounds and data contracts (Phase 1).
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class RetainingWallGeometry:
    """
    Parametric geometry for a Cantilever / Inverted-T Retaining Wall.
    Units: meters (m).
    """
    stem_height: float = 6.0         # H_stem: Vertical height of stem above base slab
    stem_thickness_top: float = 0.35   # t_top: Thickness at crest of wall
    stem_thickness_base: float = 0.65  # t_base: Thickness at base of stem
    toe_length: float = 1.0          # B_toe: Width of front toe
    heel_length: float = 2.5         # B_heel: Width of back heel
    footing_thickness: float = 0.7   # D_footing: Thickness of base footing slab
    shear_key_depth: float = 0.4     # D_key: Depth of bottom shear key (0.0 if none)
    shear_key_width: float = 0.5     # W_key: Width of bottom shear key
    wall_length: float = 5.0         # L_wall: Extruded 3D length along longitudinal axis
    concrete_unit_weight: float = 24.0 # kN/m^3 (Reinforced concrete)

    def __post_init__(self):
        if self.stem_height <= 0:
            raise ValueError(f"stem_height must be positive, got {self.stem_height}")
        if self.stem_thickness_top <= 0:
            raise ValueError(f"stem_thickness_top must be positive, got {self.stem_thickness_top}")
        if self.stem_thickness_base <= 0:
            raise ValueError(f"stem_thickness_base must be positive, got {self.stem_thickness_base}")
        if self.stem_thickness_top > self.stem_thickness_base:
            raise ValueError(
                f"stem_thickness_top ({self.stem_thickness_top}) cannot exceed "
                f"stem_thickness_base ({self.stem_thickness_base})"
            )
        if self.footing_thickness <= 0:
            raise ValueError(f"footing_thickness must be positive, got {self.footing_thickness}")
        if self.toe_length < 0:
            raise ValueError(f"toe_length cannot be negative, got {self.toe_length}")
        if self.heel_length < 0:
            raise ValueError(f"heel_length cannot be negative, got {self.heel_length}")
        if self.wall_length <= 0:
            raise ValueError(f"wall_length must be positive, got {self.wall_length}")
        if self.concrete_unit_weight <= 0:
            raise ValueError(f"concrete_unit_weight must be positive, got {self.concrete_unit_weight}")
        if self.shear_key_depth < 0:
            raise ValueError(f"shear_key_depth cannot be negative, got {self.shear_key_depth}")
        if self.shear_key_width < 0:
            raise ValueError(f"shear_key_width cannot be negative, got {self.shear_key_width}")
        if self.shear_key_width > self.base_width:
            raise ValueError(
                f"shear_key_width ({self.shear_key_width}) cannot exceed base_width ({self.base_width})"
            )

    @property
    def total_height(self) -> float:
        """Total height from bottom of base slab to top of wall."""
        return self.stem_height + self.footing_thickness

    @property
    def base_width(self) -> float:
        """Total width of the base footing (toe + stem base + heel)."""
        return self.toe_length + self.stem_thickness_base + self.heel_length


@dataclass
class SoilProperties:
    """
    Geotechnical strata properties for backfill and foundation soil.
    """
    # Backfill Soil (Behind the wall)
    friction_angle: float = 32.0           # phi in degrees (e.g. 28 - 40)
    cohesion: float = 0.0                  # c in kPa (for cohesionless backfill, typically 0)
    unit_weight: float = 18.0              # gamma in kN/m^3
    saturated_unit_weight: float = 20.0    # gamma_sat in kN/m^3
    wall_friction_angle: float = 20.0      # delta in degrees (interface friction, typically 2/3 phi)

    # Foundation / Subgrade Soil
    foundation_friction_angle: float = 30.0 # phi_f in degrees
    foundation_cohesion: float = 25.0       # c_f in kPa
    foundation_unit_weight: float = 19.0    # gamma_f in kN/m^3
    allowable_bearing_capacity: float = 350.0 # q_allow in kPa
    elastic_modulus: float = 30000.0        # E in kPa (for FEA continuum)
    poissons_ratio: float = 0.30            # nu (Poisson's ratio, 0.0 to < 0.5)

    def __post_init__(self):
        if not (0.0 < self.friction_angle < 55.0):
            raise ValueError(f"friction_angle must be between 0 and 55 degrees, got {self.friction_angle}")
        if self.cohesion < 0:
            raise ValueError(f"cohesion cannot be negative, got {self.cohesion}")
        if self.unit_weight <= 0:
            raise ValueError(f"unit_weight must be positive, got {self.unit_weight}")
        if self.saturated_unit_weight <= 0:
            raise ValueError(f"saturated_unit_weight must be positive, got {self.saturated_unit_weight}")
        if self.saturated_unit_weight < self.unit_weight:
            raise ValueError(
                f"saturated_unit_weight ({self.saturated_unit_weight}) must be >= unit_weight ({self.unit_weight})"
            )
        if self.wall_friction_angle < 0:
            raise ValueError(f"wall_friction_angle cannot be negative, got {self.wall_friction_angle}")
        if self.wall_friction_angle > self.friction_angle:
            raise ValueError(
                f"wall_friction_angle ({self.wall_friction_angle}) cannot exceed "
                f"friction_angle ({self.friction_angle})"
            )
        if not (0.0 < self.foundation_friction_angle < 55.0):
            raise ValueError(
                f"foundation_friction_angle must be between 0 and 55 degrees, got {self.foundation_friction_angle}"
            )
        if self.foundation_cohesion < 0:
            raise ValueError(f"foundation_cohesion cannot be negative, got {self.foundation_cohesion}")
        if self.foundation_unit_weight <= 0:
            raise ValueError(f"foundation_unit_weight must be positive, got {self.foundation_unit_weight}")
        if self.allowable_bearing_capacity <= 0:
            raise ValueError(
                f"allowable_bearing_capacity must be positive, got {self.allowable_bearing_capacity}"
            )
        if self.elastic_modulus <= 0:
            raise ValueError(f"elastic_modulus must be positive, got {self.elastic_modulus}")
        if not (0.0 <= self.poissons_ratio < 0.5):
            raise ValueError(f"poissons_ratio must be between 0.0 and 0.5, got {self.poissons_ratio}")


@dataclass
class SeismicParams:
    """
    Dynamic earthquake and environmental disaster inputs.
    """
    horizontal_pga: float = 0.25         # k_h: Horizontal seismic acceleration coefficient (g)
    vertical_pga: float = 0.125          # k_v: Vertical seismic acceleration coefficient (g)
    backfill_slope: float = 0.0          # beta: Backfill slope angle in degrees
    water_table_depth: float = 4.0       # H_w: Depth to water table from top of backfill (m)
    liquefaction_factor: float = 0.0     # 0.0 = solid soil, 1.0 = fully liquefied backfill
    pore_pressure_ratio_ru: float = 0.0  # r_u: Excess pore pressure ratio

    def __post_init__(self):
        if not (0.0 <= self.horizontal_pga <= 1.5):
            raise ValueError(f"horizontal_pga must be between 0.0 and 1.5 g, got {self.horizontal_pga}")
        if not (0.0 <= self.vertical_pga <= 1.5):
            raise ValueError(f"vertical_pga must be between 0.0 and 1.5 g, got {self.vertical_pga}")
        if not (0.0 <= self.backfill_slope <= 50.0):
            raise ValueError(f"backfill_slope must be between 0 and 50 degrees, got {self.backfill_slope}")
        if self.water_table_depth < 0:
            raise ValueError(f"water_table_depth cannot be negative, got {self.water_table_depth}")
        if not (0.0 <= self.liquefaction_factor <= 1.0):
            raise ValueError(
                f"liquefaction_factor must be between 0.0 and 1.0, got {self.liquefaction_factor}"
            )
        if not (0.0 <= self.pore_pressure_ratio_ru <= 1.0):
            raise ValueError(
                f"pore_pressure_ratio_ru must be between 0.0 and 1.0, got {self.pore_pressure_ratio_ru}"
            )
        if self.pore_pressure_ratio_ru > 0.0 and self.liquefaction_factor == 0.0:
            self.liquefaction_factor = self.pore_pressure_ratio_ru
        elif self.liquefaction_factor > 0.0 and self.pore_pressure_ratio_ru == 0.0:
            self.pore_pressure_ratio_ru = self.liquefaction_factor


def validate_seismic_with_soil(seismic: SeismicParams, soil: SoilProperties) -> bool:
    """
    Validates cross-compatibility between seismic parameters and soil properties.
    """
    if seismic.backfill_slope >= soil.friction_angle:
        raise ValueError(
            f"backfill_slope ({seismic.backfill_slope}°) cannot exceed soil friction_angle ({soil.friction_angle}°)"
        )
    return True


@dataclass
class AnalysisResults:
    """
    Calculated geotechnical stability factors and structural stresses.
    """
    # Dynamic Earth Pressures (Mononobe-Okabe)
    k_ae: float = 0.0                    # Total dynamic active earth pressure coefficient
    k_a_static: float = 0.0              # Static Coulomb/Rankine coefficient
    delta_k_ae: float = 0.0              # Seismic increment (K_ae - K_a)
    total_thrust: float = 0.0            # P_ae total dynamic thrust (kN per meter width)
    thrust_height: float = 0.0           # Effective height of thrust resultant (m above base)
    water_thrust: float = 0.0            # Hydrostatic thrust (kN/m)

    # Global Geotechnical Factors of Safety
    fs_sliding: float = 0.0              # Factor of safety against sliding along base
    fs_overturning: float = 0.0          # Factor of safety against tipping around toe
    fs_bearing: float = 0.0              # Factor of safety against bearing capacity failure
    max_bearing_pressure: float = 0.0    # q_max at toe (kPa)
    min_bearing_pressure: float = 0.0    # q_min at heel (kPa)
    eccentricity: float = 0.0            # Load eccentricity e (m) from base centerline

    # Structural Demands at Stem Junction
    max_bending_moment: float = 0.0      # M_max at stem base (kNm / m)
    max_shear_force: float = 0.0         # V_max at stem base (kN / m)
    concrete_tensile_stress: float = 0.0 # MPa
    cracking_predicted: bool = False     # True if stress exceeds concrete cracking modulus

    def __post_init__(self):
        if self.fs_sliding < 0:
            raise ValueError(f"fs_sliding cannot be negative, got {self.fs_sliding}")
        if self.fs_overturning < 0:
            raise ValueError(f"fs_overturning cannot be negative, got {self.fs_overturning}")
        if self.fs_bearing < 0:
            raise ValueError(f"fs_bearing cannot be negative, got {self.fs_bearing}")
        if self.total_thrust < 0:
            raise ValueError(f"total_thrust cannot be negative, got {self.total_thrust}")
