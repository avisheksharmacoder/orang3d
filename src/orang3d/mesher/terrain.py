"""
Digital Elevation Model (DEM) and Hill-Slope Terrain Ingestion Engine.
Supports GeoTIFF (via rasterio), ESRI ASCII Grid (.asc), and XYZ point clouds.
Generates 3D digital surface meshes (PyVista StructuredGrid), parametric synthetic slopes
(planar, benched, bilinear), 2D cross-sections, and wall surface draping.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union, Any, BinaryIO
import numpy as np
from scipy.interpolate import RegularGridInterpolator, griddata
import pyvista as pv

try:
    import rasterio
    from rasterio.transform import from_origin
    RASTERIO_AVAILABLE = True
except (ImportError, Exception):
    rasterio = None
    from_origin = None
    RASTERIO_AVAILABLE = False

from ..models.advanced_wall_params import MultiStrutPiledWallModel


@dataclass
class TerrainRaster:
    """Digital Elevation Model (DEM) raster container with spatial coordinates."""
    elevations: np.ndarray       # 2D array [ny, nx] containing elevation values Z (m)
    x_coords: np.ndarray         # 1D array of X coordinates (m)
    y_coords: np.ndarray         # 1D array of Y coordinates (m)
    nodata_value: Optional[float] = None
    crs: Optional[str] = None
    _interpolator: Optional[RegularGridInterpolator] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if self.elevations.ndim != 2:
            raise ValueError(f"elevations must be 2D array [ny, nx], got shape {self.elevations.shape}")
        ny, nx = self.elevations.shape
        if len(self.y_coords) != ny:
            raise ValueError(f"y_coords length ({len(self.y_coords)}) must match elevations rows ({ny})")
        if len(self.x_coords) != nx:
            raise ValueError(f"x_coords length ({len(self.x_coords)}) must match elevations cols ({nx})")

        # Mask nodata if present
        if self.nodata_value is not None:
            mask = np.isclose(self.elevations, self.nodata_value)
            if np.any(mask) and not np.all(mask):
                valid_mean = float(np.nanmean(np.where(mask, np.nan, self.elevations)))
                self.elevations = np.where(mask, valid_mean, self.elevations)

        # Build interpolator (Y axis is rows, X axis is columns)
        self._interpolator = RegularGridInterpolator(
            (self.y_coords, self.x_coords),
            self.elevations,
            method="linear",
            bounds_error=False,
            fill_value=None,
        )

    @property
    def dx(self) -> float:
        """Horizontal grid spacing in X."""
        return float(abs(self.x_coords[1] - self.x_coords[0])) if len(self.x_coords) > 1 else 1.0

    @property
    def dy(self) -> float:
        """Horizontal grid spacing in Y."""
        return float(abs(self.y_coords[1] - self.y_coords[0])) if len(self.y_coords) > 1 else 1.0

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """(xmin, ymin, xmax, ymax) spatial bounds in meters."""
        return (
            float(np.min(self.x_coords)),
            float(np.min(self.y_coords)),
            float(np.max(self.x_coords)),
            float(np.max(self.y_coords)),
        )

    @property
    def min_elevation(self) -> float:
        return float(np.min(self.elevations))

    @property
    def max_elevation(self) -> float:
        return float(np.max(self.elevations))

    def elevation_at(self, x: float, y: float) -> float:
        """Evaluates interpolated elevation Z at any coordinate (x, y)."""
        clamped_x = max(min(x, float(np.max(self.x_coords))), float(np.min(self.x_coords)))
        clamped_y = max(min(y, float(np.max(self.y_coords))), float(np.min(self.y_coords)))
        val = self._interpolator([[clamped_y, clamped_x]])
        return float(val[0])

    def gradient_at(self, x: float, y: float, step: float = 0.5) -> Tuple[float, float, float]:
        """
        Computes local slope gradients (dz/dx, dz/dy) and slope angle in degrees.
        Uses forward/backward difference near boundaries to prevent edge damping.
        """
        xmin, ymin, xmax, ymax = self.bounds

        # X direction
        if x - step < xmin:
            dz_dx = (self.elevation_at(x + step, y) - self.elevation_at(x, y)) / step
        elif x + step > xmax:
            dz_dx = (self.elevation_at(x, y) - self.elevation_at(x - step, y)) / step
        else:
            dz_dx = (self.elevation_at(x + step, y) - self.elevation_at(x - step, y)) / (2.0 * step)

        # Y direction
        if y - step < ymin:
            dz_dy = (self.elevation_at(x, y + step) - self.elevation_at(x, y)) / step
        elif y + step > ymax:
            dz_dy = (self.elevation_at(x, y) - self.elevation_at(x, y - step)) / step
        else:
            dz_dy = (self.elevation_at(x, y + step) - self.elevation_at(x, y - step)) / (2.0 * step)

        grad_mag = math.sqrt(dz_dx ** 2 + dz_dy ** 2)
        slope_angle_deg = math.degrees(math.atan(grad_mag))
        return dz_dx, dz_dy, slope_angle_deg

    def extract_cross_section(
        self,
        start_pt: Tuple[float, float],
        end_pt: Tuple[float, float],
        num_samples: int = 100,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Extracts 2D elevation cross-section between start_pt and end_pt.
        Returns: (distances, elevations, local_slopes_deg).
        """
        x0, y0 = start_pt
        x1, y1 = end_pt
        tot_dist = math.hypot(x1 - x0, y1 - y0)
        if tot_dist < 1e-6:
            raise ValueError("start_pt and end_pt cannot be identical")

        t_vals = np.linspace(0.0, 1.0, num_samples)
        x_pts = x0 + t_vals * (x1 - x0)
        y_pts = y0 + t_vals * (y1 - y0)
        distances = t_vals * tot_dist

        sample_pts = np.column_stack([y_pts, x_pts])
        elevs = self._interpolator(sample_pts)

        # Compute gradient along section line
        slopes_deg = np.zeros(num_samples, dtype=np.float64)
        for i in range(num_samples):
            _, _, slp = self.gradient_at(float(x_pts[i]), float(y_pts[i]))
            slopes_deg[i] = slp

        return distances, elevs, slopes_deg

    def to_pyvista_mesh(self) -> pv.StructuredGrid:
        """
        Converts the 2D DEM into a 3D PyVista StructuredGrid digital surface mesh
        with scalar fields for Elevation and Slope_Angle_Deg.
        """
        X, Y = np.meshgrid(self.x_coords, self.y_coords)
        Z = self.elevations

        grid = pv.StructuredGrid(X, Y, Z)
        grid.point_data["Elevation"] = Z.ravel(order="F")

        # Compute slope gradient per node
        gy, gx = np.gradient(Z, self.dy, self.dx)
        grad_mag = np.sqrt(gx ** 2 + gy ** 2)
        slope_deg = np.degrees(np.arctan(grad_mag))
        grid.point_data["Slope_Angle_Deg"] = slope_deg.ravel(order="F")

        return grid


