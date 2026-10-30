"""
Unit, invariant, and performance tests for Phase 2:
3D Parametric Curved Shell, Pier, Pile, Strut & Multi-Element Mesher.
"""

import time
import math
import pytest
import numpy as np
import pyvista as pv

from orang3d.models.advanced_wall_params import (
    CurvedShellGeometry,
    PierAndPileGeometry,
    StrutSupportSystem,
    MultiStrutPiledWallModel,
)
from orang3d.models.tower_params import TransmissionTowerParams
from orang3d.mesher.shell_mesher import (
    shell_crown_profile,
    compute_shell_surface_normals,
    compute_hex_jacobian_determinants,
    build_curved_shell_panel_mesh,
    build_multi_bay_shell_mesh,
)
from orang3d.mesher.pile_strut_mesher import (
    build_pier_mesh,
    build_pile_cap_mesh,
    build_conformal_pier_and_cap_mesh,
    build_bored_piles_mesh,
    build_raking_struts_mesh,
    build_transmission_tower_mesh,
)
from orang3d.mesher.hybrid_assembler import (
    assemble_multi_strut_piled_wall_mesh,
    verify_conformal_junctions,
    build_high_fidelity_gmsh_mesh,
)


# ==============================================================================
# 1. Shell Curvature & Geometry
# ==============================================================================

def test_shell_curvature_geometry():
    """
    Phase 2.4: Verifies that panel crown coordinates match z(x) = R - sqrt(R^2 - x^2)
    within 10^-6 m.
    """
    R = 4.5
    test_x = np.array([-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0], dtype=np.float64)

    # Theoretical closed-form formula
    expected_z = R - np.sqrt(R**2 - test_x**2)
    computed_z = shell_crown_profile(test_x, R)

    assert np.allclose(computed_z, expected_z, atol=1e-6)

    # Scalar check at apex / crown center
    assert shell_crown_profile(0.0, R) == pytest.approx(0.0, abs=1e-9)

    # Specific point check: x = 1.5, R = 4.5
    # z = 4.5 - sqrt(20.25 - 2.25) = 4.5 - sqrt(18.0)
    assert shell_crown_profile(1.5, R) == pytest.approx(4.5 - math.sqrt(18.0), abs=1e-7)

    # Exceeding radius raises ValueError
    with pytest.raises(ValueError, match="Coordinate x exceeds cylinder radius"):
        shell_crown_profile(5.0, R)


# ==============================================================================
# 2. Surface Normals & Orientation
# ==============================================================================

def test_mesh_surface_normals():
    """
    Phase 2.4: Verifies that shell normal vectors point outward toward backfill
    (n_z > 0) to ensure correct earth pressure application.
    """
    R = 4.0
    x_coords = np.linspace(-1.5, 1.5, 11)

    # Outward normals towards backfill
    normals = compute_shell_surface_normals(x_coords, R, crown_to_backfill=True)

    # 1. Normal magnitude must be strictly 1.0 (unit vectors)
    magnitudes = np.linalg.norm(normals, axis=-1)
    assert np.allclose(magnitudes, 1.0, atol=1e-7)

    # 2. All normal vectors must have strictly positive Z-component pointing into backfill
    assert np.all(normals[:, 2] > 0.0)

    # 3. Symmetry: nx(-x) = -nx(x)
    assert np.allclose(normals[:, 0], -normals[::-1, 0], atol=1e-7)

    # 4. At crown center (x=0), normal must point purely in +Z
    norm_center = compute_shell_surface_normals(0.0, R, crown_to_backfill=True)
    assert norm_center[0] == pytest.approx(0.0, abs=1e-9)
    assert norm_center[1] == pytest.approx(0.0, abs=1e-9)
    assert norm_center[2] == pytest.approx(1.0, abs=1e-9)

    # 5. Check normals attached to PyVista mesh
    geom = CurvedShellGeometry(radius=R, bay_span=3.5, panel_height=5.0)
    mesh = build_curved_shell_panel_mesh(geom, nx=8, ny=10, nz=2)
    mesh_normals = mesh.point_data["Normals"]
    assert np.all(mesh_normals[:, 2] > 0.0)


