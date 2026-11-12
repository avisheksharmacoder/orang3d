"""
Tests for Phase 2 GUI Integration of v2 Multi-Strut Curved Shell Mesher,
OpenSeesPy 2D BNWF Worker, and PINN Fast Surrogate Envelope.
"""

import os
import tempfile
import time
import numpy as np
import pytest
import pyvista as pv
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog

from orang3d.gui.main_window import MainWindow
from orang3d.models.advanced_wall_params import WallSystemMode
from orang3d.physics.bnwf_solver import OPENSEES_AVAILABLE


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_wall_system_mode_switching_and_3d_actors(qapp):
    """Verifies Cantilever <-> Curved Shell + Piles mode switching updates 3D actors cleanly."""
    win = MainWindow()
    try:
        assert win.wall_mode == WallSystemMode.CANTILEVER
        assert win.viewport_3d.wall_actor is not None
        assert win.viewport_3d.multi_strut_actor is None

        # Switch via left sidebar tab to Curved Shell -> auto-switches 3D mode
        win.tabs.setCurrentIndex(1)
        assert win.wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL
        assert win.viewport_3d.wall_actor is None
        assert win.viewport_3d.multi_strut_actor is not None
        assert win.viewport_3d.strut_actor is not None
        assert win.viewport_3d.active_wall_mesh is not None
        assert "ArchingStress_kPa" in win.viewport_3d.active_wall_mesh.point_data
        assert "Element_Type" in win.viewport_3d.active_wall_mesh.cell_data

        # Toggle piles and struts off/on
        win.viewport_3d.chk_piles.setChecked(False)
        win.viewport_3d.chk_struts.setChecked(False)
        assert win.viewport_3d.strut_actor is None
        assert win.viewport_3d.multi_strut_actor is not None

        win.viewport_3d.chk_piles.setChecked(True)
        win.viewport_3d.chk_struts.setChecked(True)
        assert win.viewport_3d.strut_actor is not None

        # Switch back to Cantilever Wall tab
        win.tabs.setCurrentIndex(0)
        assert win.wall_mode == WallSystemMode.CANTILEVER
        assert win.viewport_3d.wall_actor is not None
        assert win.viewport_3d.multi_strut_actor is None
        assert win.viewport_3d.strut_actor is None
    finally:
        win.close()


def test_live_shell_and_pinn_surrogate_propagation(qapp):
    """Verifies shell/strut parameter changes refresh 3D arching and PINN M(y)/V(y)."""
    win = MainWindow()
    try:
        assert win.last_pinn_prediction is not None
        assert win.bnwf_pinn_tab.last_pinn is not None
        assert win.last_pinn_prediction.equilibrium_imbalance_percent < 1e-4

        prev_moment = win.last_pinn_prediction.max_bending_moment_kNm_m

        # Switch to multi-strut mode and modify shell height / radius
        win.tabs.setCurrentIndex(1)
        win.panel_shell.spin_height.setValue(8.0)
        win.panel_strut.spin_dpile.setValue(1.2)

        assert win.shell_geom.panel_height == 8.0
        assert win.pier_pile_geom.pile_diameter == 1.2
        assert win.arching_results is not None
        assert win.last_pinn_prediction.max_bending_moment_kNm_m > prev_moment
    finally:
        win.close()


def test_export_active_multi_strut_mesh(qapp, monkeypatch):
    """Verifies _export_mesh_dialog exports the active curved-shell/pile mesh in multi-strut mode."""
    win = MainWindow()
    try:
        win.tabs.setCurrentIndex(1)
        assert win.wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "curved_shell_wall.vtk")
            monkeypatch.setattr(
                QFileDialog,
                "getSaveFileName",
                lambda *args, **kwargs: (out_path, "VTK Files (*.vtk)"),
            )
            win._export_mesh_dialog("vtk")
            assert os.path.exists(out_path)
            loaded = pv.read(out_path)
            assert "Element_Type" in loaded.cell_data
            assert loaded.n_cells == win.viewport_3d.active_wall_mesh.n_cells
    finally:
        win.close()


@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy not installed")
def test_main_window_bnwf_dynamic_and_pushover_execution(qapp):
    """Verifies OpenSees 2D BNWF dynamic and pushover workers run cleanly from MainWindow."""
    win = MainWindow()
    try:
        # Use short synthetic time history so dynamic OpenSees run completes fast in CI
        win.time_arr = np.linspace(0.0, 0.6, 30)
        win.accel_arr = 0.20 * np.sin(2.0 * np.pi * 2.5 * win.time_arr)

        # 1. Dynamic mode
        win.combo_bnwf_mode.setCurrentIndex(0)  # dynamic
        loop = QEventLoop()
        win._run_bnwf_simulation()
        assert win.bnwf_worker is not None
        win.bnwf_worker.finished.connect(loop.quit)
        QTimer.singleShot(15000, loop.quit)
        loop.exec()
        qapp.processEvents()

        assert win.bnwf_pinn_tab.last_bnwf is not None
        assert win.bnwf_pinn_tab.last_bnwf.total_steps == 30
        assert win.bnwf_pinn_tab.last_bnwf.max_crest_disp_cm > 0.0
        assert win.bottom_tabs.currentWidget() is win.bnwf_pinn_tab

        # 2. Pushover mode
        win.combo_bnwf_mode.setCurrentIndex(1)  # pushover
        loop2 = QEventLoop()
        win._run_bnwf_simulation()
        win.bnwf_worker.finished.connect(loop2.quit)
        QTimer.singleShot(15000, loop2.quit)
        loop2.exec()
        qapp.processEvents()

        assert win.bnwf_pinn_tab.last_pushover is not None
        assert len(win.bnwf_pinn_tab.last_pushover["displacements"]) > 5
    finally:
        win.close()


def test_multi_strut_3d_render_latency(qapp):
    """Ensures multi-strut 3D scene refresh stays fast enough for interactive desktop use."""
    win = MainWindow()
    try:
        win.tabs.setCurrentIndex(1)
        # Warm-up render
        win.viewport_3d.refresh()

        t0 = time.perf_counter()
        n_iters = 5
        for _ in range(n_iters):
            win.viewport_3d.refresh()
        avg_ms = ((time.perf_counter() - t0) / n_iters) * 1000.0
        assert avg_ms < 150.0, f"Multi-strut 3D refresh too slow: {avg_ms:.1f} ms"
    finally:
        win.close()
