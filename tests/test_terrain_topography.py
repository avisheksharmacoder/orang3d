"""
Unit, Invariant, and Benchmark Tests for Phase 5:
Hill-Slope Topography, DEM Raster Ingestion & Topographic Amplification.
"""

import math
import os
import tempfile
import pytest
import numpy as np

from orang3d.models.advanced_wall_params import (
    CurvedShellGeometry,
    PierAndPileGeometry,
    StrutSupportSystem,
    MultiStrutPiledWallModel,
)
from orang3d.mesher.terrain import (
    TerrainRaster,
    DrapedWallAlignment,
    read_geotiff_dem,
    write_geotiff_dem,
    read_ascii_grid,
    write_ascii_grid,
    read_xyz_point_cloud,
    generate_synthetic_slope,
    drape_wall_on_terrain,
    RASTERIO_AVAILABLE,
)
from orang3d.signals.topography import (
    TopographicAmplificationResult,
    compute_topographic_amplification_factor,
    apply_topographic_amplification,
    compute_slope_modified_passive_resistance,
)


# ==============================================================================
# 1. GeoTIFF DEM Parser & Round-Trip
# ==============================================================================

def test_geotiff_parser():
    """
    Phase 5.4: Verifies correct reading of elevations, nodata values, and spatial geotransforms.
    """
    if not RASTERIO_AVAILABLE:
        pytest.skip("rasterio is required for GeoTIFF parser test")

    # Generate synthetic planar terrain
    terrain_orig = generate_synthetic_slope(
        slope_type="planar",
        length_x=60.0,
        width_y=40.0,
        resolution=2.0,
        slope_angle_deg=20.0,
        crest_elevation=25.0,
    )

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        # Write to GeoTIFF
        write_geotiff_dem(tmp_path, terrain_orig, crs="EPSG:32645")

        # Read back from GeoTIFF
        terrain_read = read_geotiff_dem(tmp_path)

        assert terrain_read.elevations.shape == terrain_orig.elevations.shape
        assert math.isclose(terrain_read.bounds[0], terrain_orig.bounds[0], abs_tol=1e-3)
        assert math.isclose(terrain_read.bounds[2], terrain_orig.bounds[2], abs_tol=1e-3)
        assert np.allclose(terrain_read.elevations, terrain_orig.elevations, atol=1e-3)
        assert terrain_read.crs is not None

        # Nodata value verification
        assert terrain_read.nodata_value is not None

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ==============================================================================
# 2. Parametric Synthetic Slope Generation
# ==============================================================================

def test_synthetic_slope_generation():
    """
    Phase 5.4: Validates parametric generation of planar, benched, and bilinear slopes.
    """
    # 1. Planar slope
    slope_angle = 30.0
    planar = generate_synthetic_slope(
        slope_type="planar",
        length_x=100.0,
        width_y=50.0,
        resolution=1.0,
        slope_angle_deg=slope_angle,
        crest_elevation=50.0,
    )
    assert planar.elevations.shape == (51, 101)
    # Mean slope gradient along X must match tan(30 deg) within 1%
    dz_dx, _, slp_deg = planar.gradient_at(x=50.0, y=25.0)
    assert math.isclose(slp_deg, slope_angle, abs_tol=0.1)
    assert math.isclose(dz_dx, math.tan(math.radians(slope_angle)), rel_tol=1e-3)

    # 2. Benched slope (stepped berms)
    benched = generate_synthetic_slope(
        slope_type="benched",
        length_x=80.0,
        width_y=40.0,
        resolution=1.0,
        slope_angle_deg=35.0,
        bench_width=6.0,
        bench_height=8.0,
    )
    assert benched.elevations.shape == (41, 81)
    # Check that flat benches exist (slope angle near 0)
    # Bench occurs at the end of each cycle
    tan_slope = math.tan(math.radians(35.0))
    riser_run = 8.0 / tan_slope
    bench_x = riser_run + 3.0 # Middle of first bench
    _, _, bench_slp = benched.gradient_at(x=bench_x, y=20.0, step=0.2)
    assert bench_slp < 5.0, f"Expected flat bench slope < 5 deg, got {bench_slp} deg"

    # 3. Bilinear slope
    bilinear = generate_synthetic_slope(
        slope_type="bilinear",
        length_x=100.0,
        width_y=40.0,
        resolution=1.0,
        hinge_distance=40.0,
        slope_angle_toe_deg=40.0,
        slope_angle_crest_deg=15.0,
    )
    assert bilinear.elevations.shape == (41, 101)
    # Before hinge (x=20): steep toe slope (~40 deg)
    _, _, toe_slp = bilinear.gradient_at(x=20.0, y=20.0)
    assert math.isclose(toe_slp, 40.0, abs_tol=1.0)
    # After hinge (x=70): gentle crest slope (~15 deg)
    _, _, crest_slp = bilinear.gradient_at(x=70.0, y=20.0)
    assert math.isclose(crest_slp, 15.0, abs_tol=1.0)


