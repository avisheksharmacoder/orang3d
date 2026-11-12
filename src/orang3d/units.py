"""
Unit conversion utilities, unit systems, and round-trip invariant guarantees (Phase 1).
Supports SI Metric and Imperial (US Customary) engineering units.
"""

from enum import Enum
from typing import Tuple, Union
from .models.wall_params import RetainingWallGeometry, SeismicParams, SoilProperties

# International exact conversion constants
# 1 inch = 0.0254 m (exact), 1 ft = 0.3048 m (exact)
FT_TO_M = 0.3048
M_TO_FT = 1.0 / FT_TO_M

# 1 lbf = 4.4482216152605 N (exact standard gravity 9.80665 m/s^2 * 0.45359237 kg)
# 1 kip = 1000 lbf = 4.4482216152605 kN
KIPS_TO_KN = 4.4482216152605
KN_TO_KIPS = 1.0 / KIPS_TO_KN

# Unit weight: 1 pcf = 1 lbf / ft^3 in kN / m^3
PCF_TO_KN_M3 = 4.4482216152605e-3 / (FT_TO_M ** 3)
KN_M3_TO_PCF = 1.0 / PCF_TO_KN_M3

# Pressure: 1 psf = 1 lbf / ft^2 in kPa
PSF_TO_KPA = 4.4482216152605e-3 / (FT_TO_M ** 2)
KPA_TO_PSF = 1.0 / PSF_TO_KPA

# 1 ksf = 1000 psf in kPa
KSF_TO_KPA = PSF_TO_KPA * 1000.0
KPA_TO_KSF = 1.0 / KSF_TO_KPA

# Bending Moment: 1 kip-ft in kNm
KIP_FT_TO_KN_M = KIPS_TO_KN * FT_TO_M
KN_M_TO_KIP_FT = 1.0 / KIP_FT_TO_KN_M

# Small lengths & stress
IN_TO_MM = 25.4
MM_TO_IN = 1.0 / IN_TO_MM
IN_TO_CM = 2.54
CM_TO_IN = 1.0 / IN_TO_CM
MPA_TO_KSI = 1.0 / 6.894757293168361
KSI_TO_MPA = 1.0 / MPA_TO_KSI

# Per-unit-wall-length force & moment
KN_PER_M_TO_KIP_PER_FT = KN_TO_KIPS * FT_TO_M
KIP_PER_FT_TO_KN_PER_M = 1.0 / KN_PER_M_TO_KIP_PER_FT
KN_M_PER_M_TO_KIP_FT_PER_FT = KN_TO_KIPS
KIP_FT_PER_FT_TO_KN_M_PER_M = KIPS_TO_KN


class UnitSystem(str, Enum):
    """Supported geotechnical and structural engineering unit systems."""
    SI = "si"
    IMPERIAL = "imperial"


def m_to_ft(val: float) -> float:
    """Converts meters to feet."""
    return val * M_TO_FT


def ft_to_m(val: float) -> float:
    """Converts feet to meters."""
    return val * FT_TO_M


def kn_to_kips(val: float) -> float:
    """Converts kilonewtons (kN) to kilopounds-force (kips)."""
    return val * KN_TO_KIPS


def kips_to_kn(val: float) -> float:
    """Converts kilopounds-force (kips) to kilonewtons (kN)."""
    return val * KIPS_TO_KN


def kn_m3_to_pcf(val: float) -> float:
    """Converts kN/m^3 to pounds per cubic foot (pcf)."""
    return val * KN_M3_TO_PCF


def pcf_to_kn_m3(val: float) -> float:
    """Converts pounds per cubic foot (pcf) to kN/m^3."""
    return val * PCF_TO_KN_M3


def kpa_to_psf(val: float) -> float:
    """Converts kilopascals (kPa) to pounds per square foot (psf)."""
    return val * KPA_TO_PSF


def psf_to_kpa(val: float) -> float:
    """Converts pounds per square foot (psf) to kilopascals (kPa)."""
    return val * PSF_TO_KPA


def kpa_to_ksf(val: float) -> float:
    """Converts kilopascals (kPa) to kips per square foot (ksf)."""
    return val * KPA_TO_KSF


def ksf_to_kpa(val: float) -> float:
    """Converts kips per square foot (ksf) to kilopascals (kPa)."""
    return val * KSF_TO_KPA


def kn_m_to_kip_ft(val: float) -> float:
    """Converts kNm to kip-ft."""
    return val * KN_M_TO_KIP_FT


