"""
Parametric 3D Mesher for Piers, Bored Floating Piles, Raking Struts,
and Uphill Lattice Transmission Towers (Phase 2).
Guarantees conformal node junctions between pier bases and pile cap tops,
as well as standard 1D structural line elements (VTK_LINE) for struts and towers.
"""

from __future__ import annotations

import math
from typing import List, Tuple, Optional
import numpy as np
import pyvista as pv

from ..models.advanced_wall_params import PierAndPileGeometry, StrutSupportSystem
from ..models.tower_params import TransmissionTowerParams
from .shell_mesher import create_hex_cells


def build_pier_mesh(
    geom: PierAndPileGeometry,
    pier_x: float = 0.0,
    y_base: float = 0.0,
    z_base: float = 0.0,
    nx: int = 4,
    ny: int = 16,
    nz: int = 4,
) -> pv.UnstructuredGrid:
    """
    Generates an 8-node hexahedral solid mesh for a vertical RC pier column.
    The pier base at y = y_base is constructed with a regular grid that matches
    the top face of the pile cap.
    """
    bp = geom.pier_width
    dp = geom.pier_depth
    hp = geom.pier_height

    x_1d = np.linspace(pier_x - bp / 2.0, pier_x + bp / 2.0, nx, dtype=np.float64)
    y_1d = np.linspace(y_base, y_base + hp, ny, dtype=np.float64)
    z_1d = np.linspace(z_base, z_base + dp, nz, dtype=np.float64)

    X, Y, Z = np.meshgrid(x_1d, y_1d, z_1d, indexing="xy")
    pts = np.transpose(np.stack([X, Y, Z], axis=-1), (2, 0, 1, 3))
    flat_points = pts.reshape(-1, 3)

    cells, cell_types = create_hex_cells(nz, ny, nx, pt_offset=0)
    grid = pv.UnstructuredGrid(cells, cell_types, flat_points)
    grid.cell_data["Element_Type"] = np.full(grid.n_cells, 2, dtype=np.int32) # 2 = Pier
    return grid


def build_pile_cap_mesh(
    geom: PierAndPileGeometry,
    pier_x: float = 0.0,
    y_top: float = 0.0,
    z_base: float = 0.0,
    nx: int = 6,
    ny: int = 4,
    nz: int = 6,
) -> pv.UnstructuredGrid:
    """
    Generates an 8-node hexahedral solid mesh for the reinforced concrete pile cap.
    Positioned from y = y_top - geom.pile_cap_depth to y = y_top.
    Coordinates on the top surface align with the pier base footprint.
    """
    w_cap = geom.pile_cap_width
    l_cap = geom.pile_cap_length
    d_cap = geom.pile_cap_depth

    x_1d = np.linspace(pier_x - w_cap / 2.0, pier_x + w_cap / 2.0, nx, dtype=np.float64)
    y_1d = np.linspace(y_top - d_cap, y_top, ny, dtype=np.float64)
    z_center = z_base + geom.pier_depth / 2.0
    z_1d = np.linspace(z_center - l_cap / 2.0, z_center + l_cap / 2.0, nz, dtype=np.float64)

    X, Y, Z = np.meshgrid(x_1d, y_1d, z_1d, indexing="xy")
    pts = np.transpose(np.stack([X, Y, Z], axis=-1), (2, 0, 1, 3))
    flat_points = pts.reshape(-1, 3)

    cells, cell_types = create_hex_cells(nz, ny, nx, pt_offset=0)
    grid = pv.UnstructuredGrid(cells, cell_types, flat_points)
    grid.cell_data["Element_Type"] = np.full(grid.n_cells, 3, dtype=np.int32) # 3 = Pile Cap
    return grid