# ==============================================================================
# 3. Conformal Pier-Pile Subgrade Junction
# ==============================================================================

def test_conformal_pier_pile_junction():
    """
    Phase 2.4: Ensures nodes at the base of the pier match exactly with the top of the pile cap.
    """
    geom = PierAndPileGeometry(
        pier_width=0.8,
        pier_depth=1.0,
        pier_height=6.5,
        pile_cap_width=1.6,
        pile_cap_length=3.0,
        pile_cap_depth=1.2,
    )

    y_junction = 0.0
    pier_grid, cap_grid = build_conformal_pier_and_cap_mesh(
        geom=geom,
        pier_x=2.5,
        y_junction=y_junction,
        z_base=0.0,
        n_sub=4,
    )

    # Verify conformal alignment
    assert verify_conformal_junctions(pier_grid, cap_grid, y_junction=y_junction, tolerance=1e-6)

    # Check pier bottom node elevations
    pier_base_pts = pier_grid.points[np.isclose(pier_grid.points[:, 1], y_junction, atol=1e-6)]
    assert len(pier_base_pts) == 4 * 4 # nx=4 * nz=4 = 16 nodes

    # For each pier bottom node, find exact matching cap top node
    cap_top_pts = cap_grid.points[np.isclose(cap_grid.points[:, 1], y_junction, atol=1e-6)]
    for pb in pier_base_pts:
        min_dist = np.min(np.linalg.norm(cap_top_pts - pb, axis=1))
        assert min_dist < 1e-6, f"Node {pb} has no matching node on pile cap top"


# ==============================================================================
# 4. Mesher Latency Benchmark
# ==============================================================================

def test_mesher_latency_benchmark():
    """
    Phase 2.4: Enforces runtime threshold: full 3-bay retaining wall meshing in < 5 ms.
    """
    model = MultiStrutPiledWallModel(
        shell=CurvedShellGeometry(radius=4.5, bay_span=4.0, panel_height=6.0),
        pier_pile=PierAndPileGeometry(pier_width=0.8, pier_depth=1.0, pier_height=6.5),
        struts=StrutSupportSystem(strut_levels=[2.5, 5.0]),
    )
    tower = TransmissionTowerParams()

    # Warmup run to compile/cache
    _ = assemble_multi_strut_piled_wall_mesh(model, tower=tower, num_bays=3)

    # Benchmark over 25 iterations
    iterations = 25
    start_time = time.perf_counter()
    for _ in range(iterations):
        _ = assemble_multi_strut_piled_wall_mesh(
            model,
            tower=tower,
            num_bays=3,
            nx_shell=8,
            ny_shell=10,
            nz_shell=2,
        )
    total_time = time.perf_counter() - start_time
    avg_latency_ms = (total_time / iterations) * 1000.0

    print(f"\n[BENCHMARK] Multi-bay mesher average latency: {avg_latency_ms:.3f} ms (Threshold: < 5.0 ms)")
    assert avg_latency_ms < 5.0, f"Mesher latency {avg_latency_ms:.3f} ms exceeded 5.0 ms threshold"


# ==============================================================================
# 5. Jacobian Positivity (det(J) > 0)
# ==============================================================================

