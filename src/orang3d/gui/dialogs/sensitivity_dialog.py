"""
Parametric Sensitivity Sweep Dialog & Fast Analytical Engine (v3 Phase 5).

Lets students and researchers sweep one design variable (k_h, phi, water table
depth, r_u, or L_bay / H) across its engineering range in < 50 ms and view
live response curves (K_ae, FS_sliding, FS_overturning, FS_bearing, u_Newmark,
or eta_arch) with code safety thresholds overlaid as dashed horizontal lines.
"""

from __future__ import annotations

from dataclasses import replace, dataclass
import time
from typing import Dict, List, Optional, Tuple
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ...config import THEME
from ...models.advanced_wall_params import CurvedShellGeometry
from ...models.wall_params import RetainingWallGeometry, SeismicParams, SoilProperties
from ...physics.shell_arching import compute_shell_arching_partition
from ...physics.stability import evaluate_wall_stability
from ...signals.synthetic import (
    compute_newmark_sliding_displacement,
    compute_yield_acceleration_ky,
    generate_ricker_wavelet,
)


SWEEP_X_VARS: Dict[str, Tuple[str, str]] = {
    "k_h": ("Horizontal PGA k_h", "g"),
    "phi": ("Backfill Friction Angle phi", "deg"),
    "water_table_depth": ("Water Table Depth H_w", "m"),
    "r_u": ("Excess Pore Pressure Ratio r_u", "-"),
    "L_bay_over_H": ("Normalized Bay Span L_bay / H", "-"),
}

SWEEP_Y_METRICS: Dict[str, Tuple[str, str, Optional[float], str]] = {
    "k_ae": ("Dynamic Earth Pressure Coeff. K_ae", "-", None, ""),
    "fs_sliding": ("Factor of Safety (Sliding)", "-", 1.1, "IS Seismic Min (1.1)"),
    "fs_overturning": ("Factor of Safety (Overturning)", "-", 1.5, "Code Min (1.5)"),
    "fs_bearing": ("Factor of Safety (Bearing)", "-", 2.0, "Code Min (2.0)"),
    "u_newmark": ("Newmark Permanent Slip u_p", "cm", 5.0, "Serviceability Limit (5 cm)"),
    "arching_ratio": ("Shell Arching Transfer eta_arch", "-", None, ""),
}


@dataclass
class SensitivitySweepResult:
    """Output arrays and metadata from a fast parametric sweep."""

    x_var: str
    y_metric: str
    x_label: str
    x_unit: str
    y_label: str
    y_unit: str
    x_values: np.ndarray
    y_values: np.ndarray
    threshold_value: Optional[float]
    threshold_label: str
    elapsed_ms: float


def _x_grid_for_variable(
    x_var: str,
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    n_points: int,
) -> np.ndarray:
    """Returns monotonically increasing parameter samples for the chosen sweep axis."""
    if x_var == "k_h":
        return np.linspace(0.0, 0.50, n_points, dtype=np.float64)
    if x_var == "phi":
        # Respect validate bounds: strictly > backfill_slope and wall_friction_angle <= phi
        phi_low = max(20.0, seismic.backfill_slope + 1.0)
        return np.linspace(phi_low, 45.0, n_points, dtype=np.float64)
    if x_var == "water_table_depth":
        return np.linspace(0.0, geom.total_height, n_points, dtype=np.float64)
    if x_var == "r_u":
        return np.linspace(0.0, 0.85, n_points, dtype=np.float64)
    if x_var == "L_bay_over_H":
        return np.linspace(0.30, 1.50, n_points, dtype=np.float64)
    raise ValueError(f"Unsupported sweep X variable: '{x_var}'. Expected one of {list(SWEEP_X_VARS)}")


