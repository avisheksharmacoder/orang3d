"""
Phase 10.2(3): Standalone Packaging & CI/CD Gate Verification.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_pyinstaller_spec_bundles_v3_assets_and_solvers():
    spec_path = ROOT / "orang3d.spec"
    assert spec_path.is_file()
    src = spec_path.read_text(encoding="utf-8")
    ast.parse(src)

    # Required runtime binaries, data packages, and application icons
    for token in (
        "openseespy",
        "ezdxf",
        "pyvista",
        "vtkmodules",
        "orang3d",
        "resources",
        "orang3d.ico",
        "orang3d.png",
        "orang3d.physics.opensees_3d_solver",
        "orang3d.physics.bnwf_solver",
        "orang3d.physics.code_auditor",
        "orang3d.physics.arch_wall_solver",
        "orang3d.io.deck_export",
        "orang3d.io.bim_export",
        "orang3d.io.dxf_export",
        "orang3d.gui.panels.arch_wall_panel",
        "orang3d.gui.panels.comparison_tab",
        "orang3d.gui.panels.uq_fragility_tab",
    ):
        assert token in src, f"Missing {token} in orang3d.spec"

    assert (ROOT / "resources" / "icons" / "orang3d.png").is_file()
    assert (ROOT / "resources" / "icons" / "orang3d.ico").is_file()
    assert (ROOT / "resources" / "orang3d.desktop").is_file()


def test_github_ci_workflow_cross_platform_and_coverage_gate():
    ci_path = ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_path.is_file()
    ci_text = ci_path.read_text(encoding="utf-8")

    assert "ubuntu-latest" in ci_text
    assert "windows-latest" in ci_text
    assert "--cov=src/orang3d" in ci_text
    assert "--cov-fail-under=90" in ci_text
    assert "scripts/build_executable.py" in ci_text

