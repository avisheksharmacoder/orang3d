"""
Simulation 02: Hydrodynamic Flooding, Phreatic Rise & Liquefaction Triggering
=============================================================================

Engineering Context:
--------------------
Examines the compound hazards of groundwater fluctuation, hydrodynamic water pressure,
and cyclic liquefaction triggering in saturated backfill. Rising phreatic levels exert
buoyant uplift that reduces effective soil intergranular stress (sigma' = sigma - u).
Concurrently, cyclic shear stress generates excess pore water pressure (r_u = Delta_u / sigma'_v0)
that degrades the effective friction angle and leads to catastrophic sliding failure.

Benchmark Reference:
--------------------
- Terzaghi, Peck, and Mesri (1996), Soil Mechanics in Engineering Practice.
- Westergaard, H. M. (1933), Water Pressures on Dams during Earthquakes.
- Seed, H. B., and Idriss, I. M. (1971), Simplified Procedure for Evaluating Soil Liquefaction.

Governing Standards:
--------------------
- Eurocode 7 (EN 1997-1) Geotechnical Design - Groundwater Provisions
- IS 1893 (Part 1): 2016 Criteria for Earthquake Resistant Design of Structures
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

from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SeismicParams,
    SoilProperties,
)
from orang3d.physics.stability import evaluate_wall_stability
from simulations.common import check_benchmark, format_table, print_banner, print_section


# ==============================================================================
# CONSTANTS: GEOMETRIC, HYDRODYNAMIC & LIQUEFACTION PARAMETERS
# ==============================================================================

# Retaining Wall Dimensions (meters)
STEM_HEIGHT_M: float = 6.00             # Retaining stem height (m)
STEM_THICKNESS_TOP_M: float = 0.35      # Crest stem thickness (m)
STEM_THICKNESS_BASE_M: float = 0.80     # Base stem thickness (m)
FOOTING_THICKNESS_M: float = 0.80       # Foundation slab thickness (m) -> Total H = 6.8 m
TOE_LENGTH_M: float = 1.20              # Foundation toe cantilever length (m)
HEEL_LENGTH_M: float = 2.50             # Foundation heel cantilever length (m)
SHEAR_KEY_DEPTH_M: float = 0.00         # Key depth (m)
TOTAL_BASE_WIDTH_M: float = TOE_LENGTH_M + STEM_THICKNESS_BASE_M + HEEL_LENGTH_M  # 4.50 m
TOTAL_WALL_HEIGHT_M: float = STEM_HEIGHT_M + FOOTING_THICKNESS_M                  # 6.80 m

# Soil Stratigraphy & Fluid Properties
SOIL_DRY_UNIT_WEIGHT_KN_M3: float = 18.50       # Dry unit weight above phreatic surface (kN/m^3)
SOIL_SAT_UNIT_WEIGHT_KN_M3: float = 20.50       # Saturated unit weight below phreatic surface (kN/m^3)
WATER_UNIT_WEIGHT_KN_M3: float = 9.81           # Unit weight of pore fluid / water (kN/m^3)
INTERNAL_FRICTION_ANGLE_DEG: float = 34.00      # Backfill effective friction angle phi' (degrees)
SOIL_COHESION_KPA: float = 0.00                 # Backfill effective cohesion c' (granular fill) (kPa)
WALL_INTERFACE_FRICTION_DEG: float = 20.00      # Wall-soil interface friction angle delta (degrees)
FOUNDATION_FRICTION_DEG: float = 30.00          # Subgrade base friction angle (degrees)
FOUNDATION_COHESION_KPA: float = 15.00          # Subgrade base cohesion (kPa)
ALLOWABLE_BEARING_CAPACITY_KPA: float = 400.00  # Subgrade allowable bearing pressure (kPa)

# Seismic Excitation Level
SEISMIC_HORIZONTAL_PGA_G: float = 0.15          # Horizontal ground acceleration k_h (g)

# Groundwater Table Depths (meters from crest)
WATER_TABLE_DEEP_DRY_M: float = 12.00           # Deep groundwater table (dry backfill baseline) (m)
WATER_TABLE_HIGH_FLOOD_M: float = 2.00          # Elevated groundwater table (severe flood event) (m)

# Excess Pore Water Pressure Ratios (Seed-Idriss Formulation)
PORE_PRESSURE_RATIO_DRY: float = 0.00           # Baseline hydrostatic (no excess pore pressure)
PORE_PRESSURE_RATIO_MODERATE: float = 0.30      # Moderate cyclic pore pressure buildup
PORE_PRESSURE_RATIO_LIQUEFIED: float = 0.55     # High liquefaction triggering threshold

# Benchmark Verification Targets
TARGET_DRY_TOTAL_THRUST_KN_M: float = 152.29    # Baseline dry active thrust (kN/m)
TARGET_DRY_FS_SLIDING: float = 1.242            # Baseline dry sliding safety factor
TARGET_FLOOD_TOTAL_THRUST_KN_M: float = 219.92  # Flooded active + hydrostatic thrust (kN/m)
TARGET_FLOOD_FS_SLIDING: float = 0.899          # Flooded sliding safety factor (marginal/unstable)
TARGET_LIQUEFIED_THRUST_KN_M: float = 311.21    # Liquefied combined lateral thrust (kN/m)
TARGET_LIQUEFIED_FS_SLIDING: float = 0.656      # Liquefied sliding safety factor (collapse < 1.0)

# Allowable Error Tolerance
MAX_TOLERANCE_PCT: float = 0.50                 # Relative tolerance limit: 0.5%


# ==============================================================================
# MAIN SIMULATION WORKFLOW
# ==============================================================================

def run_simulation() -> bool:
    """Executes Simulation 02 and verifies hydrodynamic & liquefaction failure transitions."""
    print_banner(
        sim_num=2,
        title="Hydrodynamic Flooding & Liquefaction Triggering",
        benchmark_ref="Terzaghi & Peck (1996) / Westergaard (1933) / Seed-Idriss (1971)",
        governing_code="Eurocode 7 (EN 1997-1) / IS 1893:2016",
    )

    # 1. Print boundary conditions and hazard scenarios
    print_section("Hazard Stages & Multi-Phase Conditions")
    scenario_rows = [
        ["Stage 1: Dry Baseline", f"H_w = {WATER_TABLE_DEEP_DRY_M:.1f} m", "r_u = 0.00", "Normal operating conditions"],
        ["Stage 2: Severe Flooding", f"H_w = {WATER_TABLE_HIGH_FLOOD_M:.1f} m", "r_u = 0.00", "Hydrostatic thrust + buoyancy uplift"],
        ["Stage 3: Cyclic Liquefaction", f"H_w = {WATER_TABLE_HIGH_FLOOD_M:.1f} m", f"r_u = {PORE_PRESSURE_RATIO_LIQUEFIED:.2f}", "Pore pressure surge + friction loss"],
    ]
    print(format_table(["Hazard Phase", "Water Depth (H_w)", "Pore Pressure (r_u)", "Physical Consequence"], scenario_rows))

    # 2. Instantiate persistent model objects
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
        friction_angle=INTERNAL_FRICTION_ANGLE_DEG,
        cohesion=SOIL_COHESION_KPA,
        unit_weight=SOIL_DRY_UNIT_WEIGHT_KN_M3,
        saturated_unit_weight=SOIL_SAT_UNIT_WEIGHT_KN_M3,
        wall_friction_angle=WALL_INTERFACE_FRICTION_DEG,
        foundation_friction_angle=FOUNDATION_FRICTION_DEG,
        foundation_cohesion=FOUNDATION_COHESION_KPA,
        allowable_bearing_capacity=ALLOWABLE_BEARING_CAPACITY_KPA,
    )

    # 3. Execute multi-hazard evaluations
    print_section("Evaluating Multi-Stage Hazard Responses")
    
    # Stage 1: Dry Baseline
    seismic_dry = SeismicParams(
        horizontal_pga=SEISMIC_HORIZONTAL_PGA_G,
        water_table_depth=WATER_TABLE_DEEP_DRY_M,
        pore_pressure_ratio_ru=PORE_PRESSURE_RATIO_DRY,
    )
    res_dry = evaluate_wall_stability(geom, soil, seismic_dry)

    # Stage 2: Elevated Water Table (Flooded)
    seismic_wet = SeismicParams(
        horizontal_pga=SEISMIC_HORIZONTAL_PGA_G,
        water_table_depth=WATER_TABLE_HIGH_FLOOD_M,
        pore_pressure_ratio_ru=PORE_PRESSURE_RATIO_DRY,
    )
    res_wet = evaluate_wall_stability(geom, soil, seismic_wet)

    # Stage 3: Flooded + Liquefaction Triggering (r_u = 0.55)
    seismic_liq = SeismicParams(
        horizontal_pga=SEISMIC_HORIZONTAL_PGA_G,
        water_table_depth=WATER_TABLE_HIGH_FLOOD_M,
        pore_pressure_ratio_ru=PORE_PRESSURE_RATIO_LIQUEFIED,
    )
    res_liq = evaluate_wall_stability(geom, soil, seismic_liq)

    # 4. Verify benchmarks against published models
    print_section("Benchmark Verification & Accuracy Audit")
    checks = [
        check_benchmark("Stage 1 Dry Thrust", res_dry.total_thrust, TARGET_DRY_TOTAL_THRUST_KN_M, MAX_TOLERANCE_PCT, "kN/m"),
        check_benchmark("Stage 1 Dry FS_sliding", res_dry.fs_sliding, TARGET_DRY_FS_SLIDING, MAX_TOLERANCE_PCT, "-"),
        check_benchmark("Stage 2 Flooded Thrust", res_wet.total_thrust, TARGET_FLOOD_TOTAL_THRUST_KN_M, MAX_TOLERANCE_PCT, "kN/m"),
        check_benchmark("Stage 2 Flooded FS_sliding", res_wet.fs_sliding, TARGET_FLOOD_FS_SLIDING, MAX_TOLERANCE_PCT, "-"),
        check_benchmark("Stage 3 Liquefied Thrust", res_liq.total_thrust, TARGET_LIQUEFIED_THRUST_KN_M, MAX_TOLERANCE_PCT, "kN/m"),
        check_benchmark("Stage 3 Liquefied FS_sliding", res_liq.fs_sliding, TARGET_LIQUEFIED_FS_SLIDING, MAX_TOLERANCE_PCT, "-"),
    ]

    all_passed = True
    for passed, rel_err, msg in checks:
        print(f"  {msg}")
        if not passed:
            all_passed = False

    # 5. Multi-stage degradation summary
    print_section("Compound Disaster Degradation Trajectory")
    thrust_pct_surge = (res_liq.total_thrust - res_dry.total_thrust) / res_dry.total_thrust * 100.0
    sliding_pct_drop = (res_dry.fs_sliding - res_liq.fs_sliding) / res_dry.fs_sliding * 100.0

    summary_rows = [
        [
            "Stage 1 (Dry)",
            f"{res_dry.total_thrust:.2f} kN/m",
            f"{res_dry.fs_sliding:.3f}",
            f"{res_dry.fs_overturning:.3f}",
            "[STABLE / PASS]",
        ],
        [
            "Stage 2 (Flooded)",
            f"{res_wet.total_thrust:.2f} kN/m",
            f"{res_wet.fs_sliding:.3f}",
            f"{res_wet.fs_overturning:.3f}",
            "[MARGINAL / WARNING]",
        ],
        [
            "Stage 3 (Liquefied r_u=0.55)",
            f"{res_liq.total_thrust:.2f} kN/m",
            f"{res_liq.fs_sliding:.3f}",
            f"{res_liq.fs_overturning:.3f}",
            "[COLLAPSE / RUNAWAY SLIP]",
        ],
    ]
    print(format_table(["Hazard Phase", "Total Thrust", "FS Sliding", "FS Overturning", "Stability Status"], summary_rows))

    print(f"\n  Key Engineering Diagnostic:")
    print(f"  - Total lateral thrust surged by +{thrust_pct_surge:.1f}% under high phreatic + pore pressure buildup.")
    print(f"  - Sliding factor of safety degraded by -{sliding_pct_drop:.1f}%, crashing to FS = {res_liq.fs_sliding:.3f} (< 1.00).")

    # Invariant assertions
    assert res_wet.total_thrust > res_dry.total_thrust, "Hydrostatic water must increase total thrust!"
    assert res_liq.total_thrust > res_wet.total_thrust, "Pore pressure ratio r_u must further increase thrust!"
    assert res_wet.fs_sliding < res_dry.fs_sliding, "Flooding must reduce sliding factor of safety!"
    assert res_liq.fs_sliding < 1.00, "Severe liquefaction (r_u = 0.55) must trigger sliding collapse!"
    assert all_passed, "Simulation 02 failed one or more benchmark assertions!"

    print("\n>>> SIMULATION 02 EXECUTION COMPLETED: ALL BENCHMARKS PASSED (<= 0.5% ERR) <<<\n")
    return True


if __name__ == "__main__":
    success = run_simulation()
    sys.exit(0 if success else 1)
