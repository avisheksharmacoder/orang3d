"""
Phase 3 Verification & Benchmark Tests:
  1. Conformal 3D Hexahedral Continuum FEA Mesher (wall + backfill >= 3H + foundation >= 2B)
  2. Geostatic K0 Equilibrium & Patch Test (< 1% error, zero spurious drift)
  3. Static Active Transition Benchmark (smooth & rough wall-soil Coulomb interfaces)
  4. Lysmer-Kuhlemeyer Viscous Absorbing Boundary Test (< 5% wave reflection)
  5. 3D Corner / Finite-Length Restraint Effect Study (short vs long retaining wall)
  6. Multi-directional 1D / 2D / 3D UniformExcitation, brickUP u-p pore pressure,
     PDMY02 & PIMY constitutive models, HDF5 caching, and OpenSees3DFEAWorker
  7. True Kratos 2D U-Pw Continuum FEA Authenticity (Elements > 0, Conditions > 0)
  8. PyVista Viewport3D & MainWindow 3D FEA post-processing integration
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pyvista as pv
import pytest
from PySide6.QtWidgets import QApplication

from orang3d.models.wall_params import RetainingWallGeometry, SoilProperties, SeismicParams
from orang3d.models.advanced_wall_params import (
    CurvedShellGeometry,
    MultiStrutPiledWallModel,
    PierAndPileGeometry,
    StrutSupportSystem,
    WallSystemMode,
)
from orang3d.mesher.continuum_fea_mesher import (
    ContinuumFEAMesh,
    build_continuum_fea_mesh,
)
from orang3d.physics import (
    KRATOS_AVAILABLE,
    OPENSEES_AVAILABLE,
    ConstitutiveModelType,
    ContinuumFEAResult,
    OpenSees3DContinuumSolver,
    OpenSees3DFEAWorker,
    SolverTier,
    export_continuum_hdf5,
    load_continuum_hdf5,
)
from orang3d.physics.kratos_solver import KratosRetainingWallSolver
from orang3d.gui.viewport_3d import Viewport3D
from orang3d.gui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _default_models():
    geom = RetainingWallGeometry(
        stem_height=4.5,
        stem_thickness_base=0.5,
        stem_thickness_top=0.35,
        toe_length=0.8,
        heel_length=1.9,
        footing_thickness=0.5,
        wall_length=8.0,
    )
    soil = SoilProperties(
        unit_weight=18.5,
        saturated_unit_weight=20.0,
        friction_angle=32.0,
        elastic_modulus=35000.0,
        poissons_ratio=0.30,
    )
    seismic = SeismicParams(
        horizontal_pga=0.25,
        vertical_pga=0.12,
        water_table_depth=10.0,
    )
    return geom, soil, seismic


# ==============================================================================
# 1. Conformal 3D Hexahedral FEA Mesher
# ==============================================================================
def test_conformal_3d_fea_mesh_geometry_and_interfaces():
    geom, soil, _ = _default_models()
    mesh = build_continuum_fea_mesh(
        geom,
        soil=soil,
        nx_backfill=5,
        ny_wall=4,
        nz_wall=4,
        ny_found=2,
        separate_interfaces=True,
    )
    assert isinstance(mesh, ContinuumFEAMesh)
    assert mesh.n_nodes > 50
    assert mesh.n_elements > 40

    # Domain extent >= 3H behind wall backface and >= 2B foundation depth
    h_total = geom.total_height
    b_width = geom.base_width
    assert mesh.nodes[:, 0].max() >= 3.0 * h_total
    assert mesh.nodes[:, 1].min() <= -2.0 * b_width + 1e-6

    # Distinct domains populated (1=Wall, 2=Backfill, 3=Foundation)
    unique_domains = set(mesh.element_domain_ids.tolist())
    assert {1, 2, 3}.issubset(unique_domains)

    # Coincident separate wall-soil node pairs for zero-length friction/gap links
    bf_pairs = [p for p in mesh.interface_pairs if p.zone == "backface"]
    base_pairs = [p for p in mesh.interface_pairs if p.zone == "base"]
    assert len(bf_pairs) > 0
    assert len(base_pairs) > 0
    for pr in mesh.interface_pairs:
        assert pr.wall_node_id != pr.soil_node_id
        assert np.allclose(mesh.nodes[pr.wall_node_id], mesh.nodes[pr.soil_node_id])
        assert pr.area_trib > 0.0

    # Lysmer boundary nodes with unit outward normals and positive tributary area
    assert len(mesh.lysmer_nodes) > 0
    for ln in mesh.lysmer_nodes:
        assert ln.area_trib > 0.0
        assert abs(np.linalg.norm(ln.normal) - 1.0) < 1e-5

    # Valid PyVista VTK_HEXAHEDRON unstructured grid with positive cell volumes
    grid = mesh.to_pyvista_grid()
    assert grid.n_cells == mesh.n_elements
    assert np.all(grid.celltypes == pv.CellType.HEXAHEDRON)
    sized = grid.compute_cell_sizes(volume=True, area=False, length=False)
    assert np.all(sized.cell_data["Volume"] > 0.0)


def test_conformal_3d_fea_mesh_multi_strut_shell_support():
    geom, soil, _ = _default_models()
    model = MultiStrutPiledWallModel(
        shell=CurvedShellGeometry(panel_height=5.0, bay_span=6.0),
        pier_pile=PierAndPileGeometry(),
        struts=StrutSupportSystem(),
    )
    mesh = build_continuum_fea_mesh(
        geom,
        soil=soil,
        wall_mode=WallSystemMode.MULTI_STRUT_CURVED_SHELL,
        multi_strut_model=model,
        nx_backfill=4,
        ny_wall=3,
        nz_wall=3,
    )
    assert mesh.n_elements > 20
    assert mesh.geometry_meta["wall_mode"] == WallSystemMode.MULTI_STRUT_CURVED_SHELL.value


# ==============================================================================
# 2. Geostatic K0 Patch Test
# ==============================================================================
@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_geostatic_k0_patch_test():
    geom, soil, seismic = _default_models()
    solver = OpenSees3DContinuumSolver(geom, soil, seismic)
    res = solver.run_geostatic_patch_test(nx=3, ny=4, nz=2, use_k0_poisson=True)

    assert res["converged"] is True
    assert res["max_sigma_yy_rel_error"] < 0.01
    assert res["max_sigma_xx_rel_error"] < 0.01
    assert res["max_lateral_drift_m"] < 1e-6


# ==============================================================================
# 3. Static Active Transition Benchmark (Smooth & Rough Interfaces)
# ==============================================================================
@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_static_active_transition_smooth_and_rough():
    geom, soil, seismic = _default_models()
    solver = OpenSees3DContinuumSolver(geom, soil, seismic)

    res_smooth = solver.run_static_active_transition(delta_x_m=-0.0025, interface_friction_deg=0.0)
    res_rough = solver.run_static_active_transition(delta_x_m=-0.0025, interface_friction_deg=20.0)

    for res in (res_smooth, res_rough):
        assert res["converged"] is True
        assert res["k0_thrust_kn_m"] > 0.0
        assert 0.0 < res["active_thrust_kn_m"] < res["k0_thrust_kn_m"]
        assert res["thrust_reduction_factor"] < 0.90


# ==============================================================================
# 4. Lysmer-Kuhlemeyer Viscous Absorbing Boundary Test
# ==============================================================================
@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_lysmer_absorbing_boundary_reduces_reflected_energy():
    geom, soil, seismic = _default_models()
    solver = OpenSees3DContinuumSolver(geom, soil, seismic)

    res_lysmer = solver.run_lysmer_absorbing_test(use_lysmer=True)
    res_rigid = solver.run_lysmer_absorbing_test(use_lysmer=False)

    assert res_lysmer["reflected_energy_ratio"] < 0.05
    assert res_lysmer["reflected_energy_ratio"] < res_rigid["reflected_energy_ratio"]


# ==============================================================================
# 5. 3D Corner / Finite-Length Effect Benchmark
# ==============================================================================
@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_3d_corner_finite_length_reduces_midspan_pressure():
    geom, soil, seismic = _default_models()
    solver = OpenSees3DContinuumSolver(geom, soil, seismic)
    study = solver.run_3d_corner_effect_study(short_length_m=3.5, long_length_m=18.0)

    assert study["short_midspan_pressure_kpa"] > 0.0
    assert study["long_midspan_pressure_kpa"] > 0.0
    assert 0.0 < study["corner_reduction_ratio"] < 0.90


# ==============================================================================
# 6. Multi-Directional Dynamic SSI, brickUP, HDF5 Caching & Worker
# ==============================================================================
@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_3d_dynamic_multidirectional_constitutive_and_hdf5(tmp_path: Path):
    geom, soil, seismic = _default_models()
    solver = OpenSees3DContinuumSolver(geom, soil, seismic)

    t = np.arange(0.0, 0.05, 0.01)
    ax = 0.25 * np.sin(2.0 * np.pi * 2.5 * t)
    ay = 0.12 * np.sin(2.0 * np.pi * 3.0 * t)
    az = 0.15 * np.cos(2.0 * np.pi * 2.5 * t)

    h5_file = tmp_path / "continuum_3d.h5"
    res_3d = solver.run_dynamic_seismic(
        t,
        ax,
        accel_y_g=ay,
        accel_z_g=az,
        constitutive_model=ConstitutiveModelType.PDMY02,
        use_up=False,
        nx_backfill=4,
        ny_wall=3,
        nz_wall=2,
        hdf5_path=str(h5_file),
    )

    assert res_3d.status == "CONVERGED"
    assert res_3d.provenance is not None
    assert res_3d.provenance.tier == SolverTier.L2_OPENSEES_3D_FEA
    assert res_3d.provenance.extra["seismic_axes"] == ["X", "Y", "Z"]
    assert res_3d.max_crest_disp_cm > 0.0
    assert float(np.max(np.abs(res_3d.displacement_field[:, :, 2]))) > 0.0
    assert float(np.max(res_3d.total_thrust_kn_m)) > 0.0
    assert h5_file.is_file()

    # Reload HDF5 cache and attach mesh for PyVista grid extraction
    reloaded = load_continuum_hdf5(str(h5_file), mesh=res_3d.mesh)
    assert isinstance(reloaded, ContinuumFEAResult)
    assert np.allclose(reloaded.time, res_3d.time)
    assert np.allclose(reloaded.total_thrust_kn_m, res_3d.total_thrust_kn_m)
    grid = reloaded.grid_at_timestep(-1)
    assert "WallNormalStress_kPa" in grid.point_data
    assert "OctahedralShearStrain" in grid.cell_data

    # Test coupled 4-DOF brickUP u-p pore pressure + PIMY constitutive option
    seismic_wet = SeismicParams(horizontal_pga=0.25, water_table_depth=1.5)
    solver_wet = OpenSees3DContinuumSolver(geom, soil, seismic_wet)
    res_up = solver_wet.run_dynamic_seismic(
        t,
        ax,
        accel_y_g=ay,
        constitutive_model=ConstitutiveModelType.PIMY,
        use_up=True,
        nx_backfill=4,
        ny_wall=3,
        nz_wall=2,
    )
    assert res_up.status == "CONVERGED"
    assert float(np.max(res_up.excess_pore_pressure_ratio_ru)) > 0.0


@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_opensees_3d_fea_worker_qthread(qapp, tmp_path: Path):
    geom, soil, seismic = _default_models()
    t = np.array([0.0, 0.01, 0.02, 0.03])
    ax = np.array([0.0, 0.12, 0.22, 0.10])
    h5_out = tmp_path / "worker_3d.h5"

    worker = OpenSees3DFEAWorker(
        geom=geom,
        soil=soil,
        seismic=seismic,
        time_arr=t,
        accel_x_g=ax,
        constitutive_model=ConstitutiveModelType.ELASTIC_ISOTROPIC,
        use_up=False,
        output_hdf5_path=str(h5_out),
    )

    steps = []
    finished = {}
    errors = []
    worker.stepCompleted.connect(lambda s, tm, u, th: steps.append((s, tm, u, th)))
    worker.simulationFinished.connect(lambda summary: finished.update(summary))
    worker.simulationError.connect(lambda e: errors.append(e))

    worker.start()
    assert worker.wait(15000)
    qapp.processEvents()

    assert not errors
    assert finished.get("status") == "CONVERGED"
    assert finished.get("total_steps") == len(t)
    assert isinstance(finished.get("result"), ContinuumFEAResult)
    assert len(steps) > 0
    assert h5_out.is_file()


# ==============================================================================
# 7. Kratos GeoMechanics True 2D U-Pw Continuum FEA Authenticity
# ==============================================================================
@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_continuum_authenticity_and_real_elements():
    geom, soil, seismic = _default_models()
    seismic.water_table_depth = 1.5
    solver = KratosRetainingWallSolver(geom, soil, seismic)
    mp = solver.initialize_model()

    assert mp.NumberOfElements() > 0
    assert mp.NumberOfConditions() > 0
    for part in ("WallPart", "InterfacePart", "BackfillPart", "FoundationPart"):
        assert mp.HasSubModelPart(part)
        assert mp.GetSubModelPart(part).NumberOfElements() > 0
    assert mp.GetSubModelPart("LysmerBoundaryPart").NumberOfConditions() > 0

    step1 = solver.run_dynamic_step(t=0.01, dt=0.01, accel_g=0.0)
    step2 = solver.run_dynamic_step(t=0.02, dt=0.01, accel_g=0.25)

    assert step2["status"] == "CONVERGED"
    assert step2["solver_mode"] == "kratos_fea"
    assert step2["element_count"] == mp.NumberOfElements()
    assert step2["condition_count"] == mp.NumberOfConditions()
    assert abs(step2["crest_displacement_m"]) > abs(step1["crest_displacement_m"])
    assert step2["base_shear_kn"] > 0.0
    st = step2["stress_tensor"]
    assert abs(st["sigma_yy"]) > 0.0 or abs(st["sigma_xx"]) > 0.0


# ==============================================================================
# 8. GUI Viewport3D & MainWindow 3D FEA Post-Processing Integration
# ==============================================================================
@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_viewport_and_mainwindow_3d_fea_integration(qapp):
    geom, soil, seismic = _default_models()
    solver = OpenSees3DContinuumSolver(geom, soil, seismic)
    t = np.array([0.0, 0.01, 0.02])
    ax = np.array([0.0, 0.15, 0.25])
    fea_res = solver.run_dynamic_seismic(
        t, ax, constitutive_model=ConstitutiveModelType.ELASTIC_ISOTROPIC, nx_backfill=4, ny_wall=3, nz_wall=2
    )

    view = Viewport3D()
    try:
        view.update_continuum_fea_scene(fea_res, step_idx=-1, scalar_name="WallNormalStress_kPa")
        assert view.continuum_actor is not None
        assert view.continuum_result is fea_res

        view.set_continuum_timestep(0)
        assert view.continuum_step_idx == 0

        idx_ru = view.combo_scalar.findData("ExcessPorePressureRatio_ru")
        assert idx_ru >= 0
        view.combo_scalar.setCurrentIndex(idx_ru)
        qapp.processEvents()
        assert view.continuum_actor is not None
    finally:
        view.close()

    win = MainWindow()
    try:
        assert hasattr(win, "combo_3d_model")
        assert hasattr(win, "combo_3d_axes")
        assert hasattr(win, "btn_fea_3d")

        win._on_3d_fea_finished(
            {
                "status": fea_res.status,
                "total_steps": len(fea_res.time),
                "max_crest_disp_cm": fea_res.max_crest_disp_cm,
                "peak_thrust_kn_m": float(np.max(fea_res.total_thrust_kn_m)),
                "corner_concentration_ratio": fea_res.corner_concentration_ratio,
                "result": fea_res,
            }
        )
        assert win.last_continuum_fea_result is fea_res
        assert win.viewport_3d.continuum_result is fea_res

        win._on_scrubber_moved(min(1, len(win.time_arr) - 1))
        qapp.processEvents()
        assert win.viewport_3d.continuum_actor is not None
    finally:
        win.close()

