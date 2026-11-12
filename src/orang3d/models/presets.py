"""
Curated Geotechnical Textbook, Centrifuge & Code Benchmark Presets (Phase 5).

Provides deterministic, cited verification benchmarks for classroom pedagogy,
architecture/civil validation, and multi-solver cross-checking:
  1. Das (9th Ed.) Ex. 13.7 — Cantilever Retaining Wall (Coulomb / Mononobe-Okabe)
  2. Bowles (5th Ed.) Sec. 12-7 — Soil Arching Curved Shell Bay
  3. Kramer (1996) — Seed-Whitman Dynamic Thrust + Newmark Sliding Block Wall
  4. IS 14458 / IS 1893 Zone V — Hill-Slope Piled Curved Shell Retaining Wall
  5. 3D Corner Effect Benchmark — Short Cantilever Wall under 0.30g Shaking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .advanced_wall_params import (
    CurvedShellGeometry,
    PierAndPileGeometry,
    StrutSupportSystem,
    WallSystemMode,
)
from .wall_params import RetainingWallGeometry, SeismicParams, SoilProperties


@dataclass(frozen=True)
class BenchmarkPreset:
    """Self-contained geotechnical benchmark scenario with published analytical targets."""

    preset_id: str
    title: str
    reference: str
    description: str
    pedagogical_focus: str
    wall_mode: WallSystemMode
    geom: RetainingWallGeometry
    soil: SoilProperties
    seismic: SeismicParams
    shell_geom: CurvedShellGeometry
    pier_pile_geom: PierAndPileGeometry
    strut_sys: StrutSupportSystem
    num_bays: int = 3
    waveform_config: Dict[str, Any] = field(default_factory=dict)
    targets: Dict[str, float] = field(default_factory=dict)


def _build_presets() -> List[BenchmarkPreset]:
    """Constructs the library of curated benchmark presets."""
    return [
        BenchmarkPreset(
            preset_id="das_ex_13_7",
            title="Das (9th Ed.) Ex. 13.7 — Coulomb / M-O Cantilever Wall",
            reference="Das, B. M. (9th Ed.), Principles of Foundation Engineering, Ch. 13 Ex. 13.7",
            description=(
                "6.0 m total-height dry granular backfill cantilever wall (phi = 30 deg, "
                "delta = 20 deg, gamma = 18.0 kN/m^3) under moderate pseudo-static k_h = 0.15g."
            ),
            pedagogical_focus=(
                "Compare Rankine vs. Coulomb static Ka, verify Mononobe-Okabe Kae "
                "amplification, and trace overturning/sliding/Meyerhof bearing FS terms."
            ),
            wall_mode=WallSystemMode.CANTILEVER,
            geom=RetainingWallGeometry(
                stem_height=5.3,
                stem_thickness_top=0.35,
                stem_thickness_base=0.65,
                toe_length=1.0,
                heel_length=2.6,
                footing_thickness=0.7,
                shear_key_depth=0.0,
                shear_key_width=0.5,
                wall_length=10.0,
            ),
            soil=SoilProperties(
                unit_weight=18.0,
                saturated_unit_weight=20.0,
                friction_angle=30.0,
                cohesion=0.0,
                wall_friction_angle=20.0,
                foundation_friction_angle=30.0,
                foundation_cohesion=0.0,
                foundation_unit_weight=19.0,
            ),
            seismic=SeismicParams(
                horizontal_pga=0.15,
                vertical_pga=0.0,
                backfill_slope=0.0,
                water_table_depth=12.0,
            ),
            shell_geom=CurvedShellGeometry(),
            pier_pile_geom=PierAndPileGeometry(),
            strut_sys=StrutSupportSystem(),
            num_bays=3,
            waveform_config={"type": "Ricker", "pga_g": 0.15, "freq_hz": 2.5, "duration_sec": 10.0},
            targets={
                "k_a_static": 0.2973,
                "k_ae": 0.4070,
                "total_thrust": 131.88,
                "fs_sliding": 1.135,
                "fs_overturning": 2.747,
            },
        ),
        BenchmarkPreset(
            preset_id="bowles_sec_12_7",
            title="Bowles (5th Ed.) Sec. 12-7 — Soil Arching Curved Shell Bay",
            reference="Bowles, J. E. (5th Ed.), Foundation Analysis and Design, Sec. 12-7",
            description=(
                "6.0 m high horizontally arching curved shell panel (L_bay = 4.0 m, "
                "R = 3.5 m, phi = 32 deg) demonstrating horizontal soil arching reduction."
            ),
            pedagogical_focus=(
                "Inspect how horizontal arching reduces central shell pressure relative to "
                "free-field active pressure and transfers thrust to stiff vertical piers."
            ),
            wall_mode=WallSystemMode.MULTI_STRUT_CURVED_SHELL,
            geom=RetainingWallGeometry(
                stem_height=5.3,
                stem_thickness_top=0.30,
                stem_thickness_base=0.55,
                toe_length=0.9,
                heel_length=2.4,
                footing_thickness=0.7,
                shear_key_depth=0.0,
                shear_key_width=0.5,
                wall_length=12.0,
            ),
            soil=SoilProperties(
                unit_weight=18.5,
                saturated_unit_weight=20.5,
                friction_angle=32.0,
                cohesion=0.0,
                wall_friction_angle=21.0,
                foundation_friction_angle=32.0,
                foundation_cohesion=0.0,
                foundation_unit_weight=19.5,
            ),
            seismic=SeismicParams(
                horizontal_pga=0.10,
                vertical_pga=0.0,
                backfill_slope=0.0,
                water_table_depth=12.0,
            ),
            shell_geom=CurvedShellGeometry(
                radius=3.5,
                subtended_angle=68.0,
                thickness=0.28,
                bay_span=4.0,
                panel_height=6.0,
            ),
            pier_pile_geom=PierAndPileGeometry(
                pier_width=0.8,
                pier_depth=1.0,
                pier_height=6.5,
            ),
            strut_sys=StrutSupportSystem(strut_levels=[2.2, 4.5], inclination_angle_deg=15.0),
            num_bays=3,
            waveform_config={"type": "Ricker", "pga_g": 0.10, "freq_hz": 2.5, "duration_sec": 10.0},
            targets={
                "arching_ratio": 0.1673,
                "total_free_field_thrust": 409.27,
                "total_shell_thrust": 340.80,
                "total_pier_thrust": 68.46,
            },
        ),
        BenchmarkPreset(
            preset_id="kramer_1996_newmark",
            title="Kramer (1996) — Seed-Whitman & Newmark Sliding Wall",
            reference="Kramer, S. L. (1996), Geotechnical Earthquake Engineering, Ch. 11",
            description=(
                "5.6 m gravity/cantilever retaining wall (phi = 34 deg, k_y ~ 0.244g) "
                "subjected to a 0.45g Ricker pulse triggering permanent Newmark block slip."
            ),
            pedagogical_focus=(
                "Connect pseudo-static sliding yield acceleration ky to double-integrated "
                "Newmark permanent slip u_p and Seed-Whitman 0.6H resultant elevation."
            ),
            wall_mode=WallSystemMode.CANTILEVER,
            geom=RetainingWallGeometry(
                stem_height=5.0,
                stem_thickness_top=0.35,
                stem_thickness_base=0.60,
                toe_length=0.8,
                heel_length=2.2,
                footing_thickness=0.6,
                shear_key_depth=0.0,
                shear_key_width=0.5,
                wall_length=8.0,
            ),
            soil=SoilProperties(
                unit_weight=18.5,
                saturated_unit_weight=20.5,
                friction_angle=34.0,
                cohesion=0.0,
                wall_friction_angle=17.0,
                foundation_friction_angle=32.0,
                foundation_cohesion=0.0,
                foundation_unit_weight=19.5,
            ),
            seismic=SeismicParams(
                horizontal_pga=0.25,
                vertical_pga=0.0,
                backfill_slope=0.0,
                water_table_depth=12.0,
            ),
            shell_geom=CurvedShellGeometry(),
            pier_pile_geom=PierAndPileGeometry(),
            strut_sys=StrutSupportSystem(),
            num_bays=3,
            waveform_config={"type": "Ricker", "pga_g": 0.45, "freq_hz": 2.5, "duration_sec": 10.0},
            targets={
                "k_a_static": 0.2564,
                "k_ae": 0.4387,
                "fs_sliding": 0.974,
                "yield_acceleration_ky": 0.2436,
                "newmark_slip_cm": 1.3606,
            },
        ),
        BenchmarkPreset(
            preset_id="is_14458_zone_v_shell",
            title="IS 14458 / IS 1893 Zone V — Hill-Slope Piled Shell Wall",
            reference="IS 14458 (Part 1 & 2) & IS 1893 Zone V (Z = 0.36g) Himalayan Slope Design",
            description=(
                "7.0 m curved shell retaining wall supported on rock-socketed bored piles "
                "(L = 12 m) and two raking steel struts on a 10 deg hill slope in Zone V."
            ),
            pedagogical_focus=(
                "Evaluate steep-slope seismic earth pressures coupled with multi-strut "
                "lateral bracing, horizontal arching, and IS code load-combination checks."
            ),
            wall_mode=WallSystemMode.MULTI_STRUT_CURVED_SHELL,
            geom=RetainingWallGeometry(
                stem_height=6.2,
                stem_thickness_top=0.35,
                stem_thickness_base=0.70,
                toe_length=1.1,
                heel_length=2.8,
                footing_thickness=0.8,
                shear_key_depth=0.5,
                shear_key_width=0.5,
                wall_length=12.0,
            ),
            soil=SoilProperties(
                unit_weight=19.0,
                saturated_unit_weight=21.0,
                friction_angle=33.0,
                cohesion=5.0,
                wall_friction_angle=22.0,
                foundation_friction_angle=34.0,
                foundation_cohesion=5.0,
                foundation_unit_weight=20.0,
            ),
            seismic=SeismicParams(
                horizontal_pga=0.24,
                vertical_pga=0.12,
                backfill_slope=10.0,
                water_table_depth=15.0,
            ),
            shell_geom=CurvedShellGeometry(
                radius=4.0,
                subtended_angle=60.0,
                thickness=0.30,
                bay_span=4.0,
                panel_height=7.0,
            ),
            pier_pile_geom=PierAndPileGeometry(
                pier_width=0.9,
                pier_depth=1.1,
                pier_height=7.5,
                pile_diameter=0.9,
                pile_length=12.0,
                pile_spacing=2.7,
                rock_socket_length=2.0,
            ),
            strut_sys=StrutSupportSystem(
                strut_levels=[2.2, 4.8],
                inclination_angle_deg=15.0,
            ),
            num_bays=3,
            waveform_config={"type": "Ricker", "pga_g": 0.36, "freq_hz": 2.5, "duration_sec": 12.0},
            targets={
                "arching_ratio": 0.3951,
                "total_shell_thrust": 246.48,
                "total_pier_thrust": 160.97,
            },
        ),
        BenchmarkPreset(
            preset_id="corner_effect_3d_benchmark",
            title="3D Corner Effect Benchmark — Short Wall (0.30g Shaking)",
            reference="Orang3D 3D Continuum SSI Benchmark (L_wall / H = 0.66 under 0.30g)",
            description=(
                "Short 4.0 m longitudinal retaining wall (H = 6.1 m) under strong 0.30g/0.10g "
                "shaking to highlight 3D end-constraint stress concentration vs. 2D plane strain."
            ),
            pedagogical_focus=(
                "Compare classical 2D Mononobe-Okabe uniform pressure against 3D FEA "
                "mid-bay vs. corner stress redistribution and resultant height shift."
            ),
            wall_mode=WallSystemMode.CANTILEVER,
            geom=RetainingWallGeometry(
                stem_height=5.5,
                stem_thickness_top=0.35,
                stem_thickness_base=0.65,
                toe_length=1.0,
                heel_length=2.4,
                footing_thickness=0.6,
                shear_key_depth=0.4,
                shear_key_width=0.5,
                wall_length=4.0,
            ),
            soil=SoilProperties(
                unit_weight=18.5,
                saturated_unit_weight=20.5,
                friction_angle=32.0,
                cohesion=0.0,
                wall_friction_angle=20.0,
                foundation_friction_angle=32.0,
                foundation_cohesion=0.0,
                foundation_unit_weight=19.5,
            ),
            seismic=SeismicParams(
                horizontal_pga=0.30,
                vertical_pga=0.10,
                backfill_slope=0.0,
                water_table_depth=12.0,
            ),
            shell_geom=CurvedShellGeometry(),
            pier_pile_geom=PierAndPileGeometry(),
            strut_sys=StrutSupportSystem(),
            num_bays=2,
            waveform_config={"type": "Ricker", "pga_g": 0.30, "freq_hz": 2.5, "duration_sec": 10.0},
            targets={
                "k_a_static": 0.2755,
                "k_ae": 0.5761,
                "total_thrust": 187.93,
                "fs_sliding": 0.890,
                "fs_overturning": 1.370,
            },
        ),
    ]


BENCHMARK_PRESETS: List[BenchmarkPreset] = _build_presets()
_PRESET_MAP: Dict[str, BenchmarkPreset] = {p.preset_id: p for p in BENCHMARK_PRESETS}


def get_benchmark_presets() -> List[BenchmarkPreset]:
    """Returns all curated benchmark presets in display order."""
    return list(BENCHMARK_PRESETS)


def get_preset(preset_id: str) -> BenchmarkPreset:
    """Looks up a benchmark preset by `preset_id`."""
    if preset_id not in _PRESET_MAP:
        available = ", ".join(sorted(_PRESET_MAP.keys()))
        raise KeyError(f"Unknown preset_id '{preset_id}'. Available: {available}")
    return _PRESET_MAP[preset_id]