@dataclass
class DrapedWallAlignment:
    """Terrain alignment properties for a multi-strut piled wall on a hill slope."""
    mean_ground_slope_deg: float
    crest_offset_distance: float       # L_crest: Distance from wall to hill crest (m)
    toe_offset_distance: float         # L_toe: Distance from wall to downhill toe (m)
    elevation_drop_across_wall: float  # Elevation delta across wall footprint (m)
    pier_ground_elevations: Dict[int, float] = field(default_factory=dict)
    aligned_pier_bases: Dict[int, float] = field(default_factory=dict)


# ==============================================================================
# 1. DEM Ingestion Engines: GeoTIFF, ASCII Grid, XYZ
# ==============================================================================

def read_geotiff_dem(filepath: Union[str, BinaryIO]) -> TerrainRaster:
    """
    Reads a single-band GeoTIFF digital elevation model using rasterio.
    """
    if not RASTERIO_AVAILABLE:
        raise RuntimeError("rasterio is not installed. Install via `pip install rasterio`.")

    with rasterio.open(filepath) as dataset:
        elevations = dataset.read(1).astype(np.float64)
        ny, nx = elevations.shape

        t = dataset.transform
        cols = np.arange(nx)
        rows = np.arange(ny)
        xs, _ = rasterio.transform.xy(t, np.zeros(nx), cols)
        _, ys = rasterio.transform.xy(t, rows, np.zeros(ny))

        x_coords = np.array(xs, dtype=np.float64)
        y_coords = np.array(ys, dtype=np.float64)

        # Ensure y_coords are strictly ascending for RegularGridInterpolator
        if y_coords[1] < y_coords[0]:
            y_coords = y_coords[::-1]
            elevations = np.flipud(elevations)

        crs_str = str(dataset.crs) if dataset.crs else None
        nodata = dataset.nodata

    return TerrainRaster(
        elevations=elevations,
        x_coords=x_coords,
        y_coords=y_coords,
        nodata_value=nodata,
        crs=crs_str,
    )


