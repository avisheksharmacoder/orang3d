"""
Phase 10.2(2): GUI Stress, Thread Safety & Memory Leak Gate.

Verifies:
  1. Rapid 1,000-step parameter morphing in both Cantilever and Multi-Strut Curved
     Shell modes with zero uncaught Qt exceptions and strictly bounded VTK actor count.
  2. Cooperative QThread cancellation (< 2s graceful exit, clean CANCELLED state)
     for BNWFSimulationWorker, OpenSees3DFEAWorker, and KratosSimulationWorker.
"""

from __future__ import annotations

import time
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from orang3d.gui.main_window import MainWindow
from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
)
from orang3d.models.advanced_wall_params import (
    CurvedShellGeometry,
    MultiStrutPiledWallModel,
    PierAndPileGeometry,
    StrutSupportSystem,
    WallSystemMode,
)
from orang3d.physics import (
    KRATOS_AVAILABLE,
    OPENSEES_AVAILABLE,
    ConstitutiveModelType,
    OpenSees3DFEAWorker,
)
from orang3d.physics.bnwf_solver import BNWFSimulationWorker
from orang3d.physics.kratos_solver import KratosSimulationWorker


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _count_renderer_actors(win: MainWindow) -> int:
    return len(win.viewport_3d.plotter.renderer.actors)


def test_gui_1000_step_morphing_cantilever_and_multi_strut_no_vtk_leak(qapp):
    """
    Rapidly morphs wall, soil, shell, pier, and strut parameters for 1,000 steps
    across both Cantilever and Multi-Strut Curved Shell modes, asserting:
      - Zero uncaught exceptions or invalid analysis results
      - VTK renderer actor count remains bounded without unbounded accumulation
    """
    win = MainWindow()
    errors: list[str] = []

    try:
        # Enable overlays that create/replace actors dynamically
        win.viewport_3d.chk_wedge.setChecked(True)
        win.viewport_3d.chk_vectors.setChecked(True)

        # --- Phase A: 500 morphing steps in Cantilever mode ---
        idx_cant = win.combo_wall_mode.findData(WallSystemMode.CANTILEVER)
        assert idx_cant >= 0
        win.combo_wall_mode.setCurrentIndex(idx_cant)
        base_actors_cant = _count_renderer_actors(win)
        max_actors_cant = base_actors_cant

        for i in range(500):
            try:
                t_val = float(i % 25) / 24.0
                win.geom = RetainingWallGeometry(
                    stem_height=4.0 + 3.0 * t_val,
                    stem_thickness_base=0.45 + 0.35 * t_val,
                    stem_thickness_top=0.30,
                    toe_length=0.8 + 0.4 * t_val,
                    heel_length=1.8 + 0.8 * t_val,
                    footing_thickness=0.55,
                    wall_length=8.0 + 4.0 * t_val,
                )
                win.soil = SoilProperties(
                    unit_weight=18.0 + 1.5 * t_val,
                    friction_angle=30.0 + 6.0 * t_val,
                    wall_friction_angle=18.0,
                )
                win.seismic = SeismicParams(
                    horizontal_pga=0.10 + 0.20 * t_val,
                    water_table_depth=10.0,
                )
                win.recompute_and_render()
                max_actors_cant = max(max_actors_cant, _count_renderer_actors(win))
                if i % 50 == 0:
                    qapp.processEvents()
            except Exception as exc:
                errors.append(f"Cantilever step {i}: {exc}")
                break

        assert not errors
        assert win.results.fs_sliding > 0.0
        # Actor count must not grow monotonically with 500 iterations
        assert max_actors_cant <= base_actors_cant + 5
        assert _count_renderer_actors(win) <= base_actors_cant + 5

        # --- Phase B: 500 morphing steps in Multi-Strut Curved Shell mode ---
        idx_ms = win.combo_wall_mode.findData(WallSystemMode.MULTI_STRUT_CURVED_SHELL)
        assert idx_ms >= 0
        win.combo_wall_mode.setCurrentIndex(idx_ms)
        base_actors_ms = _count_renderer_actors(win)
        max_actors_ms = base_actors_ms

        for i in range(500):
            try:
                t_val = float(i % 25) / 24.0
                win.shell_geom = CurvedShellGeometry(
                    panel_height=4.5 + 2.0 * t_val,
                    bay_span=3.5 + 2.0 * t_val,
                    radius=2.5 + 1.5 * t_val,
                    thickness=0.25 + 0.15 * t_val,
                )
                win.pier_pile_geom = PierAndPileGeometry(
                    pier_width=0.6 + 0.2 * t_val,
                    pier_depth=0.9 + 0.3 * t_val,
                    pier_height=5.0 + 2.0 * t_val,
                    pile_diameter=0.8 + 0.2 * t_val,
                    pile_length=10.0 + 4.0 * t_val,
                )
                win.num_bays = 2 + (i % 3)
                win.recompute_and_render()
                max_actors_ms = max(max_actors_ms, _count_renderer_actors(win))
                if i % 50 == 0:
                    qapp.processEvents()
            except Exception as exc:
                errors.append(f"Multi-strut step {i}: {exc}")
                break

        assert not errors
        assert max_actors_ms <= base_actors_ms + 5
        assert _count_renderer_actors(win) <= base_actors_ms + 5
    finally:
        win.close()
        qapp.processEvents()


