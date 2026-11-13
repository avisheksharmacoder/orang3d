"""
Test Suite Verification for orang3D Standalone Engineering Simulations (01 - 12).
Executes each standalone simulation script in an isolated subprocess to verify
end-to-end execution, benchmark convergence, and regulatory compliance.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIMULATIONS_DIR = PROJECT_ROOT / "simulations"

SIMULATION_SCRIPTS = [
    "01_static_cantilever_stability.py",
    "02_hydrodynamic_flooding_liquefaction.py",
    "03_dynamic_earthquake_newmark_sliding.py",
    "04_curved_shell_piles_struts_arching.py",
    "05_opensees_2d_bnwf_staged_pushover.py",
    "06_continuum_3d_nonlinear_fea.py",
    "07_architectural_surcharge_stepped_wall.py",
    "08_hill_slope_terrain_topographic_amplification.py",
    "09_multi_code_regulatory_audit.py",
    "10_pinn_surrogate_monte_carlo_fragility.py",
    "11_soil_lab_calibration_swcc_infiltration.py",
    "12_sizing_advisor_sensitivity_sweep.py",
]


@pytest.mark.parametrize("script_name", SIMULATION_SCRIPTS)
def test_simulation_script_execution(script_name: str) -> None:
    """Verifies that each simulation script executes cleanly and exits with code 0."""
    script_path = SIMULATIONS_DIR / script_name
    assert script_path.exists(), f"Simulation script not found: {script_path}"

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_ROOT / 'src'}:{PROJECT_ROOT}"
    env["QT_QPA_PLATFORM"] = "offscreen"

    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert proc.returncode == 0, (
        f"Simulation {script_name} failed with exit code {proc.returncode}!\n"
        f"STDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}\n"
    )
    assert "ALL BENCHMARKS PASSED" in proc.stdout, (
        f"Simulation {script_name} did not output confirmation banner!\n"
        f"STDOUT snippet:\n{proc.stdout[-500:]}"
    )

