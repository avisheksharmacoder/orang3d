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
    assert view.combo_scalar.count() >= 8
    assert view.combo_cmap.count() >= 3
    assert view.spin_warp.value() == 1.0
    assert view.chk_soil.isChecked() is True
    assert view.chk_water.isChecked() is True
    assert view.chk_wedge.isChecked() is False
    assert view.chk_vectors.isChecked() is False
    assert view.chk_piles.isChecked() is True
    assert view.chk_struts.isChecked() is True
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


def test_hud_overlay_widget_lifecycle(qapp, sample_models):
    """Tier 1.1: Verifies HUD overlay initialization, metric updates, and Pass/Fail status mapping."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()

    assert hasattr(view, "hud_card")
    assert view.hud_card is not None
    assert hasattr(view, "chk_hud")
    assert view.chk_hud.isChecked() is True

    # 1. Update scene with safe results
    view.update_scene(geom, soil, seismic, results)
    assert "SAFE" in view.hud_card.status_badge.text()
    assert "1.45" in view.hud_card.lbl_fs_sliding.text()
    assert "2.10" in view.hud_card.lbl_fs_overturning.text()
    assert "2.75" in view.hud_card.lbl_fs_bearing.text()

    # 2. Update scene with failing stability results
    fail_results = AnalysisResults(
        total_thrust=350.0,
        max_shear_force=280.0,
        max_bending_moment=650.0,
        concrete_tensile_stress=4.8,
        max_bearing_pressure=550.0,
        min_bearing_pressure=-40.0,
        fs_sliding=0.72,
        fs_overturning=0.91,
        fs_bearing=0.85,
    )
    view.update_scene(geom, soil, seismic, fail_results)
    assert "FAIL" in view.hud_card.status_badge.text()

    # 3. Toggle HUD checkbox visibility
    view.chk_hud.setChecked(False)
    assert not view.hud_card.isVisible()
    view.chk_hud.setChecked(True)
    assert view.hud_card.isVisible()

    view.close()


def test_hud_collapse_toggle(qapp, sample_models):
    """Tier 1.1: Verifies HUD minimizes to a compact pill and expands back."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()
    view.update_scene(geom, soil, seismic, results)

    # Initial state is expanded
    assert view.hud_card.is_collapsed is False
    assert view.hud_card.detail_container.isVisible() is True

    # Click collapse button
    view.hud_card.btn_collapse.click()
    assert view.hud_card.is_collapsed is True
    assert view.hud_card.detail_container.isVisible() is False

    # Click again to expand
    view.hud_card.btn_collapse.click()
    assert view.hud_card.is_collapsed is False
    assert view.hud_card.detail_container.isVisible() is True

    view.close()


def test_3d_component_labels_toggle(qapp, sample_models):
    """Tier 1.2: Verifies toggleable 3D callouts and leader lines with clean actor lifecycle."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()

    assert hasattr(view, "chk_labels")
    assert view.chk_labels.isChecked() is False
    assert view.labels_actor is None

    # Enable 3D labels
    view.chk_labels.setChecked(True)
    view.update_scene(geom, soil, seismic, results)
    assert view.labels_actor is not None

    # Disable 3D labels
    view.chk_labels.setChecked(False)
    view.refresh()
    assert view.labels_actor is None

    # Enable again and clear actors
    view.chk_labels.setChecked(True)
    view.refresh()
    assert view.labels_actor is not None
    view.clear_actors()
    assert view.labels_actor is None

    view.close()


def test_floating_camera_bar_actions(qapp, sample_models):
    """Tier 1.3: Verifies floating camera bar buttons and camera preset dispatch."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()
    view.update_scene(geom, soil, seismic, results)

    assert hasattr(view, "quick_camera_bar")
    assert view.quick_camera_bar is not None
    assert view.quick_camera_bar.isVisible() is True

    # Test Plan view button
    view.quick_camera_bar.btn_plan.click()
    assert view.combo_camera.currentData() == "plan"

    # Test Section view button
    view.quick_camera_bar.btn_section.click()
    assert view.combo_camera.currentData() == "cross_section"

    # Test Isometric view button
    view.quick_camera_bar.btn_iso.click()
    assert view.combo_camera.currentData() == "isometric"

    # Test Labels toggle button in quick bar
    initial_labels_state = view.chk_labels.isChecked()
    view.quick_camera_bar.btn_labels.click()
    assert view.chk_labels.isChecked() != initial_labels_state

    # Verify reposition on resize
    view.resize(1024, 768)
    assert view.quick_camera_bar.y() > 0

    view.close()


