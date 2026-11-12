"""
Tests for Phase 5: Student Pedagogy, Benchmark Presets, Equation Inspector,
Multi-Solver Comparison Overlay, and Parametric Sensitivity Sweeps.
"""

from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from orang3d.models import (
    BenchmarkPreset,
    CurvedShellGeometry,
    RetainingWallGeometry,
    SeismicParams,
    SoilProperties,
    WallSystemMode,
    get_benchmark_presets,
    get_preset,
)
from orang3d.physics.bnwf_solver import BNWFSimulationResult
from orang3d.physics.opensees_3d_solver import ContinuumFEAResult
from orang3d.physics.shell_arching import compute_shell_arching_partition
from orang3d.physics.stability import evaluate_wall_stability
from orang3d.signals.synthetic import (
    compute_newmark_sliding_displacement,
    compute_yield_acceleration_ky,
    generate_ricker_wavelet,
)
from orang3d.gui.dialogs.sensitivity_dialog import (
    SWEEP_X_VARS,
    SWEEP_Y_METRICS,
    SensitivitySweepDialog,
    run_sensitivity_sweep,
)
from orang3d.gui.main_window import MainWindow
from orang3d.gui.panels.comparison_tab import (
    TheoryComparisonTab,
    compute_theory_vs_solver_comparison,
)
from orang3d.gui.panels.equation_inspector_tab import EquationInspectorTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _rel_err_pct(actual: float, target: float) -> float:
    return abs(actual - target) / max(1e-6, abs(target)) * 100.0


def test_benchmark_presets_catalog_and_lookup():
    presets = get_benchmark_presets()
    ids = [p.preset_id for p in presets]
    expected_ids = {
        "das_ex_13_7",
        "bowles_sec_12_7",
        "kramer_1996_newmark",
        "is_14458_zone_v_shell",
        "corner_effect_3d_benchmark",
    }
    assert set(ids) == expected_ids
    for pid in expected_ids:
        p = get_preset(pid)
        assert isinstance(p, BenchmarkPreset)
        assert len(p.reference) > 10
        assert len(p.pedagogical_focus) > 10

    with pytest.raises(KeyError):
        get_preset("nonexistent_benchmark")


@pytest.mark.parametrize(
    "preset_id",
    [
        "das_ex_13_7",
        "bowles_sec_12_7",
        "kramer_1996_newmark",
        "is_14458_zone_v_shell",
        "corner_effect_3d_benchmark",
    ],
)
def test_presets_match_published_targets_within_half_percent(preset_id: str):
    preset = get_preset(preset_id)
    res = evaluate_wall_stability(preset.geom, preset.soil, preset.seismic)
    arching = compute_shell_arching_partition(preset.shell_geom, preset.soil)

    # Stability & M-O targets
    for attr in ("k_a_static", "k_ae", "total_thrust", "fs_sliding", "fs_overturning"):
        if attr in preset.targets:
            assert _rel_err_pct(float(getattr(res, attr)), preset.targets[attr]) < 0.5

    # Shell arching targets
    for attr in (
        "arching_ratio",
        "total_free_field_thrust",
        "total_shell_thrust",
        "total_pier_thrust",
    ):
        if attr in preset.targets:
            assert _rel_err_pct(float(getattr(arching, attr)), preset.targets[attr]) < 0.5

    # Newmark permanent slip targets
    if "yield_acceleration_ky" in preset.targets or "newmark_slip_cm" in preset.targets:
        ky = compute_yield_acceleration_ky(preset.geom, preset.soil)
        if "yield_acceleration_ky" in preset.targets:
            assert _rel_err_pct(ky, preset.targets["yield_acceleration_ky"]) < 0.5
        if "newmark_slip_cm" in preset.targets:
            wf = preset.waveform_config
            t_arr, a_arr = generate_ricker_wavelet(
                pga_g=float(wf.get("pga_g", 0.45)),
                central_freq_hz=float(wf.get("freq_hz", 2.5)),
                duration_sec=float(wf.get("duration_sec", 10.0)),
            )
            _, slip_cm = compute_newmark_sliding_displacement(t_arr, a_arr, ky)
            assert _rel_err_pct(slip_cm, preset.targets["newmark_slip_cm"]) < 0.5


