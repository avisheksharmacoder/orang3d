"""
Simulation 07: Architectural Surcharges & Stepped Terraced Wall Alignment
=========================================================================

Engineering Context:
--------------------
In urban developments and hillside infrastructure, retaining structures support adjacent
footing surcharges from multi-story buildings, crane pads, and traffic lanes. Elastic half-space
theory dictates that surface loads induce lateral horizontal stress distributions along the
retaining stem, formulated via modified Boussinesq (1885) and Mindlin (1936) stress equations:
sigma_h(z) = (2 * q / pi) * [beta - sin(beta) * cos(2 * alpha)]. This simulation verifies the
analytical closed-form Terzaghi-Spangler solution and computes combined wall stability under
building strip and pad footing loads.

Benchmark Reference:
--------------------
- Boussinesq, J. (1885), Application des potentiels a l'etude de l'equilibre et du mouvement des solides elastiques.
- Terzaghi, K., and Peck, R. B. (1948), Soil Mechanics in Engineering Practice (Surcharge Thrust on Rigid Walls).
- Poulos, H. G., and Davis, E. H. (1974), Elastic Solutions for Soil and Rock Mechanics.

Governing Standards:
--------------------
- AASHTO LRFD Bridge Design Specifications (Section 3.11.6 Uniform and Strip Surcharges)
- Eurocode 7 (EN 1997-1) Section 7.3.2 Surcharge Actions on Retaining Structures
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
import numpy as np

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
from orang3d.physics.surcharge import (
    AdjacentSurchargeParams,
    SurchargeLoadType,
    calculate_adjacent_surcharge_profile,
    evaluate_wall_stability_with_surcharge,
)
from simulations.common import check_benchmark, format_table, print_banner, print_section


# ==============================================================================
# CONSTANTS: SURCHARGE & STEEDED WALL PARAMETERS
# ==============================================================================

# Retaining Wall Stem Dimensions (meters)
WALL_TOTAL_HEIGHT_M: float = 6.00       # Vertical retaining wall height H (m)
STEM_THICKNESS_BASE_M: float = 0.60     # Stem thickness at base (m)
STEM_THICKNESS_TOP_M: float = 0.35      # Stem thickness at top (m)
FOOTING_THICKNESS_M: float = 0.60       # Footing slab thickness (m)
TOE_LENGTH_M: float = 1.00              # Foundation toe cantilever (m)
HEEL_LENGTH_M: float = 2.40             # Foundation heel cantilever (m)

# Soil Geotechnical Properties
SOIL_UNIT_WEIGHT_KN_M3: float = 19.00   # Backfill unit weight gamma (kN/m^3)
SOIL_FRICTION_ANGLE_DEG: float = 32.00  # Backfill friction angle phi (degrees)
SOIL_COHESION_KPA: float = 0.00         # Granular backfill cohesion (kPa)

# Terzaghi-Spangler Closed-Form Benchmark Parameters (Line Load on Rigid Wall)
LINE_LOAD_MAGNITUDE_KN_M: float = 100.00 # Concentrated line surcharge force Q_line (kN/m)
LINE_LOAD_SETBACK_X0_M: float = 2.00     # Setback distance from wall crest x0 (m)
STRIP_EQUIV_WIDTH_M: float = 0.02        # Narrow strip equivalent width b (m)

# Closed-Form Terzaghi-Spangler Analytical Result:
# P_surcharge = (2 * Q_line / pi) * [H^2 / (x0^2 + H^2)]
TARGET_ANALYTICAL_LINE_THRUST_KN_M: float = (
    (2.0 * LINE_LOAD_MAGNITUDE_KN_M / math.pi)
    * ((WALL_TOTAL_HEIGHT_M ** 2) / (LINE_LOAD_SETBACK_X0_M ** 2 + WALL_TOTAL_HEIGHT_M ** 2))
)  # 57.296 kN/m

# Realistic Building Strip Footing Scenario
BUILDING_TOTAL_LOAD_KN: float = 600.00  # Column/wall foundation load (kN)
FOOTING_WIDTH_M: float = 2.00           # Strip footing width (m)
FOOTING_LENGTH_M: float = 4.00          # Footing length along wall alignment (m)
FOOTING_SETBACK_M: float = 1.20         # Distance from back of wall to footing edge (m)
FOOTING_EMBEDMENT_M: float = 0.80       # Foundation embedment depth D_f (m)
TARGET_BUILDING_THRUST_KN_M: float = 80.66 # Resulting Boussinesq lateral thrust (kN/m)

# Relative Tolerance Limit
MAX_TOLERANCE_PCT: float = 0.50         # Tolerance threshold: 0.5%


# ==============================================================================
# MAIN SIMULATION WORKFLOW
# ==============================================================================

def run_simulation() -> bool:
    """Executes Simulation 07 and verifies Boussinesq surcharge integration."""
    print_banner(
        sim_num=7,
        title="Architectural Surcharges & Stepped Wall Alignment",
        benchmark_ref="Boussinesq (1885) / Terzaghi-Spangler Closed-Form Rigid Wall Formulation",
        governing_code="AASHTO LRFD (Sec 3.11.6) / Eurocode 7 (Sec 7.3.2)",
    )

    # 1. Print surcharge geometry and loading conditions
    print_section("Surcharge Footing Geometry & Loading Demands")
    surcharge_rows = [
        ["Wall Height (H)", f"{WALL_TOTAL_HEIGHT_M:.2f} m", "Total retaining interface height"],
        ["Closed-Form Line Load (Q)", f"{LINE_LOAD_MAGNITUDE_KN_M:.1f} kN/m", f"Setback x_0 = {LINE_LOAD_SETBACK_X0_M:.1f} m from wall backface"],
        ["Building Footing Load", f"{BUILDING_TOTAL_LOAD_KN:.1f} kN", f"{FOOTING_WIDTH_M:.1f} m x {FOOTING_LENGTH_M:.1f} m pad/strip"],
        ["Building Footing Setback", f"{FOOTING_SETBACK_M:.2f} m", f"Embedment depth D_f = {FOOTING_EMBEDMENT_M:.2f} m"],
        ["Backfill Friction (phi)", f"{SOIL_FRICTION_ANGLE_DEG:.1f} deg", "Governs Coulomb active wedge slope"],
        ["Governing Theory", "Boussinesq Elastic Half-Space", "Modified for rigid vertical boundary reflection (2x)"],
    ]
    print(format_table(["Surcharge Parameter", "Magnitude", "Physical Meaning"], surcharge_rows))

    # 2. Instantiate soil and seismic state
    soil = SoilProperties(unit_weight=SOIL_UNIT_WEIGHT_KN_M3, friction_angle=SOIL_FRICTION_ANGLE_DEG)
    seismic_static = SeismicParams(horizontal_pga=0.00, vertical_pga=0.00, water_table_depth=12.00)

    # 3. Benchmark 1: Terzaghi-Spangler Closed-Form Line Load Check
    print_section("Verifying Terzaghi-Spangler Closed-Form Line Load")
    thin_strip_params = AdjacentSurchargeParams(
        load_type=SurchargeLoadType.UNIFORM_TRAFFIC,
        uniform_q_kpa=LINE_LOAD_MAGNITUDE_KN_M / STRIP_EQUIV_WIDTH_M,
        footing_width_m=STRIP_EQUIV_WIDTH_M,
        setback_m=LINE_LOAD_SETBACK_X0_M,
        embedment_m=0.00,
    )
    thin_res = calculate_adjacent_surcharge_profile(
        params=thin_strip_params,
        wall_height=WALL_TOTAL_HEIGHT_M,
        soil=soil,
        seismic=seismic_static,
        num_eval_points=401,
    )

    passed_line, rel_err_line, msg_line = check_benchmark(
        name="Terzaghi-Spangler Thrust",
        calculated=thin_res.total_thrust_kn_per_m,
        target=TARGET_ANALYTICAL_LINE_THRUST_KN_M,
        tolerance_pct=MAX_TOLERANCE_PCT,
        unit="kN/m",
    )
    print(f"  {msg_line}")
    assert passed_line, "Numerical Boussinesq integral deviated from analytical closed-form solution!"

    # 4. Benchmark 2: Realistic Building Strip Footing Evaluation
    print_section("Evaluating Adjacent Building Strip Footing")
    bld_params = AdjacentSurchargeParams(
        load_type=SurchargeLoadType.BUILDING_STRIP_FOOTING,
        building_load_kn=BUILDING_TOTAL_LOAD_KN,
        footing_width_m=FOOTING_WIDTH_M,
        footing_length_m=FOOTING_LENGTH_M,
        setback_m=FOOTING_SETBACK_M,
        embedment_m=FOOTING_EMBEDMENT_M,
    )
    bld_res = calculate_adjacent_surcharge_profile(
        params=bld_params,
        wall_height=WALL_TOTAL_HEIGHT_M,
        soil=soil,
        seismic=seismic_static,
    )

    passed_bld, rel_err_bld, msg_bld = check_benchmark(
        name="Building Surcharge Thrust",
        calculated=bld_res.total_thrust_kn_per_m,
        target=TARGET_BUILDING_THRUST_KN_M,
        tolerance_pct=MAX_TOLERANCE_PCT,
        unit="kN/m",
    )
    print(f"  {msg_bld}")
    assert passed_bld, "Building surcharge thrust deviated from benchmark target!"

    # 5. Benchmark 3: Setback Monotonicity Verification
    print_section("Verifying Setback Distance Monotonicity")
    setback_series = [4.00, 2.50, 1.50, 0.80, 0.20]
    thrust_series = []
    for sb in setback_series:
        p = AdjacentSurchargeParams(
            load_type=SurchargeLoadType.BUILDING_STRIP_FOOTING,
            building_load_kn=BUILDING_TOTAL_LOAD_KN,
            footing_width_m=FOOTING_WIDTH_M,
            footing_length_m=FOOTING_LENGTH_M,
            setback_m=sb,
            embedment_m=FOOTING_EMBEDMENT_M,
        )
        r = calculate_adjacent_surcharge_profile(p, WALL_TOTAL_HEIGHT_M, soil, seismic_static)
        thrust_series.append(r.total_thrust_kn_per_m)
        print(f"  Setback x_f = {sb:4.2f} m -> Lateral Thrust Delta P_q = {r.total_thrust_kn_per_m:6.2f} kN/m")

    # Verify strict monotonic increase as footing approaches wall backface
    is_monotonic = all(t2 > t1 for t1, t2 in zip(thrust_series, thrust_series[1:]))
    print(f"\n  Monotonicity Verification: {'[PASSED - STRICTLY INCREASING]' if is_monotonic else '[FAILED]'}")
    assert is_monotonic, "Thrust must increase monotonically as setback distance approaches zero!"

    # 6. Combined Retaining Wall Stability with Adjacent Surcharge
    print_section("Combined Stability Under Retained Soil + Building Footing")
    geom = RetainingWallGeometry(
        stem_height=WALL_TOTAL_HEIGHT_M - FOOTING_THICKNESS_M,
        stem_thickness_base=STEM_THICKNESS_BASE_M,
        stem_thickness_top=STEM_THICKNESS_TOP_M,
        footing_thickness=FOOTING_THICKNESS_M,
        toe_length=TOE_LENGTH_M,
        heel_length=HEEL_LENGTH_M,
    )
    res_comb, _ = evaluate_wall_stability_with_surcharge(geom, soil, seismic_static, bld_params)

    audit_rows = [
        ["Added Surcharge Thrust (Delta P_q)", f"{bld_res.total_thrust_kn_per_m:.2f} kN/m", "Boussinesq integral", "[APPLIED]"],
        ["Surcharge Resultant Height (z_q)", f"{bld_res.resultant_elevation_m:.2f} m", "Mid-stem elevation", "[EVALUATED]"],
        ["Combined Sliding Factor of Safety", f"{res_comb.fs_sliding:.3f}", ">= 1.50 (IS / EC7)", "[SAFE]" if res_comb.fs_sliding >= 1.50 else "[MARGINAL]"],
        ["Combined Overturn Factor of Safety", f"{res_comb.fs_overturning:.3f}", ">= 2.00 (IS / EC7)", "[SAFE]" if res_comb.fs_overturning >= 2.00 else "[FAIL]"],
        ["Eccentricity under Surcharge (e)", f"{res_comb.eccentricity:.3f} m", f"<= B/6 = {geom.base_width / 6.0:.3f} m", "[SAFE - KERN]" if res_comb.eccentricity <= geom.base_width / 6.0 else "[TENSION]"],
    ]
    print(format_table(["Stability Indicator", "Value", "Design Limit", "Compliance"], audit_rows))

    print(f"\n  Engineering Summary:")
    print(f"  - Closed-form Terzaghi-Spangler line load solution matched to within {rel_err_line:.3f}%.")
    print(f"  - Proved strict physical monotonicity: moving building footing from 4.0 m to 0.2 m surges lateral thrust from {thrust_series[0]:.1f} to {thrust_series[-1]:.1f} kN/m.")
    print("\n>>> SIMULATION 07 EXECUTION COMPLETED: ALL BENCHMARKS PASSED (<= 0.5% ERR) <<<\n")
    return True


if __name__ == "__main__":
    success = run_simulation()
    sys.exit(0 if success else 1)

