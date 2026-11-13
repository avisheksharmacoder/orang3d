#!/usr/bin/env python3
"""
================================================================================
orang3D Master Simulation Test Suite Runner
================================================================================

Description:
    Sequentially executes all 12 rigorous, standalone geotechnical and structural
    earth-retaining wall simulations implemented in the orang3D validation suite.
    Each simulation is launched in an isolated subprocess with appropriate environment
    variables (PYTHONPATH, headless Qt), monitored for runtime, and evaluated against
    published benchmarks and regulatory code safety thresholds.

    At completion, a comprehensive executive scorecard is printed detailing:
      - Simulation Number & Engineering Title
      - Governing Standard / Benchmark Reference
      - Execution Duration (seconds)
      - Verification Status (PASS / FAIL)

Usage:
    PYTHONPATH=src .venv/bin/python3 simulations/run_all_simulations.py
================================================================================
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIMULATIONS_DIR = PROJECT_ROOT / "simulations"

SIMULATION_SCRIPTS: List[Tuple[str, str, str]] = [
    (
        "01_static_cantilever_stability.py",
        "Static Cantilever Stability & Coulomb Validation",
        "Das (2019) / Coulomb (1776) / IS 14458",
    ),
    (
        "02_hydrodynamic_flooding_liquefaction.py",
        "Hydrodynamic Flooding, Seepage & Liquefaction",
        "Westergaard (1933) / Seed-Idriss / IS 1893",
    ),
    (
        "03_dynamic_earthquake_newmark_sliding.py",
        "Dynamic Earthquake & Newmark Sliding Block",
        "Newmark (1965) / Jibson / Eurocode 8",
    ),
    (
        "04_curved_shell_piles_struts_arching.py",
        "Curved Shell & Piled Wall Arching Mechanics",
        "Handy (1985) / Terzaghi Arching / CIRIA C760",
    ),
    (
        "05_opensees_2d_bnwf_staged_pushover.py",
        "OpenSees 2D BNWF Staged Excavation & Pushover",
        "Reese & Matlock (1956) / API RP 2A / OpenSeesPy",
    ),
    (
        "06_continuum_3d_nonlinear_fea.py",
        "3D Continuum Nonlinear Soil-Structure FEA",
        "Kratos GeoMechanics / Mohr-Coulomb / Patch Test",
    ),
    (
        "07_architectural_surcharge_stepped_wall.py",
        "Multi-Tier Stepped Wall & Complex Surcharge",
        "Terzaghi-Spangler (1938) / Boussinesq / AASHTO",
    ),
    (
        "08_hill_slope_terrain_topographic_amplification.py",
        "Hill-Slope Topography & Passive Wedge Reduction",
        "Eurocode 8-5 S_T / Caquot-Kérisel / IS 1893",
    ),
    (
        "09_multi_code_regulatory_audit.py",
        "Multi-Code Regulatory Audit & Stress Check",
        "IS 456 / Eurocode 7 / AASHTO LRFD / ACI 318-19",
    ),
    (
        "10_pinn_surrogate_monte_carlo_fragility.py",
        "PINN Surrogate, Latin Hypercube & Fragility",
        "Raissi et al. (2019) / HAZUS MH / Cornell (1968)",
    ),
    (
        "11_soil_lab_calibration_swcc_infiltration.py",
        "Soil Lab Calibration, SWCC & Rainstorm Infiltration",
        "Darendeli (2001) / Van Genuchten / Green-Ampt",
    ),
    (
        "12_sizing_advisor_sensitivity_sweep.py",
        "Real-Time Sizing Advisor & Parametric Sensitivity",
        "Terzaghi (1996) / ACI 318-19 / IS 14458",
    ),
]


def format_summary_table(headers: List[str], rows: List[List[str]]) -> str:
    """Formats master scorecard table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            if idx < len(col_widths):
                col_widths[idx] = max(col_widths[idx], len(str(cell)))
            else:
                col_widths.append(len(str(cell)))

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_line = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, col_widths)) + " |"

    lines = [sep, header_line, sep]
    for row in rows:
        row_line = "| " + " | ".join(str(c).ljust(w) for c, w in zip(row, col_widths)) + " |"
        lines.append(row_line)
    lines.append(sep)
    return "\n".join(lines)


def main() -> None:
    width = 96
    print("=" * width)
    print(" orang3D MASTER SIMULATION VERIFICATION SUITE")
    print(" Automated Regression & Benchmark Validation for Geotechnical Retaining Structures")
    print("=" * width)
    print(f" Working Directory: {PROJECT_ROOT}")
    print(f" Executing {len(SIMULATION_SCRIPTS)} standalone simulation scripts...\n")

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_ROOT / 'src'}:{PROJECT_ROOT}"
    env["QT_QPA_PLATFORM"] = "offscreen"

    results: List[Dict[str, str]] = []
    total_start_time = time.perf_counter()
    all_passed = True

    for idx, (script_name, title, ref) in enumerate(SIMULATION_SCRIPTS, start=1):
        script_path = SIMULATIONS_DIR / script_name
        print(f"[{idx:02d}/{len(SIMULATION_SCRIPTS):02d}] Running {script_name}...")
        print(f"     Title:     {title}")
        print(f"     Benchmark: {ref}")

        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        t1 = time.perf_counter()
        elapsed = t1 - t0

        passed = proc.returncode == 0
        if not passed:
            all_passed = False
            status_str = "FAIL"
            print(f"     >>> FAILED with exit code {proc.returncode} in {elapsed:.2f}s")
            print("     STDERR Output snippet:")
            for line in proc.stderr.strip().splitlines()[-10:]:
                print(f"       {line}")
        else:
            status_str = "PASS"
            print(f"     >>> PASSED ({elapsed:.2f}s)")

        results.append({
            "id": f"{idx:02d}",
            "script": script_name,
            "title": title,
            "reference": ref,
            "duration": f"{elapsed:.2f}s",
            "status": f"[{status_str}]",
        })

    total_duration = time.perf_counter() - total_start_time

    print("\n" + "=" * width)
    print(" orang3D SIMULATION SUITE VERIFICATION SCORECARD")
    print("=" * width)

    scorecard_headers = ["#", "Script File", "Engineering Simulation Title", "Duration", "Status"]
    scorecard_rows = [
        [r["id"], r["script"], r["title"], r["duration"], r["status"]]
        for r in results
    ]
    print(format_summary_table(scorecard_headers, scorecard_rows))

    passed_count = sum(1 for r in results if r["status"] == "[PASS]")
    print(f"\nFinal Summary: {passed_count}/{len(SIMULATION_SCRIPTS)} simulations passed in {total_duration:.2f}s.")

    if not all_passed:
        print(">>> TEST SUITE REGRESSION FAILED <<<\n")
        sys.exit(1)
    else:
        print(">>> ALL 12 SIMULATIONS VERIFIED & PASSED CONVERGENCE BENCHMARKS <<<\n")
        sys.exit(0)


if __name__ == "__main__":
    main()