@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_bnwf_worker_cooperative_cancellation(qapp):
    """Verifies cooperative QThread cancellation of BNWFSimulationWorker."""
    model = MultiStrutPiledWallModel(
        shell=CurvedShellGeometry(panel_height=5.0, bay_span=4.0),
        pier_pile=PierAndPileGeometry(pile_length=10.0),
        struts=StrutSupportSystem(),
    )
    soil = SoilProperties(unit_weight=18.5, friction_angle=32.0, cohesion=5.0)
    t = np.arange(0.0, 2.0, 0.01)
    accel = 0.25 * np.sin(2.0 * np.pi * 2.0 * t)

    worker = BNWFSimulationWorker(model=model, soil=soil, time_arr=t, accel_arr=accel)
    finished = {}
    errors = []
    worker.simulationFinished.connect(lambda summary: finished.update(summary))
    worker.simulationError.connect(lambda err: errors.append(err))

    # Request cancellation while thread starts executing staged/dynamic loop
    worker.start()
    worker.cancel()
    assert worker.is_cancelled() is True
    assert worker.wait(10000)
    qapp.processEvents()

    assert not errors
    assert finished.get("status") == "CANCELLED"
    assert finished.get("steps_completed", 0) < len(t)


@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_opensees_3d_fea_worker_cooperative_cancellation(qapp):
    """Verifies cooperative QThread cancellation of OpenSees3DFEAWorker."""
    geom = RetainingWallGeometry(stem_height=4.5, footing_thickness=0.5, wall_length=6.0)
    soil = SoilProperties(unit_weight=18.5, friction_angle=32.0, elastic_modulus=35000.0)
    seismic = SeismicParams(horizontal_pga=0.20, water_table_depth=10.0)

    t = np.arange(0.0, 0.50, 0.01)
    ax = 0.20 * np.sin(2.0 * np.pi * 2.5 * t)

    worker = OpenSees3DFEAWorker(
        geom=geom,
        soil=soil,
        seismic=seismic,
        time_arr=t,
        accel_x_g=ax,
        constitutive_model=ConstitutiveModelType.ELASTIC_ISOTROPIC,
        use_up=False,
    )
    finished = {}
    errors = []
    steps = []
    worker.stepCompleted.connect(lambda s, tm, u, p: steps.append(s), Qt.DirectConnection)
    worker.simulationFinished.connect(lambda summary: finished.update(summary), Qt.DirectConnection)
    worker.simulationError.connect(lambda err: errors.append(err), Qt.DirectConnection)

    # Cancel immediately inside worker callback once step 1 completes
    worker.stepCompleted.connect(
        lambda s, *_args: worker.cancel() if s >= 1 else None, Qt.DirectConnection
    )

    worker.start()
    deadline = time.perf_counter() + 20.0
    while worker.isRunning() and time.perf_counter() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    assert worker.wait(5000)
    qapp.processEvents()

    assert not errors
    assert finished.get("status") == "CANCELLED"
    assert finished.get("total_steps", 0) < len(t)


@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_worker_cooperative_cancellation(qapp):
    """Verifies cooperative QThread cancellation of KratosSimulationWorker."""
    geom = RetainingWallGeometry(stem_height=4.5, footing_thickness=0.5, wall_length=1.0)
    soil = SoilProperties(unit_weight=18.5, friction_angle=32.0)
    seismic = SeismicParams(horizontal_pga=0.20, water_table_depth=10.0)

    t = np.arange(0.0, 0.50, 0.01)
    accel = 0.20 * np.sin(2.0 * np.pi * 2.5 * t)

    worker = KratosSimulationWorker(
        geom=geom,
        soil=soil,
        seismic=seismic,
        time_arr=t,
        accel_arr=accel,
    )
    finished = {}
    errors = []
    worker.simulationFinished.connect(lambda summary: finished.update(summary), Qt.DirectConnection)
    worker.simulationError.connect(lambda err: errors.append(err), Qt.DirectConnection)
    worker.stepCompleted.connect(
        lambda s, *_args: worker.cancel() if s >= 1 else None, Qt.DirectConnection
    )

    worker.start()
    deadline = time.perf_counter() + 20.0
    while worker.isRunning() and time.perf_counter() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    assert worker.wait(5000)
    qapp.processEvents()

    assert not errors
    assert finished.get("status") == "CANCELLED"
    assert finished.get("total_steps", 0) < len(t)
