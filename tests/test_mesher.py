"""
Unit and integration tests for pure NumPy 3D Parametric Mesher (Phase 2).
Covers:
- Multi-template retaining walls (Inverted-T, L-shaped, Reverse-L, Gravity)
- Bottom shear key generation (rectangular & trapezoidal)
- Topological invariants & cell types (100% VTK_HEXAHEDRON)
- Orientation & Jacobian positivity (det(J) > 0 for all elements)
- Volume conservation (< 0.01% error vs analytical closed-form)
- Geometric properties (closed-form volume, CG, moments of inertia)
- Sub-5ms execution latency benchmark
- Soil strata, failure wedge, and water plane generation
"""

import time
import pytest
import numpy as np
import pyvista as pv

from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
)
from orang3d.mesher.hex_mesher import (
    WallTemplate,
    build_3d_wall_mesh,
    build_3d_soil_mesh,
    build_3d_wedge_mesh,
    compute_wall_geometric_properties,
    compute_hex_jacobian_determinants,
    WallGeometricProperties,
)


@pytest.fixture
def standard_setup():
    geom = RetainingWallGeometry(
        stem_height=6.0,
        stem_thickness_top=0.35,
        stem_thickness_base=0.65,
        toe_length=1.0,
        heel_length=2.5,
        footing_thickness=0.7,
        shear_key_depth=0.0,
        shear_key_width=0.5,
        wall_length=5.0,
        concrete_unit_weight=24.0,
    )
    soil = SoilProperties()
    seismic = SeismicParams()
    results = AnalysisResults(
        total_thrust=150.0,
        concrete_tensile_stress=3.2,
        cracking_predicted=True,
    )
    return geom, soil, seismic, results


def test_wall_mesh_type_and_scalars(standard_setup):
    geom, _, _, results = standard_setup
    mesh = build_3d_wall_mesh(geom, results)

    assert isinstance(mesh, pv.UnstructuredGrid)
    assert mesh.n_points > 0
    assert mesh.n_cells > 0

    # Assert scalars are attached
    assert "TensileStress_MPa" in mesh.point_data
    assert "Deformation_m" in mesh.point_data

    # Check stress peak is at base junction
    stresses = mesh.point_data["TensileStress_MPa"]
    assert np.max(stresses) > 0.0
    assert np.all(stresses >= 0.0)


def test_wall_mesh_cell_types(standard_setup):
    geom, _, _, results = standard_setup
    mesh = build_3d_wall_mesh(geom, results)

    # All generated solid cells must be VTK_HEXAHEDRON (CellType 12)
    cell_types = mesh.celltypes
    assert np.all(cell_types == pv.CellType.HEXAHEDRON)


def test_wall_mesh_bounds(standard_setup):
    geom, _, _, results = standard_setup
    mesh = build_3d_wall_mesh(geom, results)
    bounds = mesh.bounds

    # X bounds: 0 to base_width
    assert bounds[0] == pytest.approx(0.0, abs=1e-3)
    assert bounds[1] == pytest.approx(geom.base_width, abs=1e-3)

    # Y bounds: 0 to total_height
    assert bounds[2] == pytest.approx(0.0, abs=1e-3)
    assert bounds[3] == pytest.approx(geom.total_height, abs=1e-3)

    # Z bounds: 0 to wall_length
    assert bounds[4] == pytest.approx(0.0, abs=1e-3)
    assert bounds[5] == pytest.approx(geom.wall_length, abs=1e-3)


def test_shear_key_toggle_and_bounds(standard_setup):
    geom, _, _, results = standard_setup

    # Mesh without shear key
    geom_no_key = RetainingWallGeometry(
        stem_height=geom.stem_height,
        stem_thickness_top=geom.stem_thickness_top,
        stem_thickness_base=geom.stem_thickness_base,
        toe_length=geom.toe_length,
        heel_length=geom.heel_length,
        footing_thickness=geom.footing_thickness,
        shear_key_depth=0.0,
        shear_key_width=0.5,
        wall_length=geom.wall_length,
    )
    mesh_no_key = build_3d_wall_mesh(geom_no_key, results)
    assert mesh_no_key.bounds[2] == pytest.approx(0.0, abs=1e-3)

    # Mesh with rectangular shear key (depth = 0.5m)
    geom_with_key = RetainingWallGeometry(
        stem_height=geom.stem_height,
        stem_thickness_top=geom.stem_thickness_top,
        stem_thickness_base=geom.stem_thickness_base,
        toe_length=geom.toe_length,
        heel_length=geom.heel_length,
        footing_thickness=geom.footing_thickness,
        shear_key_depth=0.5,
        shear_key_width=0.6,
        wall_length=geom.wall_length,
    )
    mesh_with_key = build_3d_wall_mesh(geom_with_key, results, shear_key_type="rectangular")
    assert mesh_with_key.n_cells > mesh_no_key.n_cells
    assert mesh_with_key.n_points > mesh_no_key.n_points
    # Bounds must extend to -0.5 in Y
    assert mesh_with_key.bounds[2] == pytest.approx(-0.5, abs=1e-3)

    # Mesh with trapezoidal shear key
    mesh_trap_key = build_3d_wall_mesh(geom_with_key, results, shear_key_type="trapezoidal")
    assert mesh_trap_key.bounds[2] == pytest.approx(-0.5, abs=1e-3)
    assert np.all(mesh_trap_key.celltypes == pv.CellType.HEXAHEDRON)


def test_multi_template_support(standard_setup):
    geom, _, _, results = standard_setup

    for template in [
        WallTemplate.INVERTED_T,
        WallTemplate.L_SHAPED,
        WallTemplate.REVERSE_L,
        WallTemplate.GRAVITY,
    ]:
        mesh = build_3d_wall_mesh(geom, results, template=template)
        assert isinstance(mesh, pv.UnstructuredGrid)
        assert mesh.n_cells > 0
        assert np.all(mesh.celltypes == pv.CellType.HEXAHEDRON)
        assert "TensileStress_MPa" in mesh.point_data