def kip_ft_to_kn_m(val: float) -> float:
    """Converts kip-ft to kNm."""
    return val * KIP_FT_TO_KN_M


def convert_geometry_units(
    geom: RetainingWallGeometry,
    from_system: Union[UnitSystem, str],
    to_system: Union[UnitSystem, str],
) -> RetainingWallGeometry:
    """
    Converts a RetainingWallGeometry instance between SI (m, kN/m^3) and Imperial (ft, pcf).
    """
    from_sys = UnitSystem(from_system)
    to_sys = UnitSystem(to_system)

    if from_sys == to_sys:
        return RetainingWallGeometry(
            stem_height=geom.stem_height,
            stem_thickness_top=geom.stem_thickness_top,
            stem_thickness_base=geom.stem_thickness_base,
            toe_length=geom.toe_length,
            heel_length=geom.heel_length,
            footing_thickness=geom.footing_thickness,
            shear_key_depth=geom.shear_key_depth,
            shear_key_width=geom.shear_key_width,
            wall_length=geom.wall_length,
            concrete_unit_weight=geom.concrete_unit_weight,
        )

    if from_sys == UnitSystem.SI and to_sys == UnitSystem.IMPERIAL:
        l_conv = m_to_ft
        w_conv = kn_m3_to_pcf
    else:
        l_conv = ft_to_m
        w_conv = pcf_to_kn_m3

    return RetainingWallGeometry(
        stem_height=l_conv(geom.stem_height),
        stem_thickness_top=l_conv(geom.stem_thickness_top),
        stem_thickness_base=l_conv(geom.stem_thickness_base),
        toe_length=l_conv(geom.toe_length),
        heel_length=l_conv(geom.heel_length),
        footing_thickness=l_conv(geom.footing_thickness),
        shear_key_depth=l_conv(geom.shear_key_depth),
        shear_key_width=l_conv(geom.shear_key_width),
        wall_length=l_conv(geom.wall_length),
        concrete_unit_weight=w_conv(geom.concrete_unit_weight),
    )


def convert_soil_units(
    soil: SoilProperties,
    from_system: Union[UnitSystem, str],
    to_system: Union[UnitSystem, str],
) -> SoilProperties:
    """
    Converts a SoilProperties instance between SI (kPa, kN/m^3) and Imperial (psf, pcf).
    Friction angles (degrees) remain identical.
    """
    from_sys = UnitSystem(from_system)
    to_sys = UnitSystem(to_system)

    if from_sys == to_sys:
        return SoilProperties(
            friction_angle=soil.friction_angle,
            cohesion=soil.cohesion,
            unit_weight=soil.unit_weight,
            saturated_unit_weight=soil.saturated_unit_weight,
            wall_friction_angle=soil.wall_friction_angle,
            foundation_friction_angle=soil.foundation_friction_angle,
            foundation_cohesion=soil.foundation_cohesion,
            foundation_unit_weight=soil.foundation_unit_weight,
            allowable_bearing_capacity=soil.allowable_bearing_capacity,
        )

    if from_sys == UnitSystem.SI and to_sys == UnitSystem.IMPERIAL:
        p_conv = kpa_to_psf
        w_conv = kn_m3_to_pcf
    else:
        p_conv = psf_to_kpa
        w_conv = pcf_to_kn_m3

    return SoilProperties(
        friction_angle=soil.friction_angle,
        cohesion=p_conv(soil.cohesion),
        unit_weight=w_conv(soil.unit_weight),
        saturated_unit_weight=w_conv(soil.saturated_unit_weight),
        wall_friction_angle=soil.wall_friction_angle,
        foundation_friction_angle=soil.foundation_friction_angle,
        foundation_cohesion=p_conv(soil.foundation_cohesion),
        foundation_unit_weight=w_conv(soil.foundation_unit_weight),
        allowable_bearing_capacity=p_conv(soil.allowable_bearing_capacity),
    )


def mm_to_in(val: float) -> float:
    """Converts millimeters to inches."""
    return val * MM_TO_IN


def in_to_mm(val: float) -> float:
    """Converts inches to millimeters."""
    return val * IN_TO_MM


def cm_to_in(val: float) -> float:
    """Converts centimeters to inches."""
    return val * CM_TO_IN


def in_to_cm(val: float) -> float:
    """Converts inches to centimeters."""
    return val * IN_TO_CM


def mpa_to_ksi(val: float) -> float:
    """Converts megapascals (MPa) to kips per square inch (ksi)."""
    return val * MPA_TO_KSI