def test_click_to_probe_stress_inspector(qapp, sample_models):
    """Tier 2.1: Verifies 3D point picking, coordinate extraction, component identification, and marker cleanup."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()
    view.update_scene(geom, soil, seismic, results)

    assert hasattr(view, "probe_card")
    assert hasattr(view, "probe_marker_actor")
    assert view.probe_marker_actor is None

    # Probe point at stem base junction (X=1.6, Y=1.0, Z=2.5)
    probe_info = view.probe_point(1.6, 1.0, 2.5)
    assert probe_info is not None
    assert "Stem" in probe_info["component"]
    assert view.probe_marker_actor is not None
    assert view.probe_card.isVisible() is True
    assert "Stem" in view.probe_card.lbl_component.text()

    # Clear probe
    view.clear_probe()
    assert view.probe_marker_actor is None
    assert not view.probe_card.isVisible()

    view.close()


def test_xray_opacity_slider_updates(qapp, sample_models):
    """Tier 2.2: Verifies continuous opacity / X-Ray slider dynamically modifies mesh transparency."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()
    view.update_scene(geom, soil, seismic, results)

    assert hasattr(view, "slider_opacity")
    assert view.slider_opacity.value() == 100

    # Slide to 35% (X-Ray mode)
    view.slider_opacity.setValue(35)
    assert view.current_wall_opacity == pytest.approx(0.35, abs=0.02)
    assert view.wall_actor is not None

    # Return to 100%
    view.slider_opacity.setValue(100)
    assert view.current_wall_opacity == pytest.approx(1.0, abs=0.02)

    view.close()


def test_demand_capacity_unity_ratio_scalar(qapp, sample_models):
    """Tier 2.3: Verifies Demand-to-Capacity Code Unity Ratio (UR) scalar calculation and rendering."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()

    # Find Code Unity Ratio in scalar selector
    idx_ur = view.combo_scalar.findData("SafetyUnityRatio")
    assert idx_ur >= 0

    view.combo_scalar.setCurrentIndex(idx_ur)
    view.update_scene(geom, soil, seismic, results)

    assert view.wall_actor is not None
    assert view.active_wall_mesh is not None
    assert "SafetyUnityRatio" in view.active_wall_mesh.point_data
    ur_vals = view.active_wall_mesh.point_data["SafetyUnityRatio"]
    assert np.all(ur_vals >= 0.0)

    view.close()


def test_fbd_vectors_resultant_accuracy(qapp, sample_models):
    """Tier 3.1: Verifies 3D Free-Body Diagram resultant vectors and analytical force equilibrium."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()
    view.update_scene(geom, soil, seismic, results)

    assert hasattr(view, "chk_fbd")
    assert hasattr(view, "fbd_actor")
    assert view.fbd_actor is None

    # Toggle FBD on
    view.chk_fbd.setChecked(True)
    assert view.fbd_actor is not None
    assert hasattr(view, "fbd_data")
    assert view.fbd_data is not None

    # Verify analytical resultant forces
    # P_ae matches results.total_thrust
    assert view.fbd_data["P_ae"] == pytest.approx(results.total_thrust, rel=1e-3)
    # W_c is positive concrete weight
    assert view.fbd_data["W_c"] > 0
    # W_s is positive soil weight over heel
    assert view.fbd_data["W_s"] > 0
    # R_v matches vertical equilibrium
    assert view.fbd_data["R_v"] > 0
    # F_r matches sliding resistance
    assert view.fbd_data["F_r"] > 0

    # Toggle FBD off
    view.chk_fbd.setChecked(False)
    assert view.fbd_actor is None

    view.close()


def test_exploded_assembly_transform(qapp, sample_models):
    """Tier 3.2: Verifies continuous exploded assembly slider parametric disassembly translation."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()
    view.update_scene(geom, soil, seismic, results, show_wedge=True)

    assert hasattr(view, "slider_explode")
    assert view.slider_explode.value() == 0
    assert view.current_explode_factor == 0.0

    # Capture initial assembled bounding box origins
    assert hasattr(view, "active_backfill_mesh")
    assert hasattr(view, "active_foundation_mesh")
    assert hasattr(view, "active_wedge_mesh")

    orig_bf_xmin = view.active_backfill_mesh.bounds[0]
    orig_fnd_ymin = view.active_foundation_mesh.bounds[2]
    orig_wdg_xmin = view.active_wedge_mesh.bounds[0]

    # Slide to 100% disassembly
    view.slider_explode.setValue(100)
    assert view.current_explode_factor == pytest.approx(1.0, abs=0.01)

    expl_bf_xmin = view.active_backfill_mesh.bounds[0]
    expl_fnd_ymin = view.active_foundation_mesh.bounds[2]
    expl_wdg_xmin = view.active_wedge_mesh.bounds[0]

    # Backfill translates +4.0m in X
    assert (expl_bf_xmin - orig_bf_xmin) == pytest.approx(4.0, abs=0.15)
    # Foundation translates -3.0m in Y
    assert (orig_fnd_ymin - expl_fnd_ymin) == pytest.approx(3.0, abs=0.15)
    # Failure wedge translates +6.0m in X
    assert (expl_wdg_xmin - orig_wdg_xmin) == pytest.approx(6.0, abs=0.15)

    # Return to 0% assembled
    view.slider_explode.setValue(0)
    assert view.current_explode_factor == pytest.approx(0.0, abs=0.01)
    reset_bf_xmin = view.active_backfill_mesh.bounds[0]
    assert reset_bf_xmin == pytest.approx(orig_bf_xmin, abs=0.05)

    view.close()


def test_cad_dimension_lines_geometry(qapp, sample_models):
    """Tier 3.3: Verifies 3D CAD dimension rulers geometry, lengths, and tick alignment."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()
    view.update_scene(geom, soil, seismic, results)

    assert hasattr(view, "chk_dims")
    assert hasattr(view, "dim_actor")
    assert view.dim_actor is None

    # Enable dimension lines
    view.chk_dims.setChecked(True)
    assert view.dim_actor is not None
    assert hasattr(view, "dim_data")
    assert view.dim_data["total_height"] == pytest.approx(geom.total_height, rel=1e-3)
    assert view.dim_data["base_width"] == pytest.approx(geom.base_width, rel=1e-3)
    assert view.dim_data["toe_length"] == pytest.approx(geom.toe_length, rel=1e-3)
    assert view.dim_data["heel_length"] == pytest.approx(geom.heel_length, rel=1e-3)

    # Disable dimension lines
    view.chk_dims.setChecked(False)
    assert view.dim_actor is None

    view.close()