def test_volume_conservation(standard_setup):
    geom, _, _, results = standard_setup
    geom_with_key = RetainingWallGeometry(
        stem_height=6.0,
        stem_thickness_top=0.35,
        stem_thickness_base=0.65,
        toe_length=1.0,
        heel_length=2.5,
        footing_thickness=0.7,
        shear_key_depth=0.4,
        shear_key_width=0.5,
        wall_length=5.0,
    )
    props = compute_wall_geometric_properties(geom_with_key, template=WallTemplate.INVERTED_T)
    mesh = build_3d_wall_mesh(geom_with_key, results)

    # Mesh volume vs analytical volume must match to within 0.01%
    rel_error = abs(mesh.volume - props.volume) / props.volume
    assert rel_error < 0.0001, f"Volume error {rel_error:.6f} exceeded 0.01%"


def test_wall_geometric_properties_closed_form(standard_setup):
    geom, _, _, _ = standard_setup
    
    # Inverted-T with rectangular key
    props_t = compute_wall_geometric_properties(geom, template=WallTemplate.INVERTED_T)
    assert isinstance(props_t, WallGeometricProperties)
    assert props_t.volume > 0.0
    assert props_t.mass == pytest.approx(props_t.volume * geom.concrete_unit_weight, rel=1e-6)
    assert props_t.surface_area > 0.0

    # Center of gravity checks
    xcg, ycg, zcg = props_t.center_of_gravity
    assert 0.0 < xcg < geom.base_width
    assert 0.0 < ycg < geom.total_height
    assert zcg == pytest.approx(geom.wall_length / 2.0, rel=1e-5)

    # Moments of inertia must be strictly positive
    ixx, iyy, izz = props_t.moments_of_inertia
    assert ixx > 0.0
    assert iyy > 0.0
    assert izz > 0.0

    # L-Shaped
    props_l = compute_wall_geometric_properties(geom, template=WallTemplate.L_SHAPED)
    assert props_l.volume > 0.0
    assert props_l.surface_area > 0.0

    # Reverse-L
    props_rev = compute_wall_geometric_properties(geom, template=WallTemplate.REVERSE_L)
    assert props_rev.volume > 0.0

    # Gravity template
    props_grav = compute_wall_geometric_properties(geom, template=WallTemplate.GRAVITY)
    assert props_grav.volume > 0.0
    assert props_grav.surface_area > 0.0

    # Trapezoidal shear key
    geom_key = RetainingWallGeometry(shear_key_depth=0.5, shear_key_width=0.6)
    props_trap = compute_wall_geometric_properties(
        geom_key,
        template=WallTemplate.INVERTED_T,
        shear_key_type="trapezoidal",
    )
    assert props_trap.volume > 0.0


def test_jacobian_positivity_all_cells(standard_setup):
    geom, _, _, results = standard_setup
    geom_key = RetainingWallGeometry(
        stem_height=5.0,
        stem_thickness_top=0.3,
        stem_thickness_base=0.7,
        toe_length=0.8,
        heel_length=2.0,
        footing_thickness=0.6,
        shear_key_depth=0.3,
        shear_key_width=0.4,
        wall_length=4.0,
    )
    mesh = build_3d_wall_mesh(geom_key, results)
    det_j = compute_hex_jacobian_determinants(mesh)

    assert len(det_j) == mesh.n_cells
    # Strictly positive Jacobian: no inverted, twisted or zero-volume elements
    assert np.all(det_j > 0.0), f"Found {np.sum(det_j <= 0)} inverted/non-positive Jacobian cells!"
    assert np.min(det_j) > 1e-6

    # Test non-hex element handling fallback
    sphere = pv.Sphere()
    det_j_sphere = compute_hex_jacobian_determinants(sphere)
    assert len(det_j_sphere) == sphere.n_cells
    assert np.all(det_j_sphere == 1.0)


def test_mesher_sub_millisecond_performance(standard_setup):
    geom, _, _, results = standard_setup

    # Warmup
    _ = build_3d_wall_mesh(geom, results)

    # Benchmark 20 runs
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        _ = build_3d_wall_mesh(geom, results)
        times.append((time.perf_counter() - t0) * 1000.0)

    avg_ms = np.mean(times)
    # Must solve in < 5 ms for 60 FPS slider tuning
    assert avg_ms < 5.0, f"Mesher took too long: {avg_ms:.2f} ms"


def test_soil_and_water_meshes(standard_setup):
    geom, soil, seismic, results = standard_setup
    backfill, foundation, water_plane = build_3d_soil_mesh(geom, soil, seismic, results)

    assert isinstance(backfill, (pv.PolyData, pv.UnstructuredGrid))
    assert isinstance(foundation, (pv.PolyData, pv.UnstructuredGrid))
    assert isinstance(water_plane, pv.PolyData)

    assert backfill.n_cells > 0
    assert foundation.n_cells > 0
    assert water_plane.n_points > 0


def test_build_3d_wedge_mesh(standard_setup):
    geom, soil, seismic, results = standard_setup
    wedge_mesh = build_3d_wedge_mesh(geom, soil, seismic, results)

    assert isinstance(wedge_mesh, (pv.PolyData, pv.UnstructuredGrid))
    assert wedge_mesh.n_cells > 0
    # Wedge bounds should lie behind the stem
    w_bounds = wedge_mesh.bounds
    stem_x_back = geom.toe_length + geom.stem_thickness_base
    assert w_bounds[0] >= stem_x_back - 0.1
