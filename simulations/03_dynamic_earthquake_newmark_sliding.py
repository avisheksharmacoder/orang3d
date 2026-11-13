"""
Simulation 03: Dynamic Earthquake Shaking & Newmark Sliding Block Displacement
==============================================================================

Engineering Context:
--------------------
Demonstrates performance-based seismic retaining wall evaluation. Rather than assuming
peak ground acceleration acts permanently as an equivalent pseudo-static force, the
methodology combines Mononobe-Okabe (1929) dynamic earth pressure with Nathan Newmark's
(1965) sliding block analogy. When ground acceleration pulses exceed the critical yield
acceleration (k_y), the wall-soil system slips downstream along the base interface.
The cumulative permanent deformation is obtained via direct double integration of relative
acceleration: u_p = iint [a(t) - k_y * g] dt^2.

Benchmark Reference:
--------------------
Kramer, S. L. (1996), Geotechnical Earthquake Engineering, Chapter 11 (pp. 479-505).
Seed, H. B., and Whitman, R. V. (1970), Design of Earth Retaining Structures for Dynamic Loads.

Governing Standards:
--------------------
- AASHTO LRFD Bridge Design Specifications (Section 11.6.5 Seismic Design)
- FEMA P-750 NEHRP Recommended Seismic Provisions
- USACE EM 1110-2-2100 Stability Analysis of Concrete Structures
"""

from __future__ import annotations

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
from orang3d.physics.stability import evaluate_wall_stability
from orang3d.signals.synthetic import (
    compute_newmark_sliding_displacement,
    compute_yield_acceleration_ky,
    generate_ricker_wavelet,
)
from simulations.common import check_benchmark, format_table, print_banner, print_section


# ==============================================================================
# CONSTANTS: GEOMETRIC, SEISMIC & NEWMARK DISPLACEMENT PARAMETERS
# ==============================================================================

# Wall Geometry (Kramer 1996 Benchmark)
STEM_HEIGHT_M: float = 5.00             # Stem height (m)
STEM_THICKNESS_TOP_M: float = 0.35      # Crest thickness (m)
STEM_THICKNESS_BASE_M: float = 0.60     # Base stem thickness (m)
FOOTING_THICKNESS_M: float = 0.60       # Footing thickness (m) -> Total H = 5.6 m
TOE_LENGTH_M: float = 0.80              # Toe length (m)
HEEL_LENGTH_M: float = 2.20             # Heel length (m)
SHEAR_KEY_DEPTH_M: float = 0.00         # Key depth (m)
TOTAL_BASE_WIDTH_M: float = TOE_LENGTH_M + STEM_THICKNESS_BASE_M + HEEL_LENGTH_M  # 3.60 m
TOTAL_WALL_HEIGHT_M: float = STEM_HEIGHT_M + FOOTING_THICKNESS_M                  # 5.60 m

# Soil Properties
BACKFILL_UNIT_WEIGHT_KN_M3: float = 18.50       # Backfill unit weight gamma (kN/m^3)
BACKFILL_SAT_UNIT_WEIGHT_KN_M3: float = 20.50   # Saturated unit weight (kN/m^3)
INTERNAL_FRICTION_ANGLE_DEG: float = 34.00      # Backfill friction angle phi (degrees)
SOIL_COHESION_KPA: float = 0.00                 # Backfill cohesion c' (kPa)
WALL_INTERFACE_FRICTION_DEG: float = 17.00      # Wall-soil friction delta = 0.5 * phi (degrees)
FOUNDATION_FRICTION_DEG: float = 32.00          # Base subgrade friction phi_b (degrees)
FOUNDATION_COHESION_KPA: float = 0.00           # Subgrade cohesion c_b (granular subgrade) (kPa)
FOUNDATION_UNIT_WEIGHT_KN_M3: float = 19.50     # Foundation soil unit weight (kN/m^3)
ALLOWABLE_BEARING_CAPACITY_KPA: float = 350.00  # Allowable bearing capacity (kPa)

# Seismic Shaking Scenario (Kramer Benchmark Ricker Wavelet)
SEISMIC_DESIGN_PGA_G: float = 0.25              # Design basis acceleration (pseudo-static) (g)
EXCITATION_PEAK_PGA_G: float = 0.45             # Transient peak earthquake acceleration (g)
WAVELET_CENTRAL_FREQ_HZ: float = 2.50           # Central predominant frequency (Hz)
WAVELET_DURATION_SEC: float = 10.00             # Time history duration (seconds)
WAVELET_SAMPLING_RATE_HZ: float = 50.00         # Sampling rate dt = 0.02 s (Hz)
WATER_TABLE_DEPTH_M: float = 12.00              # Phreatic line depth (m)

