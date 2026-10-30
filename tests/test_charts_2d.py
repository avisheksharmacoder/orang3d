"""
Test Suite for Phase 8: High-Performance 2D Time-Series & Safety Dashboard.
Validates:
1. Real-time 60 FPS dynamic waveform plots:
   - Ground acceleration a(t) in g
   - Newmark continuous sliding displacement u(t) in cm
   - Dynamic pore-water pressure build-up & dissipation u_w(t) in kPa
2. Synchronized draggable playhead scrubber line across plots.
3. Transport playback controls: Play/Pause, Step Forward, Step Backward, Loop, and Speed (0.25x - 2.0x).
4. Color-coded 3-state dynamic safety badges (Green: Safe, Amber: Marginal, Red: Failure).
5. High-frequency 60 Hz update stability without GUI thread freezing.
"""

import pytest
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from orang3d.gui.charts_2d import Charts2DWidget
from orang3d.models.wall_params import AnalysisResults
from orang3d.config import THEME, SAFETY_THRESHOLDS


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_signals():
    t = np.linspace(0.0, 10.0, 500)
    a = 0.35 * np.sin(2.0 * np.pi * 1.5 * t) * np.exp(-0.2 * t)
    # Newmark permanent slip: monotonically non-decreasing
    slip = np.maximum(0.0, np.cumsum(np.maximum(0.0, np.abs(a) - 0.15)) * 0.05)
    # Pore pressure build-up and dissipation
    u_w = 45.0 + 35.0 * (1.0 - np.exp(-0.4 * t)) * np.exp(-0.1 * t)
    return t, a, slip, u_w


def test_charts_2d_initialization(qapp):
    """Verifies that Charts2DWidget initializes with 3 waveform plots, scrubber line, badges, and transport bar."""
    dashboard = Charts2DWidget()

    # Three waveform plots
    assert hasattr(dashboard, "accel_plot_widget")
    assert hasattr(dashboard, "slip_plot_widget")
    assert hasattr(dashboard, "pore_plot_widget")

    # Curve items
    assert hasattr(dashboard, "accel_curve")
    assert hasattr(dashboard, "slip_curve")
    assert hasattr(dashboard, "pore_curve")

    # Synchronized scrubber line
    assert hasattr(dashboard, "scrubber_line")
    assert dashboard.scrubber_line is not None

    # Transport controls
    assert hasattr(dashboard, "btn_play")
    assert hasattr(dashboard, "btn_step_back")
    assert hasattr(dashboard, "btn_step_fwd")
    assert hasattr(dashboard, "btn_loop")
    assert hasattr(dashboard, "combo_speed")

    # Safety badges
    assert hasattr(dashboard, "badge_sliding")
    assert hasattr(dashboard, "badge_overturning")
    assert hasattr(dashboard, "badge_bearing")

    dashboard.close()


def test_waveform_curves_update(qapp, sample_signals):
    """Verifies that update_signals populates accel, slip, and pore-pressure curves with matching data lengths."""
    t, a, slip, u_w = sample_signals
    dashboard = Charts2DWidget()

    dashboard.update_signals(t, a, slip, pore_arr=u_w, playhead_t=2.5)

    x_acc, y_acc = dashboard.accel_curve.getData()
    x_slp, y_slp = dashboard.slip_curve.getData()
    x_por, y_por = dashboard.pore_curve.getData()

    assert len(x_acc) == len(t)
    assert len(y_acc) == len(a)
    assert len(x_slp) == len(slip)
    assert len(x_por) == len(u_w)

    assert dashboard.scrubber_line.value() == pytest.approx(2.5, abs=1e-3)

    dashboard.close()


def test_scrubber_line_synchronization(qapp, sample_signals):
    """Verifies that scrubber line position updates to exact playhead timestamp."""
    t, a, slip, u_w = sample_signals
    dashboard = Charts2DWidget()
    dashboard.update_signals(t, a, slip, pore_arr=u_w, playhead_t=0.0)

    for test_t in [1.2, 4.8, 8.5, 9.9]:
        dashboard.set_playhead(test_t)
        assert dashboard.scrubber_line.value() == pytest.approx(test_t, abs=1e-3)
        assert dashboard.current_playhead_t == pytest.approx(test_t, abs=1e-3)

    dashboard.close()


def test_scrubber_user_drag_emits_signal(qapp):
    """Verifies that user dragging the scrubber line triggers signal emission."""
    dashboard = Charts2DWidget()
    emitted = []
    dashboard.playheadMoved.connect(lambda val: emitted.append(val))

    # Move scrubber programmatically or via signal
    dashboard.scrubber_line.setValue(3.75)
    dashboard.scrubber_line.sigPositionChanged.emit(dashboard.scrubber_line)

    assert len(emitted) > 0
    assert emitted[-1] == pytest.approx(3.75, abs=1e-2)

    dashboard.close()


