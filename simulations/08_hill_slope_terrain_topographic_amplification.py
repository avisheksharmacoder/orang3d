"""
Simulation 08: Hill-Slope DEM Terrain & Topographic Seismic Amplification
========================================================================

Engineering Context:
--------------------
Retaining structures constructed along mountainous slope cuts, ridge crests, and canyon
embankments experience amplified earthquake shaking due to topographic wave focusing.
Seismic P and SV waves reflecting within convex slopes undergo constructive interference,
amplifying peak ground accelerations at the crest. Both Eurocode 8 (Part 5, Clause 4.1.4)
and the Bureau of Indian Standards (IS 1893:2016, Clause 6.4.4) mandate a topographic
amplification factor S_T >= 1.20 for slope angles beta > 15 deg, and S_T >= 1.40 for steep
ridges (beta > 30 deg). Concurrently, down-slope ground reduces passive toe resistance.

Benchmark Reference:
--------------------
- Eurocode 8: Design of Structures for Earthquake Resistance - Part 5 (EN 1998-5:2004, Clause 4.1.4).
- Bureau of Indian Standards, IS 1893 (Part 1): 2016, Clause 6.4.4 (Topographic Amplification).
- AFPS (French Association for Earthquake Engineering) Topographical Effects Guidelines.

Governing Standards:
--------------------
- Eurocode 8 (EN 1998-5) Topographic Factor S_T
- IS 1893 (Part 1): 2016 Clause 6.4.4
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Add project root and src to path for direct terminal execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Import physics first to initialize module dependencies
import orang3d.physics
from orang3d.signals.topography import (
    apply_topographic_amplification,
    compute_slope_modified_passive_resistance,
    compute_topographic_amplification_factor,
)
from simulations.common import check_benchmark, format_table, print_banner, print_section


# ==============================================================================
# CONSTANTS: TOPOGRAPHIC, GEOMETRIC & REGULATORY PARAMETERS
# ==============================================================================

# Hillside Terrain Slope Properties
MEAN_HILL_SLOPE_BETA_DEG: float = 22.40     # Mean hillside ground inclination beta (degrees)
HILL_HEIGHT_H_M: float = 30.00              # Total elevation difference of ridge/slope (m)
CREST_DISTANCE_AT_WALL_M: float = 0.00      # Wall position relative to ridge crest (0.0 = at crest)
SHEAR_WAVE_VELOCITY_VS_M_S: float = 300.00  # Subgrade shear wave velocity V_s (m/s)

# Seismic Shaking Demand (Flat Subgrade Baseline)
BASELINE_NOMINAL_PGA_G: float = 0.20        # Baseline flat-ground peak acceleration k_h (g)

# Regulatory Topographic Factor Thresholds (Eurocode 8 / IS 1893)
EUROCODE_GENTLE_THRESHOLD_DEG: float = 15.00 # Slopes <= 15 deg have S_T = 1.00
EUROCODE_STEEP_THRESHOLD_DEG: float = 30.00  # Slopes > 30 deg have S_T = 1.40 (ridge)
TARGET_TOPOGRAPHIC_FACTOR_ST: float = 1.20   # Medium slope (15 < beta <= 30 deg) -> S_T = 1.20

# Amplified Crest Seismic Shaking Target
TARGET_AMPLIFIED_PGA_G: float = BASELINE_NOMINAL_PGA_G * TARGET_TOPOGRAPHIC_FACTOR_ST  # 0.24 g

# Passive Toe Resistance Parameters
LEVEL_PASSIVE_KP: float = 4.00              # Level ground Rankine passive coefficient K_p
SOIL_FRICTION_ANGLE_DEG: float = 34.00      # Foundation soil internal friction angle (degrees)
TARGET_SLOPING_PASSIVE_KP: float = 0.3469   # Down-slope degraded passive resistance K_p,slope

# Numerical Tolerance Limit
MAX_TOLERANCE_PCT: float = 0.50             # Relative tolerance limit: 0.5%


# ==============================================================================
# MAIN SIMULATION WORKFLOW
# ==============================================================================

def run_simulation() -> bool:
    """Executes Simulation 08 and verifies Eurocode 8 / IS 1893 topographic amplification."""
    print_banner(
        sim_num=8,
        title="Hill-Slope DEM & Topographic Seismic Amplification",
        benchmark_ref="Eurocode 8 (EN 1998-5:2004 Cl. 4.1.4) / IS 1893:2016 Cl. 6.4.4",
        governing_code="Eurocode 8 / IS 1893 (Topographic Factor S_T)",
    )

    # 1. Print terrain parameters and code rules
    print_section("Hillside Terrain Geometry & Regulatory Rules")
    terrain_rows = [
        ["Hill Slope Angle (beta)", f"{MEAN_HILL_SLOPE_BETA_DEG:.1f} deg", "Extracted local slope angle"],
        ["Hill Height (H)", f"{HILL_HEIGHT_H_M:.1f} m", "Total ridge relief height"],
        ["Location from Crest (x)", f"{CREST_DISTANCE_AT_WALL_M:.1f} m", "Retaining wall at slope crest"],
        ["Shear Wave Velocity (V_s)", f"{SHEAR_WAVE_VELOCITY_VS_M_S:.0f} m/s", "Governs characteristic wavelength"],
        ["Baseline Flat-Ground PGA", f"{BASELINE_NOMINAL_PGA_G:.2f} g", "Nominal code zoning acceleration"],
        ["Eurocode 8 Rule", "15 deg < beta <= 30 deg", "Mandates S_T = 1.20 crest amplification"],
        ["IS 1893 Cl. 6.4.4 Rule", "beta > 15 deg", "Mandates +20% amplification in Zone IV/V"],
    ]
    print(format_table(["Terrain Feature", "Magnitude", "Regulatory Reference"], terrain_rows))

    # 2. Compute Topographic Amplification Factor S_T
    print_section("Computing Topographic Amplification Factor S_T")
    st_factor = compute_topographic_amplification_factor(
        slope_angle_deg=MEAN_HILL_SLOPE_BETA_DEG,
        crest_distance=CREST_DISTANCE_AT_WALL_M,
    )
    pga_amplified = BASELINE_NOMINAL_PGA_G * st_factor

    passed_st, rel_err_st, msg_st = check_benchmark(
        name="Topographic Factor (S_T)",
        calculated=st_factor,
        target=TARGET_TOPOGRAPHIC_FACTOR_ST,
        tolerance_pct=MAX_TOLERANCE_PCT,
        unit="-",
    )
    print(f"  {msg_st}")
    assert passed_st, "Topographic amplification factor S_T deviated from Eurocode 8 benchmark!"

    passed_pga, rel_err_pga, msg_pga = check_benchmark(
        name="Amplified Crest PGA",
        calculated=pga_amplified,
        target=TARGET_AMPLIFIED_PGA_G,
        tolerance_pct=MAX_TOLERANCE_PCT,
        unit="g",
    )
    print(f"  {msg_pga}")
    assert passed_pga, "Amplified peak ground acceleration deviated from target!"

    # 3. Spatial Attenuation Check
    print_section("Verifying Spatial Decay Away from Slope Crest")
    distances = [0.0, 5.0, 15.0, 30.0, 60.0]
    st_decay = []
    for d in distances:
        factor = compute_topographic_amplification_factor(
            slope_angle_deg=MEAN_HILL_SLOPE_BETA_DEG,
            crest_distance=d,
        )
        st_decay.append(factor)
        print(f"  Distance from Crest x = {d:4.1f} m -> Local Amplification S_T(x) = {factor:.3f}")

    # Verify monotonic decay away from crest
    is_decaying = all(s1 >= s2 for s1, s2 in zip(st_decay, st_decay[1:]))
    assert is_decaying, "Topographic amplification must attenuate monotonically away from crest!"
    assert math.isclose(st_decay[-1], 1.0, abs_tol=0.05), "At large distances, S_T must decay to 1.0!"

    # 4. Slope-Modified Down-Slope Passive Resistance Reduction
    print_section("Evaluating Down-Slope Passive Resistance Loss")
    kp_slope = compute_slope_modified_passive_resistance(
        kp_level=LEVEL_PASSIVE_KP,
        slope_angle_deg=MEAN_HILL_SLOPE_BETA_DEG,
        soil_friction_angle_deg=SOIL_FRICTION_ANGLE_DEG,
    )
    pct_kp_loss = (LEVEL_PASSIVE_KP - kp_slope) / LEVEL_PASSIVE_KP * 100.0

    passed_kp, rel_err_kp, msg_kp = check_benchmark(
        name="Sloping Passive Coeff K_p",
        calculated=kp_slope,
        target=TARGET_SLOPING_PASSIVE_KP,
        tolerance_pct=MAX_TOLERANCE_PCT,
        unit="-",
    )
    print(f"  {msg_kp}")
    assert passed_kp, "Down-slope passive resistance reduction deviated from benchmark!"

    # 5. Consolidated Hillside Stability Impact Matrix
    print_section("Hillside Topographic Hazard Impact Matrix")
    impact_rows = [
        ["Baseline Nominal Seismic PGA", f"{BASELINE_NOMINAL_PGA_G:.2f} g", "Flat ground zone value", "[NOMINAL]"],
        ["Topographic Factor (S_T)", f"{st_factor:.2f}", "Eurocode 8 Cl. 4.1.4", "[+20% ACCELERATION]"],
        ["Governing Crest Seismic Demand", f"{pga_amplified:.2f} g", "Applied to Mononobe-Okabe", "[AMPLIFIED]"],
        ["Level Ground Passive K_p", f"{LEVEL_PASSIVE_KP:.2f}", "Standard Rankine passive", "[NOMINAL]"],
        ["Down-Slope Passive K_p,slope", f"{kp_slope:.4f}", f"-{pct_kp_loss:.1f}% toe loss", "[SEVERELY DEGRADED]"],
    ]
    print(format_table(["Hazard Component", "Magnitude", "Regulatory Consequence", "Status"], impact_rows))

    print(f"\n  Engineering Summary:")
    print(f"  - Eurocode 8 / IS 1893 topographic factor S_T = {st_factor:.2f} scaled seismic shaking from {BASELINE_NOMINAL_PGA_G:.2f}g to {pga_amplified:.2f}g.")
    print(f"  - Downhill slope inclination beta = {MEAN_HILL_SLOPE_BETA_DEG:.1f} deg degraded passive toe resistance by {pct_kp_loss:.1f}%.")
    print("\n>>> SIMULATION 08 EXECUTION COMPLETED: ALL BENCHMARKS PASSED (<= 0.5% ERR) <<<\n")
    return True


if __name__ == "__main__":
    success = run_simulation()
    sys.exit(0 if success else 1)