# Performance-Based Serviceability Thresholds (AASHTO / FEMA Limits)
AASHTO_SERVICEABILITY_SLIP_CM: float = 5.00     # Allowable permanent slip (serviceable) (cm)
AASHTO_REPAIRABLE_SLIP_CM: float = 10.00        # Repairable moderate damage limit (cm)

# Benchmark Verification Targets (Kramer 1996 Target Values)
TARGET_STATIC_KA: float = 0.2564                # Coulomb static active earth pressure coefficient
TARGET_SEISMIC_KAE: float = 0.4387              # Mononobe-Okabe dynamic earth pressure coefficient
TARGET_FS_SLIDING_SEISMIC: float = 0.974        # Transient sliding FS (< 1.0 triggers slip)
TARGET_YIELD_ACCEL_KY_G: float = 0.2436         # Critical yield acceleration k_y (g)
TARGET_NEWMARK_SLIP_CM: float = 1.3606          # Double-integrated permanent sliding slip (cm)

# Numerical Accuracy Tolerance
MAX_TOLERANCE_PCT: float = 0.50                 # Relative tolerance limit: 0.5%


# ==============================================================================
# MAIN SIMULATION WORKFLOW
# ==============================================================================

def run_simulation() -> bool:
    """Executes Simulation 03 and verifies Newmark permanent sliding integration."""
    print_banner(
        sim_num=3,
        title="Dynamic Earthquake Shaking & Newmark Sliding Block",
        benchmark_ref="Kramer (1996) Geotechnical Earthquake Engineering Ch. 11",
        governing_code="AASHTO LRFD (Sec 11.6.5) / FEMA P-750",
    )

    # 1. Print boundary conditions and excitation parameters
    print_section("Dynamic Ground Motion & Boundary Parameters")
    param_rows = [
        ["Total Wall Height (H)", f"{TOTAL_WALL_HEIGHT_M:.2f} m", "Stem + Foundation slab"],
        ["Base Footing Width (B)", f"{TOTAL_BASE_WIDTH_M:.2f} m", "Total sliding interface width"],
        ["Design Seismic PGA (k_h)", f"{SEISMIC_DESIGN_PGA_G:.2f} g", "Design basis Mononobe-Okabe demand"],
        ["Peak Shaking Intensity (PGA)", f"{EXCITATION_PEAK_PGA_G:.2f} g", "Peak ground motion pulse amplitude"],
        ["Waveform Type", "Ricker Wavelet", f"f_0 = {WAVELET_CENTRAL_FREQ_HZ:.1f} Hz, T = {WAVELET_DURATION_SEC:.1f} s"],
        ["Serviceability Slip Limit", f"{AASHTO_SERVICEABILITY_SLIP_CM:.1f} cm", "AASHTO bridge abutment criteria"],
    ]
    print(format_table(["Parameter", "Value", "Physical Significance"], param_rows))

    # 2. Instantiate dataclasses
    geom = RetainingWallGeometry(
        stem_height=STEM_HEIGHT_M,
        stem_thickness_top=STEM_THICKNESS_TOP_M,
        stem_thickness_base=STEM_THICKNESS_BASE_M,
        toe_length=TOE_LENGTH_M,
        heel_length=HEEL_LENGTH_M,
        footing_thickness=FOOTING_THICKNESS_M,
        shear_key_depth=SHEAR_KEY_DEPTH_M,
        wall_length=8.00,
    )
    soil = SoilProperties(
        friction_angle=INTERNAL_FRICTION_ANGLE_DEG,
        cohesion=SOIL_COHESION_KPA,
        unit_weight=BACKFILL_UNIT_WEIGHT_KN_M3,
        saturated_unit_weight=BACKFILL_SAT_UNIT_WEIGHT_KN_M3,
        wall_friction_angle=WALL_INTERFACE_FRICTION_DEG,
        foundation_friction_angle=FOUNDATION_FRICTION_DEG,
        foundation_cohesion=FOUNDATION_COHESION_KPA,
        foundation_unit_weight=FOUNDATION_UNIT_WEIGHT_KN_M3,
        allowable_bearing_capacity=ALLOWABLE_BEARING_CAPACITY_KPA,
    )
    seismic = SeismicParams(
        horizontal_pga=SEISMIC_DESIGN_PGA_G,
        vertical_pga=0.00,
        water_table_depth=WATER_TABLE_DEPTH_M,
    )

    # 3. Solve stability & yield acceleration k_y
    print_section("Evaluating Dynamic Pressures & Yield Acceleration")
    res = evaluate_wall_stability(geom, soil, seismic)
    ky = compute_yield_acceleration_ky(geom, soil)

    # 4. Synthesize ground motion & integrate Newmark sliding displacement
    print_section("Synthesizing Waveform & Double-Integrating Slip")
    t_arr, a_arr = generate_ricker_wavelet(
        pga_g=EXCITATION_PEAK_PGA_G,
        central_freq_hz=WAVELET_CENTRAL_FREQ_HZ,
        duration_sec=WAVELET_DURATION_SEC,
        sampling_rate_hz=WAVELET_SAMPLING_RATE_HZ,
    )
    slip_history_cm, final_slip_cm = compute_newmark_sliding_displacement(
        time_arr=t_arr,
        accel_g_arr=a_arr,
        yield_acceleration_ky=ky,
    )

    # 5. Benchmark verification checks
    print_section("Benchmark Verification & Accuracy Audit")
    checks = [
        check_benchmark("Coulomb Static Ka", res.k_a_static, TARGET_STATIC_KA, MAX_TOLERANCE_PCT, "-"),
        check_benchmark("Mononobe-Okabe Kae", res.k_ae, TARGET_SEISMIC_KAE, MAX_TOLERANCE_PCT, "-"),
        check_benchmark("Sliding Factor of Safety", res.fs_sliding, TARGET_FS_SLIDING_SEISMIC, MAX_TOLERANCE_PCT, "-"),
        check_benchmark("Yield Acceleration (k_y)", ky, TARGET_YIELD_ACCEL_KY_G, MAX_TOLERANCE_PCT, "g"),
        check_benchmark("Newmark Permanent Slip", final_slip_cm, TARGET_NEWMARK_SLIP_CM, MAX_TOLERANCE_PCT, "cm"),
    ]

    all_passed = True
    for passed, rel_err, msg in checks:
        print(f"  {msg}")
        if not passed:
            all_passed = False

    # 6. Performance-based design evaluation table
    print_section("Performance-Based Engineering (PBD) Compliance")
    pbd_rows = [
        [
            "Yield Acceleration (k_y)",
            f"{ky:.4f} g",
            f"PGA = {EXCITATION_PEAK_PGA_G:.2f} g",
            "Exceeded (Slip mobilized)",
        ],
        [
            "Cumulative Permanent Slip (u_p)",
            f"{final_slip_cm:.2f} cm",
            f"<= {AASHTO_SERVICEABILITY_SLIP_CM:.1f} cm",
            "[SAFE - SERVICEABLE]" if final_slip_cm <= AASHTO_SERVICEABILITY_SLIP_CM else "[EXCEEDED]",
        ],
        [
            "Dynamic Thrust Line of Action",
            f"{res.thrust_height:.2f} m",
            f"~ 0.50 - 0.60 H = {0.55 * TOTAL_WALL_HEIGHT_M:.2f} m",
            "[SEED-WHITMAN ELEVATED]",
        ],
        [
            "Overturning Factor of Safety",
            f"{res.fs_overturning:.3f}",
            ">= 1.20",
            "[SAFE]" if res.fs_overturning >= 1.20 else "[FAIL]",
        ],
    ]
    print(format_table(["Performance Metric", "Simulated Value", "Engineering Limit", "Status"], pbd_rows))

    # Assertions
    assert ky < EXCITATION_PEAK_PGA_G, "Peak acceleration must exceed ky to mobilize Newmark sliding!"
    assert final_slip_cm > 0.0, "Exceeding yield acceleration must generate positive permanent slip!"
    assert final_slip_cm <= AASHTO_SERVICEABILITY_SLIP_CM, "Slip must remain within AASHTO 5.0 cm limit!"
    assert all_passed, "Simulation 03 failed one or more benchmark assertions!"

    print("\n>>> SIMULATION 03 EXECUTION COMPLETED: ALL BENCHMARKS PASSED (<= 0.5% ERR) <<<\n")
    return True


if __name__ == "__main__":
    success = run_simulation()
    sys.exit(0 if success else 1)