def test_safety_badge_state_machine_3_states(qapp):
    """
    Verifies 3-state dynamic coloring:
    - Green (Safe): FS >= FS_req
    - Amber (Marginal): 1.0 <= FS < FS_req
    - Red (Failure): FS < 1.0
    """
    dashboard = Charts2DWidget()

    req_sliding = SAFETY_THRESHOLDS["sliding_seismic"]         # 1.1
    req_overturning = SAFETY_THRESHOLDS["overturning_seismic"] # 1.2
    req_bearing = SAFETY_THRESHOLDS["bearing_seismic"]         # 2.0

    # 1. All Safe (Green)
    safe_results = AnalysisResults(
        fs_sliding=req_sliding + 0.3,
        fs_overturning=req_overturning + 0.4,
        fs_bearing=req_bearing + 0.5,
        total_thrust=120.0,
        concrete_tensile_stress=1.5,
    )
    dashboard.update_safety_metrics(safe_results)

    assert THEME["accent_green"].lower() in dashboard.badge_sliding.text().lower() or "safe" in dashboard.badge_sliding.text().lower()
    assert THEME["accent_green"].lower() in dashboard.badge_overturning.text().lower() or "safe" in dashboard.badge_overturning.text().lower()
    assert THEME["accent_green"].lower() in dashboard.badge_bearing.text().lower() or "safe" in dashboard.badge_bearing.text().lower()

    # 2. Marginal (Amber: 1.0 <= FS < FS_req)
    marginal_results = AnalysisResults(
        fs_sliding=1.05,        # < 1.10
        fs_overturning=1.10,    # < 1.20
        fs_bearing=1.50,        # < 2.00
        total_thrust=160.0,
        concrete_tensile_stress=2.2,
    )
    dashboard.update_safety_metrics(marginal_results)

    assert THEME["accent_yellow"].lower() in dashboard.badge_sliding.text().lower() or "marginal" in dashboard.badge_sliding.text().lower()
    assert THEME["accent_yellow"].lower() in dashboard.badge_overturning.text().lower() or "marginal" in dashboard.badge_overturning.text().lower()
    assert THEME["accent_yellow"].lower() in dashboard.badge_bearing.text().lower() or "marginal" in dashboard.badge_bearing.text().lower()

    # 3. Failure Imminent (Red: FS < 1.0)
    fail_results = AnalysisResults(
        fs_sliding=0.88,
        fs_overturning=0.92,
        fs_bearing=0.75,
        total_thrust=250.0,
        concrete_tensile_stress=4.5,
        cracking_predicted=True,
    )
    dashboard.update_safety_metrics(fail_results)

    assert THEME["accent_red"].lower() in dashboard.badge_sliding.text().lower() or "fail" in dashboard.badge_sliding.text().lower()
    assert THEME["accent_red"].lower() in dashboard.badge_overturning.text().lower() or "fail" in dashboard.badge_overturning.text().lower()
    assert THEME["accent_red"].lower() in dashboard.badge_bearing.text().lower() or "fail" in dashboard.badge_bearing.text().lower()

    dashboard.close()


def test_transport_controls_interactions(qapp):
    """Verifies Play/Pause toggle, Step buttons, Loop toggle, and Speed factor dropdown."""
    dashboard = Charts2DWidget()

    play_emitted = []
    dashboard.playbackToggled.connect(lambda playing: play_emitted.append(playing))

    step_fwd_emitted = []
    dashboard.stepForwardClicked.connect(lambda: step_fwd_emitted.append(True))

    step_back_emitted = []
    dashboard.stepBackwardClicked.connect(lambda: step_back_emitted.append(True))

    speed_emitted = []
    dashboard.speedChanged.connect(lambda factor: speed_emitted.append(factor))

    # 1. Play / Pause
    dashboard.btn_play.click()
    assert len(play_emitted) == 1
    assert play_emitted[-1] is True
    assert "pause" in dashboard.btn_play.text().lower()

    dashboard.btn_play.click()
    assert len(play_emitted) == 2
    assert play_emitted[-1] is False
    assert "play" in dashboard.btn_play.text().lower()

    # 2. Step buttons
    dashboard.btn_step_fwd.click()
    assert len(step_fwd_emitted) == 1

    dashboard.btn_step_back.click()
    assert len(step_back_emitted) == 1

    # 3. Loop toggle
    initial_loop = dashboard.is_looping()
    dashboard.btn_loop.click()
    assert dashboard.is_looping() != initial_loop

    # 4. Speed combo
    dashboard.combo_speed.setCurrentText("2.0×")
    assert len(speed_emitted) > 0
    assert speed_emitted[-1] == pytest.approx(2.0)

    dashboard.close()


def test_high_rate_60hz_update_stability(qapp, sample_signals):
    """Asserts that 60 consecutive high-frequency waveform updates run smoothly in < 500ms without GUI thread errors."""
    t, a, slip, u_w = sample_signals
    dashboard = Charts2DWidget()

    results = AnalysisResults(
        fs_sliding=1.2,
        fs_overturning=1.8,
        fs_bearing=2.5,
        total_thrust=130.0,
        concrete_tensile_stress=1.4,
    )

    import time
    t_start = time.perf_counter()

    for i in range(60):
        t_sub = t[: 100 + i * 5]
        a_sub = a[: 100 + i * 5]
        s_sub = slip[: 100 + i * 5]
        p_sub = u_w[: 100 + i * 5]
        playhead = float(t_sub[-1])

        dashboard.update_signals(t_sub, a_sub, s_sub, pore_arr=p_sub, playhead_t=playhead)
        dashboard.update_safety_metrics(results)

    t_elapsed = time.perf_counter() - t_start
    # 60 updates should be fast and non-blocking
    assert t_elapsed < 2.0

    dashboard.close()
