"""
Unit and integration tests for KratosMultiphysics Geomechanics Solver (Phase 6).
Covers:
- Kernel, OpenMP threading, and GeoMechanics / StructuralMechanics application loading
- 2D plane-strain continuum discretization with submodel parts:
  (WallPart, BackfillPart, FoundationPart, InterfacePart, LysmerBoundaryPart)
- Lysmer viscous absorbing boundary parameters (Cp, Cs)
- Coupled hydromechanical dynamic step with pore-water pressure & Cauchy stresses
- Background QThread worker execution with Qt signals (stepCompleted, simulationFinished)
- Graceful worker cancellation during execution
- HDF5 binary simulation archiving and retrieval (h5py)
- Missing Kratos runtime error handling
"""

import pytest
import numpy as np
from pathlib import Path
from PySide6.QtCore import QCoreApplication

from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
)
from orang3d.physics.kratos_solver import (
    KratosRetainingWallSolver,
    KratosSimulationWorker,
    KRATOS_AVAILABLE,
)


@pytest.fixture(scope="module")
def qapp():
    """Ensure a QCoreApplication exists for QThread / Qt Signals testing."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_openmp_and_kernel_registration():
    """Verify Kratos core, OpenMP threads, and required application modules."""
    import KratosMultiphysics as KM
    import KratosMultiphysics.GeoMechanicsApplication as KGeo
    import KratosMultiphysics.StructuralMechanicsApplication as KStruct

    # Verify OpenMP parallel threads > 0
    if hasattr(KM, "ParallelUtilities"):
        num_threads = KM.ParallelUtilities.GetNumThreads()
    else:
        num_threads = KM.OpenMPUtils.GetNumThreads()
    assert num_threads >= 1

    # Verify application modules
    assert hasattr(KGeo, "WATER_PRESSURE") or hasattr(KM, "WATER_PRESSURE")
    assert hasattr(KM, "DISPLACEMENT")
    assert hasattr(KM, "ACCELERATION")


@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_solver_submodelparts_and_boundaries():
    """Verify construction of 2D continuum model part with soil, wall, interface and absorbing boundaries."""
    geom = RetainingWallGeometry(stem_height=5.0, toe_length=1.0, heel_length=2.5)
    soil = SoilProperties()
    seismic = SeismicParams()

    solver = KratosRetainingWallSolver(geom, soil, seismic)
    mp = solver.initialize_model()

    assert mp is not None
    assert mp.Name == "RetainingWallSSI"
    assert mp.GetBufferSize() == 2

    # Verify submodel parts for SSI continuum
    expected_subparts = ["WallPart", "BackfillPart", "FoundationPart", "InterfacePart", "LysmerBoundaryPart"]
    for part_name in expected_subparts:
        assert mp.HasSubModelPart(part_name), f"Missing SubModelPart: {part_name}"
        sub_part = mp.GetSubModelPart(part_name)
        assert sub_part.NumberOfNodes() > 0, f"SubModelPart {part_name} has no nodes"


@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_lysmer_absorbing_boundary_properties():
    """Verify calculation of Lysmer-Kuhlemeyer viscous absorbing boundary coefficients."""
    geom = RetainingWallGeometry()
    soil = SoilProperties(elastic_modulus=45000.0, poissons_ratio=0.30, unit_weight=18.5)
    seismic = SeismicParams()

    solver = KratosRetainingWallSolver(geom, soil, seismic)
    _ = solver.initialize_model()

    lysmer = solver.get_lysmer_coefficients()
    assert "Cp" in lysmer and "Cs" in lysmer
    assert "Vp_m_s" in lysmer and "Vs_m_s" in lysmer

    # P-wave velocity must exceed S-wave velocity: Vp > Vs
    assert lysmer["Vp_m_s"] > lysmer["Vs_m_s"] > 0.0
    # Damping parameters Cp, Cs must be strictly positive
    assert lysmer["Cp"] > lysmer["Cs"] > 0.0


@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_dynamic_single_step_detailed():
    """Verify single dynamic step with crest displacement, base shear, pore pressure, and stress tensor."""
    geom = RetainingWallGeometry()
    soil = SoilProperties()
    seismic = SeismicParams(water_table_depth=2.5, pore_pressure_ratio_ru=0.2)

    solver = KratosRetainingWallSolver(geom, soil, seismic)
    _ = solver.initialize_model()

    result = solver.run_dynamic_step(t=0.05, dt=0.01, accel_g=0.30)

    assert result["status"] == "CONVERGED"
    assert "crest_displacement_m" in result
    assert "base_shear_kn" in result
    assert "pore_pressure_kpa" in result
    assert "stress_tensor" in result

    # Cauchy stress tensor elements: sigma_xx, sigma_yy, tau_xy
    stresses = result["stress_tensor"]
    assert "sigma_xx" in stresses and "sigma_yy" in stresses and "tau_xy" in stresses
    assert result["pore_pressure_kpa"] > 0.0


@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_pore_pressure_and_liquefaction_coupling():
    """Verify that water table rise and liquefaction ratio increase pore pressure and reduce soil stiffness."""
    geom = RetainingWallGeometry(stem_height=6.0)
    soil = SoilProperties()

    # Dry condition: water table far below wall
    solver_dry = KratosRetainingWallSolver(geom, soil, SeismicParams(water_table_depth=10.0, pore_pressure_ratio_ru=0.0))
    solver_dry.initialize_model()
    res_dry = solver_dry.run_dynamic_step(t=0.1, dt=0.01, accel_g=0.20)

    # Submerged & liquefying condition: water table at crest, ru = 0.5
    solver_wet = KratosRetainingWallSolver(geom, soil, SeismicParams(water_table_depth=0.0, pore_pressure_ratio_ru=0.5))
    solver_wet.initialize_model()
    res_wet = solver_wet.run_dynamic_step(t=0.1, dt=0.01, accel_g=0.20)

    # Pore pressure must be higher in submerged condition
    assert res_wet["pore_pressure_kpa"] > res_dry["pore_pressure_kpa"]
    # Crest displacement is amplified under saturated liquefying conditions
    assert abs(res_wet["crest_displacement_m"]) > abs(res_dry["crest_displacement_m"])


@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_worker_full_run_and_signals(qapp):
    """Test full background QThread worker execution with step and finished signals."""
    geom = RetainingWallGeometry()
    soil = SoilProperties()
    seismic = SeismicParams()

    t_arr = np.linspace(0.0, 0.05, 6)
    a_arr = np.array([0.0, 0.1, 0.25, 0.20, 0.05, 0.0])

    worker = KratosSimulationWorker(geom, soil, seismic, t_arr, a_arr)

    steps_recorded = []
    finished_data = {}

    def on_step(step, t, crest_u, pore_p):
        steps_recorded.append((step, t, crest_u, pore_p))

    def on_finished(summary):
        finished_data.update(summary)

    worker.stepCompleted.connect(on_step)
    worker.simulationFinished.connect(on_finished)

    # Run worker synchronously for deterministic test execution
    worker.run()

    assert len(steps_recorded) > 0
    assert "total_steps" in finished_data
    assert finished_data["total_steps"] == len(t_arr)
    assert finished_data["max_crest_disp_cm"] >= 0.0


@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_worker_cancellation(qapp):
    """Test cooperative cancellation mid-simulation."""
    geom = RetainingWallGeometry()
    soil = SoilProperties()
    seismic = SeismicParams()

    t_arr = np.linspace(0.0, 1.0, 100)
    a_arr = np.sin(2.0 * np.pi * 3.0 * t_arr) * 0.3

    worker = KratosSimulationWorker(geom, soil, seismic, t_arr, a_arr)

    # Pre-cancel before run
    worker.cancel()
    assert worker._is_cancelled is True

    finished_summary = {}
    worker.simulationFinished.connect(lambda s: finished_summary.update(s))
    worker.run()

    # Cancelled before any steps executed
    assert finished_summary.get("total_steps", 0) == 0


@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_hdf5_caching(tmp_path: Path):
    """Verify archiving and querying simulation time history to HDF5 binary format."""
    geom = RetainingWallGeometry()
    soil = SoilProperties()
    seismic = SeismicParams()

    solver = KratosRetainingWallSolver(geom, soil, seismic)
    solver.initialize_model()

    time_hist = np.linspace(0.0, 0.5, 50)
    disp_hist = 0.02 * np.sin(2.0 * np.pi * 2.0 * time_hist)
    pore_hist = np.linspace(15.0, 25.0, 50)

    h5_file = tmp_path / "sim_results.h5"
    solver.export_simulation_hdf5(
        filepath=str(h5_file),
        time_arr=time_hist,
        crest_disp_arr=disp_hist,
        pore_pressure_arr=pore_hist,
    )

    assert h5_file.is_file()

    # Read back and verify with h5py
    import h5py
    with h5py.File(str(h5_file), "r") as f:
        assert "time" in f
        assert "crest_displacement_m" in f
        assert "pore_pressure_kpa" in f
        assert len(f["time"]) == 50
        assert f.attrs["solver"] == "KratosMultiphysics GeoMechanics"
        np.testing.assert_allclose(f["time"][:], time_hist)
        np.testing.assert_allclose(f["crest_displacement_m"][:], disp_hist)


def test_kratos_missing_runtime_error(monkeypatch):
    """Verify clear RuntimeError when Kratos is unavailable."""
    import orang3d.physics.kratos_solver as ks
    monkeypatch.setattr(ks, "KRATOS_AVAILABLE", False)

    geom = RetainingWallGeometry()
    soil = SoilProperties()
    seismic = SeismicParams()

    with pytest.raises(RuntimeError, match="KratosMultiphysics is not installed"):
        _ = ks.KratosRetainingWallSolver(geom, soil, seismic)


@pytest.mark.skipif(not KRATOS_AVAILABLE, reason="KratosMultiphysics is not installed")
def test_kratos_worker_with_hdf5_export(qapp, tmp_path: Path):
    """Verify background worker exports simulation directly to HDF5 upon completion."""
    geom = RetainingWallGeometry()
    soil = SoilProperties()
    seismic = SeismicParams()

    t_arr = np.linspace(0.0, 0.04, 5)
    a_arr = np.array([0.0, 0.1, 0.2, 0.1, 0.0])
    h5_target = tmp_path / "worker_output.h5"

    worker = KratosSimulationWorker(
        geom, soil, seismic, t_arr, a_arr, output_hdf5_path=str(h5_target)
    )
    worker.run()

    assert h5_target.is_file()
    import h5py
    with h5py.File(str(h5_target), "r") as f:
        assert len(f["time"]) == 5
        assert "base_shear_kn" in f


def test_kratos_worker_error_emission(qapp, monkeypatch):
    """Verify worker catches internal solver exceptions and emits simulationError."""
    import orang3d.physics.kratos_solver as ks
    monkeypatch.setattr(ks, "KRATOS_AVAILABLE", False)

    geom = RetainingWallGeometry()
    soil = SoilProperties()
    seismic = SeismicParams()
    worker = ks.KratosSimulationWorker(geom, soil, seismic, np.zeros(2), np.zeros(2))

    errors = []
    worker.simulationError.connect(lambda e: errors.append(e))
    worker.run()

    assert len(errors) == 1
    assert "KratosMultiphysics is not installed" in errors[0]
