"""
Cyclic & Unsaturated Soil Mechanics Sidebar Sub-Panel (v3 Phase 4).

Exposes:
  1. Non-linear cyclic soil parameters (CyclicSoilParameters) and N-cycle degradation
     scaling with live PyQtGraph G/G_max(gamma) and D(gamma) curves.
  2. Unsaturated soil Van Genuchten SWCC parameters (theta_s, theta_r, alpha, n),
     phi^b suction friction angle, antecedent suction, and monsoon rainfall infiltration
     (intensity, duration), plotting SWCC and depth-dependent matric suction psi(z, t)
     + suction-augmented apparent cohesion / shear strength profiles.
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...config import THEME
from ...models.wall_params import RetainingWallGeometry, SoilProperties
from ...physics.cyclic_soil import (
    CyclicSoilParameters,
    generate_cyclic_degradation_curves,
)
from ...physics.unsaturated_soil import (
    RainfallInfiltrationResult,
    UnsaturatedSoilParameters,
    VanGenuchtenParams,
    simulate_rainfall_infiltration,
)


class AdvancedSoilPanel(QWidget):
    """
    Interactive sidebar widget for cyclic modulus/damping characterization and
    unsaturated SWCC / rainfall infiltration modeling.
    """

    cyclicParamsChanged = Signal(CyclicSoilParameters)
    unsaturatedParamsChanged = Signal(UnsaturatedSoilParameters, object)
    openCalibrationWizardRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.geom = RetainingWallGeometry()
        self.soil = SoilProperties()
        self.cyclic_params = CyclicSoilParameters(
            friction_angle_deg=self.soil.friction_angle,
            cohesion_kpa=self.soil.cohesion,
        )
        self.swcc_params = VanGenuchtenParams()
        self.unsat_params = UnsaturatedSoilParameters(
            effective_cohesion=max(2.0, self.soil.cohesion),
            effective_friction_angle=self.soil.friction_angle,
            swcc=self.swcc_params,
        )
        self.last_infiltration: Optional[RainfallInfiltrationResult] = None

        pg.setConfigOption("background", THEME["surface_dark"])
        pg.setConfigOption("foreground", THEME["text_primary"])
        pg.setConfigOptions(antialias=True)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.btn_open_wizard = QPushButton("🧪 Open Lab Calibration Wizard (CSV)...")
        self.btn_open_wizard.setToolTip(
            "Import laboratory CSV data (Resonant Column, Pressure Plate SWCC, Direct Shear)"
        )
        self.btn_open_wizard.clicked.connect(self.openCalibrationWizardRequested.emit)
        root.addWidget(self.btn_open_wizard)

        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(self._build_cyclic_tab(), "Cyclic G/Gmax & D")
        self.sub_tabs.addTab(self._build_unsat_tab(), "SWCC & Rainfall")
        root.addWidget(self.sub_tabs)

        self._recompute_cyclic()
        self._recompute_unsaturated()

    def _make_dspin(
        self,
        form: QFormLayout,
        label: str,
        vmin: float,
        vmax: float,
        val: float,
        step: float,
        decimals: int,
        slot,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(vmin, vmax)
        spin.setValue(val)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.valueChanged.connect(slot)
        form.addRow(label, spin)
        return spin

    def _build_cyclic_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        grp = QGroupBox("Cyclic Constitutive Parameters")
        form = QFormLayout(grp)
        self.spin_gmax = self._make_dspin(
            form, "G_max (kPa):", 5000.0, 500000.0, self.cyclic_params.max_shear_modulus_gmax_kpa,
            5000.0, 0, self._recompute_cyclic
        )
        self.spin_gamma_r = self._make_dspin(
            form, "Ref. Strain gamma_r (%):", 0.005, 0.50,
            self.cyclic_params.reference_shear_strain * 100.0, 0.01, 4, self._recompute_cyclic
        )
        self.spin_a = self._make_dspin(
            form, "Curvature Param a:", 0.50, 2.00, self.cyclic_params.curvature_param_a,
            0.05, 2, self._recompute_cyclic
        )
        self.spin_dmin = self._make_dspin(
            form, "Small-Strain D_min (%):", 0.5, 10.0,
            self.cyclic_params.min_damping_ratio * 100.0, 0.5, 2, self._recompute_cyclic
        )
        self.spin_dmax = self._make_dspin(
            form, "Max Damping D_max (%):", 10.0, 40.0,
            self.cyclic_params.max_damping_ratio * 100.0, 1.0, 1, self._recompute_cyclic
        )
        self.spin_n_cycles = QSpinBox()
        self.spin_n_cycles.setRange(1, 200)
        self.spin_n_cycles.setValue(15)
        self.spin_n_cycles.valueChanged.connect(self._recompute_cyclic)
        form.addRow("Loading Cycles N:", self.spin_n_cycles)
        layout.addWidget(grp)

        self.lbl_cyclic_summary = QLabel("Vs: -- m/s | N-Cycle Factor: --")
        self.lbl_cyclic_summary.setStyleSheet(f"color: {THEME['accent_blue']}; font-size: 11px;")
        self.lbl_cyclic_summary.setWordWrap(True)
        layout.addWidget(self.lbl_cyclic_summary)

        self.cyclic_plot = pg.PlotWidget(title="G/Gmax & Damping D(gamma)")
        self.cyclic_plot.setMinimumHeight(180)
        self.cyclic_plot.setLabel("left", "Normalized Ratio")
        self.cyclic_plot.setLabel("bottom", "Log10 Shear Strain gamma (%)")
        self.cyclic_plot.showGrid(x=True, y=True, alpha=0.25)
        self.cyclic_plot.addLegend(offset=(8, 8))
        self.curve_g_ratio = self.cyclic_plot.plot(
            pen=pg.mkPen(color=THEME["accent_blue"], width=2.0), name="G/Gmax"
        )
        self.curve_g_cycled = self.cyclic_plot.plot(
            pen=pg.mkPen(color=THEME["accent_yellow"], width=1.6, style=pg.QtCore.Qt.DashLine),
            name="G(N)/Gmax",
        )
        self.curve_damping = self.cyclic_plot.plot(
            pen=pg.mkPen(color=THEME["accent_orange"], width=2.0), name="D(gamma)"
        )
        layout.addWidget(self.cyclic_plot)
        return tab

    def _build_unsat_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        grp_vg = QGroupBox("Van Genuchten SWCC & Suction")
        form_vg = QFormLayout(grp_vg)
        self.spin_theta_sat = self._make_dspin(
            form_vg, "Sat. theta_s:", 0.25, 0.75, self.swcc_params.theta_sat,
            0.02, 3, self._recompute_unsaturated
        )
        self.spin_theta_res = self._make_dspin(
            form_vg, "Res. theta_r:", 0.01, 0.24, self.swcc_params.theta_res,
            0.01, 3, self._recompute_unsaturated
        )
        self.spin_alpha = self._make_dspin(
            form_vg, "SWCC alpha (1/kPa):", 0.002, 0.500, self.swcc_params.alpha_kpa_inv,
            0.005, 4, self._recompute_unsaturated
        )
        self.spin_n_vg = self._make_dspin(
            form_vg, "SWCC n (> 1):", 1.05, 4.50, self.swcc_params.n_param,
            0.05, 2, self._recompute_unsaturated
        )
        self.spin_psi0 = self._make_dspin(
            form_vg, "Initial Suction psi_0 (kPa):", 0.0, 300.0, self.unsat_params.initial_matric_suction,
            5.0, 1, self._recompute_unsaturated
        )
        self.spin_rain_int = self._make_dspin(
            form_vg, "Rainfall Intensity (mm/hr):", 0.0, 150.0, 25.0,
            5.0, 1, self._recompute_unsaturated
        )
        self.spin_rain_dur = self._make_dspin(
            form_vg, "Storm Duration (hr):", 0.5, 120.0, 24.0,
            2.0, 1, self._recompute_unsaturated
        )
        layout.addWidget(grp_vg)

        self.lbl_unsat_summary = QLabel("Wetting Front z_w: -- m | c_app drop: --%")
        self.lbl_unsat_summary.setStyleSheet(f"color: {THEME['accent_green']}; font-size: 11px;")
        self.lbl_unsat_summary.setWordWrap(True)
        layout.addWidget(self.lbl_unsat_summary)

        self.swcc_plot = pg.PlotWidget(title="SWCC & Matric Suction Profile")
        self.swcc_plot.setMinimumHeight(140)
        self.swcc_plot.setLabel("left", "Saturation S_r")
        self.swcc_plot.setLabel("bottom", "Log10 Suction psi (kPa)")
        self.swcc_plot.showGrid(x=True, y=True, alpha=0.25)
        self.curve_swcc = self.swcc_plot.plot(
            pen=pg.mkPen(color=THEME["accent_green"], width=2.0), name="SWCC S_r(psi)"
        )
        layout.addWidget(self.swcc_plot)

        self.suction_profile_plot = pg.PlotWidget(title="Depth Profile: Suction psi(z) & Tau_f(z)")
        self.suction_profile_plot.setMinimumHeight(140)
        self.suction_profile_plot.setLabel("left", "Depth z", units="m")
        self.suction_profile_plot.setLabel("bottom", "Suction psi / Shear Tau_f", units="kPa")
        self.suction_profile_plot.getViewBox().invertY(True)
        self.suction_profile_plot.showGrid(x=True, y=True, alpha=0.25)
        self.suction_profile_plot.addLegend(offset=(8, 8))
        self.curve_psi_post = self.suction_profile_plot.plot(
            pen=pg.mkPen(color=THEME["accent_blue"], width=2.0), name="psi(z, t)"
        )
        self.curve_tau_post = self.suction_profile_plot.plot(
            pen=pg.mkPen(color=THEME["accent_orange"], width=2.0), name="tau_f(z)"
        )
        layout.addWidget(self.suction_profile_plot)
        return tab

    def _recompute_cyclic(self):
        dmin = min(0.095, self.spin_dmin.value() / 100.0)
        dmax = max(dmin + 0.02, self.spin_dmax.value() / 100.0)
        params = CyclicSoilParameters(
            max_shear_modulus_gmax_kpa=self.spin_gmax.value(),
            reference_shear_strain=self.spin_gamma_r.value() / 100.0,
            curvature_param_a=self.spin_a.value(),
            min_damping_ratio=dmin,
            max_damping_ratio=dmax,
            friction_angle_deg=self.soil.friction_angle,
            cohesion_kpa=self.soil.cohesion,
            poissons_ratio=self.soil.poissons_ratio,
        )
        self.cyclic_params = params
        curves = generate_cyclic_degradation_curves(params, num_points=45)

        # Empirical N-cycle stiffness degradation index delta = N^(-t_cyc), t_cyc ~ 0.06
        n_cyc = max(1, int(self.spin_n_cycles.value()))
        cyc_factor = float(n_cyc ** (-0.06))

        x_log = np.log10(np.asarray(curves.strain_percentages, dtype=float))
        g_arr = np.asarray(curves.modulus_reduction_ratios, dtype=float)
        d_arr = np.asarray(curves.damping_ratios, dtype=float)
        self.curve_g_ratio.setData(x_log, g_arr)
        self.curve_g_cycled.setData(x_log, g_arr * cyc_factor)
        self.curve_damping.setData(x_log, d_arr)

        self.lbl_cyclic_summary.setText(
            f"Vs = {params.shear_wave_velocity_mps:.1f} m/s | "
            f"N={n_cyc} Cyclic Stiffness Ratio = {cyc_factor:.3f}"
        )
        self.cyclicParamsChanged.emit(params)

    def _recompute_unsaturated(self):
        theta_s = self.spin_theta_sat.value()
        theta_r = min(theta_s - 0.02, self.spin_theta_res.value())
        vg = VanGenuchtenParams(
            alpha_kpa_inv=self.spin_alpha.value(),
            n_param=self.spin_n_vg.value(),
            theta_res=max(0.0, theta_r),
            theta_sat=theta_s,
        )
        self.swcc_params = vg
        phi_eff = self.soil.friction_angle
        unsat = UnsaturatedSoilParameters(
            effective_cohesion=max(2.0, self.soil.cohesion),
            effective_friction_angle=phi_eff,
            phi_b_angle=min(20.0, 0.65 * phi_eff),
            dry_unit_weight=max(12.0, self.soil.unit_weight - 2.0),
            initial_matric_suction=self.spin_psi0.value(),
            swcc=vg,
        )
        self.unsat_params = unsat

        infil = simulate_rainfall_infiltration(
            unsat,
            self.geom,
            rainfall_intensity_mm_hr=self.spin_rain_int.value(),
            rainfall_duration_hours=self.spin_rain_dur.value(),
        )
        self.last_infiltration = infil

        # Plot SWCC
        psi_grid = np.logspace(-1, 3, 60)
        sr_grid = np.array([vg.degree_of_saturation(p) for p in psi_grid])
        self.curve_swcc.setData(np.log10(psi_grid), sr_grid)

        # Plot matric suction profile psi(z, t) and suction-augmented shear strength tau_f(z)
        h_wall = max(1.0, self.geom.total_height)
        z_grid = np.linspace(0.0, h_wall, 30)
        z_w = infil.wetting_front_depth_m
        psi_profile = np.array(
            [0.5 if z <= z_w else self.spin_psi0.value() * (1.0 - np.exp(-3.0 * (z - z_w))) for z in z_grid]
        )
        tan_phi = np.tan(np.radians(unsat.effective_friction_angle))
        tau_profile = np.array(
            [
                unsat.compute_total_cohesion(psi) + infil.degraded_unit_weight_kpa * z * tan_phi
                for z, psi in zip(z_grid, psi_profile)
            ]
        )
        self.curve_psi_post.setData(psi_profile, z_grid)
        self.curve_tau_post.setData(tau_profile, z_grid)

        self.lbl_unsat_summary.setText(
            f"Wetting Front z_w = {z_w:.2f} m | "
            f"Cohesion: {infil.initial_cohesion_kpa:.1f} -> {infil.degraded_cohesion_kpa:.1f} kPa "
            f"(-{infil.percent_cohesion_loss:.1f}%)"
        )
        self.unsaturatedParamsChanged.emit(unsat, infil)

    def set_context(self, geom: RetainingWallGeometry, soil: SoilProperties):
        """Synchronizes geometry and base soil parameters from MainWindow."""
        self.geom = geom
        self.soil = soil
        self._recompute_cyclic()
        self._recompute_unsaturated()

    def apply_calibrated_cyclic(
        self,
        *,
        gamma_r: Optional[float] = None,
        curvature_a: Optional[float] = None,
        d_min: Optional[float] = None,
        d_max: Optional[float] = None,
        g_max_kpa: Optional[float] = None,
    ):
        """Updates cyclic soil controls cleanly from Lab Calibration Wizard outputs."""
        spins = (self.spin_gmax, self.spin_gamma_r, self.spin_a, self.spin_dmin, self.spin_dmax)
        for sp in spins:
            sp.blockSignals(True)
        if g_max_kpa is not None:
            self.spin_gmax.setValue(float(g_max_kpa))
        if gamma_r is not None:
            self.spin_gamma_r.setValue(float(gamma_r) * 100.0)
        if curvature_a is not None:
            self.spin_a.setValue(float(curvature_a))
        if d_min is not None:
            self.spin_dmin.setValue(float(d_min) * 100.0)
        if d_max is not None:
            self.spin_dmax.setValue(float(d_max) * 100.0)
        for sp in spins:
            sp.blockSignals(False)
        self._recompute_cyclic()

    def apply_calibrated_swcc(self, swcc: VanGenuchtenParams):
        """Updates Van Genuchten SWCC controls from Lab Calibration Wizard outputs."""
        spins = (self.spin_theta_sat, self.spin_theta_res, self.spin_alpha, self.spin_n_vg)
        for sp in spins:
            sp.blockSignals(True)
        self.spin_theta_sat.setValue(float(swcc.theta_sat))
        self.spin_theta_res.setValue(float(swcc.theta_res))
        self.spin_alpha.setValue(float(swcc.alpha_kpa_inv))
        self.spin_n_vg.setValue(float(swcc.n_param))
        for sp in spins:
            sp.blockSignals(False)
        self._recompute_unsaturated()
