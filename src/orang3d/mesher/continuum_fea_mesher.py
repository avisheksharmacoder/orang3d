"""
Conformal 3D Continuum Finite Element Mesher for Retaining Wall Soil-Structure Interaction (Phase 3).

Generates structured 8-node hexahedral (VTK_HEXAHEDRON / OpenSees stdBrick / brickUP)
meshes in the orang3D global coordinate frame:
  - X: Transverse direction (0 at footing toe, +X into backfill)
  - Y: Vertical elevation (0 at footing base, +Y upward, -Y foundation subgrade)
  - Z: Longitudinal direction along wall length

Supports:
  - Cantilever inverted-T/L/gravity walls and multi-strut curved-shell wall proxies
  - Separate coincident wall-soil interface node pairs at the wall backface and footing base
    (allowing zero-length Coulomb friction & normal no-tension gapping elements)
  - Lysmer-Kuhlemeyer viscous absorbing boundary face metadata (Cp, Cs tributary areas)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pyvista as pv

from ..models.wall_params import RetainingWallGeometry, SoilProperties
from ..models.advanced_wall_params import MultiStrutPiledWallModel, WallSystemMode


@dataclass(frozen=True)
class ContinuumInterfacePair:
    """Paired coincident nodes across the wall-soil contact interface."""

    wall_node_id: int
    soil_node_id: int
    area_trib: float
    normal: Tuple[float, float, float]
    coord: Tuple[float, float, float]
    zone: str  # "backface" or "base"


@dataclass(frozen=True)
class LysmerBoundaryNode:
    """Boundary node carrying tributary area and outward normal for Lysmer dashpots."""

    node_id: int
    area_trib: float
    normal: Tuple[float, float, float]
    face_name: str  # "right", "left", "front_z", "back_z", "bottom"


@dataclass
class ContinuumFEAMesh:
    """
    Complete 3D continuum hexahedral FEA mesh with interface topology and boundary metadata.
    All node indices are 0-based into `nodes`; OpenSees/Kratos solvers add +1 for 1-based tags.
    """

    nodes: np.ndarray                     # (N, 3) float64
    elements: np.ndarray                  # (E, 8) int64
    element_domain_ids: np.ndarray        # (E,) int32: 1=Wall, 2=Backfill, 3=Foundation
    node_domain_ids: np.ndarray           # (N,) int32
    interface_pairs: List[ContinuumInterfacePair] = field(default_factory=list)
    lysmer_nodes: List[LysmerBoundaryNode] = field(default_factory=list)
    fixed_base_nodes: List[int] = field(default_factory=list)
    lateral_x_nodes: List[int] = field(default_factory=list)
    lateral_z_nodes: List[int] = field(default_factory=list)
    wall_crest_nodes: List[int] = field(default_factory=list)
    backfill_backface_nodes: List[int] = field(default_factory=list)
    wall_backface_nodes: List[int] = field(default_factory=list)
    top_surface_nodes: List[int] = field(default_factory=list)
    geometry_meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def n_nodes(self) -> int:
        return int(self.nodes.shape[0])

    @property
    def n_elements(self) -> int:
        return int(self.elements.shape[0])

    def to_pyvista_grid(self) -> pv.UnstructuredGrid:
        """Converts the continuum FEA mesh into a PyVista VTK_HEXAHEDRON UnstructuredGrid."""
        n_cells = self.elements.shape[0]
        cells = np.column_stack([np.full(n_cells, 8, dtype=np.int64), self.elements]).ravel()
        cell_types = np.full(n_cells, pv.CellType.HEXAHEDRON, dtype=np.uint8)
        grid = pv.UnstructuredGrid(cells, cell_types, self.nodes.astype(np.float64))
        grid.cell_data["Domain_ID"] = self.element_domain_ids.astype(np.int32)
        grid.point_data["Domain_ID"] = self.node_domain_ids.astype(np.int32)
        return grid

    def compute_min_jacobian(self) -> float:
        """Evaluates determinant of the isoparametric Jacobian at element centers (must be > 0)."""
        p = self.nodes[self.elements]  # (E, 8, 3)
        # Central trilinear derivatives at (0, 0, 0) for standard hex ordering:
        # 0:(-,-,-), 1:(+,-,-), 2:(+,+,-), 3:(-,+,-), 4:(-,-,+), 5:(+,-,+), 6:(+,+,+), 7:(-,+,+)
        d_xi = 0.125 * (
            (p[:, 1] + p[:, 2] + p[:, 5] + p[:, 6])
            - (p[:, 0] + p[:, 3] + p[:, 4] + p[:, 7])
        )
        d_eta = 0.125 * (
            (p[:, 2] + p[:, 3] + p[:, 6] + p[:, 7])
            - (p[:, 0] + p[:, 1] + p[:, 4] + p[:, 5])
        )
        d_zeta = 0.125 * (
            (p[:, 4] + p[:, 5] + p[:, 6] + p[:, 7])
            - (p[:, 0] + p[:, 1] + p[:, 2] + p[:, 3])
        )
        cross = np.cross(d_xi, d_eta)
        dets = np.einsum("ij,ij->i", cross, d_zeta)
        return float(np.min(dets))


def _unique_sorted_coords(values: List[float], tol: float = 1e-6) -> np.ndarray:
    """Merges nearly identical coordinate ticks and returns strictly increasing array."""
    sorted_vals = np.sort(np.asarray(values, dtype=np.float64))
    kept = [float(sorted_vals[0])]
    for val in sorted_vals[1:]:
        if abs(float(val) - kept[-1]) > tol:
            kept.append(float(val))
    return np.asarray(kept, dtype=np.float64)


def _subdivide_ticks(anchors: List[float], counts: List[int]) -> np.ndarray:
    """Subdivides sorted anchor intervals using requested element counts per segment."""
    parts = [np.linspace(anchors[i], anchors[i + 1], max(1, counts[i]) + 1)[:-1] for i in range(len(counts))]
    parts.append(np.array([anchors[-1]], dtype=np.float64))
    return _unique_sorted_coords(np.concatenate(parts).tolist())


def _compute_tributary_face_areas(
    axis_a: np.ndarray,
    axis_b: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Computes 1D nodal tributary weights along two orthogonal grid axes."""
    da = np.zeros_like(axis_a, dtype=np.float64)
    if len(axis_a) > 1:
        diffs_a = np.diff(axis_a)
        da[0] = 0.5 * diffs_a[0]
        da[-1] = 0.5 * diffs_a[-1]
        if len(axis_a) > 2:
            da[1:-1] = 0.5 * (diffs_a[:-1] + diffs_a[1:])

    db = np.zeros_like(axis_b, dtype=np.float64)
    if len(axis_b) > 1:
        diffs_b = np.diff(axis_b)
        db[0] = 0.5 * diffs_b[0]
        db[-1] = 0.5 * diffs_b[-1]
        if len(axis_b) > 2:
            db[1:-1] = 0.5 * (diffs_b[:-1] + diffs_b[1:])
    return da, db


