"""
Simulation 01: Static Cantilever Retaining Wall Sizing & Stability Equilibrium
==============================================================================

Engineering Context:
--------------------
Evaluates the baseline static and pseudo-static external stability of a reinforced
concrete cantilever retaining wall. When a granular backfill undergoes active shear
failure along a Coulomb planar slip surface inclined at theta = 45 + phi / 2, the
mobilized lateral earth thrust is resisted by base friction, soil weight over the heel,
and toe bearing pressure.

Benchmark Reference:
--------------------
Das, B. M. (9th Ed.), Principles of Foundation Engineering, Chapter 13, Example 13.7.

Governing Standards:
--------------------
- IS 456:2000 (Plain and Reinforced Concrete - Code of Practice)
- IS 1904:1986 (Design and Construction of Foundations in Soils)
- Eurocode 7 (EN 1997-1) / AASHTO LRFD Bridge Design Specifications
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root and src to path for direct terminal execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from orang3d.config import RegionalStandard, get_safety_thresholds
from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SeismicParams,
    SoilProperties,
)
from orang3d.physics.stability import evaluate_wall_stability
from simulations.common import check_benchmark, format_table, print_banner, print_section


# ==============================================================================
# CONSTANTS: GEOMETRIC, GEOTECHNICAL & NUMERICAL PARAMETERS
# ==============================================================================

# Cantilever Wall Geometry (Das Ex. 13.7)
STEM_HEIGHT_M: float = 5.30            # Stem height above base slab (m)
STEM_THICKNESS_TOP_M: float = 0.35     # Crest thickness of concrete stem (m)
STEM_THICKNESS_BASE_M: float = 0.65    # Stem thickness at junction with footing (m)
FOOTING_THICKNESS_M: float = 0.70      # Footing slab thickness (m) -> Total H = 6.0 m
TOE_LENGTH_M: float = 1.00             # Footing toe cantilever projection (m)
HEEL_LENGTH_M: float = 2.60            # Footing heel cantilever projection (m)
SHEAR_KEY_DEPTH_M: float = 0.00        # Shear key depth (0.0 = no key) (m)
TOTAL_BASE_WIDTH_M: float = TOE_LENGTH_M + STEM_THICKNESS_BASE_M + HEEL_LENGTH_M  # 4.25 m
TOTAL_WALL_HEIGHT_M: float = STEM_HEIGHT_M + FOOTING_THICKNESS_M                  # 6.00 m

# Soil Strata & Interface Friction Parameters
BACKFILL_UNIT_WEIGHT_KN_M3: float = 18.00         # Dry unit weight of granular backfill (kN/m^3)
BACKFILL_SAT_UNIT_WEIGHT_KN_M3: float = 20.00     # Saturated unit weight of backfill (kN/m^3)
INTERNAL_FRICTION_ANGLE_DEG: float = 30.00        # Internal angle of friction phi (degrees)
SOIL_COHESION_KPA: float = 0.00                   # Backfill cohesion c' (granular fill) (kPa)
FOUNDATION_COHESION_KPA: float = 0.00             # Subgrade cohesion c_f (granular subgrade) (kPa)
WALL_INTERFACE_FRICTION_DEG: float = 20.00        # Wall friction angle delta (degrees)
FOUNDATION_FRICTION_DEG: float = 30.00            # Foundation base friction angle (degrees)
FOUNDATION_UNIT_WEIGHT_KN_M3: float = 19.00       # Subgrade soil unit weight (kN/m^3)
ALLOWABLE_BEARING_CAPACITY_KPA: float = 350.00    # Subgrade allowable bearing pressure (kPa)

# Seismic Shaking Demands (Das Ex. 13.7 Pseudo-Static Case)
SEISMIC_HORIZONTAL_PGA_G: float = 0.15            # Peak horizontal seismic coefficient k_h (g)
SEISMIC_VERTICAL_PGA_G: float = 0.00              # Vertical seismic coefficient k_v (g)
WATER_TABLE_DEPTH_M: float = 12.00                # Depth to phreatic line below crest (m)

# Benchmark Targets (Das Ex. 13.7 Published Values)
TARGET_STATIC_KA: float = 0.2973                  # Coulomb static active earth pressure coefficient
TARGET_SEISMIC_KAE: float = 0.4070                # Mononobe-Okabe dynamic earth pressure coefficient
TARGET_TOTAL_THRUST_KN_M: float = 131.88          # Combined static + dynamic thrust Pae (kN/m)
TARGET_FS_SLIDING: float = 1.135                  # Seismic sliding factor of safety
TARGET_FS_OVERTURNING: float = 2.747              # Seismic overturning factor of safety
TARGET_ECCENTRICITY_M: float = 0.62               # Load resultant eccentricity e from center (m)

# Maximum Permissible Relative Error for Verification
MAX_TOLERANCE_PCT: float = 0.50                   # Relative tolerance limit: 0.5%


# ==============================================================================
# MAIN SIMULATION WORKFLOW
# ==============================================================================

def run_simulation() -> bool:
    """Executes Simulation 01 and verifies results against published benchmark."""
    print_banner(
        sim_num=1,
        title="Static Cantilever Sizing & Stability Equilibrium",
        benchmark_ref="Das (9th Ed.) Foundation Engineering Ex. 13.7",
        governing_code="IS 456:2000 / IS 1904:1986 / Eurocode 7",
    )

    # 1. Print input parameter summary
    print_section("Model Parameters & Boundary Conditions")
    input_rows = [
        ["Total Wall Height (H)", f"{TOTAL_WALL_HEIGHT_M:.2f} m", "Stem + Footing slab"],
        ["Base Width (B)", f"{TOTAL_BASE_WIDTH_M:.2f} m", "Toe + Base Stem + Heel"],
        ["Heel Length (B_heel)", f"{HEEL_LENGTH_M:.2f} m", "Supports stabilizing backfill soil"],
        ["Toe Projection (B_toe)", f"{TOE_LENGTH_M:.2f} m", "Controls toe bearing concentration"],
        ["Backfill Unit Weight (gamma)", f"{BACKFILL_UNIT_WEIGHT_KN_M3:.2f} kN/m^3", "Granular fill"],
        ["Friction Angle (phi)", f"{INTERNAL_FRICTION_ANGLE_DEG:.1f} deg", "Rankine / Coulomb shear angle"],
        ["Wall Friction (delta)", f"{WALL_INTERFACE_FRICTION_DEG:.1f} deg", "Rough concrete interface"],
        ["Seismic Demand (k_h)", f"{SEISMIC_HORIZONTAL_PGA_G:.2f} g", "Pseudo-static Mononobe-Okabe"],
    ]
    print(format_table(["Parameter", "Value", "Physical Role"], input_rows))

    # 2. Instantiate dataclasses
    geom = RetainingWallGeometry(
        stem_height=STEM_HEIGHT_M,
        stem_thickness_top=STEM_THICKNESS_TOP_M,
        stem_thickness_base=STEM_THICKNESS_BASE_M,
        toe_length=TOE_LENGTH_M,
        heel_length=HEEL_LENGTH_M,
        footing_thickness=FOOTING_THICKNESS_M,
        shear_key_depth=SHEAR_KEY_DEPTH_M,
    )
    soil = SoilProperties(
        unit_weight=BACKFILL_UNIT_WEIGHT_KN_M3,
        saturated_unit_weight=BACKFILL_SAT_UNIT_WEIGHT_KN_M3,
        friction_angle=INTERNAL_FRICTION_ANGLE_DEG,
        cohesion=SOIL_COHESION_KPA,
        foundation_cohesion=FOUNDATION_COHESION_KPA,
        wall_friction_angle=WALL_INTERFACE_FRICTION_DEG,
        foundation_friction_angle=FOUNDATION_FRICTION_DEG,
        foundation_unit_weight=FOUNDATION_UNIT_WEIGHT_KN_M3,
        allowable_bearing_capacity=ALLOWABLE_BEARING_CAPACITY_KPA,
    )
    seismic = SeismicParams(
        horizontal_pga=SEISMIC_HORIZONTAL_PGA_G,
        vertical_pga=SEISMIC_VERTICAL_PGA_G,
        water_table_depth=WATER_TABLE_DEPTH_M,
    )

    # 3. Solve stability equilibrium via orang3D physics engine
    print_section("Executing Physics Equilibrium Solver")
    res = evaluate_wall_stability(geom, soil, seismic)

    # 4. Check results against published Das Ex. 13.7 benchmark
    print_section("Benchmark Verification & Accuracy Audit")
    checks = [
        check_benchmark("Coulomb Static Ka", res.k_a_static, TARGET_STATIC_KA, MAX_TOLERANCE_PCT, "-"),
        check_benchmark("Mononobe-Okabe Kae", res.k_ae, TARGET_SEISMIC_KAE, MAX_TOLERANCE_PCT, "-"),
        check_benchmark("Total Earth Thrust Pae", res.total_thrust, TARGET_TOTAL_THRUST_KN_M, MAX_TOLERANCE_PCT, "kN/m"),
        check_benchmark("Sliding Safety Factor", res.fs_sliding, TARGET_FS_SLIDING, MAX_TOLERANCE_PCT, "-"),
        check_benchmark("Overturn Safety Factor", res.fs_overturning, TARGET_FS_OVERTURNING, MAX_TOLERANCE_PCT, "-"),
    ]

    all_passed = True
    for passed, rel_err, msg in checks:
        print(f"  {msg}")
        if not passed:
            all_passed = False

    # 5. Regulatory compliance summary
    print_section("Regulatory Code Compliance Matrix")
    thresh = get_safety_thresholds(RegionalStandard.STANDARD)
    code_rows = [
        [
            "Sliding Stability",
            f"{res.fs_sliding:.3f}",
            f">= {thresh['sliding_seismic']:.2f}",
            "[SAFE]" if res.fs_sliding >= thresh["sliding_seismic"] else "[FAIL]",
        ],
        [
            "Overturning Stability",
            f"{res.fs_overturning:.3f}",
            f">= {thresh['overturning_seismic']:.2f}",
            "[SAFE]" if res.fs_overturning >= thresh["overturning_seismic"] else "[FAIL]",
        ],
        [
            "Bearing Capacity",
            f"{res.fs_bearing:.3f}",
            f">= {thresh['bearing_seismic']:.2f}",
            "[SAFE]" if res.fs_bearing >= thresh["bearing_seismic"] else "[FAIL]",
        ],
        [
            "Resultant Eccentricity",
            f"{res.eccentricity:.3f} m",
            f"<= B/6 = {TOTAL_BASE_WIDTH_M / 6.0:.3f} m",
            "[SAFE - KERN]" if res.eccentricity <= TOTAL_BASE_WIDTH_M / 6.0 else "[TENSION DETACHMENT]",
        ],
        [
            "Stem Base Flexural Tension",
            f"{res.concrete_tensile_stress:.2f} MPa",
            "<= 2.80 MPa",
            "[ELASTIC / UNCRACKED]" if not res.cracking_predicted else "[CRACKED]",
        ],
    ]
    print(format_table(["Limit State", "Calculated Metric", "Code Limit", "Compliance"], code_rows))

    # Assert all checks passed within tolerance
    assert all_passed, "Simulation 01 failed one or more benchmark assertions!"
    print("\n>>> SIMULATION 01 EXECUTION COMPLETED: ALL BENCHMARKS PASSED (<= 0.5% ERR) <<<\n")
    return True


if __name__ == "__main__":
    success = run_simulation()
    sys.exit(0 if success else 1)
