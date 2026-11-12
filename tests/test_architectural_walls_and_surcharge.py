"""
Tests for Phase 7: Architectural Wall Morphologies & Adjacent Building Surcharges.

Verifies:
  1. Strictly positive hex Jacobian determinants (det(J) > 0) for stepped, corner
     (at 60°, 90°, 135°), counterfort/buttress, curved-plan (concave & convex),
     MSE/Gabion/Crib meshes, and 3D surcharge footing blocks.
  2. Boussinesq lateral surcharge thrust monotonically increases as setback x_f -> 0
     across uniform strip, building strip footing, and isolated 3D pad footing modes.
  3. Integrated vertical/lateral equilibrium matching exact closed-form Flamant strip
     integral & trapezoidal moment integration.
  4. Architectural solvers: inter-tier interference, 3D FEA corner stiffening, two-way
     counterfort slab bending, curved-plan hoop action, and MSE pullout/rupture checks.
  5. Offscreen Qt MainWindow & Viewport3D translucent surcharge / architectural rendering
     plus SI <-> Imperial unit parity.
"""

from __future__ import annotations

import math
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from orang3d.gui.main_window import MainWindow
from orang3d.gui.panels.arch_wall_panel import ArchWallAndSurchargePanel
from orang3d.mesher.arch_wall_mesher import (
    build_architectural_wall_mesh,
    build_corner_wingwall_mesh,
    build_counterfort_wall_mesh,
    build_curved_plan_wall_mesh,
    build_mse_gabion_wall_mesh,
    build_stepped_terraced_wall_mesh,
    build_surcharge_3d_meshes,
    verify_arch_mesh_jacobians,
)
from orang3d.models.advanced_wall_params import WallSystemMode
from orang3d.models.architectural_wall_params import (
    ArchWallMorphology,
    ArchitecturalWallSpec,
    CornerWingwallParams,
    CounterfortWallParams,
    CurvedPlanWallParams,
    MSEGabionWallParams,
    SteppedTerracedWallParams,
)
from orang3d.models.wall_params import RetainingWallGeometry, SeismicParams, SoilProperties
from orang3d.physics.arch_wall_solver import (
    evaluate_architectural_wall,
    evaluate_corner_wingwall,
    evaluate_counterfort_wall,
    evaluate_curved_plan_wall,
    evaluate_mse_gabion_wall,
    evaluate_stepped_terraced_wall,
)
from orang3d.physics.stability import evaluate_wall_stability
from orang3d.physics.surcharge import (
    AdjacentSurchargeParams,
    SurchargeLoadType,
    calculate_adjacent_surcharge_profile,
    evaluate_wall_stability_with_surcharge,
)
from orang3d.units import M_TO_FT, UnitSystem


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_all_architectural_meshes_have_strictly_positive_jacobians():
    # Stepped (2, 3, and 4 tiers)
    for tiers in (2, 3, 4):
        g_step = build_stepped_terraced_wall_mesh(SteppedTerracedWallParams(num_tiers=tiers))
        ok, min_j = verify_arch_mesh_jacobians(g_step)
        assert ok, f"Stepped {tiers}-tier mesh had non-positive Jacobian: {min_j}"

    # L-Corner & Angled Wingwall across valid [60°, 150°] range
    for ang in (60.0, 90.0, 120.0, 145.0):
        g_cor = build_corner_wingwall_mesh(CornerWingwallParams(corner_angle_deg=ang))
        ok, min_j = verify_arch_mesh_jacobians(g_cor)
        assert ok, f"Corner wingwall ({ang} deg) had non-positive Jacobian: {min_j}"
        assert 2 in set(g_cor.cell_data["Element_Type"].tolist())  # 3D corner stiffener present

    # Counterfort & Front Buttress
    for is_but in (False, True):
        g_cf = build_counterfort_wall_mesh(CounterfortWallParams(is_buttress=is_but))
        ok, min_j = verify_arch_mesh_jacobians(g_cf)
        assert ok, f"Counterfort (is_buttress={is_but}) had non-positive Jacobian: {min_j}"

    # Curved Plan-View (both concave and convex)
    for concave in (True, False):
        g_cp = build_curved_plan_wall_mesh(CurvedPlanWallParams(concave_to_backfill=concave))
        ok, min_j = verify_arch_mesh_jacobians(g_cp)
        assert ok, f"Curved plan (concave={concave}) had non-positive Jacobian: {min_j}"

    # MSE / Gabion / Crib
    for sub in ("mse_geogrid", "gabion", "crib"):
        g_mse = build_mse_gabion_wall_mesh(MSEGabionWallParams(wall_subtype=sub))
        ok, min_j = verify_arch_mesh_jacobians(g_mse)
        assert ok, f"MSE ({sub}) had non-positive Jacobian: {min_j}"