def build_conformal_pier_and_cap_mesh(
    geom: PierAndPileGeometry,
    pier_x: float = 0.0,
    y_junction: float = 0.0,
    z_base: float = 0.0,
    n_sub: int = 4,
) -> Tuple[pv.UnstructuredGrid, pv.UnstructuredGrid]:
    """
    Builds conformal pier and pile cap meshes where the nodes at the base of the pier
    (y = y_junction) match identically with corresponding nodes on the top face of the pile cap.
    Returns (pier_grid, cap_grid).
    """
    bp = geom.pier_width
    dp = geom.pier_depth
    hp = geom.pier_height
    d_cap = geom.pile_cap_depth
    w_cap = geom.pile_cap_width
    l_cap = geom.pile_cap_length

    eff_w_cap = max(w_cap, bp)
    eff_l_cap = max(l_cap, dp)

    # 1. Pier Mesh: nx = n_sub, nz = n_sub, ny = 12
    nx_pier = n_sub
    nz_pier = n_sub
    ny_pier = 12

    x_pier = np.linspace(pier_x - bp / 2.0, pier_x + bp / 2.0, nx_pier, dtype=np.float64)
    z_pier = np.linspace(z_base, z_base + dp, nz_pier, dtype=np.float64)

    pier_grid = build_pier_mesh(geom, pier_x, y_junction, z_base, nx=nx_pier, ny=ny_pier, nz=nz_pier)

    # 2. Conformal Pile Cap Mesh:
    ny_cap = 4
    y_cap = np.linspace(y_junction - d_cap, y_junction, ny_cap, dtype=np.float64)

    # Outer wings along x
    x_cap_left = np.linspace(pier_x - eff_w_cap / 2.0, pier_x - bp / 2.0, 2, dtype=np.float64)[:-1]
    x_cap_right = np.linspace(pier_x + bp / 2.0, pier_x + eff_w_cap / 2.0, 2, dtype=np.float64)[1:]
    x_cap = np.concatenate([x_cap_left, x_pier, x_cap_right])

    # Outer wings along z
    z_mid = z_base + dp / 2.0
    z_min_cap = z_mid - eff_l_cap / 2.0
    z_max_cap = z_mid + eff_l_cap / 2.0
    z_cap_front = np.linspace(z_min_cap, z_base, 2, dtype=np.float64)[:-1]
    z_cap_back = np.linspace(z_base + dp, z_max_cap, 2, dtype=np.float64)[1:]
    z_cap = np.concatenate([z_cap_front, z_pier, z_cap_back])

    nx_cap = len(x_cap)
    nz_cap = len(z_cap)

    X_c, Y_c, Z_c = np.meshgrid(x_cap, y_cap, z_cap, indexing="xy")
    pts_c = np.transpose(np.stack([X_c, Y_c, Z_c], axis=-1), (2, 0, 1, 3))
    flat_pts_c = pts_c.reshape(-1, 3)

    cells_c, types_c = create_hex_cells(nz_cap, ny_cap, nx_cap, pt_offset=0)
    cap_grid = pv.UnstructuredGrid(cells_c, types_c, flat_pts_c)
    cap_grid.cell_data["Element_Type"] = np.full(cap_grid.n_cells, 3, dtype=np.int32)

    return pier_grid, cap_grid


