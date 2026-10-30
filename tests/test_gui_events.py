"""
GUI and widget event interaction tests (Phase 7, 8, & 10).
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from orang3d.gui.main_window import MainWindow
from orang3d.gui.panels import GeometryPanel, SoilPanel, SeismicPanel
from orang3d.gui.charts_2d import Charts2DWidget
from orang3d.models.wall_params import RetainingWallGeometry, SoilProperties, SeismicParams, AnalysisResults


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_geometry_panel_signals(qapp):
    panel = GeometryPanel()
    received = []
    panel.geometryChanged.connect(lambda g: received.append(g))

    panel.spin_height.setValue(7.5)

    assert len(received) > 0
    assert received[-1].stem_height == 7.5


def test_soil_panel_signals(qapp):
    panel = SoilPanel()
    received = []
    panel.soilChanged.connect(lambda s: received.append(s))

    panel.spin_phi.setValue(36.0)

    assert len(received) > 0
    assert received[-1].friction_angle == 36.0


def test_seismic_panel_signals(qapp):
    panel = SeismicPanel()
    received = []
    panel.seismicChanged.connect(lambda s: received.append(s))

    panel.spin_kh.setValue(0.35)

    assert len(received) > 0
    assert received[-1].horizontal_pga == 0.35


def test_charts_2d_metrics_update(qapp):
    charts = Charts2DWidget()
    results = AnalysisResults(
        fs_sliding=1.4,
        fs_overturning=2.2,
        fs_bearing=2.8,
        total_thrust=150.0,
        concrete_tensile_stress=1.8,
        cracking_predicted=False,
    )
    charts.update_safety_metrics(results)
    assert "1.40" in charts.lbl_fs_sliding.text()
    assert "2.20" in charts.lbl_fs_overturning.text()


def test_main_window_lifecycle(qapp):
    win = MainWindow()
    assert win.windowTitle().startswith("orang3D")
    assert win.results.fs_sliding > 0.0

    # Test playback toggle
    assert win.is_playing is False
    win._toggle_playback()
    assert win.is_playing is True
    win._toggle_playback()
    assert win.is_playing is False

    win.close()


def test_main_window_viewport_integration(qapp):
    win = MainWindow()
    assert win.viewport_3d.wall_actor is not None

    # Test scrubber step updating viewport
    win._on_scrubber_moved(5)
    assert win.playhead_idx == 5
    assert win.viewport_3d.wall_actor is not None

    # Test toggles from viewport toolbar in MainWindow
    win.viewport_3d.chk_wedge.setChecked(True)
    assert win.viewport_3d.wedge_actor is not None

    win.viewport_3d.chk_vectors.setChecked(True)
    assert win.viewport_3d.contact_vector_actor is not None
    assert win.viewport_3d.bearing_vector_actor is not None

    win.viewport_3d.combo_slice.setCurrentIndex(1) # X Cut
    assert win.viewport_3d.outline_actor is not None

    win.close()


def test_panels_set_methods(qapp):
    """Verifies that panels update their UI widgets and state when set_* is called."""
    geom_panel = GeometryPanel()
    soil_panel = SoilPanel()
    seismic_panel = SeismicPanel()

    new_geom = RetainingWallGeometry(stem_height=7.2, toe_length=1.4)
    geom_panel.set_geometry(new_geom)
    assert geom_panel.spin_height.value() == 7.2
    assert geom_panel.spin_toe.value() == 1.4

    new_soil = SoilProperties(friction_angle=38.0, allowable_bearing_capacity=420.0)
    soil_panel.set_soil(new_soil)
    assert soil_panel.spin_phi.value() == 38.0
    assert soil_panel.spin_q_allow.value() == 420.0

    new_seismic = SeismicParams(horizontal_pga=0.32, water_table_depth=2.5, liquefaction_factor=0.4)
    seismic_panel.set_seismic(new_seismic)
    assert round(seismic_panel.spin_kh.value(), 2) == 0.32
    assert seismic_panel.spin_water.value() == 2.5
    assert seismic_panel.slider_liq.value() == 40


def test_main_window_save_and_open_session(qapp, monkeypatch, tmp_path):
    """Verifies MainWindow session save and load through file dialog monkeypatch."""
    win = MainWindow()
    session_file = str(tmp_path / "gui_test_session.o3d")

    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.critical",
        lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.information",
        lambda *args, **kwargs: None
    )
    # Monkeypatch QFileDialog.getSaveFileName to return session_file
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (session_file, "orang3D Project Session (*.o3d)")
    )
    win._save_project()
    assert (tmp_path / "gui_test_session.o3d").exists()

    # Modify window geometry and reload
    win.panel_geom.spin_height.setValue(8.8)
    assert win.geom.stem_height == 8.8

    # Monkeypatch QFileDialog.getOpenFileName to return session_file
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (session_file, "orang3D Project Session (*.o3d)")
    )
    win._open_project()
    # It should have restored the saved height (default 6.0)
    assert win.geom.stem_height == 6.0
    assert win.panel_geom.spin_height.value() == 6.0

    win.close()


def test_app_main_entrypoint(monkeypatch):
    """Verifies orang3d.main entry point boots and creates MainWindow."""
    from orang3d.main import main
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.exec", lambda self: 0)
    monkeypatch.setattr("sys.exit", lambda code=0: None)
    main()