# ==============================================================================
# 3. Topographic Seismic Amplification Invariants
# ==============================================================================

def test_topographic_amplification_bounds():
    """
    Phase 5.4: Checks that S_T >= 1.0 for all valid slopes, peaking at the crest.
    Validates Eurocode 8 / IS 1893 criteria:
    - beta <= 15 deg: S_T = 1.0
    - 15 deg < beta <= 30 deg: S_T = 1.2
    - beta > 30 deg: S_T = 1.4 (ridge)
    """
    # 1. Gentle slope (beta = 10 deg <= 15 deg): No amplification
    st_gentle = compute_topographic_amplification_factor(slope_angle_deg=10.0, crest_distance=0.0)
    assert st_gentle == 1.0

    # 2. Medium slope (15 < beta <= 30 deg): S_T = 1.2 at crest
    st_medium = compute_topographic_amplification_factor(slope_angle_deg=25.0, crest_distance=0.0)
    assert math.isclose(st_medium, 1.2, abs_tol=1e-4)

    # 3. Steep slope (beta = 38 deg > 30 deg): S_T = 1.4 for ridge, 1.2 for cliff
    st_steep_ridge = compute_topographic_amplification_factor(
        slope_angle_deg=38.0, crest_distance=0.0, feature_type="ridge"
    )
    assert math.isclose(st_steep_ridge, 1.4, abs_tol=1e-4)

    st_steep_cliff = compute_topographic_amplification_factor(
        slope_angle_deg=38.0, crest_distance=0.0, feature_type="cliff"
    )
    assert math.isclose(st_steep_cliff, 1.2, abs_tol=1e-4)

    # 4. Spatial attenuation: Amplification strictly decays away from crest
    st_at_crest = compute_topographic_amplification_factor(slope_angle_deg=35.0, crest_distance=0.0)
    st_dist_10m = compute_topographic_amplification_factor(slope_angle_deg=35.0, crest_distance=10.0)
    st_dist_50m = compute_topographic_amplification_factor(slope_angle_deg=35.0, crest_distance=50.0)

    assert st_at_crest > st_dist_10m > st_dist_50m >= 1.0

    # 5. Time-history scaling
    time_arr = np.linspace(0.0, 1.0, 100)
    accel_arr = 0.25 * np.sin(2.0 * np.pi * 3.0 * time_arr)
    res = apply_topographic_amplification(
        time_arr=time_arr,
        accel_arr=accel_arr,
        slope_angle_deg=32.0,
        crest_distance=0.0,
        hill_height=30.0,
        shear_wave_velocity=300.0,
    )
    assert math.isclose(res.st_factor, 1.4, abs_tol=1e-4)
    assert math.isclose(res.peak_ground_acceleration_crest, res.peak_ground_acceleration_base * res.st_factor, rel_tol=1e-4)
    # Resonant frequency f_0 = Vs / (4 * H) = 300 / (4 * 30) = 2.5 Hz
    assert math.isclose(res.resonant_frequency_hz, 2.5, abs_tol=1e-4)


# ==============================================================================
# 4. Surface Draping & Alignment Verification
# ==============================================================================

def test_surface_draping_alignment():
    """
    Phase 5.4: Verifies that pile collar and pier base elevations match
    sampled terrain elevation at every pier location.
    """
    # 25 degree planar slope rising from X=0 to X=100
    terrain = generate_synthetic_slope(
        slope_type="planar",
        length_x=100.0,
        width_y=60.0,
        resolution=1.0,
        slope_angle_deg=25.0,
        crest_elevation=40.0,
    )

    model = MultiStrutPiledWallModel(
        shell=CurvedShellGeometry(bay_span=4.0)
    )

    # Drape wall at center (X=50, Y=30)
    alignment = drape_wall_on_terrain(
        model=model,
        terrain=terrain,
        wall_center_x=50.0,
        wall_center_y=30.0,
        num_bays=3,
    )

    assert len(alignment.pier_ground_elevations) == 4 # 3 bays -> 4 piers
    # Wall is aligned along Y (perpendicular to slope along X)
    # For a slope rising along X, all piers at X=50 have identical elevation
    z_expected = terrain.elevation_at(50.0, 30.0)
    for p_idx, z_val in alignment.pier_ground_elevations.items():
        assert math.isclose(z_val, z_expected, abs_tol=1e-4)
        assert math.isclose(alignment.aligned_pier_bases[p_idx], z_val, abs_tol=1e-4)

    assert math.isclose(alignment.crest_offset_distance, 50.0, abs_tol=1.0)
    assert math.isclose(alignment.toe_offset_distance, 50.0, abs_tol=1.0)
    assert math.isclose(alignment.mean_ground_slope_deg, 25.0, abs_tol=0.2)