def generate_pile_wedge_arrays(
    pier_x: float,
    y_cap_bottom: float,
    z_offsets: List[float],
    r_pile: float,
    lp: float,
    n_theta: int = 6,
    n_depth: int = 8,
    pt_offset: int = 0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Fast vectorized generation of points, cells, cell_types, and element types for bored piles.
    Returns (points, cells, cell_types, elem_types).
    """
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    y_depths = np.linspace(y_cap_bottom, y_cap_bottom - lp, n_depth, dtype=np.float64)
    nodes_per_level = 1 + n_theta
    nodes_per_pile = len(y_depths) * nodes_per_level
    wedges_per_pile = (n_depth - 1) * n_theta

    total_pts_list = []
    total_cells_list = []

    for p_idx, z_pile_c in enumerate(z_offsets):
        p_base_offset = pt_offset + p_idx * nodes_per_pile

        # Points
        pts = np.empty((len(y_depths), nodes_per_level, 3), dtype=np.float64)
        for d_idx, y_d in enumerate(y_depths):
            pts[d_idx, 0, :] = [pier_x, y_d, z_pile_c]
            for t_idx, th in enumerate(theta):
                pts[d_idx, 1 + t_idx, :] = [
                    pier_x + r_pile * math.cos(th),
                    y_d,
                    z_pile_c + r_pile * math.sin(th),
                ]
        total_pts_list.append(pts.reshape(-1, 3))

        # Vectorized wedge connectivity
        d_arr, t_arr = np.meshgrid(np.arange(n_depth - 1), np.arange(n_theta), indexing="ij")
        d_arr = d_arr.ravel()
        t_arr = t_arr.ravel()
        t_next = (t_arr + 1) % n_theta

        top_base = p_base_offset + d_arr * nodes_per_level
        bot_base = p_base_offset + (d_arr + 1) * nodes_per_level

        p0 = top_base
        p1 = top_base + 1 + t_arr
        p2 = top_base + 1 + t_next
        p3 = bot_base
        p4 = bot_base + 1 + t_arr
        p5 = bot_base + 1 + t_next

        wedge_cells = np.empty((len(d_arr), 7), dtype=np.int64)
        wedge_cells[:, 0] = 6
        wedge_cells[:, 1] = p0
        wedge_cells[:, 2] = p1
        wedge_cells[:, 3] = p2
        wedge_cells[:, 4] = p3
        wedge_cells[:, 5] = p4
        wedge_cells[:, 6] = p5

        total_cells_list.append(wedge_cells.ravel())

    all_pts = np.vstack(total_pts_list)
    all_cells = np.concatenate(total_cells_list)
    total_wedges = len(z_offsets) * wedges_per_pile
    all_types = np.full(total_wedges, int(pv.CellType.WEDGE), dtype=np.uint8)
    all_elem = np.full(total_wedges, 4, dtype=np.int32) # 4 = Pile
    return all_pts, all_cells, all_types, all_elem


def build_bored_piles_mesh(
    geom: PierAndPileGeometry,
    pier_x: float = 0.0,
    y_cap_bottom: float = -1.0,
    z_base: float = 0.0,
    n_theta: int = 6,
    n_depth: int = 8,
) -> pv.UnstructuredGrid:
    """
    Generates 3D solid circular/cylindrical hexahedral/wedge elements for bored piles
    extending from bottom of pile cap (y_cap_bottom) into hill foundation soil.
    """
    dp = geom.pile_diameter
    r_pile = dp / 2.0
    lp = geom.pile_length
    n_piles = geom.num_piles_per_pier
    sp = geom.pile_spacing
    z_center = z_base + geom.pier_depth / 2.0

    if n_piles == 1:
        z_offsets = [z_center]
    else:
        total_span = (n_piles - 1) * sp
        z_offsets = [z_center - total_span / 2.0 + i * sp for i in range(n_piles)]

    pts, cells, types, elem_data = generate_pile_wedge_arrays(
        pier_x, y_cap_bottom, z_offsets, r_pile, lp, n_theta, n_depth, pt_offset=0
    )
    grid = pv.UnstructuredGrid(cells, types, pts)
    grid.cell_data["Element_Type"] = elem_data
    return grid


def generate_strut_line_arrays(
    struts: StrutSupportSystem,
    pier_x: float = 0.0,
    pier_height: float = 6.5,
    y_base: float = 0.0,
    z_front: float = 0.0,
    pt_offset: int = 0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Fast vectorized generation of line elements for raking struts.
    Returns (points, cells, cell_types, elem_types).
    """
    alpha_rad = math.radians(struts.inclination_angle)
    L = struts.unbraced_length
    dy = -L * math.sin(alpha_rad)
    dz = -L * math.cos(alpha_rad)

    levels = np.array(struts.strut_levels, dtype=np.float64)
    n_struts = len(levels)

    y_attach = y_base + pier_height - levels

    p_starts = np.column_stack([
        np.full(n_struts, pier_x),
        y_attach,
        np.full(n_struts, z_front),
    ])
    p_ends = np.column_stack([
        np.full(n_struts, pier_x),
        y_attach + dy,
        np.full(n_struts, z_front + dz),
    ])

    points = np.empty((2 * n_struts, 3), dtype=np.float64)
    points[0::2] = p_starts
    points[1::2] = p_ends

    cells = np.empty((n_struts, 3), dtype=np.int64)
    cells[:, 0] = 2
    cells[:, 1] = pt_offset + np.arange(0, 2 * n_struts, 2)
    cells[:, 2] = pt_offset + np.arange(1, 2 * n_struts, 2)

    cell_types = np.full(n_struts, int(pv.CellType.LINE), dtype=np.uint8)
    elem_types = np.full(n_struts, 5, dtype=np.int32) # 5 = Strut

    return points, cells.ravel(), cell_types, elem_types


def build_raking_struts_mesh(
    struts: StrutSupportSystem,
    pier_x: float = 0.0,
    pier_height: float = 6.5,
    y_base: float = 0.0,
    z_front: float = 0.0,
) -> pv.UnstructuredGrid:
    """
    Generates structural 1D line elements (VTK_LINE) for multi-tier raking struts
    attached to the vertical pier column.
    """
    pts, cells, types, elem_types = generate_strut_line_arrays(
        struts, pier_x, pier_height, y_base, z_front, pt_offset=0
    )
    grid = pv.UnstructuredGrid(cells, types, pts)
    grid.cell_data["Element_Type"] = elem_types
    grid.cell_data["Section_Area"] = np.full(grid.n_cells, struts.cross_section_area)
    grid.cell_data["Moment_of_Inertia"] = np.full(grid.n_cells, struts.moment_of_inertia)
    grid.cell_data["Pre_Stress_Load"] = np.full(grid.n_cells, struts.pre_stress_load)
    grid.cell_data["Slenderness"] = np.full(grid.n_cells, struts.slenderness_ratio)
    return grid


def generate_tower_line_arrays(
    tower: TransmissionTowerParams,
    crest_x: float = 0.0,
    crest_y: float = 6.5,
    crest_z: float = 2.0,
    pt_offset: int = 0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Fast vectorized generation of transmission tower space truss lines.
    Returns (points, cells, cell_types, elem_types).
    """
    bw = tower.base_width
    bl = tower.base_length
    ht = tower.total_height
    x_off = tower.crest_offset

    z_base_legs = crest_z + x_off
    p0 = [crest_x - bl / 2.0, crest_y, z_base_legs]
    p1 = [crest_x + bl / 2.0, crest_y, z_base_legs]
    p2 = [crest_x + bl / 2.0, crest_y, z_base_legs + bw]
    p3 = [crest_x - bl / 2.0, crest_y, z_base_legs + bw]

    h_mid = crest_y + ht * 0.6
    w_mid = bw * 0.4
    l_mid = bl * 0.4
    z_mid = z_base_legs + bw / 2.0
    p4 = [crest_x - l_mid / 2.0, h_mid, z_mid - w_mid / 2.0]
    p5 = [crest_x + l_mid / 2.0, h_mid, z_mid - w_mid / 2.0]
    p6 = [crest_x + l_mid / 2.0, h_mid, z_mid + w_mid / 2.0]
    p7 = [crest_x - l_mid / 2.0, h_mid, z_mid + w_mid / 2.0]

    h_top = crest_y + ht
    p_peak = [crest_x, h_top, z_mid]
    p_cross_left = [crest_x - bl * 0.8, h_top - 3.0, z_mid]
    p_cross_right = [crest_x + bl * 0.8, h_top - 3.0, z_mid]

    points = np.array([p0, p1, p2, p3, p4, p5, p6, p7, p_peak, p_cross_left, p_cross_right], dtype=np.float64)

    lines = [
        (0, 4), (1, 5), (2, 6), (3, 7),
        (0, 1), (1, 2), (2, 3), (3, 0),
        (0, 5), (1, 4), (1, 6), (2, 5), (2, 7), (3, 6), (3, 4), (0, 7),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (4, 8), (5, 8), (6, 8), (7, 8),
        (8, 9), (8, 10),
    ]

    n_lines = len(lines)
    cells = np.empty((n_lines, 3), dtype=np.int64)
    cells[:, 0] = 2
    for idx, (s, e) in enumerate(lines):
        cells[idx, 1] = pt_offset + s
        cells[idx, 2] = pt_offset + e

    cell_types = np.full(n_lines, int(pv.CellType.LINE), dtype=np.uint8)
    elem_types = np.full(n_lines, 6, dtype=np.int32) # 6 = Tower

    return points, cells.ravel(), cell_types, elem_types


def build_transmission_tower_mesh(
    tower: TransmissionTowerParams,
    crest_x: float = 0.0,
    crest_y: float = 6.5,
    crest_z: float = 2.0,
) -> pv.UnstructuredGrid:
    """
    Generates a 3D structural lattice space truss frame using VTK_LINE elements
    representing the uphill 4-legged transmission tower.
    """
    pts, cells, types, elem_types = generate_tower_line_arrays(
        tower, crest_x, crest_y, crest_z, pt_offset=0
    )
    grid = pv.UnstructuredGrid(cells, types, pts)
    grid.cell_data["Element_Type"] = elem_types
    return grid
