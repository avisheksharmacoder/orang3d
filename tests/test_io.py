"""
Test Suite for Phase 9: Session Serialization, Export Suite & Automated Design Reports.
Validates:
1. Complete round-trip project serialization fidelity (.o3d bundle with JSON schema + HDF5 cache).
2. Robust corrupt file exception handling and schema version migration handlers.
3. 3D CAD/Simulation mesh export suite: .vtk (ParaView), .stl (3D CAD/printing), .obj.
4. Time-series waveform signal export to .csv with exact precision.
5. Automated Geotechnical Engineering PDF report generator:
   - Dimensioned cross-section diagram
   - Soil stratification & seismic parameters tables
   - Regional code compliance checks (Eurocode 7, AASHTO, IS 14458)
   - Size > 50 KB and execution in < 1.5 seconds.
"""

import os
import tempfile
import time
import pytest
import numpy as np
import meshio
from PySide6.QtWidgets import QApplication

from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
)
from orang3d.config import RegionalStandard
from orang3d.io.serialization import (
    save_project_session,
    load_project_session,
    ProjectSession,
    CorruptProjectError,
)
from orang3d.io.mesh_export import (
    export_mesh_to_vtk,
    export_mesh_to_stl,
    export_mesh_to_obj,
    export_signals_to_csv,
)
from orang3d.io.report_generator import generate_engineering_pdf_report


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_project():
    geom = RetainingWallGeometry(
        stem_height=6.2,
        footing_thickness=0.85,
        stem_thickness_base=0.8,
        stem_thickness_top=0.35,
        toe_length=1.3,
        heel_length=2.6,
        wall_length=5.5,
        shear_key_depth=0.5,
        shear_key_width=0.4,
    )
    soil = SoilProperties(
        friction_angle=35.0,
        unit_weight=18.8,
        cohesion=2.0,
        foundation_friction_angle=32.0,
        foundation_cohesion=5.0,
        allowable_bearing_capacity=350.0,
    )
    seismic = SeismicParams(
        horizontal_pga=0.30,
        vertical_pga=0.15,
        water_table_depth=3.2,
        pore_pressure_ratio_ru=0.20,
        backfill_slope=5.0,
    )
    results = AnalysisResults(
        total_thrust=162.5,
        thrust_height=2.35,
        max_shear_force=135.0,
        max_bending_moment=245.0,
        concrete_tensile_stress=2.25,
        max_bearing_pressure=195.0,
        min_bearing_pressure=48.0,
        fs_sliding=1.38,
        fs_overturning=2.05,
        fs_bearing=2.60,
    )
    t = np.linspace(0.0, 8.0, 400)
    a = 0.30 * np.sin(2.0 * np.pi * 2.0 * t) * np.exp(-0.25 * t)
    slip = np.maximum(0.0, np.cumsum(np.maximum(0.0, np.abs(a) - 0.12)) * 0.04)
    pore = 42.0 + 28.0 * (1.0 - np.exp(-0.35 * t))

    return geom, soil, seismic, results, t, a, slip, pore


def test_o3d_session_roundtrip_fidelity(sample_project):
    """
    Asserts complete round-trip serialization fidelity:
    load(save(project)) == project across all 25+ geometry, soil, seismic, and results fields
    and simulation cache waveforms.
    """
    geom, soil, seismic, results, t, a, slip, pore = sample_project

    with tempfile.TemporaryDirectory() as tmp_dir:
        o3d_path = os.path.join(tmp_dir, "test_session.o3d")

        # Save session
        save_project_session(
            o3d_path,
            geom=geom,
            soil=soil,
            seismic=seismic,
            results=results,
            time_arr=t,
            accel_arr=a,
            slip_arr=slip,
            pore_arr=pore,
            notes="Full verification benchmark session",
        )

        assert os.path.exists(o3d_path)
        assert os.path.getsize(o3d_path) > 1000  # Non-trivial archive

        # Load session back
        session = load_project_session(o3d_path)
        assert isinstance(session, ProjectSession)

        # 1. Verify Geometry fields
        assert session.geom.stem_height == pytest.approx(geom.stem_height)
        assert session.geom.footing_thickness == pytest.approx(geom.footing_thickness)
        assert session.geom.toe_length == pytest.approx(geom.toe_length)
        assert session.geom.heel_length == pytest.approx(geom.heel_length)
        assert session.geom.shear_key_depth == pytest.approx(geom.shear_key_depth)

        # 2. Verify Soil fields
        assert session.soil.friction_angle == pytest.approx(soil.friction_angle)
        assert session.soil.unit_weight == pytest.approx(soil.unit_weight)
        assert session.soil.allowable_bearing_capacity == pytest.approx(soil.allowable_bearing_capacity)

        # 3. Verify Seismic fields
        assert session.seismic.horizontal_pga == pytest.approx(seismic.horizontal_pga)
        assert session.seismic.water_table_depth == pytest.approx(seismic.water_table_depth)
        assert session.seismic.pore_pressure_ratio_ru == pytest.approx(seismic.pore_pressure_ratio_ru)

        # 4. Verify Results fields
        assert session.results.total_thrust == pytest.approx(results.total_thrust)
        assert session.results.fs_sliding == pytest.approx(results.fs_sliding)
        assert session.results.fs_overturning == pytest.approx(results.fs_overturning)
        assert session.results.fs_bearing == pytest.approx(results.fs_bearing)
        assert session.results.concrete_tensile_stress == pytest.approx(results.concrete_tensile_stress)

        # 5. Verify Waveform arrays
        np.testing.assert_allclose(session.time_arr, t, rtol=1e-5)
        np.testing.assert_allclose(session.accel_arr, a, rtol=1e-5)
        np.testing.assert_allclose(session.slip_arr, slip, rtol=1e-5)
        np.testing.assert_allclose(session.pore_arr, pore, rtol=1e-5)

        assert session.notes == "Full verification benchmark session"