def test_jacobian_determinants():
    """
    Phase 2.4: Guarantees all 3D solid elements have det(J) > 0.
    """
    # 1. Shell Panel Hex Elements
    shell_geom = CurvedShellGeometry(radius=4.0, bay_span=3.5, panel_height=6.0, thickness=0.25)
    shell_mesh = build_curved_shell_panel_mesh(shell_geom, nx=8, ny=10, nz=3)
    det_j_shell = compute_hex_jacobian_determinants(shell_mesh)

    assert len(det_j_shell) == (8 - 1) * (10 - 1) * (3 - 1)
    assert np.all(det_j_shell > 0.0), f"Found non-positive Jacobian in shell mesh: min={np.min(det_j_shell)}"

    # 2. Pier Hex Elements
    pier_geom = PierAndPileGeometry(pier_width=0.8, pier_depth=1.0, pier_height=6.0)
    pier_mesh = build_pier_mesh(pier_geom, nx=4, ny=8, nz=4)
    det_j_pier = compute_hex_jacobian_determinants(pier_mesh)

    assert len(det_j_pier) == (4 - 1) * (8 - 1) * (4 - 1)
    assert np.all(det_j_pier > 0.0), f"Found non-positive Jacobian in pier mesh: min={np.min(det_j_pier)}"

    # 3. Pile Cap Hex Elements
    cap_mesh = build_pile_cap_mesh(pier_geom, nx=4, ny=4, nz=4)
    det_j_cap = compute_hex_jacobian_determinants(cap_mesh)

    assert len(det_j_cap) == (4 - 1) * (4 - 1) * (4 - 1)
    assert np.all(det_j_cap > 0.0), f"Found non-positive Jacobian in cap mesh: min={np.min(det_j_cap)}"

    # 4. Assembled Multi-Bay Retaining Wall Solid Elements
    model = MultiStrutPiledWallModel(shell=shell_geom, pier_pile=pier_geom)
    assembled = assemble_multi_strut_piled_wall_mesh(model, num_bays=2, nx_shell=6, ny_shell=8, nz_shell=2)
    det_j_assembled = compute_hex_jacobian_determinants(assembled)

    assert len(det_j_assembled) > 0
    assert np.all(det_j_assembled > 0.0), f"Found non-positive Jacobian in assembled system: min={np.min(det_j_assembled)}"


# ==============================================================================
# 6. Bored Piles, Struts & Transmission Tower Elements
# ==============================================================================

def test_bored_piles_mesh():
    pier_geom = PierAndPileGeometry(
        pile_diameter=0.8,
        pile_length=10.0,
        num_piles_per_pier=2,
        pile_spacing=2.5,
    )
    piles_mesh = build_bored_piles_mesh(pier_geom, pier_x=0.0, y_cap_bottom=-1.0, n_theta=6, n_depth=5)

    assert piles_mesh.n_cells > 0
    # All elements are 3D wedges (CellType 13)
    assert np.all(piles_mesh.celltypes == int(pv.CellType.WEDGE))
    assert np.all(piles_mesh.cell_data["Element_Type"] == 4) # 4 = Pile
    # Depth bounds check: piles must reach y = -1.0 - 10.0 = -11.0 m
    assert np.isclose(np.min(piles_mesh.points[:, 1]), -11.0, atol=1e-5)


def test_raking_struts_mesh():
    struts = StrutSupportSystem(strut_levels=[2.0, 4.5], inclination_angle=30.0, unbraced_length=8.0)
    struts_mesh = build_raking_struts_mesh(struts, pier_x=3.0, pier_height=6.0, y_base=0.0, z_front=0.0)

    # 2 struts = 2 line cells
    assert struts_mesh.n_cells == 2
    assert np.all(struts_mesh.celltypes == int(pv.CellType.LINE))
    assert np.all(struts_mesh.cell_data["Element_Type"] == 5) # 5 = Strut

    # Verify attachment elevations: y1 = 6.0 - 2.0 = 4.0 m, y2 = 6.0 - 4.5 = 1.5 m
    p_starts = struts_mesh.points[::2]
    assert np.isclose(p_starts[0, 1], 4.0)
    assert np.isclose(p_starts[1, 1], 1.5)

    # Verify downward rake: end points have lower y
    p_ends = struts_mesh.points[1::2]
    expected_dy = -8.0 * math.sin(math.radians(30.0)) # -4.0 m
    assert np.isclose(p_ends[0, 1] - p_starts[0, 1], expected_dy)


def test_transmission_tower_mesh():
    tower = TransmissionTowerParams(base_width=6.0, base_length=6.0, total_height=30.0, crest_offset=5.0)
    tower_mesh = build_transmission_tower_mesh(tower, crest_x=10.0, crest_y=6.0, crest_z=2.0)

    assert tower_mesh.n_cells > 0
    assert np.all(tower_mesh.celltypes == int(pv.CellType.LINE))
    assert np.all(tower_mesh.cell_data["Element_Type"] == 6) # 6 = Tower

    # Height bounds: base at y=6.0, peak at y = 6.0 + 30.0 = 36.0 m
    assert np.isclose(np.min(tower_mesh.points[:, 1]), 6.0)
    assert np.isclose(np.max(tower_mesh.points[:, 1]), 36.0)


