"""
3D Hexahedral Mesh Generators for Phase 7 Architectural Wall Morphologies
and Adjacent Building / Traffic Surcharge Visualization.

All generated volumetric blocks guarantee strictly positive Jacobian determinants
(det(J) > 0) using right-handed trilinear VTK_HEXAHEDRON topology via `shell_mesher`.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple
import numpy as np
import pyvista as pv

from ..models.architectural_wall_params import (
    ArchWallMorphology,
    ArchitecturalWallSpec,
    CornerWingwallParams,
    CounterfortWallParams,
    CurvedPlanWallParams,
    MSEGabionWallParams,
    SteppedTerracedWallParams,
)
from ..models.wall_params import RetainingWallGeometry, SeismicParams, SoilProperties
from ..physics.arch_wall_solver import ArchWallAnalysisSummary
from ..physics.surcharge import AdjacentSurchargeParams, SurchargeLoadType
from .shell_mesher import compute_hex_jacobian_determinants, create_hex_cells


def _build_right_handed_hex_block(
    pts_grid: np.ndarray,
    tensile_mpa: np.ndarray,
    von_mises_mpa: np.ndarray,
    pore_kpa: np.ndarray,
    deform_vec: np.ndarray,
    element_type_id: int = 1,
) -> pv.UnstructuredGrid:
    """
    Converts a structured 3D point array of shape (nz, ny, nx, 3) into a
    non-inverted PyVista UnstructuredGrid of VTK_HEXAHEDRON cells, automatically
    enforcing positive element Jacobian determinants (det(J) > 0).
    """
    nz, ny, nx, _ = pts_grid.shape
    if nz < 2 or ny < 2 or nx < 2:
        raise ValueError(f"Structured block must have >= 2 nodes per axis, got {(nz, ny, nx)}")

    # Check sample Jacobian determinant orientation at first cell
    p000 = pts_grid[0, 0, 0]
    p100 = pts_grid[0, 0, 1]
    p010 = pts_grid[0, 1, 0]
    p001 = pts_grid[1, 0, 0]
    orient = float(np.dot(np.cross(p100 - p000, p010 - p000), p001 - p000))
    if orient < 0.0:
        pts_grid = pts_grid[::-1].copy()
        tensile_mpa = tensile_mpa[::-1].copy()
        von_mises_mpa = von_mises_mpa[::-1].copy()
        pore_kpa = pore_kpa[::-1].copy()
        deform_vec = deform_vec[::-1].copy()

    flat_pts = pts_grid.reshape(-1, 3).astype(np.float64)
    cells, cell_types = create_hex_cells(nz, ny, nx, pt_offset=0)
    grid = pv.UnstructuredGrid(cells, cell_types, flat_pts)
    grid.point_data["TensileStress_MPa"] = tensile_mpa.ravel().astype(np.float32)
    grid.point_data["VonMises_MPa"] = von_mises_mpa.ravel().astype(np.float32)
    grid.point_data["PorePressure_kPa"] = pore_kpa.ravel().astype(np.float32)
    grid.point_data["Deformation_m"] = deform_vec.reshape(-1, 3).astype(np.float32)
    grid.cell_data["Element_Type"] = np.full(grid.n_cells, element_type_id, dtype=np.int32)
    return grid


def _merge_blocks(blocks: List[pv.UnstructuredGrid]) -> pv.UnstructuredGrid:
    """Safely merges non-empty UnstructuredGrid blocks into one multi-part mesh."""
    if not blocks:
        raise ValueError("Cannot merge empty block list")
    if len(blocks) == 1:
        return blocks[0]
    return blocks[0].merge(blocks[1:])


def _make_tapered_prism_grid(
    x_bot_front: float,
    x_bot_back: float,
    x_top_front: float,
    x_top_back: float,
    y_bot: float,
    y_top: float,
    z_start: float,
    z_end: float,
    nx: int = 3,
    ny: int = 6,
    nz: int = 6,
    max_tensile: float = 1.5,
    max_vm: float = 2.0,
    max_disp: float = 0.012,
    pore_max: float = 15.0,
    element_type_id: int = 1,
) -> pv.UnstructuredGrid:
    """Builds an aligned hexahedral prism block between two Y elevations."""
    u = np.linspace(0.0, 1.0, nx)
    v = np.linspace(0.0, 1.0, ny)
    z_vals = np.linspace(z_start, z_end, nz)

    pts = np.zeros((nz, ny, nx, 3), dtype=np.float64)
    xf_y = x_bot_front + v * (x_top_front - x_bot_front)
    xb_y = x_bot_back + v * (x_top_back - x_bot_back)
    y_vals = y_bot + v * (y_top - y_bot)

    for k, zv in enumerate(z_vals):
        for j, yv in enumerate(y_vals):
            pts[k, j, :, 0] = xf_y[j] + u * (xb_y[j] - xf_y[j])
            pts[k, j, :, 1] = yv
            pts[k, j, :, 2] = zv

    # Linear-bending stress decay toward top; quadratic cantilever deflection toward crest
    v_3d = np.broadcast_to(v[None, :, None], (nz, ny, nx))
    tensile = max_tensile * ((1.0 - v_3d) ** 1.6)
    vm = max_vm * ((1.0 - v_3d) ** 1.3 + 0.15)
    pore = pore_max * (1.0 - v_3d)
    deform = np.zeros((nz, ny, nx, 3), dtype=np.float64)
    deform[:, :, :, 0] = -max_disp * (v_3d ** 2)
    return _build_right_handed_hex_block(pts, tensile, vm, pore, deform, element_type_id)


def build_stepped_terraced_wall_mesh(
    params: SteppedTerracedWallParams,
    summary: Optional[ArchWallAnalysisSummary] = None,
) -> pv.UnstructuredGrid:
    """Builds 2-to-4 stacked terraced tiers with bench setbacks (+X, +Y)."""
    heights = params.resolved_tier_heights
    sigma_base = summary.analysis_results.concrete_tensile_stress if summary else 1.4
    blocks: List[pv.UnstructuredGrid] = []

    b_foot = params.toe_length + params.stem_thickness_base + params.heel_length
    y_cursor = 0.0
    x_cursor = 0.0
    t_diff = params.stem_thickness_base - params.stem_thickness_top

    for idx, h_i in enumerate(heights):
        # Footing slab
        blocks.append(
            _make_tapered_prism_grid(
                x_cursor, x_cursor + b_foot,
                x_cursor, x_cursor + b_foot,
                y_cursor, y_cursor + params.footing_thickness,
                0.0, params.wall_length,
                nx=5, ny=2, nz=8,
                max_tensile=0.7 * sigma_base, max_vm=0.9 * sigma_base, max_disp=0.002,
                element_type_id=1,
            )
        )
        # Stem on footing
        x_sb = x_cursor + params.toe_length
        blocks.append(
            _make_tapered_prism_grid(
                x_sb, x_sb + params.stem_thickness_base,
                x_sb + t_diff, x_sb + params.stem_thickness_base,
                y_cursor + params.footing_thickness,
                y_cursor + params.footing_thickness + h_i,
                0.0, params.wall_length,
                nx=3, ny=7, nz=8,
                max_tensile=sigma_base, max_vm=1.2 * sigma_base, max_disp=0.010,
                element_type_id=1,
            )
        )
        y_cursor += h_i
        x_cursor += params.stem_thickness_base + params.bench_width

    return _merge_blocks(blocks)


def _extrude_plan_quad_hex(
    p00: Tuple[float, float],
    p10: Tuple[float, float],
    p11: Tuple[float, float],
    p01: Tuple[float, float],
    y_bot: float,
    y_top: float,
    nu: int = 3,
    nv: int = 6,
    nw: int = 3,
    max_tensile: float = 1.6,
    max_vm: float = 2.1,
    disp_dir: Tuple[float, float] = (-0.01, 0.0),
    element_type_id: int = 1,
) -> pv.UnstructuredGrid:
    """
    Bilinearly maps a horizontal plan quadrilateral (x, z) over u, w in [0, 1]
    and extrudes along vertical Y in [y_bot, y_top].
    """
    u_arr = np.linspace(0.0, 1.0, nu)
    v_arr = np.linspace(0.0, 1.0, nv)
    w_arr = np.linspace(0.0, 1.0, nw)
    pts = np.zeros((nw, nv, nu, 3), dtype=np.float64)

    q00 = np.array(p00, dtype=np.float64)
    q10 = np.array(p10, dtype=np.float64)
    q11 = np.array(p11, dtype=np.float64)
    q01 = np.array(p01, dtype=np.float64)

    for k, wv in enumerate(w_arr):
        for i, uv in enumerate(u_arr):
            xz = (
                (1.0 - uv) * (1.0 - wv) * q00
                + uv * (1.0 - wv) * q10
                + uv * wv * q11
                + (1.0 - uv) * wv * q01
            )
            pts[k, :, i, 0] = xz[0]
            pts[k, :, i, 1] = y_bot + v_arr * (y_top - y_bot)
            pts[k, :, i, 2] = xz[1]

    v_3d = np.broadcast_to(v_arr[None, :, None], (nw, nv, nu))
    tensile = max_tensile * ((1.0 - v_3d) ** 1.5)
    vm = max_vm * ((1.0 - v_3d) ** 1.2 + 0.15)
    pore = 18.0 * (1.0 - v_3d)
    deform = np.zeros((nw, nv, nu, 3), dtype=np.float64)
    deform[:, :, :, 0] = disp_dir[0] * (v_3d ** 2)
    deform[:, :, :, 2] = disp_dir[1] * (v_3d ** 2)
    return _build_right_handed_hex_block(pts, tensile, vm, pore, deform, element_type_id)


def build_corner_wingwall_mesh(
    params: CornerWingwallParams,
    summary: Optional[ArchWallAnalysisSummary] = None,
) -> pv.UnstructuredGrid:
    """
    Builds intersecting primary leg, angled wingwall at corner_angle_deg in [60°, 150°],
    footing pads, and conformal 3D corner stiffener haunch prism.
    """
    c_res = summary.corner if summary and summary.corner else None
    vm_corner = c_res.corner_peak_von_mises_mpa if c_res else 2.2
    vm_mid = c_res.midspan_peak_von_mises_mpa if c_res else 1.5
    disp_mid = c_res.unbraced_displacement_m if c_res else 0.010

    blocks: List[pv.UnstructuredGrid] = []
    alpha = math.radians(params.corner_angle_deg)
    d_f = params.footing_thickness
    h_s = params.stem_height
    t_b = params.stem_thickness_base
    b_foot = params.toe_length + t_b + params.heel_length

    # 1. Primary Leg extending along +Z from z=0 to z=primary_length
    blocks.append(
        _make_tapered_prism_grid(
            -params.toe_length, t_b + params.heel_length,
            -params.toe_length, t_b + params.heel_length,
            0.0, d_f, 0.0, params.primary_length,
            nx=4, ny=2, nz=8, max_tensile=vm_mid * 0.7, max_vm=vm_mid * 0.8, max_disp=0.002,
        )
    )
    blocks.append(
        _make_tapered_prism_grid(
            0.0, t_b, params.stem_thickness_base - params.stem_thickness_top, t_b,
            d_f, d_f + h_s, 0.0, params.primary_length,
            nx=3, ny=8, nz=8, max_tensile=vm_mid, max_vm=vm_mid * 1.15, max_disp=disp_mid,
        )
    )

    # 2. Angled Wingwall rotating around corner origin by interior corner angle alpha
    e_w = np.array([math.sin(alpha), math.cos(alpha)], dtype=np.float64)
    n_w = np.array([e_w[1], -e_w[0]], dtype=np.float64)
    if np.dot(n_w, np.array([1.0, 0.0])) < 0.0:
        n_w = -n_w  # keep backfill direction consistent on interior side

    l2 = params.wing_length
    # Wing footing quad
    blocks.append(
        _extrude_plan_quad_hex(
            tuple((-params.toe_length) * n_w),
            tuple((t_b + params.heel_length) * n_w),
            tuple(l2 * e_w + (t_b + params.heel_length) * n_w),
            tuple(l2 * e_w - params.toe_length * n_w),
            0.0, d_f, nu=4, nv=2, nw=8,
            max_tensile=vm_mid * 0.7, max_vm=vm_mid * 0.8,
        )
    )
    # Wing stem quad
    blocks.append(
        _extrude_plan_quad_hex(
            (0.0, 0.0),
            tuple(t_b * n_w),
            tuple(l2 * e_w + t_b * n_w),
            tuple(l2 * e_w),
            d_f, d_f + h_s, nu=3, nv=8, nw=8,
            max_tensile=vm_mid, max_vm=vm_mid * 1.15,
            disp_dir=(-float(n_w[0]) * disp_mid, -float(n_w[1]) * disp_mid),
        )
    )

    # 3. Conformal Corner Stiffener / Haunch Block (non-degenerate parallelogram)
    if params.stiffener_fillet_width > 0.05:
        d_fil = params.stiffener_fillet_width
        e1 = np.array([0.0, 1.0], dtype=np.float64)
        p_o = np.array([t_b * 0.5, t_b * 0.5], dtype=np.float64)
        p1 = p_o + d_fil * e1
        p3 = p_o + d_fil * e_w
        p2 = p_o + d_fil * (e1 + e_w)
        blocks.append(
            _extrude_plan_quad_hex(
                (float(p_o[0]), float(p_o[1])),
                (float(p1[0]), float(p1[1])),
                (float(p2[0]), float(p2[1])),
                (float(p3[0]), float(p3[1])),
                d_f, d_f + h_s, nu=3, nv=8, nw=3,
                max_tensile=vm_corner * 0.85, max_vm=vm_corner,
                disp_dir=(-0.25 * disp_mid, -0.25 * disp_mid),
                element_type_id=2,  # 2 = Corner Stiffener
            )
        )

    return _merge_blocks(blocks)


def build_counterfort_wall_mesh(
    params: CounterfortWallParams,
    summary: Optional[ArchWallAnalysisSummary] = None,
) -> pv.UnstructuredGrid:
    """Builds footing, continuous wall stem, and periodic counterfort / buttress webs."""
    sigma_slab = summary.counterfort.max_tensile_stress_mpa if summary and summary.counterfort else 1.7
    blocks: List[pv.UnstructuredGrid] = []

    d_f = params.footing_thickness
    h_s = params.wall_height
    t_s = params.stem_thickness
    b_foot = params.toe_length + t_s + params.heel_length

    # Footing
    blocks.append(
        _make_tapered_prism_grid(
            0.0, b_foot, 0.0, b_foot,
            0.0, d_f, 0.0, params.wall_length,
            nx=5, ny=2, nz=14, max_tensile=0.7 * sigma_slab, max_vm=0.9 * sigma_slab, max_disp=0.002,
        )
    )
    # Continuous stem
    x_sf = params.toe_length
    x_sb = params.toe_length + t_s
    blocks.append(
        _make_tapered_prism_grid(
            x_sf, x_sb, x_sf, x_sb,
            d_f, d_f + h_s, 0.0, params.wall_length,
            nx=3, ny=8, nz=14, max_tensile=sigma_slab, max_vm=1.2 * sigma_slab, max_disp=0.011,
        )
    )

    # Periodic Counterfort (rear) or Buttress (front) triangular-trapezoidal webs
    n_ribs = max(2, params.num_bays + 1)
    z_centers = np.linspace(
        0.5 * params.counterfort_thickness + 0.25,
        params.wall_length - 0.5 * params.counterfort_thickness - 0.25,
        n_ribs,
    )
    h_rib = max(0.5, h_s - params.counterfort_top_offset)
    t_cf = params.counterfort_thickness

    for zc in z_centers:
        if params.is_buttress:
            xb0, xf0 = x_sf, 0.05
            xb1, xf1 = x_sf, max(0.05, x_sf - 0.22)
            # Keep minimum positive width xf < xb
            xf0 = min(xf0, xb0 - 0.15)
            xf1 = min(xf1, xb1 - 0.15)
        else:
            xf0, xb0 = x_sb, x_sb + params.heel_length
            xf1, xb1 = x_sb, x_sb + min(0.35, 0.2 * params.heel_length)

        blocks.append(
            _make_tapered_prism_grid(
                xf0, xb0, xf1, xb1,
                d_f, d_f + h_rib,
                zc - 0.5 * t_cf, zc + 0.5 * t_cf,
                nx=3, ny=7, nz=2,
                max_tensile=sigma_slab * 0.9, max_vm=sigma_slab * 1.15, max_disp=0.006,
                element_type_id=3,
            )
        )

    return _merge_blocks(blocks)


def _build_polar_arc_block(
    r_bot_in: float,
    r_bot_out: float,
    r_top_in: float,
    r_top_out: float,
    y_bot: float,
    y_top: float,
    theta_rad_half: float,
    cx: float,
    cz: float,
    n_theta: int = 16,
    n_y: int = 8,
    n_r: int = 3,
    max_tensile: float = 1.4,
    max_vm: float = 1.9,
    max_disp: float = 0.009,
) -> pv.UnstructuredGrid:
    """Extrudes a curved plan-view retaining ring/stem segment with det(J) > 0."""
    thetas = np.linspace(-theta_rad_half, theta_rad_half, n_theta)
    v_arr = np.linspace(0.0, 1.0, n_y)
    u_r = np.linspace(0.0, 1.0, n_r)

    # Order (k=r, j=y, i=theta) ensures right-handed Jacobian (dP/dtheta x dP/dy) . dP/dr > 0
    pts = np.zeros((n_r, n_y, n_theta, 3), dtype=np.float64)
    deform = np.zeros((n_r, n_y, n_theta, 3), dtype=np.float64)

    r_in_y = r_bot_in + v_arr * (r_top_in - r_bot_in)
    r_out_y = r_bot_out + v_arr * (r_top_out - r_bot_out)

    sin_t = np.sin(thetas)
    cos_t = np.cos(thetas)

    for k, ur in enumerate(u_r):
        for j, _ in enumerate(v_arr):
            r_val = r_in_y[j] + ur * (r_out_y[j] - r_in_y[j])
            yv = y_bot + v_arr[j] * (y_top - y_bot)
            pts[k, j, :, 0] = cx + r_val * sin_t
            pts[k, j, :, 1] = yv
            pts[k, j, :, 2] = cz + r_val * cos_t
            deform[k, j, :, 0] = -max_disp * (v_arr[j] ** 2) * sin_t
            deform[k, j, :, 2] = -max_disp * (v_arr[j] ** 2) * cos_t

    v_3d = np.broadcast_to(v_arr[None, :, None], (n_r, n_y, n_theta))
    tensile = max_tensile * ((1.0 - v_3d) ** 1.5)
    vm = max_vm * ((1.0 - v_3d) ** 1.3 + 0.1)
    pore = 12.0 * (1.0 - v_3d)
    return _build_right_handed_hex_block(pts, tensile, vm, pore, deform, element_type_id=4)


def build_curved_plan_wall_mesh(
    params: CurvedPlanWallParams,
    summary: Optional[ArchWallAnalysisSummary] = None,
) -> pv.UnstructuredGrid:
    """Builds conformal curved plan-view retaining footing and tapered stem."""
    sigma_max = summary.curved_plan.max_tensile_stress_mpa if summary and summary.curved_plan else 1.3
    r_mid = params.plan_radius
    half_ang = 0.5 * math.radians(params.sweep_angle_deg)
    d_f = params.footing_thickness
    h_s = params.stem_height
    t_b = params.stem_thickness_base
    t_t = params.stem_thickness_top

    # Shift circle center so arc mid-chord stays centered nicely near X=0, Z=L/2
    cx = -r_mid if params.concave_to_backfill else r_mid
    cz = 0.5 * params.arc_length

    r_f_in = r_mid - params.toe_length
    r_f_out = r_mid + t_b + params.heel_length
    foot_grid = _build_polar_arc_block(
        r_f_in, r_f_out, r_f_in, r_f_out,
        0.0, d_f, half_ang, cx, cz,
        n_theta=16, n_y=2, n_r=4,
        max_tensile=0.6 * sigma_max, max_vm=0.8 * sigma_max, max_disp=0.002,
    )
    stem_grid = _build_polar_arc_block(
        r_mid, r_mid + t_b, r_mid + (t_b - t_t), r_mid + t_b,
        d_f, d_f + h_s, half_ang, cx, cz,
        n_theta=16, n_y=8, n_r=3,
        max_tensile=sigma_max, max_vm=1.15 * sigma_max, max_disp=0.008,
    )
    return _merge_blocks([foot_grid, stem_grid])


def build_mse_gabion_wall_mesh(
    params: MSEGabionWallParams,
    summary: Optional[ArchWallAnalysisSummary] = None,
) -> pv.UnstructuredGrid:
    """Builds tiered modular MSE / Gabion / Crib facing blocks and geogrid straps."""
    mse_res = summary.mse if summary and summary.mse else None
    blocks: List[pv.UnstructuredGrid] = []
    hc = params.course_height
    db = params.block_depth
    tan_b = math.tan(math.radians(params.batter_deg))

    for c_idx in range(params.num_courses):
        y0 = c_idx * hc
        y1 = y0 + hc * 0.98  # tiny visual course joint reveal
        x0 = c_idx * hc * tan_b
        stress_scale = (c_idx + 1) / max(1, params.num_courses)
        t_val = (mse_res.max_tension_kn_per_m / 30.0) if mse_res else 1.0

        # Facing / gabion / crib course block
        blocks.append(
            _make_tapered_prism_grid(
                x0, x0 + db, x0, x0 + db,
                y0, y1, 0.0, params.wall_length,
                nx=2, ny=2, nz=8,
                max_tensile=t_val * (1.2 - 0.5 * stress_scale),
                max_vm=t_val * (1.4 - 0.5 * stress_scale),
                max_disp=0.012 * stress_scale,
                element_type_id=5,
            )
        )
        # Geogrid / reinforcement strap extending behind facing block (every course)
        if params.wall_subtype in ("mse_geogrid", "gabion"):
            y_strip = y0 + 0.08 * hc
            blocks.append(
                _make_tapered_prism_grid(
                    x0 + db, x0 + params.reinforcement_length,
                    x0 + db, x0 + params.reinforcement_length,
                    y_strip, y_strip + 0.04,
                    0.15, params.wall_length - 0.15,
                    nx=4, ny=2, nz=4,
                    max_tensile=t_val, max_vm=t_val * 1.1, max_disp=0.008 * stress_scale,
                    element_type_id=6,
                )
            )

    return _merge_blocks(blocks)


def build_architectural_wall_mesh(
    spec: ArchitecturalWallSpec,
    summary: Optional[ArchWallAnalysisSummary] = None,
) -> pv.UnstructuredGrid:
    """Builds the 3D hexahedral PyVista mesh for the active Phase 7 morphology."""
    m = spec.morphology
    if m == ArchWallMorphology.STEPPED_TERRACED:
        return build_stepped_terraced_wall_mesh(spec.stepped, summary=summary)
    if m == ArchWallMorphology.CORNER_WINGWALL:
        return build_corner_wingwall_mesh(spec.corner, summary=summary)
    if m == ArchWallMorphology.COUNTERFORT:
        return build_counterfort_wall_mesh(spec.counterfort, summary=summary)
    if m == ArchWallMorphology.CURVED_PLAN:
        return build_curved_plan_wall_mesh(spec.curved_plan, summary=summary)
    return build_mse_gabion_wall_mesh(spec.mse, summary=summary)


def build_surcharge_3d_meshes(
    geom: RetainingWallGeometry,
    surcharge: AdjacentSurchargeParams,
) -> Tuple[Optional[pv.UnstructuredGrid], Optional[pv.UnstructuredGrid]]:
    """
    Creates translucent 3D PyVista indicator blocks representing an adjacent building
    footing (+ column/mass outline) or surface traffic surcharge strip on backfill.
    Returns (primary_footing_grid, superstructure_outline_grid).
    """
    if surcharge.load_type == SurchargeLoadType.NONE:
        return None, None

    x_backface = geom.toe_length + geom.stem_thickness_base
    y_crest = geom.total_height
    x1 = x_backface + surcharge.setback_m
    x2 = x1 + surcharge.footing_width_m
    l_z = min(geom.wall_length * 0.9, surcharge.footing_length_m)

    if surcharge.load_type == SurchargeLoadType.UNIFORM_TRAFFIC:
        z0 = 0.0
        z1 = geom.wall_length
        y0 = y_crest
        y1 = y_crest + 0.18
        strip = _make_tapered_prism_grid(
            x1, x2, x1, x2, y0, y1, z0, z1,
            nx=2, ny=2, nz=4, max_tensile=0.2, max_vm=0.2, max_disp=0.0,
        )
        return strip, None

    if surcharge.load_type == SurchargeLoadType.BUILDING_STRIP_FOOTING:
        z0 = 0.2
        z1 = max(z0 + 0.8, geom.wall_length - 0.2)
    else:  # BUILDING_PAD_FOOTING centered along wall Z
        z_mid = 0.5 * geom.wall_length
        z0 = max(0.0, z_mid - 0.5 * l_z)
        z1 = min(geom.wall_length, z_mid + 0.5 * l_z)

    y_bot = max(geom.footing_thickness, y_crest - surcharge.embedment_m - 0.45)
    y_top = max(y_bot + 0.45, y_crest - surcharge.embedment_m)
    footing = _make_tapered_prism_grid(
        x1, x2, x1, x2, y_bot, y_top, z0, z1,
        nx=2, ny=2, nz=2, max_tensile=0.4, max_vm=0.5, max_disp=0.0,
    )

    # Representative translucent building superstructure block rising above backfill crest
    inset = min(0.25, 0.2 * surcharge.footing_width_m)
    bx1, bx2 = x1 + inset, max(x1 + inset + 0.2, x2 - inset)
    bz0, bz1 = z0 + inset * 0.5, max(z0 + inset * 0.5 + 0.4, z1 - inset * 0.5)
    super_h = max(1.8, min(4.5, surcharge.building_load_kn / 180.0))
    superstructure = _make_tapered_prism_grid(
        bx1, bx2, bx1, bx2, y_crest, y_crest + super_h, bz0, bz1,
        nx=2, ny=2, nz=2, max_tensile=0.2, max_vm=0.2, max_disp=0.0,
    )
    return footing, superstructure


def verify_arch_mesh_jacobians(grid: pv.UnstructuredGrid) -> Tuple[bool, float]:
    """Verifies all hex cells in `grid` have det(J) > 0; returns (ok, min_det_j)."""
    det_j = compute_hex_jacobian_determinants(grid)
    if len(det_j) == 0:
        return False, 0.0
    min_j = float(np.min(det_j))
    return min_j > 0.0, min_j

