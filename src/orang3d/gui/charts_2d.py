"""
Real-time 2D Plotting Dashboard using PyQtGraph (Phase 8).
Displays dynamic earthquake accelerogram a(t), Newmark permanent displacement u(t),
and pore-water pressure build-up u_w(t) at 60 FPS with synchronized scrubbing,
playback transport controls, and color-coded dynamic safety badges.
"""

from typing import Optional
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QComboBox,
)
from PySide6.QtCore import Qt, Signal

from ..config import THEME, SAFETY_THRESHOLDS
from ..models.wall_params import AnalysisResults


class Charts2DWidget(QWidget):
    """
    High-Performance 2D dynamic waveform dashboard and geotechnical safety card.
    """

    playheadMoved = Signal(float)
    playbackToggled = Signal(bool)
    stepForwardClicked = Signal()
    stepBackwardClicked = Signal()
    speedChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_playhead_t: float = 0.0
        self._is_playing: bool = False

        # Master horizontal layout: Left = Transport Bar + 3 Waveform Plots, Right = Safety Badges
        master_layout = QHBoxLayout(self)
        master_layout.setContentsMargins(6, 6, 6, 6)
        master_layout.setSpacing(10)

        # Apply PyQtGraph global dark engineering styling
        pg.setConfigOption("background", THEME["surface_dark"])
        pg.setConfigOption("foreground", THEME["text_primary"])
        pg.setConfigOptions(antialias=True)

        # ----------------------------------------------------
        # Left Panel: Transport Bar + Waveform Plots
        # ----------------------------------------------------
        charts_container = QWidget()
        charts_layout = QVBoxLayout(charts_container)
        charts_layout.setContentsMargins(0, 0, 0, 0)
        charts_layout.setSpacing(4)

        # Transport Controls Bar
        self.transport_bar = self._build_transport_bar()
        charts_layout.addWidget(self.transport_bar)

        # 3 Synchronized Waveform Plots
        plots_layout = QHBoxLayout()
        plots_layout.setContentsMargins(0, 0, 0, 0)
        plots_layout.setSpacing(8)

        # 1. Seismic Ground Acceleration Plot a(t)
        self.accel_plot_widget = pg.PlotWidget(title="<b style='color:#00a6fb;'>Seismic Motion a(t)</b>")
        self.accel_plot_widget.setLabel("left", "Accel", units="g")
        self.accel_plot_widget.setLabel("bottom", "Time", units="s")
        self.accel_plot_widget.showGrid(x=True, y=True, alpha=0.25)
        self.accel_curve = self.accel_plot_widget.plot(pen=pg.mkPen(color=THEME["accent_blue"], width=1.5))

        # Main interactive vertical scrubber line
        self.scrubber_line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=True,
            pen=pg.mkPen(color="#ffffff", width=1.8, style=Qt.DashLine),
            hoverPen=pg.mkPen(color=THEME["accent_orange"], width=2.2),
        )
        self.scrubber_line.sigPositionChanged.connect(self._on_scrubber_dragged)
        self.accel_plot_widget.addItem(self.scrubber_line)
        plots_layout.addWidget(self.accel_plot_widget, stretch=1)

        # 2. Cumulative Permanent Slip (Newmark) Plot u(t)
        self.slip_plot_widget = pg.PlotWidget(title="<b style='color:#ff6b35;'>Newmark Slip u(t)</b>")
        self.slip_plot_widget.setLabel("left", "Permanent Slip", units="cm")
        self.slip_plot_widget.setLabel("bottom", "Time", units="s")
        self.slip_plot_widget.showGrid(x=True, y=True, alpha=0.25)
        self.slip_plot_widget.setXLink(self.accel_plot_widget)
        self.slip_curve = self.slip_plot_widget.plot(pen=pg.mkPen(color=THEME["accent_orange"], width=2.0))

        # Synchronized scrubber line on slip plot
        self.slip_scrubber = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen(color="#ffffff", width=1.2, style=Qt.DashLine),
        )
        self.slip_plot_widget.addItem(self.slip_scrubber)
        plots_layout.addWidget(self.slip_plot_widget, stretch=1)

        # 3. Dynamic Pore-Water Pressure Curve u_w(t)
        self.pore_plot_widget = pg.PlotWidget(title="<b style='color:#06d6a0;'>Pore Pressure u_w(t)</b>")
        self.pore_plot_widget.setLabel("left", "Pore Pressure", units="kPa")
        self.pore_plot_widget.setLabel("bottom", "Time", units="s")
        self.pore_plot_widget.showGrid(x=True, y=True, alpha=0.25)
        self.pore_plot_widget.setXLink(self.accel_plot_widget)
        self.pore_curve = self.pore_plot_widget.plot(pen=pg.mkPen(color=THEME["accent_green"], width=1.8))

        # Synchronized scrubber line on pore plot
        self.pore_scrubber = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen(color="#ffffff", width=1.2, style=Qt.DashLine),
        )
        self.pore_plot_widget.addItem(self.pore_scrubber)
        plots_layout.addWidget(self.pore_plot_widget, stretch=1)

        charts_layout.addLayout(plots_layout)
        master_layout.addWidget(charts_container, stretch=7)

        # ----------------------------------------------------
        # Right Panel: 3-State Geotechnical Safety Badges
        # ----------------------------------------------------
        self.safety_card = self._build_safety_summary_panel()
        master_layout.addWidget(self.safety_card, stretch=3)

    def _build_transport_bar(self) -> QWidget:
        """Constructs the playback transport control bar."""
        bar = QFrame(self)
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME["surface_elevated"]};
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
                padding: 2px 6px;
            }}
            QPushButton {{
                background-color: {THEME["surface_dark"]};
                color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]};
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {THEME["border"]};
            }}
            QPushButton:checked {{
                background-color: {THEME["accent_orange"]};
                color: #ffffff;
            }}
            QComboBox {{
                background-color: {THEME["surface_dark"]};
                color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]};
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 11px;
            }}
            QLabel {{
                color: {THEME["text_secondary"]};
                font-size: 11px;
                font-family: monospace;
            }}
        """)

        h_layout = QHBoxLayout(bar)
        h_layout.setContentsMargins(4, 2, 4, 2)
        h_layout.setSpacing(6)

        # Transport Buttons
        self.btn_step_back = QPushButton("⏮ Step")
        self.btn_step_back.setToolTip("Step backward 1 frame")
        self.btn_step_back.clicked.connect(lambda: self.stepBackwardClicked.emit())
        h_layout.addWidget(self.btn_step_back)

        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setToolTip("Start or pause dynamic earthquake waveform playback")
        self.btn_play.clicked.connect(self._on_play_toggle)
        h_layout.addWidget(self.btn_play)

        self.btn_step_fwd = QPushButton("Step ⏭")
        self.btn_step_fwd.setToolTip("Step forward 1 frame")
        self.btn_step_fwd.clicked.connect(lambda: self.stepForwardClicked.emit())
        h_layout.addWidget(self.btn_step_fwd)

        self.btn_loop = QPushButton("🔁 Loop")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setChecked(True)
        self.btn_loop.setToolTip("Toggle continuous looping of seismic record")
        h_layout.addWidget(self.btn_loop)

        # Playback Speed Selector
        h_layout.addWidget(QLabel("Speed:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.25×", "0.5×", "1.0×", "2.0×"])
        self.combo_speed.setCurrentText("1.0×")
        self.combo_speed.currentTextChanged.connect(self._on_speed_changed)
        h_layout.addWidget(self.combo_speed)

        h_layout.addStretch()

        # Playhead Timestamp Label
        self.lbl_time = QLabel("t = 0.00 s")
        self.lbl_time.setStyleSheet(f"color: {THEME['accent_yellow']}; font-weight: bold;")
        h_layout.addWidget(self.lbl_time)

        return bar

    def _build_safety_summary_panel(self) -> QFrame:
        """Constructs the geotechnical safety badges with 3-state state machine."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME["surface_elevated"]};
                border: 1px solid {THEME["border"]};
                border-radius: 8px;
                padding: 8px;
            }}
            QLabel {{
                color: {THEME["text_primary"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        title = QLabel("<b>DYNAMIC SAFETY DASHBOARD</b>")
        title.setStyleSheet(f"color: {THEME['accent_yellow']}; font-size: 11px; letter-spacing: 1px; font-weight: bold;")
        layout.addWidget(title)

        # 3-State Badges (Sliding, Overturning, Bearing)
        self.badge_sliding = QLabel("FS Sliding: --")
        self.badge_overturning = QLabel("FS Overturning: --")
        self.badge_bearing = QLabel("FS Bearing: --")

        # Backwards-compatibility aliases for existing MainWindow & test references
        self.lbl_fs_sliding = self.badge_sliding
        self.lbl_fs_overturning = self.badge_overturning
        self.lbl_fs_bearing = self.badge_bearing

        for badge in [self.badge_sliding, self.badge_overturning, self.badge_bearing]:
            layout.addWidget(badge)

        # Secondary Engineering Demand Metrics
        self.lbl_thrust = QLabel("P_ae Thrust: --")
        self.lbl_thrust.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.lbl_thrust)

        self.lbl_stress = QLabel("Stem Tension: --")
        self.lbl_stress.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.lbl_stress)

        layout.addStretch()
        return card

    def _on_play_toggle(self):
        """Toggles play/pause state and emits signal."""
        self._is_playing = not self._is_playing
        if self._is_playing:
            self.btn_play.setText("⏸ Pause")
        else:
            self.btn_play.setText("▶ Play")
        self.playbackToggled.emit(self._is_playing)

    def _on_speed_changed(self, text: str):
        """Converts speed string (e.g. '0.5×') to float multiplier."""
        clean = text.replace("×", "").strip()
        try:
            val = float(clean)
            self.speedChanged.emit(val)
        except ValueError:
            pass

    def _on_scrubber_dragged(self, line):
        """Called when user drags the vertical playhead line."""
        pos = float(line.value())
        self.current_playhead_t = pos
        self.slip_scrubber.setValue(pos)
        self.pore_scrubber.setValue(pos)
        self.lbl_time.setText(f"t = {pos:.2f} s")
        self.playheadMoved.emit(pos)

    def is_looping(self) -> bool:
        """Returns True if continuous playback looping is active."""
        return self.btn_loop.isChecked()

    def get_playback_speed(self) -> float:
        """Returns the active speed factor (e.g. 1.0)."""
        clean = self.combo_speed.currentText().replace("×", "").strip()
        try:
            return float(clean)
        except ValueError:
            return 1.0

    def set_playhead(self, t: float):
        """Programmatically moves all synchronized scrubber lines to time t."""
        self.current_playhead_t = float(t)
        self.scrubber_line.blockSignals(True)
        self.scrubber_line.setValue(t)
        self.scrubber_line.blockSignals(False)

        self.slip_scrubber.setValue(t)
        self.pore_scrubber.setValue(t)
        self.lbl_time.setText(f"t = {t:.2f} s")

    def update_signals(
        self,
        time_arr: np.ndarray,
        accel_arr: np.ndarray,
        slip_arr: np.ndarray,
        pore_arr: Optional[np.ndarray] = None,
        playhead_t: float = 0.0,
    ):
        """
        Updates 2D accelerogram, Newmark displacement, and pore-water pressure curves at 60 FPS.
        """
        self.accel_curve.setData(time_arr, accel_arr)
        self.slip_curve.setData(time_arr, slip_arr)

        if pore_arr is not None:
            self.pore_curve.setData(time_arr, pore_arr)
        elif len(time_arr) > 0:
            # Synthesize representative excess pore-pressure generation curve if not supplied
            u_synth = 30.0 + 25.0 * (1.0 - np.exp(-0.3 * time_arr))
            self.pore_curve.setData(time_arr, u_synth)

        self.set_playhead(playhead_t)

    def update_safety_metrics(self, results: AnalysisResults):
        """
        Updates dynamic safety badges using a 3-state state machine:
        - Safe: Green (#06d6a0) when FS >= FS_req
        - Marginal: Amber (#ffd166) when 1.0 <= FS < FS_req
        - Failure: Red (#ef476f) when FS < 1.0
        """
        def format_badge(name: str, val: float, req: float) -> str:
            if val >= req:
                color = THEME["accent_green"]
                status = "SAFE"
            elif val >= 1.0:
                color = THEME["accent_yellow"]
                status = "MARGINAL"
            else:
                color = THEME["accent_red"]
                status = "FAIL"

            return (
                f"<div style='border: 1px solid {color}; border-radius: 5px; padding: 3px 6px; margin: 1px 0; background-color: rgba(0,0,0,0.25);'>"
                f"<span style='color:{THEME['text_secondary']}; font-size:11px;'>FS {name}:</span> "
                f"<b style='color:{color}; font-size:12px;'>{val:.2f}</b> "
                f"<span style='color:{color}; font-size:10px; font-weight:bold;'>[{status}]</span> "
                f"<span style='color:{THEME['text_muted']}; font-size:9px;'>(req. {req:.2f})</span>"
                f"</div>"
            )

        # 1. Sliding Badge
        req_s = SAFETY_THRESHOLDS["sliding_seismic"]
        self.badge_sliding.setText(format_badge("Sliding", results.fs_sliding, req_s))

        # 2. Overturning Badge
        req_o = SAFETY_THRESHOLDS["overturning_seismic"]
        self.badge_overturning.setText(format_badge("Overturning", results.fs_overturning, req_o))

        # 3. Bearing Capacity Badge
        req_b = SAFETY_THRESHOLDS["bearing_seismic"]
        self.badge_bearing.setText(format_badge("Bearing", results.fs_bearing, req_b))

        # Dynamic Thrust Demand
        self.lbl_thrust.setText(f"P_ae Dynamic Thrust: <b>{results.total_thrust:.1f} kN/m</b>")

        # Stem Concrete Tensile Stress & Cracking Modulus Flag
        stress_color = THEME["accent_red"] if results.cracking_predicted else THEME["text_primary"]
        crack_flag = " <span style='color:#ef476f; font-weight:bold;'>[CRACKED]</span>" if results.cracking_predicted else " <span style='color:#06d6a0;'>[ELASTIC]</span>"
        self.lbl_stress.setText(
            f"Stem Base Tension: <b style='color:{stress_color};'>{results.concrete_tensile_stress:.2f} MPa</b>{crack_flag}"
        )
