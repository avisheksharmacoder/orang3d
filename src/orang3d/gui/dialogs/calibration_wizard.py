"""
Laboratory Soil Test Calibration Wizard Dialog (v3 Phase 4).

Imports CSV lab records for:
  1. Resonant Column / Cyclic Triaxial -> fits gamma_r, a, D_min, D_max
  2. Pressure Plate / Dewpoint SWCC    -> fits Van Genuchten alpha, n
  3. Direct Shear / Triaxial Envelope  -> fits Mohr-Coulomb cohesion c, friction phi

Reports R^2, RMSE, and applies calibrated parameters directly to `SoilProperties`
and `AdvancedSoilPanel`.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...config import THEME
from ...models.wall_params import SoilProperties
from ...physics.calibration import (
    CalibrationFitResult,
    fit_cyclic_modulus_reduction_curve,
    fit_hysteretic_damping_curve,
    fit_mohr_coulomb_shear_strength,
    fit_van_genuchten_swcc,
)
from ...physics.cyclic_soil import (
    compute_hysteretic_damping,
    compute_modulus_reduction,
)
from ...physics.unsaturated_soil import VanGenuchtenParams


class CalibrationWizardDialog(QDialog):
    """Interactive dialog for nonlinear least-squares calibration from CSV lab data."""

    TEST_RESONANT = "Resonant Column / Cyclic Triaxial"
    TEST_SWCC = "Pressure Plate / SWCC"
    TEST_DIRECT_SHEAR = "Direct Shear / Triaxial (Mohr-Coulomb)"

    calibrationApplied = Signal(str, dict)

    def __init__(
        self,
        soil: Optional[SoilProperties] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Lab Soil Calibration Wizard (v3 Phase 4)")
        self.resize(780, 560)
        self.soil = soil if soil is not None else SoilProperties()

        self.x_data: np.ndarray = np.array([], dtype=np.float64)
        self.y_data: np.ndarray = np.array([], dtype=np.float64)
        self.damping_data: Optional[np.ndarray] = None
        self.last_fit_result: Optional[CalibrationFitResult] = None
        self.last_fitted_payload: Dict[str, Any] = {}
        self.last_swcc_obj: Optional[VanGenuchtenParams] = None

        pg.setConfigOption("background", THEME["surface_dark"])
        pg.setConfigOption("foreground", THEME["text_primary"])
        pg.setConfigOptions(antialias=True)

        self._build_ui()
        self.load_synthetic_sample()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Header & Controls
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("<b>Lab Test Type:</b>"))
        self.combo_test_type = QComboBox()
        self.combo_test_type.addItems(
            [self.TEST_RESONANT, self.TEST_SWCC, self.TEST_DIRECT_SHEAR]
        )
        self.combo_test_type.currentIndexChanged.connect(lambda _: self.load_synthetic_sample())
        top_row.addWidget(self.combo_test_type, stretch=2)

        self.btn_load_csv = QPushButton("📂 Load Lab CSV...")
        self.btn_load_csv.clicked.connect(self._browse_csv)
        top_row.addWidget(self.btn_load_csv)

        self.btn_sample = QPushButton("Load Benchmark Sample")
        self.btn_sample.clicked.connect(self.load_synthetic_sample)
        top_row.addWidget(self.btn_sample)
        root.addLayout(top_row)

        # Plot: Measured Scatter vs Fitted Curve
        self.plot = pg.PlotWidget(title="Laboratory Data vs. Calibrated Model")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.addLegend(offset=(10, 10))
        self.scatter_measured = pg.ScatterPlotItem(
            size=9,
            brush=pg.mkBrush(THEME["accent_orange"]),
            pen=pg.mkPen("white", width=0.8),
            name="Measured Lab Points",
        )
        self.plot.addItem(self.scatter_measured)
        self.curve_fitted = self.plot.plot(
            pen=pg.mkPen(color=THEME["accent_blue"], width=2.4),
            name="Calibrated Fit",
        )
        root.addWidget(self.plot, stretch=4)

        # Metrics Summary Card
        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {THEME["surface_elevated"]};
                border: 1px solid {THEME["border"]};
                border-radius: 6px;
                padding: 8px;
            }}
            QLabel {{ color: {THEME["text_primary"]}; font-size: 12px; }}
            """
        )
        card_l = QVBoxLayout(card)
        self.lbl_fit_metrics = QLabel("R² = -- | RMSE = -- | Status: Pending")
        self.lbl_fit_metrics.setStyleSheet(f"color: {THEME['accent_green']}; font-weight: bold;")
        card_l.addWidget(self.lbl_fit_metrics)

        self.lbl_fit_params = QLabel("Calibrated Parameters: --")
        self.lbl_fit_params.setWordWrap(True)
        card_l.addWidget(self.lbl_fit_params)
        root.addWidget(card)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_fit = QPushButton("📈 Re-Fit Curve")
        self.btn_fit.clicked.connect(self.fit_current_data)
        btn_row.addWidget(self.btn_fit)
        btn_row.addStretch()

        self.btn_apply = QPushButton("✅ Apply to Project Soil")
        self.btn_apply.clicked.connect(self.apply_calibration)
        btn_row.addWidget(self.btn_apply)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

    def _browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Laboratory Calibration CSV",
            "",
            "CSV Files (*.csv *.txt);;All Files (*)",
        )
        if not path:
            return
        try:
            self.load_csv(path)
        except Exception as exc:
            QMessageBox.critical(self, "CSV Import Error", f"Failed to parse lab CSV:\n{exc}")

    @staticmethod
    def _parse_csv_columns(
        filepath: str,
        x_aliases: Tuple[str, ...],
        y_aliases: Tuple[str, ...],
        opt_aliases: Tuple[str, ...] = (),
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
        """Parses named or positional numeric columns from a CSV file."""
        with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.reader(f) if any(cell.strip() for cell in r)]
        if len(rows) < 2:
            raise ValueError("CSV file must contain at least 2 data rows.")

        # Detect header row cleanly
        has_header = False
        try:
            float(rows[0][0].strip())
        except ValueError:
            has_header = True

        x_idx, y_idx, z_idx = 0, 1, None
        start_row = 0
        if has_header:
            start_row = 1
            headers = [h.strip().lower() for h in rows[0]]
            for idx, h in enumerate(headers):
                if any(alias in h for alias in x_aliases):
                    x_idx = idx
                    break
            for idx, h in enumerate(headers):
                if idx != x_idx and any(alias in h for alias in y_aliases):
                    y_idx = idx
                    break
            if opt_aliases:
                for idx, h in enumerate(headers):
                    if idx not in (x_idx, y_idx) and any(alias in h for alias in opt_aliases):
                        z_idx = idx
                        break
        elif len(rows[0]) >= 3 and opt_aliases:
            z_idx = 2

        xs: List[float] = []
        ys: List[float] = []
        zs: List[float] = []
        for row in rows[start_row:]:
            if len(row) <= max(x_idx, y_idx):
                continue
            xs.append(float(row[x_idx].strip()))
            ys.append(float(row[y_idx].strip()))
            if z_idx is not None and len(row) > z_idx and row[z_idx].strip():
                zs.append(float(row[z_idx].strip()))

        x_arr = np.asarray(xs, dtype=np.float64)
        y_arr = np.asarray(ys, dtype=np.float64)
        z_arr = np.asarray(zs, dtype=np.float64) if len(zs) == len(xs) and len(zs) > 0 else None
        return x_arr, y_arr, z_arr

    def load_csv(self, filepath: str, test_type: Optional[str] = None) -> CalibrationFitResult:
        """Loads lab data from `filepath` and immediately runs nonlinear least-squares fitting."""
        if test_type is not None:
            idx = self.combo_test_type.findText(test_type)
            if idx >= 0:
                self.combo_test_type.blockSignals(True)
                self.combo_test_type.setCurrentIndex(idx)
                self.combo_test_type.blockSignals(False)

        active_type = self.combo_test_type.currentText()
        if active_type == self.TEST_RESONANT:
            x_arr, y_arr, z_arr = self._parse_csv_columns(
                filepath,
                ("strain", "gamma"),
                ("g_over_gmax", "g/gmax", "g_ratio", "modulus"),
                ("damp", "d_ratio"),
            )
        elif active_type == self.TEST_SWCC:
            x_arr, y_arr, z_arr = self._parse_csv_columns(
                filepath,
                ("suction", "psi", "kpa"),
                ("sr", "s_r", "saturation", "degree", "theta"),
            )
            # Auto-normalize volumetric water content theta -> degree of saturation S_r
            if np.max(y_arr) <= 0.70 and np.min(y_arr) >= 0.0:
                y_max = max(0.42, float(np.max(y_arr)))
                y_arr = np.clip(y_arr / y_max, 0.0, 1.0)
        else:
            x_arr, y_arr, z_arr = self._parse_csv_columns(
                filepath,
                ("sigma", "normal"),
                ("tau", "shear", "strength"),
            )

        self.x_data = x_arr
        self.y_data = y_arr
        self.damping_data = z_arr
        return self.fit_current_data()

    def load_synthetic_sample(self) -> CalibrationFitResult:
        """Loads built-in reference benchmark points for the active test type."""
        active_type = self.combo_test_type.currentText()
        self.damping_data = None

        if active_type == self.TEST_RESONANT:
            gammas = np.logspace(-5, -1.5, 10)
            self.x_data = gammas
            self.y_data = np.array(
                [compute_modulus_reduction(g, 0.0005, 0.92) for g in gammas]
            )
            self.damping_data = np.array(
                [compute_hysteretic_damping(g, 0.0005, 0.92, 0.022, 0.26) for g in gammas]
            )
        elif active_type == self.TEST_SWCC:
            suctions = np.array([0.5, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 600.0])
            vg_ref = VanGenuchtenParams(alpha_kpa_inv=0.045, n_param=1.65)
            self.x_data = suctions
            self.y_data = np.array([vg_ref.degree_of_saturation(p) for p in suctions])
        else:
            sigmas = np.array([25.0, 50.0, 100.0, 150.0, 220.0])
            self.x_data = sigmas
            self.y_data = 14.0 + sigmas * np.tan(np.radians(33.5))

        return self.fit_current_data()

    def fit_current_data(self) -> CalibrationFitResult:
        """Fits the corresponding calibration model to `self.x_data` and `self.y_data`."""
        active_type = self.combo_test_type.currentText()
        payload: Dict[str, Any] = {}
        self.last_swcc_obj = None

        if active_type == self.TEST_RESONANT:
            gamma_r, a_val, fit_res = fit_cyclic_modulus_reduction_curve(self.x_data, self.y_data)
            payload.update({"gamma_r": gamma_r, "curvature_a": a_val})
            if self.damping_data is not None and len(self.damping_data) == len(self.x_data):
                d_min, d_max, _ = fit_hysteretic_damping_curve(
                    self.x_data, self.damping_data, reference_strain=gamma_r, curvature_a=a_val
                )
                payload.update({"d_min": d_min, "d_max": d_max})

            x_plot = np.log10(np.maximum(self.x_data, 1e-7) * 100.0)
            x_dense = np.logspace(np.log10(np.min(self.x_data)), np.log10(np.max(self.x_data)), 80)
            y_dense = np.array([compute_modulus_reduction(g, gamma_r, a_val) for g in x_dense])
            self.scatter_measured.setData(x_plot, self.y_data)
            self.curve_fitted.setData(np.log10(x_dense * 100.0), y_dense)
            self.plot.setLabel("bottom", "Log10 Shear Strain gamma (%)")
            self.plot.setLabel("left", "Normalized Modulus G/G_max")

        elif active_type == self.TEST_SWCC:
            swcc, fit_res = fit_van_genuchten_swcc(self.x_data, self.y_data)
            self.last_swcc_obj = swcc
            payload.update({"alpha_kpa_inv": swcc.alpha_kpa_inv, "n_param": swcc.n_param})

            x_plot = np.log10(np.maximum(self.x_data, 0.1))
            x_dense = np.logspace(
                np.log10(max(0.1, float(np.min(self.x_data)))),
                np.log10(max(1.0, float(np.max(self.x_data)))),
                80,
            )
            y_dense = np.array([swcc.degree_of_saturation(p) for p in x_dense])
            self.scatter_measured.setData(x_plot, self.y_data)
            self.curve_fitted.setData(np.log10(x_dense), y_dense)
            self.plot.setLabel("bottom", "Log10 Matric Suction psi (kPa)")
            self.plot.setLabel("left", "Degree of Saturation S_r")

        else:
            cohesion_kpa, phi_deg, fit_res = fit_mohr_coulomb_shear_strength(self.x_data, self.y_data)
            payload.update({"cohesion_kpa": cohesion_kpa, "friction_angle_deg": phi_deg})

            x_dense = np.linspace(0.0, float(np.max(self.x_data)) * 1.05, 50)
            y_dense = cohesion_kpa + x_dense * np.tan(np.radians(phi_deg))
            self.scatter_measured.setData(self.x_data, self.y_data)
            self.curve_fitted.setData(x_dense, y_dense)
            self.plot.setLabel("bottom", "Normal Stress sigma_n (kPa)")
            self.plot.setLabel("left", "Shear Strength tau_f (kPa)")

        self.last_fit_result = fit_res
        self.last_fitted_payload = payload

        sig_badge = "PASS (R² >= 0.95)" if fit_res.is_statistically_significant else "LOW FIT (R² < 0.95)"
        self.lbl_fit_metrics.setText(
            f"{fit_res.test_type} | R² = {fit_res.r_squared:.4f} | "
            f"RMSE = {fit_res.rmse:.4f} | N = {fit_res.num_data_points} | {sig_badge}"
        )
        param_str = ", ".join(f"{k} = {v}" for k, v in fit_res.fitted_parameters.items())
        self.lbl_fit_params.setText(f"Calibrated Parameters: {param_str}")
        return fit_res

    def apply_calibration(self) -> Dict[str, Any]:
        """Pushes calibrated soil parameters directly into `self.soil` and emits `calibrationApplied`."""
        active_type = self.combo_test_type.currentText()
        payload = dict(self.last_fitted_payload)

        if active_type == self.TEST_DIRECT_SHEAR and payload:
            phi_new = float(np.clip(payload["friction_angle_deg"], 5.0, 50.0))
            coh_new = float(max(0.0, payload["cohesion_kpa"]))
            self.soil.friction_angle = phi_new
            self.soil.cohesion = coh_new
            if self.soil.wall_friction_angle > phi_new:
                self.soil.wall_friction_angle = round(0.67 * phi_new, 2)
        elif active_type == self.TEST_SWCC and self.last_swcc_obj is not None:
            payload["swcc"] = self.last_swcc_obj

        self.calibrationApplied.emit(active_type, payload)
        return payload