def ksi_to_mpa(val: float) -> float:
    """Converts kips per square inch (ksi) to megapascals (MPa)."""
    return val * KSI_TO_MPA


def kn_per_m_to_kip_per_ft(val: float) -> float:
    """Converts linear thrust kN/m to kip/ft."""
    return val * KN_PER_M_TO_KIP_PER_FT


def kip_per_ft_to_kn_per_m(val: float) -> float:
    """Converts linear thrust kip/ft to kN/m."""
    return val * KIP_PER_FT_TO_KN_PER_M


def kn_m_per_m_to_kip_ft_per_ft(val: float) -> float:
    """Converts bending moment per unit width kNm/m to kip-ft/ft."""
    return val * KN_M_PER_M_TO_KIP_FT_PER_FT


def kip_ft_per_ft_to_kn_m_per_m(val: float) -> float:
    """Converts bending moment per unit width kip-ft/ft to kNm/m."""
    return val * KIP_FT_PER_FT_TO_KN_M_PER_M


def convert_seismic_units(
    seismic: SeismicParams,
    from_system: Union[UnitSystem, str],
    to_system: Union[UnitSystem, str],
) -> SeismicParams:
    """Converts water_table_depth between SI (m) and Imperial (ft)."""
    from_sys = UnitSystem(from_system)
    to_sys = UnitSystem(to_system)
    if from_sys == to_sys:
        w_d = seismic.water_table_depth
    elif from_sys == UnitSystem.SI and to_sys == UnitSystem.IMPERIAL:
        w_d = m_to_ft(seismic.water_table_depth)
    else:
        w_d = ft_to_m(seismic.water_table_depth)
    return SeismicParams(
        horizontal_pga=seismic.horizontal_pga,
        vertical_pga=seismic.vertical_pga,
        backfill_slope=seismic.backfill_slope,
        water_table_depth=w_d,
        liquefaction_factor=seismic.liquefaction_factor,
        pore_pressure_ratio_ru=seismic.pore_pressure_ratio_ru,
    )


_UNIT_QUANTITY_MAP: dict[str, Tuple[str, str, float]] = {
    # kind -> (si_unit, imperial_unit, factor si -> imperial)
    "length": ("m", "ft", M_TO_FT),
    "disp_cm": ("cm", "in", CM_TO_IN),
    "disp_mm": ("mm", "in", MM_TO_IN),
    "force": ("kN", "kip", KN_TO_KIPS),
    "force_per_m": ("kN/m", "kip/ft", KN_PER_M_TO_KIP_PER_FT),
    "moment": ("kNm", "kip-ft", KN_M_TO_KIP_FT),
    "moment_per_m": ("kNm/m", "kip-ft/ft", KN_M_PER_M_TO_KIP_FT_PER_FT),
    "pressure": ("kPa", "ksf", KPA_TO_KSF),
    "pressure_psf": ("kPa", "psf", KPA_TO_PSF),
    "stress_mpa": ("MPa", "ksi", MPA_TO_KSI),
    "unit_weight": ("kN/m³", "pcf", KN_M3_TO_PCF),
    "ratio": ("-", "-", 1.0),
    "angle": ("deg", "deg", 1.0),
}


def unit_label(kind: str, unit_system: Union[UnitSystem, str]) -> str:
    """Returns canonical display unit symbol for a physical quantity kind."""
    sys_enum = UnitSystem(unit_system)
    if kind not in _UNIT_QUANTITY_MAP:
        return kind
    si_lbl, imp_lbl, _ = _UNIT_QUANTITY_MAP[kind]
    return si_lbl if sys_enum == UnitSystem.SI else imp_lbl


def from_si_value(val: float, kind: str, unit_system: Union[UnitSystem, str]) -> float:
    """Converts a canonical SI value into display units (`SI` or `IMPERIAL`)."""
    sys_enum = UnitSystem(unit_system)
    if sys_enum == UnitSystem.SI or kind not in _UNIT_QUANTITY_MAP:
        return float(val)
    _, _, factor = _UNIT_QUANTITY_MAP[kind]
    return float(val) * factor


def to_si_value(val: float, kind: str, unit_system: Union[UnitSystem, str]) -> float:
    """Converts a display-unit value back into canonical SI."""
    sys_enum = UnitSystem(unit_system)
    if sys_enum == UnitSystem.SI or kind not in _UNIT_QUANTITY_MAP:
        return float(val)
    _, _, factor = _UNIT_QUANTITY_MAP[kind]
    return float(val) / factor