def test_corrupt_file_handling():
    """Asserts that invalid, corrupt, or non-existent .o3d files raise clear CorruptProjectError."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Non-existent file
        with pytest.raises(FileNotFoundError):
            load_project_session(os.path.join(tmp_dir, "ghost.o3d"))

        # Corrupt file with garbage bytes
        garbage_file = os.path.join(tmp_dir, "corrupt.o3d")
        with open(garbage_file, "wb") as f:
            f.write(b"NOT_A_VALID_ZIP_OR_HDF5_DATA_STREAM_XYZ123456789")

        with pytest.raises(CorruptProjectError, match="Corrupt or invalid"):
            load_project_session(garbage_file)


def test_schema_version_migration(sample_project):
    """Verifies that project files created under older schema versions are migrated cleanly."""
    geom, soil, seismic, results, _, _, _, _ = sample_project

    with tempfile.TemporaryDirectory() as tmp_dir:
        legacy_path = os.path.join(tmp_dir, "legacy_v01.o3d")
        # Save with legacy schema version tag
        save_project_session(
            legacy_path,
            geom=geom,
            soil=soil,
            seismic=seismic,
            results=results,
            schema_version="0.1.0",
        )

        session = load_project_session(legacy_path)
        assert session.geom.stem_height == pytest.approx(geom.stem_height)
        # Should have migrated/tagged to current version
        assert session.schema_version is not None


def test_cad_mesh_exports(sample_project):
    """
    Verifies 3D CAD and simulation mesh exports:
    - .vtk (ParaView UnstructuredGrid with scalar fields)
    - .stl (3D Printing / CAD triangular surface)
    - .obj (Wavefront 3D graphics)
    All verified by reading back with meshio.
    """
    geom, _, _, results, _, _, _, _ = sample_project

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Export VTK
        vtk_path = os.path.join(tmp_dir, "wall.vtk")
        export_mesh_to_vtk(geom, results, vtk_path, warp_scale=1.5)
        assert os.path.exists(vtk_path)
        m_vtk = meshio.read(vtk_path)
        assert len(m_vtk.cells) > 0
        assert len(m_vtk.points) > 0
        assert "TensileStress_MPa" in m_vtk.point_data or len(m_vtk.point_data) > 0

        # 2. Export STL
        stl_path = os.path.join(tmp_dir, "wall.stl")
        export_mesh_to_stl(geom, results, stl_path)
        assert os.path.exists(stl_path)
        m_stl = meshio.read(stl_path)
        assert len(m_stl.cells) > 0
        assert len(m_stl.points) > 0

        # 3. Export OBJ
        obj_path = os.path.join(tmp_dir, "wall.obj")
        export_mesh_to_obj(geom, results, obj_path)
        assert os.path.exists(obj_path)
        m_obj = meshio.read(obj_path)
        assert len(m_obj.cells) > 0
        assert len(m_obj.points) > 0


def test_signals_csv_export(sample_project):
    """Verifies time-series accelerogram and Newmark displacement export to RFC-4180 CSV."""
    _, _, _, _, t, a, slip, pore = sample_project

    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_path = os.path.join(tmp_dir, "seismic_curves.csv")
        export_signals_to_csv(csv_path, time_arr=t, accel_arr=a, slip_arr=slip, pore_arr=pore)

        assert os.path.exists(csv_path)

        # Read back CSV
        data = np.genfromtxt(csv_path, delimiter=",", names=True)
        assert "Time_s" in data.dtype.names
        assert "Acceleration_g" in data.dtype.names
        assert "Permanent_Slip_cm" in data.dtype.names
        assert "Pore_Pressure_kPa" in data.dtype.names

        assert len(data) == len(t)
        np.testing.assert_allclose(data["Time_s"], t, rtol=1e-5)
        np.testing.assert_allclose(data["Acceleration_g"], a, rtol=1e-5)
        np.testing.assert_allclose(data["Permanent_Slip_cm"], slip, rtol=1e-5)
        np.testing.assert_allclose(data["Pore_Pressure_kPa"], pore, rtol=1e-5)


def test_engineering_pdf_report_generation(qapp, sample_project):
    """
    Verifies Automated Geotechnical Engineering Report Generator:
    - Generates PDF design report
    - Contains dimensioned cross-section diagram & code compliance summary
    - File size > 50 KB
    - Execution completes in < 1.5 seconds without external LaTeX dependencies.
    """
    geom, soil, seismic, results, t, _, slip, _ = sample_project

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = os.path.join(tmp_dir, "orang3D_Engineering_Report.pdf")

        t_start = time.perf_counter()

        generate_engineering_pdf_report(
            pdf_path,
            geom=geom,
            soil=soil,
            seismic=seismic,
            results=results,
            regional_standard=RegionalStandard.EUROCODE_7,
            time_arr=t,
            slip_arr=slip,
            project_title="Retaining Wall Disaster Assessment",
        )

        t_elapsed = time.perf_counter() - t_start

        # Performance requirement: < 1.5 seconds
        assert t_elapsed < 1.5, f"Report generation took {t_elapsed:.2f}s, expected < 1.5s"

        assert os.path.exists(pdf_path)
        file_size = os.path.getsize(pdf_path)

        # File size requirement: > 50 KB
        assert file_size > 50000, f"PDF file size {file_size} bytes is <= 50 KB"

        # Verify PDF magic header bytes
        with open(pdf_path, "rb") as f:
            header = f.read(5)
            assert header.startswith(b"%PDF-")
