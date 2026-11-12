"""
Tests for Phase 8: Site Topography Importer, Light Studio Theme, Camera Presets,
4K Viewport Snapshots, and Interactive Sizing Advisor.
"""

from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from PySide6.QtWidgets import QApplication

from orang3d.config import RegionalStandard, ThemeMode, THEME_LIGHT, VIEWPORT_COLORS, get_safety_thresholds
from orang3d.gui.main_window import MainWindow
from orang3d.mesher.terrain import (
    TerrainRaster,
    generate_synthetic_slope,
    write_ascii_grid,
)
from orang3d.models.wall_params import RetainingWallGeometry, SeismicParams, SoilProperties
from orang3d.physics.sizing_advisor import evaluate_sizing_advisor
from orang3d.physics.stability import evaluate_wall_stability


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_sizing_advisor_repairs_failing_wall_to_pass():
    # Intentionally undersized wall under seismic load -> fails sliding, overturning, bearing & tension
    bad_geom = RetainingWallGeometry(
        stem_height=6.5,
        stem_thickness_top=0.25,
        stem_thickness_base=0.35,
        footing_thickness=0.40,
        toe_length=0.40,
        heel_length=1.00,
    )
    soil = SoilProperties(unit_weight=19.5, friction_angle=30.0, allowable_bearing_capacity=220.0)
    seismic = SeismicParams(horizontal_pga=0.22, vertical_pga=0.05, water_table_depth=12.0)

    advice = evaluate_sizing_advisor(
        geom=bad_geom,
        soil=soil,
        seismic=seismic,
        standard=RegionalStandard.STANDARD,
    )
    assert not advice.all_checks_passing
    assert len(advice.recommendations) >= 1
    assert any("heel" in msg.lower() or "stem" in msg.lower() or "toe" in msg.lower() for msg in advice.summary_lines)

    # Applying recommended geometry must pass all seismic thresholds
    thresh = get_safety_thresholds(RegionalStandard.STANDARD)
    applied = evaluate_wall_stability(advice.recommended_geom, soil, seismic)
    assert applied.fs_sliding >= thresh["sliding_seismic"]
    assert applied.fs_overturning >= thresh["overturning_seismic"]
    assert applied.fs_bearing >= thresh["bearing_seismic"]
    assert not applied.cracking_predicted

    # Re-running advisor on the fixed geometry reports all checks passing
    advice_ok = evaluate_sizing_advisor(advice.recommended_geom, soil, seismic)
    assert advice_ok.all_checks_passing


def test_asc_csv_obj_terrain_loading_and_draped_ui(qapp, tmp_path: Path):
    # 1. Create sample ESRI .asc grid (steep ~25 deg slope -> S_T == 1.2)
    asc_path = tmp_path / "hillside_slope.asc"
    synth = generate_synthetic_slope(
        slope_type="planar", length_x=30.0, width_y=20.0, resolution=2.0, slope_angle_deg=25.0
    )
    write_ascii_grid(str(asc_path), synth)

    # 2. Create XYZ .csv survey point cloud with comma separators and header
    csv_path = tmp_path / "survey_cloud.csv"
    xs = np.linspace(0.0, 24.0, 9)
    ys = np.linspace(0.0, 16.0, 7)
    lines = ["X,Y,Z"]
    for yv in ys:
        for xv in xs:
            zv = 100.0 + xv * np.tan(np.radians(22.0))
            lines.append(f"{xv:.2f},{yv:.2f},{zv:.3f}")
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    # 3. Create minimal Wavefront .obj terrain surface
    obj_path = tmp_path / "site_mesh.obj"
    obj_lines = ["# Wavefront OBJ terrain"]
    for yv in ys[:5]:
        for xv in xs[:5]:
            zv = xv * 0.45
            obj_lines.append(f"v {xv:.2f} {yv:.2f} {zv:.3f}")
    obj_path.write_text("\n".join(obj_lines), encoding="utf-8")

    window = MainWindow()
    try:
        # Load .asc via TerrainAndStudioPanel -> renders draped terrain & contours in Viewport3D
        r_asc = window.panel_terrain.load_terrain_from_path(str(asc_path))
        assert isinstance(r_asc, TerrainRaster)
        qapp.processEvents()
        assert window.viewport_3d.terrain_actor is not None
        assert window.viewport_3d.terrain_contour_actor is not None
        assert window.panel_terrain.mean_slope_deg == pytest.approx(25.0, abs=1.0)
        assert 1.05 < window.panel_terrain.st_factor <= 1.25
        assert window.panel_terrain.current_cut_profile is not None
        assert len(window.panel_terrain.current_cut_profile.retained_heights_m) == 5

        # Load .csv point cloud
        r_csv = window.panel_terrain.load_terrain_from_path(str(csv_path))
        assert isinstance(r_csv, TerrainRaster)
        assert window.panel_terrain.mean_slope_deg == pytest.approx(22.0, abs=1.5)
        assert "22." in window.panel_terrain.lbl_terrain_info.text()

        # Load .obj surface
        r_obj = window.panel_terrain.load_terrain_from_path(str(obj_path))
        assert isinstance(r_obj, TerrainRaster)
        assert window.viewport_3d.terrain_actor is not None
    finally:
        window.close()
        qapp.processEvents()


def test_studio_theme_camera_presets_4k_snapshot_and_apply_advisor(qapp, tmp_path: Path):
    window = MainWindow()
    try:
        # 1. Theme toggle: Dark Engineering <-> Light Studio
        assert window.theme_mode == ThemeMode.DARK
        window.set_theme_mode(ThemeMode.LIGHT)
        qapp.processEvents()
        assert window.theme_mode == ThemeMode.LIGHT
        assert window.viewport_3d.theme_mode == ThemeMode.LIGHT
        assert THEME_LIGHT["background_dark"] in window.styleSheet()
        bg_light = window.viewport_3d.plotter.background_color
        assert bg_light.float_rgb[0] > 0.90  # Crisp studio light background

        window.set_theme_mode(ThemeMode.DARK)
        qapp.processEvents()
        assert window.theme_mode == ThemeMode.DARK
        bg_dark = window.viewport_3d.plotter.background_color
        assert bg_dark.float_rgb[0] < 0.20

        # 2. Camera presets move camera to distinct projections
        cam_positions = {}
        for preset in ("isometric", "plan", "front", "cross_section"):
            window.viewport_3d.set_camera_preset(preset)
            pos = tuple(round(v, 3) for v in window.viewport_3d.plotter.camera.position)
            cam_positions[preset] = pos
        assert len(set(cam_positions.values())) >= 3

        # 3. 4K high-res snapshot export produces a valid 3840x2160 PNG
        png_path = tmp_path / "studio_render_4k.png"
        out = window.viewport_3d.save_high_res_snapshot(str(png_path), width=3840, height=2160)
        assert Path(out).exists()
        with Image.open(out) as im:
            assert im.size == (3840, 2160)

        # 4. Interactive Sizing Advisor 1-click apply inside MainWindow repairs an unsafe wall
        window.panel_geom.spin_height.setValue(8.0)
        window.panel_geom.spin_heel.setValue(0.8)
        window.panel_geom.spin_toe.setValue(0.4)
        qapp.processEvents()
        assert window.last_sizing_advice is not None
        assert not window.last_sizing_advice.all_checks_passing
        assert window.panel_terrain.btn_apply_advice.isEnabled()

        window.panel_terrain.btn_apply_advice.click()
        qapp.processEvents()
        assert window.last_sizing_advice.all_checks_passing
    finally:
        window.close()
        qapp.processEvents()