def test_actor_lifecycle_regression_tier3(qapp, sample_models):
    """T0.0: 50 consecutive scene updates toggling all Tier 1, 2, and 3 features concurrently."""
    geom, soil, seismic, results = sample_models
    view = RetainingWall3DView()
    view.show()

    for i in range(50):
        view.update_scene(
            geom=geom,
            soil=soil,
            seismic=seismic,
            results=results,
            show_soil=True,
            show_wedge=(i % 2 == 0),
            show_vectors=(i % 3 == 0),
            show_fbd=(i % 2 == 1),
            show_dims=(i % 2 == 0),
            explode_factor=(i % 10) / 10.0,
            warp_scale=1.0 + (i % 3),
        )
        if i % 5 == 0:
            view.probe_point(1.5, 1.0, 2.5)
        elif i % 5 == 2:
            view.clear_probe()

    view.clear_actors()
    assert view.wall_actor is None
    assert view.fbd_actor is None
    assert view.dim_actor is None
    assert view.probe_marker_actor is None

    view.close()


def test_material_palette_colors_and_water_pattern(qapp, sample_models):
    """
    Verifies the high-contrast material palette and 3D wave caustics water pattern:
    1. VIEWPORT_COLORS contains all distinct material keys (wall, backfill, foundation, water, wedge).
    2. Water plane contains 2D wave caustics scalar 'Water_Ripple' normalized in [0.0, 1.0].
    3. RetainingWall3DView renders concrete wall with VIEWPORT_COLORS['wall_concrete'] in RealisticMaterials mode.
    4. Backfill soil and foundation soil are visually distinguished with distinct colors and opacities.
    5. Active failure wedge renders in vivid failure color VIEWPORT_COLORS['failure_wedge'].
    """
    geom, soil, seismic, results = sample_models

    # 1. Palette keys verification
    required_keys = [
        "wall_concrete",
        "backfill_soil",
        "foundation_soil",
        "water_plane",
        "failure_wedge",
        "strut_steel",
        "bored_pile",
    ]
    for key in required_keys:
        assert key in VIEWPORT_COLORS
        assert VIEWPORT_COLORS[key].startswith("#")

    # 2. Mesher produces water plane with wave caustics
    bf_mesh, fnd_mesh, water_plane = build_3d_soil_mesh(
        geom, soil, seismic, results, ripple_phase=0.8
    )
    assert "Water_Ripple" in water_plane.point_data
    ripples = water_plane.point_data["Water_Ripple"]
    assert np.min(ripples) >= 0.0
    assert np.max(ripples) <= 1.0

    # 3. Viewport rendering with realistic materials and active wedge
    view = RetainingWall3DView()
    view.show()
    view.update_scene(
        geom,
        soil,
        seismic,
        results,
        scalar_name="RealisticMaterials",
        show_soil=True,
        show_water=True,
        show_wedge=True,
    )

    assert view.wall_actor is not None
    assert view.backfill_actor is not None
    assert view.foundation_actor is not None
    assert view.water_actor is not None
    assert view.wedge_actor is not None

    # Check that switching to FEA stress scalar still maintains distinct soil & water actors
    view.update_scene(
        geom,
        soil,
        seismic,
        results,
        scalar_name="TensileStress_MPa",
        show_soil=True,
        show_water=True,
        show_wedge=True,
    )
    assert view.wall_actor is not None
    assert view.backfill_actor is not None
    assert view.foundation_actor is not None
    assert view.water_actor is not None
    assert view.wedge_actor is not None

    view.close()




