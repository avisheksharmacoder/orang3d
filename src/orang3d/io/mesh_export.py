"""
CAD and Simulation Mesh & Signal Export Suite for orang3D (Phase 9).
Provides exporters for:
- 3D Finite Element and CAD meshes: .vtk (ParaView), .stl (3D Printing/CAD), .obj (Graphics)
- Dynamic accelerograms, Newmark sliding displacement, and pore pressure to RFC-4180 CSV
"""

import os
import csv
from typing import Optional
import numpy as np
import pyvista as pv

from ..models.wall_params import RetainingWallGeometry, AnalysisResults
from ..mesher.hex_mesher import build_3d_wall_mesh


def _apply_warp(grid: pv.DataSet, warp_scale: float) -> pv.DataSet:
    """Applies displacement vector warping to a PyVista dataset when available."""
    if warp_scale > 0.0 and "Deformation_m" in grid.point_data:
        return grid.warp_by_vector("Deformation_m", factor=warp_scale)
    return grid


def export_grid_mesh(
    grid: pv.DataSet,
    filepath: str,
    fmt: Optional[str] = None,
    warp_scale: float = 0.0,
) -> str:
    """
    Exports any PyVista 3D mesh/dataset to .vtk, .stl, or .obj format.
    """
    ext = (fmt or os.path.splitext(filepath)[1].lstrip(".") or "vtk").lower()
    if ext not in {"vtk", "stl", "obj"}:
        raise ValueError(f"Unsupported mesh export format '{ext}'. Expected 'vtk', 'stl', or 'obj'.")

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    work_grid = _apply_warp(grid, warp_scale)

    if ext == "vtk":
        work_grid.save(filepath)
    elif ext == "stl":
        surface = work_grid.extract_surface(algorithm="dataset_surface").triangulate()
        surface.save(filepath)
    else:  # obj
        surface = work_grid.extract_surface(algorithm="dataset_surface")
        surface.save(filepath)

    return filepath


def export_mesh_to_vtk(
    geom: RetainingWallGeometry,
    results: AnalysisResults,
    filepath: str,
    warp_scale: float = 0.0,
) -> str:
    """
    Exports the retaining wall 3D hexahedral solid mesh with internal stress tensors
    and deformation fields to standard VTK UnstructuredGrid format readable by ParaView & meshio.
    """
    grid = build_3d_wall_mesh(geom, results)
    return export_grid_mesh(grid, filepath, fmt="vtk", warp_scale=warp_scale)


def export_mesh_to_stl(
    geom: RetainingWallGeometry,
    results: AnalysisResults,
    filepath: str,
    warp_scale: float = 0.0,
) -> str:
    """
    Exports the exterior boundary surface of the retaining wall to standard STL
    triangular facet format for 3D CAD modeling, CNC, and 3D printing.
    """
    grid = build_3d_wall_mesh(geom, results)
    return export_grid_mesh(grid, filepath, fmt="stl", warp_scale=warp_scale)


def export_mesh_to_obj(
    geom: RetainingWallGeometry,
    results: AnalysisResults,
    filepath: str,
    warp_scale: float = 0.0,
) -> str:
    """
    Exports the retaining wall geometry to standard Wavefront .OBJ format
    for scientific rendering, Blender, and web visualization.
    """
    grid = build_3d_wall_mesh(geom, results)
    return export_grid_mesh(grid, filepath, fmt="obj", warp_scale=warp_scale)


def export_signals_to_csv(
    filepath: str,
    time_arr: np.ndarray,
    accel_arr: np.ndarray,
    slip_arr: np.ndarray,
    pore_arr: Optional[np.ndarray] = None,
) -> str:
    """
    Exports dynamic earthquake accelerograms, Newmark sliding displacement,
    and pore-water pressure time histories to standard RFC-4180 CSV format.
    """
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    n_points = len(time_arr)

    p_data = pore_arr if pore_arr is not None and len(pore_arr) == n_points else np.zeros(n_points)

    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Time_s", "Acceleration_g", "Permanent_Slip_cm", "Pore_Pressure_kPa"])
        for i in range(n_points):
            writer.writerow([
                f"{time_arr[i]:.8e}",
                f"{accel_arr[i]:.8e}",
                f"{slip_arr[i]:.8e}",
                f"{p_data[i]:.8e}",
            ])

    return filepath