def write_geotiff_dem(
    filepath: Union[str, BinaryIO],
    terrain: TerrainRaster,
    crs: str = "EPSG:32645", # UTM Zone 45N (Himalayan / North-East India region)
) -> None:
    """
    Exports a TerrainRaster to a standard GeoTIFF raster file.
    """
    if not RASTERIO_AVAILABLE:
        raise RuntimeError("rasterio is not installed. Install via `pip install rasterio`.")

    ny, nx = terrain.elevations.shape
    xmin, _, _, ymax = terrain.bounds
    transform = from_origin(
        xmin - 0.5 * terrain.dx,
        ymax + 0.5 * terrain.dy,
        terrain.dx,
        terrain.dy,
    )

    # Flip if necessary so top row corresponds to ymax
    data_out = np.flipud(terrain.elevations).astype(np.float32)

    with rasterio.open(
        filepath,
        "w",
        driver="GTiff",
        height=ny,
        width=nx,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=-9999.0,
    ) as dst:
        dst.write(data_out, 1)


def read_ascii_grid(filepath: str) -> TerrainRaster:
    """
    Parses an ESRI ASCII Grid raster (.asc / .txt).
    """
    header = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for _ in range(6):
            line = f.readline().strip().split()
            if len(line) == 2:
                header[line[0].lower()] = float(line[1])

        ncols = int(header["ncols"])
        nrows = int(header["nrows"])
        cellsize = header["cellsize"]
        xll = header.get("xllcorner", header.get("xllcenter", 0.0))
        yll = header.get("yllcorner", header.get("yllcenter", 0.0))
        nodata = header.get("nodata_value", -9999.0)

        data = np.loadtxt(f, dtype=np.float64)

    if data.shape != (nrows, ncols):
        data = data.reshape((nrows, ncols))

    x_coords = np.linspace(xll + 0.5 * cellsize, xll + (ncols - 0.5) * cellsize, ncols)
    y_coords = np.linspace(yll + 0.5 * cellsize, yll + (nrows - 0.5) * cellsize, nrows)

    # In ASCII grids, row 0 is at the top (maximum Y); flip to make ascending
    elevations = np.flipud(data)

    return TerrainRaster(
        elevations=elevations,
        x_coords=x_coords,
        y_coords=y_coords,
        nodata_value=nodata,
    )