def test_equation_inspector_tab_renders_substituted_formulas(qapp):
    tab = EquationInspectorTab()
    try:
        preset = get_preset("das_ex_13_7")
        res = evaluate_wall_stability(preset.geom, preset.soil, preset.seismic)
        tab.update_equations(
            geom=preset.geom,
            soil=preset.soil,
            seismic=preset.seismic,
            results=res,
            shell_geom=preset.shell_geom,
            wall_mode=preset.wall_mode,
            preset_note=preset.title,
        )
        html = tab.current_html()
        assert "0.407" in html  # M-O K_ae
        assert "0.297" in html  # Static K_a
        assert "131.88" in html  # Combined thrust P_total
        assert "Meyerhof" in html
        assert "Das (9th Ed.)" in html
        assert "1.135" in html  # FS_sliding
        assert "2.747" in html  # FS_overturning

        # Update shaking and verify live update changes numbers
        high_seismic = SeismicParams(horizontal_pga=0.35, vertical_pga=0.10, water_table_depth=12.0)
        res_hi = evaluate_wall_stability(preset.geom, preset.soil, high_seismic)
        tab.update_equations(
            geom=preset.geom,
            soil=preset.soil,
            seismic=high_seismic,
            results=res_hi,
            shell_geom=preset.shell_geom,
        )
        html_hi = tab.current_html()
        assert f"{res_hi.k_ae:.4f}" in html_hi
        assert html_hi != html
    finally:
        tab.close()
        tab.deleteLater()
        qapp.processEvents()


def _make_mock_bnwf_and_fea(geom: RetainingWallGeometry):
    H = geom.total_height
    L = geom.wall_length
    elevs = np.linspace(0.0, geom.stem_height, 6)
    m_profile = {float(y): np.array([max(0.0, 180.0 * (1.0 - y / geom.stem_height) ** 2)]) for y in elevs}
    bnwf = BNWFSimulationResult(
        time_history=np.array([0.0, 0.1]),
        crest_displacement=np.array([0.0, 0.015]),
        pile_head_displacement=np.array([0.0, 0.004]),
        max_bending_moment=np.array([0.0, 185.0]),
        bending_moment_profile=m_profile,
        max_crest_disp_cm=1.5,
        max_moment_knm=185.0,
    )

    # Build 3D backface grid (4 heights x 3 longitudinal locations)
    ys = np.linspace(0.5, H - 0.5, 4)
    zs = np.array([0.1 * L, 0.5 * L, 0.9 * L])
    coords = []
    stresses = []
    for y in ys:
        depth = H - y
        for z in zs:
            coords.append([geom.base_width, y, z])
            factor = 1.25 if (z <= 0.2 * L or z >= 0.8 * L) else 0.95
            stresses.append(8.5 * depth * factor)
    bf_coords = np.asarray(coords, dtype=np.float64)
    bf_stress = np.vstack([0.5 * np.asarray(stresses), np.asarray(stresses)])
    fea = ContinuumFEAResult(
        time=np.array([0.0, 0.5]),
        displacement_field=np.zeros((2, 4, 3)),
        backface_coords=bf_coords,
        backface_normal_stress_kpa=bf_stress,
        backface_shear_stress_kpa=np.zeros_like(bf_stress),
        total_thrust_kn_m=np.array([95.0, 198.0]),
        total_thrust_3d_kn=np.array([95.0 * L, 198.0 * L]),
        thrust_elevation_m=np.array([0.35 * H, 0.43 * H]),
        corner_concentration_ratio=1.25 / 0.95,
        octahedral_shear_strain=np.zeros((2, 2)),
        excess_pore_pressure_ratio_ru=np.zeros((2, 4)),
        foundation_bearing_stress_kpa=np.zeros((2, 2)),
        max_crest_disp_cm=1.8,
    )
    return bnwf, fea


def test_theory_comparison_tab_overlays_and_metrics(qapp):
    tab = TheoryComparisonTab()
    try:
        preset = get_preset("corner_effect_3d_benchmark")
        res = evaluate_wall_stability(preset.geom, preset.soil, preset.seismic)
        bnwf, fea = _make_mock_bnwf_and_fea(preset.geom)

        tab.set_bnwf_result(bnwf)
        tab.set_fea_result(fea)
        metrics = tab.update_comparison(
            geom=preset.geom,
            soil=preset.soil,
            seismic=preset.seismic,
            results=res,
            shell_geom=preset.shell_geom,
        )

        # Dynamic M-O must exceed static Rankine under 0.30g shaking
        assert np.all(np.isfinite(metrics.rankine_pressure_kpa))
        assert np.all(np.isfinite(metrics.mo_dynamic_pressure_kpa))
        assert float(np.trapezoid(metrics.mo_dynamic_pressure_kpa, metrics.depths_m)) > float(
            np.trapezoid(metrics.rankine_pressure_kpa, metrics.depths_m)
        )

        # Multi-solver fields populated accurately
        assert metrics.fea_peak_thrust_kn_m == pytest.approx(198.0)
        assert metrics.fea_corner_ratio == pytest.approx(1.25 / 0.95, rel=1e-3)
        assert len(metrics.fea_mid_depths_m) == 4
        assert len(metrics.fea_corner_depths_m) == 4
        assert np.all(metrics.fea_corner_pressure_kpa > metrics.fea_mid_pressure_kpa)
        assert len(metrics.bnwf_elevations_m) == 6
        assert metrics.bnwf_max_moment_knm == pytest.approx(185.0)
        assert metrics.bnwf_moment_diff_pct is not None
        assert metrics.fea_thrust_diff_pct is not None
        assert "3D FEA Peak Thrust" in tab.lbl_metrics.text()
        assert "2D BNWF Max Moment" in tab.lbl_metrics.text()
    finally:
        tab.close()
        tab.deleteLater()
        qapp.processEvents()


