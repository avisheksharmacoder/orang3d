"""
Nonlinear OpenSees 2D BNWF & PINN Fast Surrogate Dashboard Tab (v3 Phase 2).
Displays:
1. Real-time PINN equilibrium-projected bending moment M(y) and shear force V(y) profiles.
2. OpenSeesPy 2D BNWF dynamic crest displacement / strut force histories or lateral pushover curve.
3. Summary metrics card with inference latency and equilibrium verification.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...config import THEME
from ...physics.bnwf_solver import BNWFSimulationResult
from ...physics.surrogate_engine import SurrogatePrediction


class BNWFAndPINNTab(QWidget):
    """Bottom dashboard tab hosting PINN surrogate profiles and OpenSees 2D BNWF plots."""

    pinnToggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.last_pinn: Optional[SurrogatePrediction] = None
        self.last_bnwf: Optional[BNWFSimulationResult] = None
        self.last_pushover: Optional[Dict[str, np.ndarray]] = None

        master_layout = QHBoxLayout(self)
        master_layout.setContentsMargins(6, 6, 6, 6)
        master_layout.setSpacing(10)

        pg.setConfigOption("background", THEME["surface_dark"])
        pg.setConfigOption("foreground", THEME["text_primary"])
        pg.setConfigOptions(antialias=True)

        # Left side: 2 PyQtGraph plots
        plots_container = QWidget()
        plots_v = QVBoxLayout(plots_container)
        plots_v.setContentsMargins(0, 0, 0, 0)
        plots_v.setSpacing(4)

        top_bar = QHBoxLayout()
        self.chk_pinn_enabled = QCheckBox("Live PINN Envelope (< 1 ms)")
        self.chk_pinn_enabled.setChecked(True)
        self.chk_pinn_enabled.toggled.connect(self.pinnToggled.emit)
        top_bar.addWidget(self.chk_pinn_enabled)
        top_bar.addStretch()
        self.lbl_pinn_status = QLabel("PINN: Ready")
        self.lbl_pinn_status.setStyleSheet(f"color: {THEME['accent_green']}; font-size: 11px;")
        top_bar.addWidget(self.lbl_pinn_status)
        plots_v.addLayout(top_bar)

        plots_row = QHBoxLayout()
        plots_row.setSpacing(8)

        # Plot 1: PINN Bending Moment M(y) & Shear V(y)
        self.pinn_plot = pg.PlotWidget(
            title="<b style='color:#ff6b35;'>PINN Stem Profiles: M(y) & V(y)</b>"
        )
        self.pinn_plot.setLabel("left", "Elevation y", units="m")
        self.pinn_plot.setLabel("bottom", "Force / Moment", units="kN or kNm/m")
        self.pinn_plot.showGrid(x=True, y=True, alpha=0.25)
        self.pinn_plot.addLegend(offset=(10, 10))
        self.pinn_moment_curve = self.pinn_plot.plot(
            pen=pg.mkPen(color=THEME["accent_orange"], width=2.2),
            name="Moment M(y) [kNm/m]",
        )
        self.pinn_shear_curve = self.pinn_plot.plot(
            pen=pg.mkPen(color=THEME["accent_blue"], width=1.8),
            name="Shear V(y) [kN/m]",
        )
        plots_row.addWidget(self.pinn_plot, stretch=1)

        # Plot 2: OpenSees 2D BNWF Dynamic or Pushover Curve
        self.bnwf_plot = pg.PlotWidget(
            title="<b style='color:#06d6a0;'>OpenSeesPy 2D BNWF Response</b>"
        )
        self.bnwf_plot.setLabel("left", "Crest Displacement", units="cm")
        self.bnwf_plot.setLabel("bottom", "Time", units="s")
        self.bnwf_plot.showGrid(x=True, y=True, alpha=0.25)
        self.bnwf_curve = self.bnwf_plot.plot(
            pen=pg.mkPen(color=THEME["accent_green"], width=2.0),
        )
        plots_row.addWidget(self.bnwf_plot, stretch=1)

        plots_v.addLayout(plots_row)
        master_layout.addWidget(plots_container, stretch=7)

        # Right side: Summary Card
        self.summary_card = self._build_summary_card()
        master_layout.addWidget(self.summary_card, stretch=3)

    def _build_summary_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {THEME["surface_elevated"]};
                border: 1px solid {THEME["border"]};
                border-radius: 8px;
                padding: 8px;
            }}
            QLabel {{
                color: {THEME["text_primary"]};
                font-size: 11px;
            }}
            """
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        lbl_pinn_hdr = QLabel("<b>PINN SURROGATE (EQUILIBRIUM)</b>")
        lbl_pinn_hdr.setStyleSheet(f"color: {THEME['accent_orange']}; font-size: 11px;")
        layout.addWidget(lbl_pinn_hdr)

        self.lbl_pinn_metrics = QLabel("Waiting for prediction...")
        self.lbl_pinn_metrics.setWordWrap(True)
        layout.addWidget(self.lbl_pinn_metrics)

        lbl_bnwf_hdr = QLabel("<b>OPENSEES 2D BNWF SSI</b>")
        lbl_bnwf_hdr.setStyleSheet(f"color: {THEME['accent_green']}; font-size: 11px; margin-top: 6px;")
        layout.addWidget(lbl_bnwf_hdr)

        self.lbl_bnwf_metrics = QLabel("Not run yet. Click 'Run 2D BNWF' in toolbar.")
        self.lbl_bnwf_metrics.setWordWrap(True)
        layout.addWidget(self.lbl_bnwf_metrics)

        layout.addStretch()
        return card

    def is_pinn_enabled(self) -> bool:
        """Returns True if live PINN surrogate evaluation is active."""
        return self.chk_pinn_enabled.isChecked()

    def update_pinn_prediction(self, pred: SurrogatePrediction) -> None:
        """Updates the PINN M(y)/V(y) profiles and equilibrium metrics card."""
        self.last_pinn = pred
        self.pinn_moment_curve.setData(pred.bending_moment_kNm_m, pred.elevations_m)
        self.pinn_shear_curve.setData(pred.shear_force_kN_m, pred.elevations_m)

        struts_str = ", ".join(f"{s:.0f}" for s in pred.strut_loads_kN)
        self.lbl_pinn_status.setText(
            f"PINN: {pred.inference_latency_ms:.2f} ms | Imbalance: {pred.equilibrium_imbalance_percent:.2f}%"
        )
        self.lbl_pinn_metrics.setText(
            f"Max Moment: <b>{pred.max_bending_moment_kNm_m:.1f} kNm/m</b><br>"
            f"Max Shear: <b>{pred.max_shear_force_kN_m:.1f} kN/m</b><br>"
            f"Crest Disp: <b>{pred.crest_displacement_mm:.1f} mm</b> | "
            f"FS<sub>slide</sub>: <b>{pred.sliding_factor_of_safety:.2f}</b><br>"
            f"Struts (kN): [{struts_str}]"
        )

    def update_bnwf_dynamic(
        self,
        result: BNWFSimulationResult,
        elapsed_seconds: float = 0.0,
    ) -> None:
        """Displays OpenSees 2D BNWF time-history crest displacement and metrics."""
        self.last_bnwf = result
        self.last_pushover = None

        self.bnwf_plot.setTitle("<b style='color:#06d6a0;'>OpenSees 2D BNWF: Crest Disp vs Time</b>")
        self.bnwf_plot.setLabel("left", "Crest Displacement", units="cm")
        self.bnwf_plot.setLabel("bottom", "Time", units="s")
        self.bnwf_curve.setData(result.time_history, result.crest_displacement * 100.0)

        peak_strut = 0.0
        for arr in result.strut_forces.values():
            if len(arr) > 0:
                peak_strut = max(peak_strut, float(np.max(np.abs(arr))))

        self.lbl_bnwf_metrics.setText(
            f"Status: <b>{result.status}</b> ({result.total_steps} steps, {elapsed_seconds:.2f}s)<br>"
            f"Max Crest Disp: <b>{result.max_crest_disp_cm:.2f} cm</b><br>"
            f"Peak Moment: <b>{result.max_moment_knm:.1f} kNm</b> | "
            f"Peak Strut: <b>{peak_strut:.1f} kN</b>"
        )

    def update_bnwf_pushover(
        self,
        pushover: Dict[str, np.ndarray],
        elapsed_seconds: float = 0.0,
    ) -> None:
        """Displays OpenSees 2D BNWF lateral pushover capacity curve."""
        self.last_pushover = pushover
        self.last_bnwf = None

        disp_cm = np.asarray(pushover.get("displacements", []), dtype=np.float64) * 100.0
        shear_kn = np.asarray(pushover.get("base_shears", []), dtype=np.float64)

        self.bnwf_plot.setTitle("<b style='color:#06d6a0;'>OpenSees 2D BNWF: Lateral Pushover Curve</b>")
        self.bnwf_plot.setLabel("left", "Base Shear", units="kN")
        self.bnwf_plot.setLabel("bottom", "Crest Displacement", units="cm")
        self.bnwf_curve.setData(disp_cm, shear_kn)

        max_u = float(np.max(np.abs(disp_cm))) if len(disp_cm) else 0.0
        max_v = float(np.max(np.abs(shear_kn))) if len(shear_kn) else 0.0
        self.lbl_bnwf_metrics.setText(
            f"Mode: <b>Lateral Pushover</b> ({len(disp_cm)} steps, {elapsed_seconds:.2f}s)<br>"
            f"Max Crest Disp: <b>{max_u:.2f} cm</b> | Max Shear: <b>{max_v:.1f} kN</b>"
        )