def test_boussinesq_surcharge_monotonicity_and_equilibrium():
    wall_h = 6.0
    soil = SoilProperties(unit_weight=19.0, friction_angle=32.0)
    seis_static = SeismicParams(horizontal_pga=0.0, vertical_pga=0.0, water_table_depth=12.0)
    seis_dyn = SeismicParams(horizontal_pga=0.22, vertical_pga=0.05, water_table_depth=12.0)

    # 1. Monotonic increase in lateral thrust as setback x_f -> 0 for strip & pad footings
    setbacks = [5.0, 3.0, 1.5, 0.6, 0.15]
    for ltype in (
        SurchargeLoadType.UNIFORM_TRAFFIC,
        SurchargeLoadType.BUILDING_STRIP_FOOTING,
        SurchargeLoadType.BUILDING_PAD_FOOTING,
    ):
        thrusts = []
        for xf in setbacks:
            p = AdjacentSurchargeParams(
                load_type=ltype,
                uniform_q_kpa=25.0,
                building_load_kn=500.0,
                footing_width_m=2.0,
                footing_length_m=3.0,
                setback_m=xf,
                embedment_m=0.5,
            )
            res = calculate_adjacent_surcharge_profile(p, wall_h, soil, seis_static)
            thrusts.append(res.total_thrust_kn_per_m)

            # Numerical equilibrium check:
            # integral sigma_h(z) dz == total_thrust & integral sigma_h(z) * (H - z) dz == total_thrust * y_bar
            z_arr = np.asarray(res.depths_m, dtype=float)
            e_arr = np.asarray(res.elevations_m, dtype=float)
            sig_arr = np.asarray(res.sigma_h_total_kpa, dtype=float)
            p_check = float(np.trapezoid(sig_arr, z_arr))
            m_check = float(np.trapezoid(sig_arr * e_arr, z_arr))
            assert p_check == pytest.approx(res.total_thrust_kn_per_m, rel=1e-4)
            assert m_check == pytest.approx(res.moment_about_base_knm_per_m, rel=1e-4)
            if res.total_thrust_kn_per_m > 1e-3:
                assert m_check == pytest.approx(res.total_thrust_kn_per_m * res.resultant_elevation_m, rel=1e-3)

        assert all(t2 > t1 for t1, t2 in zip(thrusts, thrusts[1:])), (
            f"Expected strictly increasing thrust as setback -> 0 for {ltype}: {thrusts}"
        )

    # 2. Closed-form Terzaghi-Spangler rigid-wall strip check:
    # A very thin strip (line load Q_line at x0, Df=0) integrates to (2 * Q_line / pi) * H^2 / (x0^2 + H^2)
    x0 = 2.0
    b_thin = 0.02
    q_line = 100.0
    thin_params = AdjacentSurchargeParams(
        load_type=SurchargeLoadType.UNIFORM_TRAFFIC,
        uniform_q_kpa=q_line / b_thin,
        footing_width_m=b_thin,
        setback_m=x0,
        embedment_m=0.0,
    )
    thin_res = calculate_adjacent_surcharge_profile(
        thin_params, wall_h, soil, seis_static, num_eval_points=401
    )
    analytical_thrust = (2.0 * q_line / math.pi) * ((wall_h ** 2) / (x0 ** 2 + wall_h ** 2))
    assert thin_res.total_thrust_kn_per_m == pytest.approx(analytical_thrust, rel=0.01)

    # 3. Seismic inertial increment + combined wall stability check
    bld = AdjacentSurchargeParams(
        load_type=SurchargeLoadType.BUILDING_STRIP_FOOTING,
        building_load_kn=600.0,
        footing_width_m=2.0,
        footing_length_m=4.0,
        setback_m=1.2,
        embedment_m=0.8,
    )
    dyn_res = calculate_adjacent_surcharge_profile(bld, wall_h, soil, seis_dyn)
    assert dyn_res.seismic_increment_kn_per_m > 0.0
    assert dyn_res.total_thrust_kn_per_m > dyn_res.static_thrust_kn_per_m

    geom = RetainingWallGeometry(stem_height=5.4, heel_length=1.0, footing_thickness=0.6)
    base_only = evaluate_wall_stability(geom, soil, seis_dyn)
    with_sur, sur_res = evaluate_wall_stability_with_surcharge(geom, soil, seis_dyn, bld)
    assert sur_res is not None
    assert with_sur.total_thrust > base_only.total_thrust
    assert with_sur.fs_sliding < base_only.fs_sliding
    assert with_sur.fs_overturning < base_only.fs_overturning


