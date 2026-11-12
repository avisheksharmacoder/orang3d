"""
Uncertainty Quantification (LHS Monte Carlo) & Seismic Fragility Tab (v3 Phase 4).

Exposes:
  1. Random variable distribution configurator (`Normal`, `Lognormal`, `Uniform`)
     for friction angle phi, cohesion c, unit weight gamma, seismic k_h, and resistance R.
  2. Cooperative `UQSimulationWorker(QThread)` running seeded Latin Hypercube Sampling
     (`N = 200` to `10,000`) via Analytical Limit Equilibrium or FastPINNSurrogate.
  3. Live PyQtGraph Factor of Safety histogram (with FS=1.0 threshold line), Cornell
     reliability index beta, failure probability Pf, and monotonic HAZUS seismic fragility curves.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)
from scipy import stats

from ...config import THEME
from ...models.advanced_wall_params import CurvedShellGeometry, PierAndPileGeometry, StrutSupportSystem
from ...models.wall_params import RetainingWallGeometry, SeismicParams, SoilProperties
from ...physics.stability import evaluate_wall_stability
from ...physics.surrogate_engine import FastPINNSurrogate, SurrogateInputs
from ...physics.uncertainty import (
    DamageState,
    DistributionConfig,
    FragilityCurveData,
    LatinHypercubeSampler,
    ReliabilityResult,
    SeismicFragilityEngine,
)


class UQSimulationWorker(QThread):
    """Background worker executing seeded LHS Monte Carlo UQ and fragility evaluation."""

    progressUpdated = Signal(int)
    uqFinished = Signal(dict)
    uqError = Signal(str)

    def __init__(
        self,
        distributions: Dict[str, DistributionConfig],
        n_samples: int = 500,
        random_seed: int = 42,
        engine_mode: str = "analytical",
        geom: Optional[RetainingWallGeometry] = None,
        soil: Optional[SoilProperties] = None,
        seismic: Optional[SeismicParams] = None,
        shell_geom: Optional[CurvedShellGeometry] = None,
        pier_geom: Optional[PierAndPileGeometry] = None,
        strut_sys: Optional[StrutSupportSystem] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.distributions = distributions
        self.n_samples = int(n_samples)
        self.random_seed = int(random_seed)
        self.engine_mode = engine_mode
        self.geom = copy.deepcopy(geom) if geom is not None else RetainingWallGeometry()
        self.soil = copy.deepcopy(soil) if soil is not None else SoilProperties()
        self.seismic = copy.deepcopy(seismic) if seismic is not None else SeismicParams()
        self.shell_geom = shell_geom or CurvedShellGeometry()
        self.pier_geom = pier_geom or PierAndPileGeometry()
        self.strut_sys = strut_sys or StrutSupportSystem()
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            sampler = LatinHypercubeSampler(random_seed=self.random_seed)
            var_order = ("phi", "c", "gamma", "k_h", "R")
            u_mat = sampler.sample_uniform(n_samples=self.n_samples, n_dims=len(var_order))

            phi_vals = np.clip(
                self.distributions["phi"].sample_quantiles(u_mat[:, 0]), 10.0, 50.0
            )
            c_vals = np.clip(
                self.distributions["c"].sample_quantiles(u_mat[:, 1]), 0.0, 200.0
            )
            gamma_vals = np.clip(
                self.distributions["gamma"].sample_quantiles(u_mat[:, 2]), 12.0, 24.0
            )
            kh_vals = np.clip(
                self.distributions["k_h"].sample_quantiles(u_mat[:, 3]), 0.0, 0.85
            )
            r_vals = np.clip(
                self.distributions["R"].sample_quantiles(u_mat[:, 4]), 0.30, 2.00
            )

            fs_samples = np.zeros(self.n_samples, dtype=np.float64)
            use_pinn = self.engine_mode == "pinn"
            surrogate = FastPINNSurrogate() if use_pinn else None

            soil_i = copy.deepcopy(self.soil)
            seis_i = copy.deepcopy(self.seismic)

            for i in range(self.n_samples):
                if self._is_cancelled:
                    self.uqFinished.emit({"status": "CANCELLED"})
                    return

                phi_i = float(phi_vals[i])
                c_i = float(c_vals[i])
                gamma_i = float(gamma_vals[i])
                kh_i = float(kh_vals[i])
                r_i = float(r_vals[i])

                if use_pinn and surrogate is not None:
                    inp = SurrogateInputs(
                        panel_height=float(self.shell_geom.panel_height),
                        bay_span=float(self.shell_geom.bay_span),
                        shell_radius=float(self.shell_geom.radius),
                        cohesion=max(0.5, c_i),
                        friction_angle=phi_i,
                        unit_weight=gamma_i,
                        pga_g=max(0.01, kh_i),
                        num_struts=len(self.strut_sys.strut_levels),
                        pile_diameter=float(self.pier_geom.pile_diameter),
                        pile_length=float(self.pier_geom.pile_length),
                        wall_thickness=float(self.shell_geom.thickness),
                    )
                    fs_base = float(surrogate.predict(inp).sliding_factor_of_safety)
                else:
                    soil_i.friction_angle = phi_i
                    soil_i.wall_friction_angle = min(self.soil.wall_friction_angle, phi_i)
                    soil_i.cohesion = c_i
                    soil_i.unit_weight = gamma_i
                    soil_i.saturated_unit_weight = max(gamma_i, self.soil.saturated_unit_weight)
                    seis_i.horizontal_pga = kh_i
                    res_i = evaluate_wall_stability(self.geom, soil_i, seis_i)
                    fs_base = float(res_i.fs_sliding)

                fs_samples[i] = max(0.01, r_i * fs_base)
                if i % max(1, self.n_samples // 10) == 0 or i == self.n_samples - 1:
                    self.progressUpdated.emit(int(round(100.0 * (i + 1) / self.n_samples)))

            mean_fs = float(np.mean(fs_samples))
            std_fs = float(np.std(fs_samples))
            cov_fs = float(std_fs / max(mean_fs, 1e-4))
            beta = float((mean_fs - 1.0) / max(std_fs, 1e-4))
            pf = float(np.mean(fs_samples < 1.0))
            if pf == 0.0 and beta > 0.0:
                pf = float(stats.norm.cdf(-beta))
            p5, p50, p95 = np.percentile(fs_samples, [5.0, 50.0, 95.0])

            reliability = ReliabilityResult(
                num_samples=self.n_samples,
                mean_fs=mean_fs,
                std_fs=std_fs,
                cov_fs=cov_fs,
                reliability_index_beta=beta,
                probability_of_failure=pf,
                fs_percentile_5=float(p5),
                fs_percentile_50=float(p50),
                fs_percentile_95=float(p95),
                fs_samples=fs_samples,
            )

            # Calibrate monotonic HAZUS fragility medians around median safety margin
            cap_scale = max(0.45, min(1.80, float(p50) / 1.50))
            disp_beta = max(0.28, min(0.65, cov_fs + 0.25))
            frag_engine = SeismicFragilityEngine(
                theta_medians={
                    DamageState.SLIGHT: 0.18 * cap_scale,
                    DamageState.MODERATE: 0.32 * cap_scale,
                    DamageState.EXTENSIVE: 0.48 * cap_scale,
                    DamageState.COLLAPSE: 0.68 * cap_scale,
                },
                beta_dispersions={
                    DamageState.SLIGHT: disp_beta,
                    DamageState.MODERATE: disp_beta,
                    DamageState.EXTENSIVE: disp_beta + 0.05,
                    DamageState.COLLAPSE: disp_beta + 0.10,
                },
            )
            fragility_curves = frag_engine.generate_fragility_curves(
                pga_min=0.05, pga_max=0.85, num_points=45
            )

            self.uqFinished.emit(
                {
                    "status": "COMPLETED",
                    "reliability": reliability,
                    "fragility_curves": fragility_curves,
                    "engine_mode": self.engine_mode,
                    "random_seed": self.random_seed,
                }
            )
        except Exception as exc:
            self.uqError.emit(str(exc))


class UQFragilityTab(QWidget):
    """Bottom dashboard tab for probabilistic LHS UQ and seismic fragility analysis."""

    VAR_SPECS = [
        ("phi", "Friction Angle phi (°)", "normal", 32.0, 3.0),
        ("c", "Cohesion c (kPa)", "lognormal", 5.0, 1.5),
        ("gamma", "Unit Weight gamma (kN/m³)", "normal", 18.0, 0.9),
        ("k_h", "Seismic Coeff. k_h (g)", "lognormal", 0.20, 0.06),
        ("R", "Resistance Factor R (-)", "normal", 1.00, 0.10),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.geom = RetainingWallGeometry()
        self.soil = SoilProperties()
        self.seismic = SeismicParams()
        self.shell_geom = CurvedShellGeometry()
        self.pier_geom = PierAndPileGeometry()
        self.strut_sys = StrutSupportSystem()

        self.worker: Optional[UQSimulationWorker] = None
        self.last_reliability: Optional[ReliabilityResult] = None
        self.last_fragility: Optional[Dict[DamageState, FragilityCurveData]] = None
        self._row_widgets: Dict[str, tuple[QComboBox, QDoubleSpinBox, QDoubleSpinBox]] = {}

        pg.setConfigOption("background", THEME["surface_dark"])
        pg.setConfigOption("foreground", THEME["text_primary"])
        pg.setConfigOptions(antialias=True)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(10)

        # Left Pane: Distributions + Run Settings
        left_panel = QWidget()
        left_v = QVBoxLayout(left_panel)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(6)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Engine:"))
        self.combo_engine = QComboBox()
        self.combo_engine.addItem("Analytical Limit Eq.", "analytical")
        self.combo_engine.addItem("PINN Surrogate", "pinn")
        ctrl_row.addWidget(self.combo_engine)

        ctrl_row.addWidget(QLabel("N:"))
        self.spin_samples = QSpinBox()
        self.spin_samples.setRange(200, 10000)
        self.spin_samples.setSingleStep(200)
        self.spin_samples.setValue(500)
        ctrl_row.addWidget(self.spin_samples)

        ctrl_row.addWidget(QLabel("Seed:"))
        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(0, 99999)
        self.spin_seed.setValue(42)
        ctrl_row.addWidget(self.spin_seed)

        self.btn_run_uq = QPushButton("🎲 Run LHS UQ")
        self.btn_run_uq.clicked.connect(self.run_uq_analysis)
        ctrl_row.addWidget(self.btn_run_uq)
        left_v.addLayout(ctrl_row)

        self.dist_table = QTableWidget(len(self.VAR_SPECS), 4)
        self.dist_table.setHorizontalHeaderLabels(["Random Var", "Distribution", "Mean / Min", "Std / Max"])
        self.dist_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dist_table.verticalHeader().setVisible(False)
        for row_idx, (key, label, dist_default, v1, v2) in enumerate(self.VAR_SPECS):
            lbl_item = QLabel(label)
            lbl_item.setStyleSheet("padding-left: 4px;")
            self.dist_table.setCellWidget(row_idx, 0, lbl_item)

            combo = QComboBox()
            combo.addItems(["normal", "lognormal", "uniform"])
            combo.setCurrentText(dist_default)
            self.dist_table.setCellWidget(row_idx, 1, combo)

            sp1 = QDoubleSpinBox()
            sp1.setRange(0.0, 200.0)
            sp1.setDecimals(2)
            sp1.setValue(v1)
            self.dist_table.setCellWidget(row_idx, 2, sp1)

            sp2 = QDoubleSpinBox()
            sp2.setRange(0.001, 200.0)
            sp2.setDecimals(3)
            sp2.setValue(v2)
            self.dist_table.setCellWidget(row_idx, 3, sp2)

            self._row_widgets[key] = (combo, sp1, sp2)
        left_v.addWidget(self.dist_table)

        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {THEME["surface_elevated"]};
                border: 1px solid {THEME["border"]};
                border-radius: 6px;
                padding: 6px;
            }}
            QLabel {{ color: {THEME["text_primary"]}; font-size: 11px; }}
            """
        )
        card_l = QVBoxLayout(card)
        self.lbl_uq_summary = QLabel("Click 'Run LHS UQ' to compute Cornell beta, Pf, and fragility.")
        self.lbl_uq_summary.setWordWrap(True)
        card_l.addWidget(self.lbl_uq_summary)
        left_v.addWidget(card)

        root.addWidget(left_panel, stretch=4)

        # Right Pane: FS Histogram + Monotonic HAZUS Fragility Curves
        plots_row = QHBoxLayout()
        plots_row.setSpacing(8)

        self.fs_hist_plot = pg.PlotWidget(title="Monte Carlo Factor of Safety Distribution")
        self.fs_hist_plot.setLabel("left", "Frequency")
        self.fs_hist_plot.setLabel("bottom", "Sliding Factor of Safety (FS)")
        self.fs_hist_plot.showGrid(x=True, y=True, alpha=0.25)
        self.hist_bar_item = pg.BarGraphItem(
            x=[], height=[], width=0.1, brush=THEME["accent_blue"], pen="white"
        )
        self.fs_hist_plot.addItem(self.hist_bar_item)
        self.fs_limit_line = pg.InfiniteLine(
            pos=1.0,
            angle=90,
            pen=pg.mkPen(color=THEME["accent_red"], width=2.0, style=Qt.DashLine),
        )
        self.fs_hist_plot.addItem(self.fs_limit_line)
        plots_row.addWidget(self.fs_hist_plot, stretch=1)

        self.fragility_plot = pg.PlotWidget(title="HAZUS Seismic Fragility Curves")
        self.fragility_plot.setLabel("left", "Exceedance Prob. P(DS >= ds | PGA)")
        self.fragility_plot.setLabel("bottom", "Peak Ground Acceleration PGA", units="g")
        self.fragility_plot.setYRange(0.0, 1.02)
        self.fragility_plot.showGrid(x=True, y=True, alpha=0.25)
        self.fragility_plot.addLegend(offset=(8, 8))

        colors = {
            DamageState.SLIGHT: THEME["accent_green"],
            DamageState.MODERATE: THEME["accent_yellow"],
            DamageState.EXTENSIVE: THEME["accent_orange"],
            DamageState.COLLAPSE: THEME["accent_red"],
        }
        self.fragility_curves_items: Dict[DamageState, Any] = {}
        for ds in (
            DamageState.SLIGHT,
            DamageState.MODERATE,
            DamageState.EXTENSIVE,
            DamageState.COLLAPSE,
        ):
            self.fragility_curves_items[ds] = self.fragility_plot.plot(
                pen=pg.mkPen(color=colors[ds], width=2.2),
                name=ds.value,
            )
        plots_row.addWidget(self.fragility_plot, stretch=1)

        plots_wrap = QWidget()
        plots_wrap.setLayout(plots_row)
        root.addWidget(plots_wrap, stretch=6)

    def set_context(
        self,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        shell_geom: Optional[CurvedShellGeometry] = None,
        pier_geom: Optional[PierAndPileGeometry] = None,
        strut_sys: Optional[StrutSupportSystem] = None,
    ) -> None:
        """Synchronizes nominal mean values from the active MainWindow project state."""
        self.geom = geom
        self.soil = soil
        self.seismic = seismic
        if shell_geom is not None:
            self.shell_geom = shell_geom
        if pier_geom is not None:
            self.pier_geom = pier_geom
        if strut_sys is not None:
            self.strut_sys = strut_sys

        # Update nominal center values cleanly when in normal/lognormal mode
        defaults = {
            "phi": (soil.friction_angle, max(1.0, 0.10 * soil.friction_angle)),
            "c": (max(1.0, soil.cohesion), max(0.5, 0.25 * max(2.0, soil.cohesion))),
            "gamma": (soil.unit_weight, max(0.5, 0.05 * soil.unit_weight)),
            "k_h": (max(0.05, seismic.horizontal_pga), max(0.02, 0.25 * max(0.05, seismic.horizontal_pga))),
        }
        for key, (mean_val, std_val) in defaults.items():
            combo, sp1, sp2 = self._row_widgets[key]
            if combo.currentText() != "uniform":
                sp1.setValue(float(mean_val))
                sp2.setValue(float(std_val))

    def get_distribution_configs(self) -> Dict[str, DistributionConfig]:
        """Reads UI distribution rows into `DistributionConfig` dataclasses."""
        configs: Dict[str, DistributionConfig] = {}
        for key, (combo, sp1, sp2) in self._row_widgets.items():
            dist_type = combo.currentText()
            v1 = float(sp1.value())
            v2 = float(sp2.value())
            if dist_type == "uniform":
                lo, hi = min(v1, v2), max(v1, v2)
                if math.isclose(lo, hi):
                    hi = lo + 0.1
                configs[key] = DistributionConfig(
                    name=key,
                    dist_type="uniform",
                    min_val=lo,
                    max_val=hi,
                    mean=0.5 * (lo + hi),
                    std=(hi - lo) / math.sqrt(12.0),
                )
            else:
                configs[key] = DistributionConfig(
                    name=key,
                    dist_type=dist_type,
                    min_val=max(0.0, v1 - 3.0 * v2),
                    max_val=v1 + 3.0 * v2,
                    mean=v1,
                    std=max(1e-4, v2),
                )
        return configs

    def run_uq_analysis(self) -> Optional[UQSimulationWorker]:
        """Launches or cancels the LHS Monte Carlo UQ background worker."""
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.btn_run_uq.setText("⏳ Cancelling...")
            return self.worker

        self.btn_run_uq.setText("⏹ Cancel UQ")
        self.lbl_uq_summary.setText("Running Latin Hypercube Sampling Monte Carlo UQ...")

        self.worker = UQSimulationWorker(
            distributions=self.get_distribution_configs(),
            n_samples=int(self.spin_samples.value()),
            random_seed=int(self.spin_seed.value()),
            engine_mode=str(self.combo_engine.currentData() or "analytical"),
            geom=self.geom,
            soil=self.soil,
            seismic=self.seismic,
            shell_geom=self.shell_geom,
            pier_geom=self.pier_geom,
            strut_sys=self.strut_sys,
            parent=self,
        )
        self.worker.uqFinished.connect(self._on_uq_finished)
        self.worker.uqError.connect(self._on_uq_error)
        self.worker.start()
        return self.worker

    def _on_uq_finished(self, payload: dict) -> None:
        self.btn_run_uq.setText("🎲 Run LHS UQ")
        if payload.get("status") != "COMPLETED":
            self.lbl_uq_summary.setText("UQ simulation cancelled.")
            return

        rel: ReliabilityResult = payload["reliability"]
        frags: Dict[DamageState, FragilityCurveData] = payload["fragility_curves"]
        self.last_reliability = rel
        self.last_fragility = frags

        # Update Histogram
        counts, edges = np.histogram(rel.fs_samples, bins=22)
        centers = 0.5 * (edges[:-1] + edges[1:])
        widths = 0.85 * float(edges[1] - edges[0]) if len(edges) > 1 else 0.1
        self.hist_bar_item.setOpts(x=centers, height=counts, width=widths)

        # Update Fragility Curves
        for ds, item in self.fragility_curves_items.items():
            if ds in frags:
                curve = frags[ds]
                item.setData(curve.pga_values_g, curve.exceedance_probabilities)

        self.lbl_uq_summary.setText(
            f"N = {rel.num_samples} (Seed={payload['random_seed']}) | "
            f"Mean FS = {rel.mean_fs:.3f} (CoV={rel.cov_fs:.2%}) | "
            f"Cornell beta = {rel.reliability_index_beta:.2f} | "
            f"Pf = P(FS<1.0) = {rel.probability_of_failure:.4f} | "
            f"P5/P50/P95 = {rel.fs_percentile_5:.2f} / {rel.fs_percentile_50:.2f} / {rel.fs_percentile_95:.2f}"
        )

    def _on_uq_error(self, err: str) -> None:
        self.btn_run_uq.setText("🎲 Run LHS UQ")
        self.lbl_uq_summary.setStyleSheet(f"color: {THEME['accent_red']};")
        self.lbl_uq_summary.setText(f"UQ Error: {err}")

    def cancel_worker(self) -> None:
        """Stops any running UQ thread safely during shutdown."""
        if self.worker is not None and self.worker.isRunning():
            try:
                self.worker.cancel()
                self.worker.wait(1000)
            except Exception:
                pass