def build_continuum_fea_mesh(
    geom: RetainingWallGeometry,
    soil: Optional[SoilProperties] = None,
    wall_mode: WallSystemMode = WallSystemMode.CANTILEVER,
    multi_strut_model: Optional[MultiStrutPiledWallModel] = None,
    backfill_extent_factor: float = 3.0,
    foundation_depth_factor: float = 2.0,
    z_buffer_m: float = 1.0,
    nx_backfill: int = 6,
    ny_wall: int = 5,
    nz_wall: int = 4,
    nz_buffer: int = 1,
    ny_found: int = 3,
    nx_toe_pad: int = 2,
    separate_interfaces: bool = True,
) -> ContinuumFEAMesh:
    """
    Constructs a conformal 3D hexahedral soil-structure interaction FEA mesh.

    Backfill extends >= backfill_extent_factor * H behind the wall backface;
    foundation extends >= foundation_depth_factor * B below the base slab.
    When `separate_interfaces=True`, coincident soil/wall interface nodes are
    duplicated along the vertical stem backface and footing base so zero-length
    Coulomb friction + no-tension gap elements can be inserted cleanly.
    """
    # Resolve wall dimensions depending on system mode
    if wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL and multi_strut_model is not None:
        h_total = float(multi_strut_model.shell.panel_height)
        t_footing = min(0.8, 0.12 * h_total)
        t_stem = float(multi_strut_model.shell.thickness)
        toe_len = 0.0
        b_width = float(max(multi_strut_model.pier_pile.pier_depth, t_stem))
        l_wall = float(multi_strut_model.shell.bay_span * 3.0)
        x_backface = t_stem
    else:
        h_total = float(geom.total_height)
        t_footing = float(geom.footing_thickness)
        t_stem = float(geom.stem_thickness_base)
        toe_len = float(geom.toe_length)
        b_width = float(geom.base_width)
        l_wall = float(geom.wall_length)
        x_backface = toe_len + t_stem

    extent_back = max(backfill_extent_factor * h_total, b_width + 2.0 * h_total)
    depth_found = max(foundation_depth_factor * b_width, 4.0)
    x_left = -max(1.5 * b_width, 2.0)
    x_right = x_backface + extent_back
    z_buf = max(0.0, float(z_buffer_m))

    # Build monotonic X, Y, Z grid coordinates aligned with structural interfaces
    x_anchors = _unique_sorted_coords([x_left, 0.0, toe_len, x_backface, b_width, x_right])
    x_counts = []
    for i in range(len(x_anchors) - 1):
        mid = 0.5 * (x_anchors[i] + x_anchors[i + 1])
        if mid < 0.0:
            x_counts.append(max(1, nx_toe_pad))
        elif mid > b_width:
            x_counts.append(max(2, nx_backfill))
        else:
            x_counts.append(1)
    xs = _subdivide_ticks(x_anchors.tolist(), x_counts)

    y_anchors = _unique_sorted_coords([-depth_found, 0.0, t_footing, h_total])
    y_counts = []
    for i in range(len(y_anchors) - 1):
        mid = 0.5 * (y_anchors[i] + y_anchors[i + 1])
        if mid < 0.0:
            y_counts.append(max(2, ny_found))
        elif mid < t_footing:
            y_counts.append(1)
        else:
            y_counts.append(max(2, ny_wall))
    ys = _subdivide_ticks(y_anchors.tolist(), y_counts)

    if z_buf > 1e-5 and nz_buffer >= 1:
        z_anchors = _unique_sorted_coords([-z_buf, 0.0, l_wall, l_wall + z_buf])
        zs = _subdivide_ticks(z_anchors.tolist(), [nz_buffer, max(1, nz_wall), nz_buffer])
    else:
        zs = np.linspace(0.0, l_wall, max(1, nz_wall) + 1, dtype=np.float64)

    nx_pts, ny_pts, nz_pts = len(xs), len(ys), len(zs)
    gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij")
    base_nodes = np.stack([gx, gy, gz], axis=-1).reshape(-1, 3)

    def base_nid(ix: int, iy: int, iz: int) -> int:
        return ix * ny_pts * nz_pts + iy * nz_pts + iz

    # Build elements and assign physical domain IDs (1=Wall, 2=Backfill, 3=Foundation)
    raw_elems: List[List[int]] = []
    elem_domains: List[int] = []
    elem_is_backfill_soil: List[bool] = []
    elem_is_found_soil: List[bool] = []

    for ix in range(nx_pts - 1):
        xc = 0.5 * (xs[ix] + xs[ix + 1])
        for iy in range(ny_pts - 1):
            yc = 0.5 * (ys[iy] + ys[iy + 1])
            for iz in range(nz_pts - 1):
                zc = 0.5 * (zs[iz] + zs[iz + 1])

                # Skip empty air pockets in front of wall stem (x < toe and y > t_footing)
                # Keep full rectangular soil + wall block where backfill >= x_backface
                in_wall_z = (-1e-6 <= zc <= l_wall + 1e-6)
                in_footing = in_wall_z and (0.0 <= xc <= b_width) and (0.0 <= yc <= t_footing)
                in_stem = in_wall_z and (toe_len <= xc <= x_backface) and (t_footing <= yc <= h_total)
                in_heel_soil = (x_backface < xc <= b_width) and (t_footing <= yc <= h_total)
                in_far_backfill = (xc > b_width) and (0.0 <= yc <= h_total)
                in_side_backfill = (not in_wall_z) and (xc >= x_backface) and (0.0 <= yc <= h_total)
                in_foundation = (yc < 0.0)

                if not (in_footing or in_stem or in_heel_soil or in_far_backfill or in_side_backfill or in_foundation):
                    continue

                if in_footing or in_stem:
                    dom = 1
                elif in_foundation:
                    dom = 3
                else:
                    dom = 2

                # Standard VTK/OpenSees right-handed brick connectivity:
                # 0:(ix,iy,iz), 1:(ix+1,iy,iz), 2:(ix+1,iy+1,iz), 3:(ix,iy+1,iz),
                # 4:(ix,iy,iz+1), 5:(ix+1,iy,iz+1), 6:(ix+1,iy+1,iz+1), 7:(ix,iy+1,iz+1)
                conn = [
                    base_nid(ix, iy, iz),
                    base_nid(ix + 1, iy, iz),
                    base_nid(ix + 1, iy + 1, iz),
                    base_nid(ix, iy + 1, iz),
                    base_nid(ix, iy, iz + 1),
                    base_nid(ix + 1, iy, iz + 1),
                    base_nid(ix + 1, iy + 1, iz + 1),
                    base_nid(ix, iy + 1, iz + 1),
                ]
                raw_elems.append(conn)
                elem_domains.append(dom)
                elem_is_backfill_soil.append(dom == 2)
                elem_is_found_soil.append(dom == 3)

    # Filter only active nodes referenced by created elements
    elems_arr = np.asarray(raw_elems, dtype=np.int64)
    elem_dom_arr = np.asarray(elem_domains, dtype=np.int32)
    used_old_ids = np.unique(elems_arr)
    remap = np.full(base_nodes.shape[0], -1, dtype=np.int64)
    remap[used_old_ids] = np.arange(len(used_old_ids), dtype=np.int64)
    nodes_list = [base_nodes[used_old_ids]]
    elems_arr = remap[elems_arr]

    node_dom = np.full(len(used_old_ids), 2, dtype=np.int32)
    for dom_val in (3, 2, 1):
        mask = elem_dom_arr == dom_val
        if np.any(mask):
            node_dom[np.unique(elems_arr[mask])] = dom_val

    # Tributary area weights for interface & boundary nodes
    dx_trib, dy_trib = _compute_tributary_face_areas(xs, ys)
    _, dz_trib = _compute_tributary_face_areas(xs, zs)

    interface_pairs: List[ContinuumInterfacePair] = []
    backfill_backface_nodes: List[int] = []
    wall_backface_nodes: List[int] = []

    coords_cur = nodes_list[0]
    next_nid = int(coords_cur.shape[0])
    extra_coords: List[np.ndarray] = []
    extra_doms: List[int] = []

    # Create paired duplicate soil nodes along wall backface (x == x_backface, y >= t_footing, z in [0, l_wall])
    if separate_interfaces:
        dup_map_backface: Dict[int, int] = {}
        dup_map_base: Dict[int, int] = {}

        # Backface interface nodes: on plane x = x_backface, t_footing <= y <= h_total, 0 <= z <= l_wall
        for nid_cur in range(coords_cur.shape[0]):
            px, py, pz = coords_cur[nid_cur]
            in_z_wall = (-1e-6 <= pz <= l_wall + 1e-6)
            if in_z_wall and abs(px - x_backface) < 1e-5 and (t_footing - 1e-5 <= py <= h_total + 1e-5):
                ix_match = int(np.argmin(np.abs(xs - px)))
                iy_match = int(np.argmin(np.abs(ys - py)))
                iz_match = int(np.argmin(np.abs(zs - pz)))
                area = float(dy_trib[iy_match] * dz_trib[iz_match])
                soil_nid = next_nid
                next_nid += 1
                extra_coords.append(coords_cur[nid_cur].copy())
                extra_doms.append(2)
                dup_map_backface[nid_cur] = soil_nid
                wall_backface_nodes.append(nid_cur)
                backfill_backface_nodes.append(soil_nid)
                interface_pairs.append(
                    ContinuumInterfacePair(
                        wall_node_id=nid_cur,
                        soil_node_id=soil_nid,
                        area_trib=max(1e-4, area),
                        normal=(1.0, 0.0, 0.0),
                        coord=(float(px), float(py), float(pz)),
                        zone="backface",
                    )
                )

            # Footing base interface nodes: on plane y = 0.0, 0 <= x <= b_width, 0 <= z <= l_wall
            elif in_z_wall and abs(py) < 1e-5 and (-1e-5 <= px <= b_width + 1e-5):
                ix_match = int(np.argmin(np.abs(xs - px)))
                iz_match = int(np.argmin(np.abs(zs - pz)))
                area = float(dx_trib[ix_match] * dz_trib[iz_match])
                soil_nid = next_nid
                next_nid += 1
                extra_coords.append(coords_cur[nid_cur].copy())
                extra_doms.append(3)
                dup_map_base[nid_cur] = soil_nid
                interface_pairs.append(
                    ContinuumInterfacePair(
                        wall_node_id=nid_cur,
                        soil_node_id=soil_nid,
                        area_trib=max(1e-4, area),
                        normal=(0.0, -1.0, 0.0),
                        coord=(float(px), float(py), float(pz)),
                        zone="base",
                    )
                )

        # Rewire backfill (Domain 2) & foundation (Domain 3) elements onto the soil side of interfaces
        for e_idx in range(elems_arr.shape[0]):
            dom_e = int(elem_dom_arr[e_idx])
            if dom_e == 2:
                for k in range(8):
                    old_n = int(elems_arr[e_idx, k])
                    if old_n in dup_map_backface:
                        elems_arr[e_idx, k] = dup_map_backface[old_n]
            elif dom_e == 3:
                for k in range(8):
                    old_n = int(elems_arr[e_idx, k])
                    if old_n in dup_map_base:
                        elems_arr[e_idx, k] = dup_map_base[old_n]

    if extra_coords:
        nodes_all = np.vstack([coords_cur, np.asarray(extra_coords, dtype=np.float64)])
        node_dom_all = np.concatenate([node_dom, np.asarray(extra_doms, dtype=np.int32)])
    else:
        nodes_all = coords_cur
        node_dom_all = node_dom

    # Boundary node sets and Lysmer tributary areas
    x_min = float(xs[0])
    x_max = float(xs[-1])
    y_min = float(ys[0])
    z_min = float(zs[0])
    z_max = float(zs[-1])

    fixed_base_nodes: List[int] = []
    lateral_x_nodes: List[int] = []
    lateral_z_nodes: List[int] = []
    wall_crest_nodes: List[int] = []
    top_surface_nodes: List[int] = []
    lysmer_nodes: List[LysmerBoundaryNode] = []

    # Backfill soil nodes along backface when separate_interfaces=False
    if not separate_interfaces:
        for nid in range(nodes_all.shape[0]):
            px, py, pz = nodes_all[nid]
            if abs(px - x_backface) < 1e-5 and (t_footing - 1e-5 <= py <= h_total + 1e-5):
                backfill_backface_nodes.append(nid)
                wall_backface_nodes.append(nid)

    for nid in range(nodes_all.shape[0]):
        px, py, pz = nodes_all[nid]
        dom_n = int(node_dom_all[nid])
        ix_m = int(np.argmin(np.abs(xs - px)))
        iy_m = int(np.argmin(np.abs(ys - py)))
        iz_m = int(np.argmin(np.abs(zs - pz)))

        if abs(py - y_min) < 1e-5:
            fixed_base_nodes.append(nid)
            lysmer_nodes.append(
                LysmerBoundaryNode(
                    node_id=nid,
                    area_trib=max(1e-4, float(dx_trib[ix_m] * dz_trib[iz_m])),
                    normal=(0.0, -1.0, 0.0),
                    face_name="bottom",
                )
            )

        if abs(px - x_max) < 1e-5 or abs(px - x_min) < 1e-5:
            lateral_x_nodes.append(nid)
            nx_dir = 1.0 if abs(px - x_max) < 1e-5 else -1.0
            face = "right" if nx_dir > 0 else "left"
            lysmer_nodes.append(
                LysmerBoundaryNode(
                    node_id=nid,
                    area_trib=max(1e-4, float(dy_trib[iy_m] * dz_trib[iz_m])),
                    normal=(nx_dir, 0.0, 0.0),
                    face_name=face,
                )
            )

        if abs(pz - z_min) < 1e-5 or abs(pz - z_max) < 1e-5:
            lateral_z_nodes.append(nid)
            nz_dir = 1.0 if abs(pz - z_max) < 1e-5 else -1.0
            face = "back_z" if nz_dir > 0 else "front_z"
            lysmer_nodes.append(
                LysmerBoundaryNode(
                    node_id=nid,
                    area_trib=max(1e-4, float(dx_trib[ix_m] * dy_trib[iy_m])),
                    normal=(0.0, 0.0, nz_dir),
                    face_name=face,
                )
            )

        if abs(py - h_total) < 1e-5:
            top_surface_nodes.append(nid)
            if dom_n == 1 and (-1e-5 <= pz <= l_wall + 1e-5):
                wall_crest_nodes.append(nid)

    return ContinuumFEAMesh(
        nodes=nodes_all,
        elements=elems_arr,
        element_domain_ids=elem_dom_arr,
        node_domain_ids=node_dom_all,
        interface_pairs=interface_pairs,
        lysmer_nodes=lysmer_nodes,
        fixed_base_nodes=fixed_base_nodes,
        lateral_x_nodes=lateral_x_nodes,
        lateral_z_nodes=lateral_z_nodes,
        wall_crest_nodes=wall_crest_nodes,
        backfill_backface_nodes=backfill_backface_nodes,
        wall_backface_nodes=wall_backface_nodes,
        top_surface_nodes=top_surface_nodes,
        geometry_meta={
            "wall_mode": wall_mode.value,
            "H_wall": h_total,
            "t_footing": t_footing,
            "t_stem": t_stem,
            "toe_length": toe_len,
            "B_wall": b_width,
            "L_wall": l_wall,
            "x_backface": x_backface,
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": h_total,
            "z_min": z_min,
            "z_max": z_max,
            "extent_back": extent_back,
            "depth_found": depth_found,
            "z_buffer": z_buf,
        },
    )