def run_sensitivity_sweep(
    x_var: str,
    y_metric: str,
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    shell_geom: Optional[CurvedShellGeometry] = None,
    n_points: int = 25,
) -> SensitivitySweepResult:
    """
    Evaluates `y_metric` monotonically across `n_points` values of `x_var`.
    Executes purely analytically in < 50 ms.
    """
    if x_var not in SWEEP_X_VARS:
        raise ValueError(f"Unknown x_var '{x_var}'")
    if y_metric not in SWEEP_Y_METRICS:
        raise ValueError(f"Unknown y_metric '{y_metric}'")

    t_start = time.perf_counter()
    n_pts = max(5, int(n_points))
    x_vals = _x_grid_for_variable(x_var, geom, soil, seismic, n_pts)
    y_vals = np.zeros(n_pts, dtype=np.float64)

    base_shell = shell_geom if shell_geom is not None else CurvedShellGeometry(panel_height=geom.total_height)

    # Compact Ricker pulse for fast Newmark evaluation across all sweep points
    t_wave: Optional[np.ndarray] = None
    a_unit: Optional[np.ndarray] = None
    if y_metric == "u_newmark":
        t_wave, a_raw = generate_ricker_wavelet(
            pga_g=1.0,
            central_freq_hz=2.5,
            duration_sec=8.0,
            sampling_rate_hz=40.0,
        )
        a_unit = a_raw

    for idx, x in enumerate(x_vals):
        xv = float(x)
        g_i = geom
        s_i = soil
        e_i = seismic
        sh_i = base_shell

        if x_var == "k_h":
            e_i = replace(seismic, horizontal_pga=xv)
        elif x_var == "phi":
            delta_clamped = min(soil.wall_friction_angle, xv - 0.5)
            s_i = replace(soil, friction_angle=xv, wall_friction_angle=max(0.0, delta_clamped))
        elif x_var == "water_table_depth":
            e_i = replace(seismic, water_table_depth=xv)
        elif x_var == "r_u":
            e_i = replace(seismic, liquefaction_factor=xv, pore_pressure_ratio_ru=xv)
        elif x_var == "L_bay_over_H":
            bay_span = xv * base_shell.panel_height
            radius = max(base_shell.radius, 0.55 * bay_span)
            sh_i = replace(base_shell, bay_span=bay_span, radius=radius)

        if y_metric == "arching_ratio":
            arch = compute_shell_arching_partition(sh_i, s_i, num_depth_points=25)
            y_vals[idx] = arch.arching_ratio
        elif y_metric == "u_newmark":
            assert t_wave is not None and a_unit is not None
            ky = compute_yield_acceleration_ky(g_i, s_i)
            # Effective seismic shaking amplitude scales with k_h (floor 0.30g for non-k_h sweeps)
            pga_eff = max(0.30, e_i.horizontal_pga) if x_var != "k_h" else max(0.01, e_i.horizontal_pga)
            _, slip_cm = compute_newmark_sliding_displacement(t_wave, a_unit * pga_eff, ky)
            y_vals[idx] = slip_cm
        else:
            res = evaluate_wall_stability(g_i, s_i, e_i)
            y_vals[idx] = float(getattr(res, y_metric))

    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
    x_label, x_unit = SWEEP_X_VARS[x_var]
    y_label, y_unit, thresh_val, thresh_lbl = SWEEP_Y_METRICS[y_metric]
    if y_metric == "fs_sliding" and seismic.horizontal_pga == 0.0 and x_var != "k_h":
        thresh_val = 1.5
        thresh_lbl = "IS Static Min (1.5)"

    return SensitivitySweepResult(
        x_var=x_var,
        y_metric=y_metric,
        x_label=x_label,
        x_unit=x_unit,
        y_label=y_label,
        y_unit=y_unit,
        x_values=x_vals,
        y_values=y_vals,
        threshold_value=thresh_val,
        threshold_label=thresh_lbl,
        elapsed_ms=elapsed_ms,
    )