# ==============================================================================
# 5. ASCII Grid & XYZ Point Cloud Formats
# ==============================================================================

def test_ascii_grid_roundtrip():
    """Verifies reading and writing of ESRI ASCII Grid (.asc) files."""
    terrain_orig = generate_synthetic_slope(
        slope_type="planar", length_x=40.0, width_y=30.0, resolution=2.0, slope_angle_deg=18.0
    )

    with tempfile.NamedTemporaryFile(suffix=".asc", delete=False, mode="w") as tmp_file:
        tmp_path = tmp_file.name

    try:
        write_ascii_grid(tmp_path, terrain_orig)
        terrain_read = read_ascii_grid(tmp_path)

        assert terrain_read.elevations.shape == terrain_orig.elevations.shape
        assert np.allclose(terrain_read.elevations, terrain_orig.elevations, atol=1e-3)
        assert math.isclose(terrain_read.dx, terrain_orig.dx, abs_tol=1e-3)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_xyz_point_cloud_parser():
    """Verifies XYZ point cloud ingestion and irregular scatter gridding."""
    # Create sample XYZ point cloud
    np.random.seed(42)
    n_pts = 100
    x_pts = np.random.uniform(0.0, 50.0, n_pts)
    y_pts = np.random.uniform(0.0, 30.0, n_pts)
    # Planar slope z = 10.0 + 0.5 * x
    z_pts = 10.0 + 0.5 * x_pts

    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False, mode="w") as tmp_file:
        tmp_path = tmp_file.name
        for x, y, z in zip(x_pts, y_pts, z_pts):
            tmp_file.write(f"{x:.4f} {y:.4f} {z:.4f}\n")

    try:
        terrain_xyz = read_xyz_point_cloud(tmp_path, grid_resolution=2.0)
        assert terrain_xyz.elevations.ndim == 2
        # Center point should have elevation ~ 10 + 0.5 * 25 = 22.5
        z_mid = terrain_xyz.elevation_at(25.0, 15.0)
        assert math.isclose(z_mid, 22.5, abs_tol=1.5)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ==============================================================================
# 6. Cross-Section, PyVista Mesh & Slope Passive Resistance
# ==============================================================================

def test_cross_section_and_pyvista_mesh():
    """Verifies 2D transect extraction and PyVista StructuredGrid mesh creation."""
    terrain = generate_synthetic_slope(
        slope_type="planar", length_x=80.0, width_y=40.0, resolution=2.0, slope_angle_deg=22.0
    )

    # 1. 2D Cross section
    dists, elevs, slopes = terrain.extract_cross_section(
        start_pt=(0.0, 20.0), end_pt=(80.0, 20.0), num_samples=50
    )
    assert len(dists) == 50
    assert len(elevs) == 50
    assert math.isclose(dists[0], 0.0)
    assert math.isclose(dists[-1], 80.0)
    assert np.all(np.diff(elevs) > 0) # Monotonically rising
    assert np.allclose(slopes, 22.0, atol=0.5)

    # 2. PyVista StructuredGrid conversion
    mesh = terrain.to_pyvista_mesh()
    assert mesh.n_points == terrain.elevations.size
    assert "Elevation" in mesh.point_data
    assert "Slope_Angle_Deg" in mesh.point_data
    assert float(np.max(mesh.point_data["Slope_Angle_Deg"])) > 0.0


def test_slope_modified_passive_resistance():
    """Verifies reduction of passive resistance Kp on sloping ground."""
    kp_level = 4.0
    phi = 32.0

    # Downhill slope beta = 15 deg reduces passive resistance
    kp_slope_15 = compute_slope_modified_passive_resistance(
        kp_level=kp_level, slope_angle_deg=15.0, soil_friction_angle_deg=phi
    )
    assert kp_slope_15 < kp_level
    assert kp_slope_15 > 0.0

    # Steeper slope beta = 25 deg further reduces passive resistance
    kp_slope_25 = compute_slope_modified_passive_resistance(
        kp_level=kp_level, slope_angle_deg=25.0, soil_friction_angle_deg=phi
    )
    assert kp_slope_25 < kp_slope_15

    # Slope angle exceeding friction angle (unstable daylight)
    kp_unstable = compute_slope_modified_passive_resistance(
        kp_level=kp_level, slope_angle_deg=35.0, soil_friction_angle_deg=phi
    )
    assert kp_unstable == 0.1 * kp_level