def test_sensitivity_sweeps_performance_and_monotonicity(qapp):
    geom = RetainingWallGeometry()
    soil = SoilProperties()
    seismic = SeismicParams(horizontal_pga=0.20, vertical_pga=0.05, water_table_depth=12.0)
    shell = CurvedShellGeometry()

    # Check all supported X/Y combinations remain finite and fast (< 50 ms each)
    for x_var in SWEEP_X_VARS:
        y_metric = "arching_ratio" if x_var == "L_bay_over_H" else "fs_sliding"
        sw = run_sensitivity_sweep(x_var, y_metric, geom, soil, seismic, shell_geom=shell, n_points=25)
        assert len(sw.x_values) == 25
        assert len(sw.y_values) == 25
        assert np.all(np.isfinite(sw.y_values))
        assert sw.elapsed_ms < 50.0

    # Verify monotonic physics trends
    sw_kae = run_sensitivity_sweep("k_h", "k_ae", geom, soil, seismic, n_points=20)
    assert np.all(np.diff(sw_kae.y_values) >= -1e-6)
    assert sw_kae.y_values[-1] > sw_kae.y_values[0]

    sw_phi = run_sensitivity_sweep("phi", "fs_sliding", geom, soil, seismic, n_points=20)
    assert np.all(np.diff(sw_phi.y_values) >= -1e-6)
    assert sw_phi.y_values[-1] > sw_phi.y_values[0]

    sw_ru = run_sensitivity_sweep("r_u", "fs_sliding", geom, soil, seismic, n_points=20)
    assert np.all(np.diff(sw_ru.y_values) <= 1e-6)
    assert sw_ru.y_values[-1] < sw_ru.y_values[0]

    sw_newmark = run_sensitivity_sweep("k_h", "u_newmark", geom, soil, seismic, n_points=20)
    assert np.all(np.diff(sw_newmark.y_values) >= -1e-6)
    assert sw_newmark.elapsed_ms < 50.0

    # Interactive dialog sanity test
    dlg = SensitivitySweepDialog(geom, soil, seismic, shell_geom=shell)
    try:
        assert dlg.last_result() is not None
        idx_ru = dlg.combo_x.findData("r_u")
        idx_u = dlg.combo_y.findData("u_newmark")
        dlg.combo_x.setCurrentIndex(idx_ru)
        dlg.combo_y.setCurrentIndex(idx_u)
        res_dlg = dlg.last_result()
        assert res_dlg is not None
        assert res_dlg.x_var == "r_u"
        assert res_dlg.y_metric == "u_newmark"
        assert res_dlg.threshold_value == 5.0
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.processEvents()


def test_main_window_preset_loading_and_phase5_tabs(qapp):
    window = MainWindow()
    try:
        assert len(window.preset_actions) == 5
        assert window.act_sensitivity_sweep is not None
        assert window.bottom_tabs.count() == 6

        # Load curved-shell preset & verify full UI/model sync
        preset_shell = window.load_preset("is_14458_zone_v_shell")
        assert window.wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL
        assert window.shell_geom.panel_height == pytest.approx(preset_shell.shell_geom.panel_height)
        assert window.seismic.backfill_slope == pytest.approx(10.0)
        assert "IS 14458" in window.equation_inspector_tab.current_html()

        # Load Das benchmark & verify exact analytical match in MainWindow
        window.load_preset("das_ex_13_7")
        assert window.wall_mode == WallSystemMode.CANTILEVER
        assert _rel_err_pct(window.results.k_ae, 0.4070) < 0.5
        assert _rel_err_pct(window.results.fs_sliding, 1.135) < 0.5
        assert window.comparison_tab.last_metrics() is not None
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()