def test_architectural_solvers_physics_and_corner_3d_fea():
    soil = SoilProperties()
    seis = SeismicParams(horizontal_pga=0.15, vertical_pga=0.04, water_table_depth=12.0)

    # 1. Stepped terraced: narrower bench increases inter-tier interference & demand
    wide = evaluate_stepped_terraced_wall(SteppedTerracedWallParams(num_tiers=3, bench_width=3.5), soil, seis)
    tight = evaluate_stepped_terraced_wall(SteppedTerracedWallParams(num_tiers=3, bench_width=0.6), soil, seis)
    assert max(tight.interference_ratios) > max(wide.interference_ratios)
    assert tight.total_thrust_kn_per_m > wide.total_thrust_kn_per_m

    # 2. Corner wingwall 3D FEA corner stiffening reduces deflection relative to unbraced midspan
    corner_res = evaluate_corner_wingwall(CornerWingwallParams(corner_angle_deg=90.0), soil, seis, use_3d_fea=True)
    assert corner_res.corner_peak_von_mises_mpa > 0.0
    assert corner_res.corner_stiffening_reduction_ratio > 0.0
    assert corner_res.corner_displacement_m < corner_res.unbraced_displacement_m

    # 3. Counterfort two-way slab bending increases with counterfort spacing
    cf_tight = evaluate_counterfort_wall(CounterfortWallParams(counterfort_spacing=2.4), soil, seis)
    cf_wide = evaluate_counterfort_wall(CounterfortWallParams(counterfort_spacing=4.8), soil, seis)
    assert cf_wide.slab_horizontal_moment_support_knm_per_m > cf_tight.slab_horizontal_moment_support_knm_per_m

    # 4. Curved plan-view: concave in compression, convex in tension
    cp_conc = evaluate_curved_plan_wall(CurvedPlanWallParams(concave_to_backfill=True), soil, seis)
    cp_conv = evaluate_curved_plan_wall(CurvedPlanWallParams(concave_to_backfill=False), soil, seis)
    assert cp_conc.hoop_force_kn_per_m < 0.0
    assert cp_conv.hoop_force_kn_per_m > 0.0
    assert cp_conc.reduced_cantilever_moment_knm_per_m < cp_conc.cantilever_moment_knm_per_m

    # 5. MSE / Gabion / Crib: longer geogrid increases pullout factor of safety
    mse_short = evaluate_mse_gabion_wall(MSEGabionWallParams(reinforcement_length=2.8), soil, seis)
    mse_long = evaluate_mse_gabion_wall(MSEGabionWallParams(reinforcement_length=5.5), soil, seis)
    assert mse_long.min_fs_pullout > mse_short.min_fs_pullout
    assert len(mse_long.course_fs_rupture) == 6

    # Dispatcher covers all 5 morphologies cleanly
    for morph in ArchWallMorphology:
        spec = ArchitecturalWallSpec(morphology=morph)
        summary = evaluate_architectural_wall(spec, soil, seis, use_3d_fea=False)
        grid = build_architectural_wall_mesh(spec, summary=summary)
        ok, _ = verify_arch_mesh_jacobians(grid)
        assert ok


def test_main_window_architectural_mode_surcharge_3d_and_units(qapp):
    window = MainWindow()
    try:
        # 1. Enable an adjacent building pad surcharge in Cantilever mode
        idx_pad = window.panel_arch.combo_sur_type.findData(SurchargeLoadType.BUILDING_PAD_FOOTING)
        assert idx_pad >= 0
        window.panel_arch.combo_sur_type.setCurrentIndex(idx_pad)
        qapp.processEvents()
        assert window.viewport_3d.surcharge_actor is not None
        assert window.viewport_3d.surcharge_super_actor is not None
        assert window.last_surcharge_result is not None
        assert window.last_surcharge_result.total_thrust_kn_per_m > 0.0

        # Surcharge 3D mesh builder produces valid positive-Jacobian blocks
        fg, sg = build_surcharge_3d_meshes(window.geom, window.surcharge_params)
        assert fg is not None and sg is not None
        assert verify_arch_mesh_jacobians(fg)[0]
        assert verify_arch_mesh_jacobians(sg)[0]

        # 2. Switch through all 5 Architectural Wall morphologies in MainWindow
        idx_arch_mode = window.combo_wall_mode.findData(WallSystemMode.ARCHITECTURAL)
        assert idx_arch_mode >= 0
        window.combo_wall_mode.setCurrentIndex(idx_arch_mode)
        assert window.wall_mode == WallSystemMode.ARCHITECTURAL

        for morph in ArchWallMorphology:
            idx_m = window.panel_arch.combo_morphology.findData(morph)
            window.panel_arch.combo_morphology.setCurrentIndex(idx_m)
            qapp.processEvents()
            assert window.viewport_3d.wall_actor is not None
            assert window.viewport_3d.active_wall_mesh is not None
            assert window.last_arch_summary is not None

        # 3. Verify Phase 6 SI <-> Imperial unit parity on ArchWallAndSurchargePanel
        bench_si = window.arch_spec.stepped.bench_width
        window.set_unit_system(UnitSystem.IMPERIAL)
        assert window.panel_arch.spin_bench_w.value() == pytest.approx(bench_si * M_TO_FT, rel=1e-2)
        window.set_unit_system(UnitSystem.SI)
        assert window.panel_arch.spin_bench_w.value() == pytest.approx(bench_si, abs=1e-9)
    finally:
        window.close()
        qapp.processEvents()