def test_terrain_edge_cases():
    """Verifies edge cases and error bounds in terrain and topography."""
    # Invalid synthetic slope dimensions
    with pytest.raises(ValueError, match="length_x and width_y must be positive"):
        generate_synthetic_slope(length_x=-10.0)

    with pytest.raises(ValueError, match="resolution must be positive"):
        generate_synthetic_slope(resolution=0.0)

    with pytest.raises(ValueError, match="Unknown slope_type"):
        generate_synthetic_slope(slope_type="nonexistent")

    # Identical start and end points in cross section
    terrain = generate_synthetic_slope()
    with pytest.raises(ValueError, match="cannot be identical"):
        terrain.extract_cross_section(start_pt=(10.0, 10.0), end_pt=(10.0, 10.0))

    # Invalid hill height in topographic amplification
    with pytest.raises(ValueError, match="hill_height must be positive"):
        compute_topographic_amplification_factor(slope_angle_deg=20.0, hill_height=0.0)

    # Empty acceleration array
    with pytest.raises(ValueError, match="accel_arr cannot be empty"):
        apply_topographic_amplification(time_arr=np.array([]), accel_arr=np.array([]), slope_angle_deg=20.0)

    # Invalid friction angle in passive resistance
    with pytest.raises(ValueError, match="soil_friction_angle_deg must be in"):
        compute_slope_modified_passive_resistance(kp_level=3.0, slope_angle_deg=10.0, soil_friction_angle_deg=0.0)

    with pytest.raises(ValueError, match="kp_level must be positive"):
        compute_slope_modified_passive_resistance(kp_level=-1.0, slope_angle_deg=10.0, soil_friction_angle_deg=30.0)

    # Invalid shear wave velocity
    with pytest.raises(ValueError, match="shear_wave_velocity must be positive"):
        apply_topographic_amplification(
            time_arr=np.array([0.0, 1.0]),
            accel_arr=np.array([0.1, 0.2]),
            slope_angle_deg=20.0,
            shear_wave_velocity=-100.0,
        )

    # Terrain raster validation checks
    with pytest.raises(ValueError, match="elevations must be 2D array"):
        TerrainRaster(elevations=np.ones(10), x_coords=np.ones(10), y_coords=np.ones(10))

    with pytest.raises(ValueError, match="y_coords length"):
        TerrainRaster(elevations=np.ones((5, 10)), x_coords=np.ones(10), y_coords=np.ones(6))

    with pytest.raises(ValueError, match="x_coords length"):
        TerrainRaster(elevations=np.ones((5, 10)), x_coords=np.ones(9), y_coords=np.ones(5))

    # Nodata replacement in TerrainRaster
    elev_nodata = np.array([[10.0, -9999.0], [12.0, 14.0]])
    raster_nodata = TerrainRaster(
        elevations=elev_nodata,
        x_coords=np.array([0.0, 10.0]),
        y_coords=np.array([0.0, 10.0]),
        nodata_value=-9999.0,
    )
    assert not np.any(np.isclose(raster_nodata.elevations, -9999.0))
    assert math.isclose(raster_nodata.min_elevation, 10.0, abs_tol=1e-4)
    assert math.isclose(raster_nodata.max_elevation, 14.0, abs_tol=1e-4)

    # Gradient boundary checks in Y direction
    dz_dx, dz_dy_min, _ = raster_nodata.gradient_at(5.0, 0.0, step=1.0)
    assert isinstance(dz_dy_min, float)
    dz_dx, dz_dy_max, _ = raster_nodata.gradient_at(5.0, 10.0, step=1.0)
    assert isinstance(dz_dy_max, float)

    # XYZ point cloud invalid shape
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False, mode="w") as tmp_xyz:
        tmp_xyz.write("1.0 2.0\n3.0 4.0\n")
        tmp_xyz_path = tmp_xyz.name

    try:
        with pytest.raises(ValueError, match="must contain at least 3 columns"):
            read_xyz_point_cloud(tmp_xyz_path)
    finally:
        if os.path.exists(tmp_xyz_path):
            os.remove(tmp_xyz_path)