def write_ascii_grid(filepath: str, terrain: TerrainRaster) -> None:
    """
    Exports a TerrainRaster to an ESRI ASCII Grid raster file.
    """
    ny, nx = terrain.elevations.shape
    xmin, ymin, _, _ = terrain.bounds
    nodata = terrain.nodata_value if terrain.nodata_value is not None else -9999.0

    # Flip back so row 0 is at top (ymax)
    data_out = np.flipud(terrain.elevations)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"ncols         {nx}\n")
        f.write(f"nrows         {ny}\n")
        f.write(f"xllcorner     {xmin:.6f}\n")
        f.write(f"yllcorner     {ymin:.6f}\n")
        f.write(f"cellsize      {terrain.dx:.6f}\n")
        f.write(f"NODATA_value  {nodata}\n")
        for row in data_out:
            f.write(" ".join(f"{val:.4f}" for val in row) + "\n")


def read_xyz_point_cloud(
    filepath: str,
    grid_resolution: float = 1.0,
) -> TerrainRaster:
    """
    Parses an XYZ point cloud file (space/comma separated) and interpolates onto a regular grid.
    """
    points = np.loadtxt(filepath, delimiter=None, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] < 3:
        raise ValueError(f"XYZ file must contain at least 3 columns (X, Y, Z), got shape {points.shape}")

    x_raw = points[:, 0]
    y_raw = points[:, 1]
    z_raw = points[:, 2]

    xmin, xmax = float(np.min(x_raw)), float(np.max(x_raw))
    ymin, ymax = float(np.min(y_raw)), float(np.max(y_raw))

    nx = max(int(math.ceil((xmax - xmin) / grid_resolution)) + 1, 3)
    ny = max(int(math.ceil((ymax - ymin) / grid_resolution)) + 1, 3)

    x_grid = np.linspace(xmin, xmax, nx)
    y_grid = np.linspace(ymin, ymax, ny)
    X, Y = np.meshgrid(x_grid, y_grid)

    z_grid = griddata(
        (x_raw, y_raw),
        z_raw,
        (X, Y),
        method="linear",
        fill_value=float(np.mean(z_raw)),
    )

    return TerrainRaster(
        elevations=z_grid,
        x_coords=x_grid,
        y_coords=y_grid,
    )


# ==============================================================================
# 2. Parametric Synthetic Slope Generator
# ==============================================================================

