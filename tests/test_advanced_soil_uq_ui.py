"""
Phase 4 Verification & Offscreen Qt Tests:
  1. Cyclic & Unsaturated Soil Sub-Panel (`AdvancedSoilPanel`) live G/G_max, D(gamma), SWCC,
     and Green-Ampt rainfall infiltration depth-profile plots.
  2. Lab Data Calibration Wizard (`CalibrationWizardDialog`) CSV import & nonlinear fit
     (R^2 >= 0.95) for Resonant Column, SWCC, and Direct Shear pushing calibrated parameters
     into `SoilProperties`.
  3. Uncertainty Quantification & Seismic Fragility Tab (`UQFragilityTab` + `UQSimulationWorker`)
     with Normal/Lognormal/Uniform distributions over phi, c, gamma, k_h, R producing
     deterministic seeded Cornell beta, Pf, FS histogram, and monotonic HAZUS fragility curves.
  4. MainWindow integration of soil sub-panel, Tools calibration action, and UQ dashboard tab.
"""

from __future__ import annotations

import csv
from pathlib import Path
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from orang3d.models.wall_params import RetainingWallGeometry, SoilProperties, SeismicParams
from orang3d.physics.cyclic_soil import compute_hysteretic_damping, compute_modulus_reduction
from orang3d.physics.unsaturated_soil import VanGenuchtenParams
from orang3d.physics.uncertainty import DamageState
from orang3d.gui.panels.advanced_soil_panel import AdvancedSoilPanel
from orang3d.gui.panels.uq_fragility_tab import UQFragilityTab
from orang3d.gui.dialogs.calibration_wizard import CalibrationWizardDialog
from orang3d.gui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ==============================================================================
# 1. Cyclic & Unsaturated Soil Sub-Panel
# ==============================================================================
def test_advanced_soil_panel_cyclic_and_swcc_updates(qapp):
    panel = AdvancedSoilPanel()
    try:
        cyclic_events = []
        unsat_events = []
        panel.cyclicParamsChanged.connect(lambda p: cyclic_events.append(p))
        panel.unsaturatedParamsChanged.connect(lambda u, r: unsat_events.append((u, r)))

        panel.spin_gmax.setValue(110000.0)
        panel.spin_gamma_r.setValue(0.08)
        panel.spin_n_cycles.setValue(30)
        assert len(cyclic_events) >= 1
        assert abs(panel.cyclic_params.max_shear_modulus_gmax_kpa - 110000.0) < 1e-3

        x_g, y_g = panel.curve_g_ratio.getData()
        assert x_g is not None and len(y_g) > 10
        assert 0.0 <= float(np.min(y_g)) <= float(np.max(y_g)) <= 1.0

        panel.spin_rain_int.setValue(40.0)
        panel.spin_rain_dur.setValue(24.0)
        assert len(unsat_events) >= 1
        assert panel.last_infiltration is not None
        assert panel.last_infiltration.wetting_front_depth_m > 0.0
        assert panel.last_infiltration.percent_cohesion_loss > 0.0

        x_sw, y_sw = panel.curve_swcc.getData()
        assert x_sw is not None and len(y_sw) > 10
        assert panel.curve_psi_post.getData()[0] is not None
        assert panel.curve_tau_post.getData()[0] is not None
    finally:
        panel.close()


# ==============================================================================
# 2. Lab Calibration Wizard CSV Fits (R^2 >= 0.95) -> SoilProperties
# ==============================================================================
def test_lab_calibration_wizard_csv_fits_and_pushes_to_soil(qapp, tmp_path: Path):
    soil = SoilProperties(friction_angle=30.0, cohesion=2.0, wall_friction_angle=20.0)
    wizard = CalibrationWizardDialog(soil=soil)
    try:
        # 2a. Resonant Column / Cyclic Triaxial CSV
        rc_csv = tmp_path / "resonant_column.csv"
        gammas = np.logspace(-5, -1.3, 9)
        with open(rc_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["shear_strain", "g_over_gmax", "damping_ratio"])
            for g in gammas:
                writer.writerow([
                    f"{g:.6e}",
                    f"{compute_modulus_reduction(g, 0.00045, 0.90):.6f}",
                    f"{compute_hysteretic_damping(g, 0.00045, 0.90, 0.02, 0.25):.6f}",
                ])
        fit_rc = wizard.load_csv(str(rc_csv), test_type=CalibrationWizardDialog.TEST_RESONANT)
        assert fit_rc.r_squared >= 0.95
        assert fit_rc.is_statistically_significant is True
        assert abs(wizard.last_fitted_payload["gamma_r"] - 0.00045) < 5e-5

        # 2b. Pressure Plate / SWCC CSV
        swcc_csv = tmp_path / "swcc.csv"
        vg_true = VanGenuchtenParams(alpha_kpa_inv=0.06, n_param=1.75)
        suctions = [0.5, 2.0, 5.0, 12.0, 25.0, 60.0, 150.0, 400.0]
        with open(swcc_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["suction_kpa", "degree_of_saturation"])
            for psi in suctions:
                writer.writerow([f"{psi:.2f}", f"{vg_true.degree_of_saturation(psi):.6f}"])
        fit_swcc = wizard.load_csv(str(swcc_csv), test_type=CalibrationWizardDialog.TEST_SWCC)
        assert fit_swcc.r_squared >= 0.95
        assert abs(wizard.last_swcc_obj.alpha_kpa_inv - 0.06) < 0.01

        # 2c. Direct Shear Mohr-Coulomb CSV -> updates SoilProperties
        ds_csv = tmp_path / "direct_shear.csv"
        c_true, phi_true = 18.0, 36.5
        sigmas = [30.0, 60.0, 120.0, 180.0, 250.0]
        with open(ds_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["sigma_n_kpa", "tau_f_kpa"])
            for sig in sigmas:
                tau = c_true + sig * np.tan(np.radians(phi_true))
                writer.writerow([f"{sig:.2f}", f"{tau:.4f}"])
        fit_ds = wizard.load_csv(str(ds_csv), test_type=CalibrationWizardDialog.TEST_DIRECT_SHEAR)
        assert fit_ds.r_squared >= 0.95

        applied_events = []
        wizard.calibrationApplied.connect(lambda tt, pl: applied_events.append((tt, pl)))
        wizard.apply_calibration()

        assert len(applied_events) == 1
        assert abs(soil.cohesion - c_true) < 0.2
        assert abs(soil.friction_angle - phi_true) < 0.2
    finally:
        wizard.close()