class SensitivitySweepDialog(QDialog):
    """Interactive parametric sensitivity sweep dialog with live PyQtGraph plot."""

    def __init__(
        self,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        shell_geom: Optional[CurvedShellGeometry] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Parametric Sensitivity Sweep (Phase 5)")
        self.resize(780, 520)

        self.geom = geom
        self.soil = soil
        self.seismic = seismic
        self.shell_geom = shell_geom if shell_geom is not None else CurvedShellGeometry()
        self._last_result: Optional[SensitivitySweepResult] = None

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {THEME['background_dark']};
                color: {THEME['text_primary']};
            }}
            QLabel {{
                color: {THEME['text_primary']};
            }}
            QComboBox, QSpinBox, QPushButton {{
                background-color: {THEME['surface_elevated']};
                color: {THEME['text_primary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()

        controls.addWidget(QLabel("X Variable:"))
        self.combo_x = QComboBox()
        for key, (label, unit) in SWEEP_X_VARS.items():
            self.combo_x.addItem(f"{label} ({unit})", key)
        self.combo_x.currentIndexChanged.connect(self.recompute)
        controls.addWidget(self.combo_x)

        controls.addWidget(QLabel("Y Metric:"))
        self.combo_y = QComboBox()
        for key, (label, unit, _, _) in SWEEP_Y_METRICS.items():
            suffix = f" ({unit})" if unit and unit != "-" else ""
            self.combo_y.addItem(f"{label}{suffix}", key)
        # Default Y to FS_sliding for immediate geotechnical feedback
        idx_fs = self.combo_y.findData("fs_sliding")
        if idx_fs >= 0:
            self.combo_y.setCurrentIndex(idx_fs)
        self.combo_y.currentIndexChanged.connect(self.recompute)
        controls.addWidget(self.combo_y)

        controls.addWidget(QLabel("Samples:"))
        self.spin_points = QSpinBox()
        self.spin_points.setRange(10, 80)
        self.spin_points.setValue(25)
        self.spin_points.valueChanged.connect(self.recompute)
        controls.addWidget(self.spin_points)

        self.btn_run = QPushButton("Sweep")
        self.btn_run.clicked.connect(self.recompute)
        controls.addWidget(self.btn_run)

        layout.addLayout(controls)

        pg.setConfigOption("background", THEME["surface_dark"])
        pg.setConfigOption("foreground", THEME["text_primary"])
        pg.setConfigOptions(antialias=True)

        self.plot_widget = pg.PlotWidget(title="Parametric Sensitivity Curve")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.curve = self.plot_widget.plot(
            pen=pg.mkPen(THEME["accent_orange"], width=2.5),
            symbol="o",
            symbolSize=5,
            symbolBrush=THEME["accent_blue"],
        )
        self.threshold_line = pg.InfiniteLine(
            pos=1.1,
            angle=0,
            pen=pg.mkPen(THEME["accent_red"], width=2, style=Qt.DashLine),
        )
        self.plot_widget.addItem(self.threshold_line)
        layout.addWidget(self.plot_widget, stretch=1)

        footer = QHBoxLayout()
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet(f"color: {THEME['accent_green']}; font-size: 11px;")
        footer.addWidget(self.lbl_status)
        footer.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

        self.recompute()

    def set_context(
        self,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        shell_geom: Optional[CurvedShellGeometry] = None,
    ) -> None:
        """Updates active model context and refreshes the plot."""
        self.geom = geom
        self.soil = soil
        self.seismic = seismic
        if shell_geom is not None:
            self.shell_geom = shell_geom
        self.recompute()

    def recompute(self) -> SensitivitySweepResult:
        """Executes the sensitivity sweep and updates the plot."""
        x_var = str(self.combo_x.currentData())
        y_metric = str(self.combo_y.currentData())
        n_pts = int(self.spin_points.value())

        res = run_sensitivity_sweep(
            x_var=x_var,
            y_metric=y_metric,
            geom=self.geom,
            soil=self.soil,
            seismic=self.seismic,
            shell_geom=self.shell_geom,
            n_points=n_pts,
        )
        self._last_result = res

        self.curve.setData(res.x_values, res.y_values)
        self.plot_widget.setLabel("bottom", res.x_label, units=res.x_unit)
        self.plot_widget.setLabel("left", res.y_label, units=res.y_unit)
        self.plot_widget.setTitle(f"{res.y_label} vs. {res.x_label}")

        if res.threshold_value is not None:
            self.threshold_line.setValue(res.threshold_value)
            self.threshold_line.show()
            thresh_text = f" | Threshold: {res.threshold_label}"
        else:
            self.threshold_line.hide()
            thresh_text = ""

        self.lbl_status.setText(
            f"Evaluated {n_pts} points in {res.elapsed_ms:.2f} ms | "
            f"Range: [{float(np.min(res.y_values)):.3f}, {float(np.max(res.y_values)):.3f}]"
            f"{thresh_text}"
        )
        return res

    def last_result(self) -> Optional[SensitivitySweepResult]:
        """Returns the last sweep result."""
        return self._last_result