def test_multi_bay_mesh_generation():
    shell_geom = CurvedShellGeometry(radius=4.5, bay_span=4.0, panel_height=5.0)
    # 3 bays
    multi_bay = build_multi_bay_shell_mesh(shell_geom, num_bays=3, pier_width=0.8, nx=6, ny=8, nz=2)

    assert multi_bay.n_cells > 0
    # Must contain 3 bay indices (0, 1, 2)
    bay_indices = np.unique(multi_bay.cell_data["Bay_Index"])
    assert list(bay_indices) == [0, 1, 2]

    # Single bay returns single grid without merge
    single_bay = build_multi_bay_shell_mesh(shell_geom, num_bays=1, pier_width=0.8, nx=4, ny=4, nz=2)
    assert single_bay.n_cells > 0

    # Invalid subdivisions or bay counts
    with pytest.raises(ValueError, match="num_bays must be >= 1"):
        build_multi_bay_shell_mesh(shell_geom, num_bays=0)
    with pytest.raises(ValueError, match="num_bays must be >= 1"):
        assemble_multi_strut_piled_wall_mesh(MultiStrutPiledWallModel(), num_bays=0)
    with pytest.raises(ValueError, match="Mesh subdivisions must be at least 2"):
        build_curved_shell_panel_mesh(shell_geom, nx=1)


def test_edge_cases_and_conformal_verification():
    # 1. Concave shell normals and scalar output
    norm_scalar = compute_shell_surface_normals(0.5, radius=4.0, crown_to_backfill=False)
    assert norm_scalar[2] < 0.0 # Pointing opposite

    # Coordinate x exceeding radius in normals
    with pytest.raises(ValueError, match="Coordinate x exceeds radius"):
        compute_shell_surface_normals(5.0, radius=4.0)

    # 2. Empty hex grid Jacobian
    empty_grid = pv.UnstructuredGrid()
    assert len(compute_hex_jacobian_determinants(empty_grid)) == 0

    # 3. Single pile configuration in subgrade and assembler
    single_pile_geom = PierAndPileGeometry(num_piles_per_pier=1, pile_spacing=0.0)
    sp_grid = build_bored_piles_mesh(single_pile_geom, n_theta=4, n_depth=4)
    assert sp_grid.n_cells > 0

    sp_model = MultiStrutPiledWallModel(pier_pile=single_pile_geom)
    sp_assembled = assemble_multi_strut_piled_wall_mesh(sp_model, num_bays=1, nx_shell=4, ny_shell=4, nz_shell=2)
    assert sp_assembled.n_cells > 0

    # 4. Conformal junction verification failure cases
    pier_grid, cap_grid = build_conformal_pier_and_cap_mesh(PierAndPileGeometry(), y_junction=0.0)
    # Empty points grid returns False
    assert verify_conformal_junctions(empty_grid, cap_grid) is False
    # Shifted grid returns False
    shifted_cap = cap_grid.copy()
    shifted_cap.points[:, 1] += 5.0 # Shifted away from y=0
    assert verify_conformal_junctions(pier_grid, shifted_cap, y_junction=0.0) is False
    # Shifted x-coordinate of single node at y=0 returns False
    perturbed_pier = pier_grid.copy()
    perturbed_pier.points[0, 0] += 5.0
    assert verify_conformal_junctions(perturbed_pier, cap_grid, y_junction=0.0) is False


def test_gmsh_fallback_graceful(monkeypatch):
    """Verifies that Gmsh fallback returns gracefully without throwing unhandled exceptions."""
    model = MultiStrutPiledWallModel()
    res = build_high_fidelity_gmsh_mesh(model)
    assert res is None or res is True

    # Test gmsh available path with mock
    import sys
    from unittest.mock import MagicMock
    mock_gmsh = MagicMock()
    monkeypatch.setitem(sys.modules, "gmsh", mock_gmsh)
    res_mocked = build_high_fidelity_gmsh_mesh(model)
    assert res_mocked is True
    mock_gmsh.initialize.assert_called_once()
    mock_gmsh.finalize.assert_called_once()
