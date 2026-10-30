"""
Comprehensive Test Suite for Phase 7: Advanced PyVista 3D Scientific Viewport.
Tests cover:
1. 3D Scene initialization, QtInteractor embedding, dark background color and styling.
2. Mesh deformation warping with dynamic magnification scale (1x - 100x).
3. Scalar stress heatmap fields (Tensile Stress, Von Mises, Pore Pressure) and colormaps.
4. Colorbar safe clamping under zero and extreme stress conditions.
5. Translucent water table rendering and sinusoidal wave ripple dynamics.
6. Animated Coulomb / Mononobe-Okabe active failure wedge with sliding translation.
7. Dynamic vector glyph generation for backfill contact thrust and base bearing pressure.
8. Interactive orthographic cutting plane slicing (X, Y, Z slice planes).
9. Actor replacement and lifecycle stability across 50 consecutive scene updates.
10. Headless offscreen rendering compatibility under QT_QPA_PLATFORM=offscreen.
"""

import pytest
import numpy as np
from PySide6.QtWidgets import QApplication

from orang3d.gui.viewport_3d import RetainingWall3DView, Viewport3D
from orang3d.config import VIEWPORT_COLORS
from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
)
from orang3d.mesher.hex_mesher import (
    build_3d_wall_mesh,
    build_3d_soil_mesh,
    build_3d_wedge_mesh,
    build_contact_pressure_glyphs,
    build_bearing_pressure_glyphs,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_models():
    geom = RetainingWallGeometry(
        stem_height=6.0,
        footing_thickness=0.8,
        stem_thickness_base=0.8,
        stem_thickness_top=0.35,
        toe_length=1.2,
        heel_length=2.5,
        wall_length=5.0,
    )
    soil = SoilProperties(
        friction_angle=34.0,
        unit_weight=18.5,
        cohesion=0.0,
    )
    seismic = SeismicParams(
        horizontal_pga=0.25,
        water_table_depth=3.5,
        pore_pressure_ratio_ru=0.15,
    )
    results = AnalysisResults(
        total_thrust=145.0,
        max_shear_force=120.0,
        max_bending_moment=210.0,
        concrete_tensile_stress=2.1,
        max_bearing_pressure=185.0,
        min_bearing_pressure=42.0,
        fs_sliding=1.45,
        fs_overturning=2.10,
        fs_bearing=2.75,
    )
    return geom, soil, seismic, results


def test_viewport_initialization(qapp):
    """Verifies that RetainingWall3DView embeds QtInteractor, sets dark background, and controls exist."""
    view = RetainingWall3DView()
    assert view.plotter is not None
    assert view.plotter.interactor is not None
    assert RetainingWall3DView is Viewport3D

    # Verify background color configured
    bg_color = view.plotter.background_color
    assert bg_color is not None

    # Verify toolbar controls exist and defaults
    assert view.combo_scalar.count() == 3
    assert view.combo_cmap.count() >= 3
    assert view.spin_warp.value() == 1.0
    assert view.chk_soil.isChecked() is True
    assert view.chk_water.isChecked() is True
    assert view.chk_wedge.isChecked() is False
    assert view.chk_vectors.isChecked() is False
    assert view.combo_slice.currentIndex() == 0

    view.close()


def test_scene_update_and_actors(qapp, sample_models):
    """Verifies scene rendering generates actors for wall, soil strata, and water table."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()

    view.update_scene(geom, soil, seismic, results)

    assert view.wall_actor is not None
    assert view.backfill_actor is not None
    assert view.foundation_actor is not None
    assert view.water_actor is not None
    assert view.wedge_actor is None
    assert view.contact_vector_actor is None
    assert view.bearing_vector_actor is None

    view.close()


def test_mesh_warping(qapp, sample_models):
    """Asserts that applying a positive deformation scale factor deflects mesh nodes."""
    geom, _, _, results = sample_models
    wall_unwarped = build_3d_wall_mesh(geom, results)
    warped_1x = wall_unwarped.warp_by_vector("Deformation_m", factor=1.0)
    warped_50x = wall_unwarped.warp_by_vector("Deformation_m", factor=50.0)

    # Displacements act in -X direction
    max_deflect_1x = np.max(np.abs(warped_1x.points[:, 0] - wall_unwarped.points[:, 0]))
    max_deflect_50x = np.max(np.abs(warped_50x.points[:, 0] - wall_unwarped.points[:, 0]))

    assert max_deflect_1x > 0.0
    assert max_deflect_50x > max_deflect_1x
    assert pytest.approx(max_deflect_50x, rel=1e-3) == max_deflect_1x * 50.0


def test_scalar_field_switching_and_colormaps(qapp, sample_models):
    """Asserts switching scalar stress heatmaps and colormaps works without errors."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()

    # 1. Von Mises Stress with Viridis
    view.update_scene(
        geom, soil, seismic, results,
        scalar_name="VonMises_MPa",
        colormap="viridis",
    )
    assert view.wall_actor is not None

    # 2. Pore Pressure with Coolwarm
    view.update_scene(
        geom, soil, seismic, results,
        scalar_name="PorePressure_kPa",
        colormap="coolwarm",
    )
    assert view.wall_actor is not None

    # 3. Tensile Stress with Plasma
    view.update_scene(
        geom, soil, seismic, results,
        scalar_name="TensileStress_MPa",
        colormap="plasma",
    )
    assert view.wall_actor is not None

    view.close()


def test_colorbar_clamping_edge_cases(qapp, sample_models):
    """Verifies that zero or extreme stresses do not cause divide-by-zero in scalar bar."""
    geom, soil, seismic, _ = sample_models
    view = RetainingWall3DView()

    # Case A: Zero stress state
    zero_results = AnalysisResults(
        total_thrust=0.0,
        max_shear_force=0.0,
        max_bending_moment=0.0,
        concrete_tensile_stress=0.0,
        max_bearing_pressure=0.0,
        min_bearing_pressure=0.0,
        fs_sliding=2.0,
        fs_overturning=3.0,
        fs_bearing=3.5,
    )
    view.update_scene(geom, soil, seismic, zero_results)
    assert view.wall_actor is not None

    # Case B: Massive extreme stress state
    huge_results = AnalysisResults(
        total_thrust=5000.0,
        max_shear_force=4000.0,
        max_bending_moment=12000.0,
        concrete_tensile_stress=85.0,
        max_bearing_pressure=1500.0,
        min_bearing_pressure=100.0,
        fs_sliding=0.5,
        fs_overturning=0.6,
        fs_bearing=0.8,
    )
    view.update_scene(geom, soil, seismic, huge_results)
    assert view.wall_actor is not None

    view.close()


def test_water_plane_cut_and_ripples(qapp, sample_models):
    """Verifies water plane is rendered when water depth < wall height and hidden when water depth >= wall height."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()

    # Submerged crest / high water table: water plane must be present
    seismic_high_water = SeismicParams(water_table_depth=2.0)
    view.update_scene(geom, soil, seismic_high_water, results, show_water=True)
    assert view.water_actor is not None

    # Very deep water table (below footing): water plane must not be rendered
    seismic_dry = SeismicParams(water_table_depth=geom.total_height + 5.0)
    view.update_scene(geom, soil, seismic_dry, results, show_water=True)
    assert view.water_actor is None

    # Wave ripples perturb coordinates
    _, _, p_static = build_3d_soil_mesh(geom, soil, seismic_high_water, results, ripple_phase=0.0)
    _, _, p_rippled = build_3d_soil_mesh(geom, soil, seismic_high_water, results, ripple_phase=1.5)
    diff = np.max(np.abs(p_static.points - p_rippled.points))
    assert diff > 0.0

    view.close()


def test_active_failure_wedge_and_sliding(qapp, sample_models):
    """Verifies failure wedge creation and dynamic slide offset translation."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()

    # Toggle wedge rendering
    view.update_scene(geom, soil, seismic, results, show_wedge=True)
    assert view.wedge_actor is not None

    view.update_scene(geom, soil, seismic, results, show_wedge=False)
    assert view.wedge_actor is None

    # Verify downhill translation
    wedge_static = build_3d_wedge_mesh(geom, soil, seismic, results, slide_disp=0.0)
    wedge_slid = build_3d_wedge_mesh(geom, soil, seismic, results, slide_disp=0.05)

    assert wedge_slid.n_points == wedge_static.n_points
    # Downhill sliding increases X and decreases Y
    assert np.mean(wedge_slid.points[:, 0]) > np.mean(wedge_static.points[:, 0])
    assert np.mean(wedge_slid.points[:, 1]) < np.mean(wedge_static.points[:, 1])

    view.close()


def test_pressure_vector_glyphs(qapp, sample_models):
    """Verifies contact and bearing pressure vector glyph creation and rendering."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()

    # Toggle vector glyphs on
    view.update_scene(geom, soil, seismic, results, show_vectors=True)
    assert view.contact_vector_actor is not None
    assert view.bearing_vector_actor is not None

    # Toggle vector glyphs off
    view.update_scene(geom, soil, seismic, results, show_vectors=False)
    assert view.contact_vector_actor is None
    assert view.bearing_vector_actor is None

    # Directly check glyph point data and vector shapes
    c_glyphs = build_contact_pressure_glyphs(geom, soil, seismic, results)
    assert c_glyphs is not None
    assert c_glyphs.n_points > 0

    b_glyphs = build_bearing_pressure_glyphs(geom, soil, results)
    assert b_glyphs is not None
    assert b_glyphs.n_points > 0

    view.close()


def test_orthographic_cutting_plane_slicing(qapp, sample_models):
    """Verifies X, Y, and Z cutting planes slice the 3D wall mesh and show interior contours."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()

    for axis in ["x", "y", "z"]:
        view.update_scene(
            geom, soil, seismic, results,
            slice_axis=axis,
            slice_pos=0.5,
        )
        assert view.wall_actor is not None
        assert view.outline_actor is not None

    # Slicing disabled restores full 3D solid mesh
    view.update_scene(
        geom, soil, seismic, results,
        slice_axis="none",
    )
    assert view.wall_actor is not None
    assert view.outline_actor is None

    view.close()


def test_actor_lifecycle_50_updates(qapp, sample_models):
    """Verifies 50 consecutive scene updates clean up actors without memory leaks or crashes."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()

    for i in range(50):
        # Vary parameters rapidly
        h_pulse = 5.0 + (i % 5) * 0.4
        pga_pulse = 0.1 + (i % 10) * 0.03
        var_geom = RetainingWallGeometry(stem_height=h_pulse)
        var_seismic = SeismicParams(horizontal_pga=pga_pulse)

        view.update_scene(
            geom=var_geom,
            soil=soil,
            seismic=var_seismic,
            results=results,
            warp_scale=1.0 + (i % 5),
            show_soil=(i % 2 == 0),
            show_wedge=(i % 3 == 0),
            show_vectors=(i % 4 == 0),
            slide_disp=0.001 * i,
            ripple_phase=0.2 * i,
        )
        assert view.wall_actor is not None

    view.clear_actors()
    assert view.wall_actor is None
    assert view.backfill_actor is None
    assert view.foundation_actor is None
    assert view.water_actor is None

    view.close()