# ==============================================================================
# 3. UQ & Seismic Fragility Tab (Deterministic Seeded Worker + Monotonic Curves)
# ==============================================================================
def _run_uq_sync(tab: UQFragilityTab, qapp) -> None:
    worker = tab.run_uq_analysis()
    assert worker is not None
    assert worker.wait(10000)
    qapp.processEvents()


def test_uq_fragility_deterministic_seeded_and_monotonic(qapp):
    tab_a = UQFragilityTab()
    tab_b = UQFragilityTab()
    try:
        # Configure Normal, Lognormal, and Uniform distributions across 5 variables
        tab_a._row_widgets["phi"][0].setCurrentText("normal")
        tab_a._row_widgets["c"][0].setCurrentText("uniform")
        tab_a._row_widgets["c"][1].setValue(2.0)
        tab_a._row_widgets["c"][2].setValue(12.0)
        tab_a._row_widgets["k_h"][0].setCurrentText("lognormal")

        tab_b._row_widgets["phi"][0].setCurrentText("normal")
        tab_b._row_widgets["c"][0].setCurrentText("uniform")
        tab_b._row_widgets["c"][1].setValue(2.0)
        tab_b._row_widgets["c"][2].setValue(12.0)
        tab_b._row_widgets["k_h"][0].setCurrentText("lognormal")

        for tab in (tab_a, tab_b):
            tab.spin_samples.setValue(250)
            tab.spin_seed.setValue(42)
            idx_ana = tab.combo_engine.findData("analytical")
            tab.combo_engine.setCurrentIndex(idx_ana)

        _run_uq_sync(tab_a, qapp)
        _run_uq_sync(tab_b, qapp)

        rel_a = tab_a.last_reliability
        rel_b = tab_b.last_reliability
        assert rel_a is not None and rel_b is not None
        assert rel_a.num_samples == 250
        assert rel_a.mean_fs > 0.0
        assert 0.0 <= rel_a.probability_of_failure <= 1.0
        assert np.isclose(rel_a.reliability_index_beta, rel_b.reliability_index_beta, atol=1e-12)
        assert np.isclose(rel_a.probability_of_failure, rel_b.probability_of_failure, atol=1e-12)
        assert np.allclose(rel_a.fs_samples, rel_b.fs_samples)

        # Verify monotonic non-decreasing & hierarchical HAZUS fragility curves
        frags = tab_a.last_fragility
        assert frags is not None
        for ds in (DamageState.SLIGHT, DamageState.MODERATE, DamageState.EXTENSIVE, DamageState.COLLAPSE):
            probs = frags[ds].exceedance_probabilities
            assert np.all(np.diff(probs) >= -1e-12)
            assert np.all((probs >= 0.0) & (probs <= 1.0))

        assert np.all(frags[DamageState.SLIGHT].exceedance_probabilities >= frags[DamageState.MODERATE].exceedance_probabilities - 1e-12)
        assert np.all(frags[DamageState.MODERATE].exceedance_probabilities >= frags[DamageState.EXTENSIVE].exceedance_probabilities - 1e-12)
        assert np.all(frags[DamageState.EXTENSIVE].exceedance_probabilities >= frags[DamageState.COLLAPSE].exceedance_probabilities - 1e-12)

        # Verify PINN Surrogate UQ worker mode as well
        idx_pinn = tab_a.combo_engine.findData("pinn")
        tab_a.combo_engine.setCurrentIndex(idx_pinn)
        tab_a.spin_samples.setValue(200)
        _run_uq_sync(tab_a, qapp)
        assert tab_a.last_reliability.num_samples == 200
        assert tab_a.last_reliability.mean_fs > 0.0
    finally:
        tab_a.close()
        tab_b.close()


# ==============================================================================
# 4. MainWindow Phase 4 Integration
# ==============================================================================
def test_main_window_phase4_integration(qapp, tmp_path: Path):
    win = MainWindow()
    try:
        assert hasattr(win, "panel_adv_soil")
        assert hasattr(win, "uq_fragility_tab")
        assert hasattr(win, "act_lab_calibration")
        assert win.bottom_tabs.indexOf(win.uq_fragility_tab) == 3

        # Simulate applying Direct Shear calibration into MainWindow
        ds_csv = tmp_path / "mw_shear.csv"
        with open(ds_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["sigma_n", "tau_f"])
            for s in (40.0, 80.0, 160.0):
                writer.writerow([s, 15.0 + s * np.tan(np.radians(38.0))])

        dlg = CalibrationWizardDialog(soil=win.soil, parent=win)
        dlg.calibrationApplied.connect(win._on_calibration_applied)
        fit = dlg.load_csv(str(ds_csv), test_type=CalibrationWizardDialog.TEST_DIRECT_SHEAR)
        assert fit.r_squared >= 0.95
        dlg.apply_calibration()
        dlg.close()

        assert abs(win.soil.friction_angle - 38.0) < 0.2
        assert abs(win.panel_soil.spin_phi.value() - 38.0) < 0.2
    finally:
        win.close()