def generate_synthetic_slope(
    slope_type: str = "planar",
    length_x: float = 100.0,
    width_y: float = 50.0,
    resolution: float = 1.0,
    slope_angle_deg: float = 25.0,
    crest_elevation: float = 30.0,
    bench_width: float = 6.0,
    bench_height: float = 10.0,
    hinge_distance: float = 40.0,
    slope_angle_toe_deg: float = 35.0,
    slope_angle_crest_deg: float = 15.0,
) -> TerrainRaster:
    """
    Generates synthetic parametric hill slope terrains:
    - "planar": Uniform planar hill slope with slope angle beta.
    - "benched": Stepped slope with horizontal berms / benches.
    - "bilinear": Broken slope transitioning from steep toe to gentle crest.
    """
    if length_x <= 0 or width_y <= 0:
        raise ValueError("length_x and width_y must be positive")
    if resolution <= 0:
        raise ValueError("resolution must be positive")

    nx = max(int(math.ceil(length_x / resolution)) + 1, 3)
    ny = max(int(math.ceil(width_y / resolution)) + 1, 3)

    x_coords = np.linspace(0.0, length_x, nx, dtype=np.float64)
    y_coords = np.linspace(0.0, width_y, ny, dtype=np.float64)

    elevations = np.zeros((ny, nx), dtype=np.float64)
    tan_slope = math.tan(math.radians(slope_angle_deg))

    if slope_type == "planar":
        # Z(x) = Z_toe + x * tan(beta)
        z_toe = max(crest_elevation - length_x * tan_slope, 0.0)
        profile_x = z_toe + x_coords * tan_slope
        elevations = np.tile(profile_x, (ny, 1))

    elif slope_type == "benched":
        # Periodically alternating inclined risers and flat benches
        profile_x = np.zeros(nx, dtype=np.float64)
        cur_z = 0.0
        riser_run = bench_height / max(tan_slope, 0.1)
        cycle_len = riser_run + bench_width

        for idx, x in enumerate(x_coords):
            cycle_pos = x % cycle_len
            num_cycles = int(x // cycle_len)
            if cycle_pos <= riser_run:
                # On inclined riser
                z = num_cycles * bench_height + cycle_pos * tan_slope
            else:
                # On flat horizontal bench
                z = (num_cycles + 1) * bench_height
            profile_x[idx] = z

        elevations = np.tile(profile_x, (ny, 1))

    elif slope_type == "bilinear":
        # Steep toe slope up to hinge_distance, then gentle crest slope
        profile_x = np.zeros(nx, dtype=np.float64)
        tan_toe = math.tan(math.radians(slope_angle_toe_deg))
        tan_crest = math.tan(math.radians(slope_angle_crest_deg))
        z_hinge = hinge_distance * tan_toe

        for idx, x in enumerate(x_coords):
            if x <= hinge_distance:
                profile_x[idx] = x * tan_toe
            else:
                profile_x[idx] = z_hinge + (x - hinge_distance) * tan_crest

        elevations = np.tile(profile_x, (ny, 1))

    else:
        raise ValueError(f"Unknown slope_type '{slope_type}'. Must be 'planar', 'benched', or 'bilinear'.")

    return TerrainRaster(
        elevations=elevations,
        x_coords=x_coords,
        y_coords=y_coords,
    )


# ==============================================================================
# 3. Wall Terrain Draping & Invariant Calculator
# ==============================================================================

def drape_wall_on_terrain(
    model: MultiStrutPiledWallModel,
    terrain: TerrainRaster,
    wall_center_x: float = 50.0,
    wall_center_y: float = 25.0,
    num_bays: int = 3,
) -> DrapedWallAlignment:
    """
    Drapes a multi-strut retaining wall system onto the sampled 3D hill slope:
    - Samples exact ground elevation at each pier column location.
    - Evaluates slope invariants: mean slope angle, crest offset distance L_crest, and toe distance.
    - Adjusts pier base and pile collar elevations to conformal contact.
    """
    n_bays = num_bays
    shell_obj = getattr(model, "shell", getattr(model, "curved_shell", None))
    bay_span = shell_obj.bay_span if shell_obj and hasattr(shell_obj, "bay_span") else 4.0
    tot_wall_len = n_bays * bay_span

    # Piers are located along Y axis in wall local coordinates
    # Let wall run along Y in global coordinates, facing downhill (-X)
    n_piers = n_bays + 1
    y_start = wall_center_y - 0.5 * tot_wall_len

    pier_ground_elevs = {}
    pier_aligned_bases = {}
    slopes = []

    for p_idx in range(n_piers):
        p_x = wall_center_x
        p_y = y_start + p_idx * bay_span
        z_ground = terrain.elevation_at(p_x, p_y)
        pier_ground_elevs[p_idx] = z_ground
        pier_aligned_bases[p_idx] = z_ground
        _, _, slp = terrain.gradient_at(p_x, p_y)
        slopes.append(slp)

    mean_slope = float(np.mean(slopes))

    # Crest distance: distance to top edge of terrain (uphill = +X)
    _, _, xmax, _ = terrain.bounds
    crest_dist = max(xmax - wall_center_x, 0.0)

    # Toe distance: distance to downhill bottom (downhill = -X)
    xmin, _, _, _ = terrain.bounds
    toe_dist = max(wall_center_x - xmin, 0.0)

    # Elevation drop across wall length
    z_vals = list(pier_ground_elevs.values())
    elev_drop = float(max(z_vals) - min(z_vals))

    return DrapedWallAlignment(
        mean_ground_slope_deg=mean_slope,
        crest_offset_distance=crest_dist,
        toe_offset_distance=toe_dist,
        elevation_drop_across_wall=elev_drop,
        pier_ground_elevations=pier_ground_elevs,
        aligned_pier_bases=pier_aligned_bases,
    )
