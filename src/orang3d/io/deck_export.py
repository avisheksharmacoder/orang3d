"""
Runnable Solver Deck & Reproducible Research Archive Exporters (Phase 9).

Provides:
  1. Standalone runnable OpenSeesPy BNWF script export (.py) matching the in-app solver.
  2. Standard Kratos GeoMechanics input deck export (RetainingWallSSI.mdpa + ProjectParameters.json).
  3. Research Archive export (.h5 compressed tensors + metadata.json provenance manifest).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence
import h5py
import numpy as np

from ..models.advanced_wall_params import MultiStrutPiledWallModel
from ..models.wall_params import (
    AnalysisResults,
    RetainingWallGeometry,
    SeismicParams,
    SoilProperties,
)
from ..physics.solver_registry import SolverProvenance
from ..physics.spring_curves import generate_soil_spring_profile


def export_opensees_bnwf_deck(
    filepath: str | Path,
    model: MultiStrutPiledWallModel,
    soil: SoilProperties,
    time_arr: Sequence[float] | np.ndarray,
    accel_arr: Sequence[float] | np.ndarray,
    slope_angle: float = 0.0,
    damping_ratio: float = 0.05,
    num_pile_nodes: int = 15,
    num_pier_nodes: int = 10,
    concrete_modulus: float = 30.0e6,
) -> str:
    """
    Exports a standalone, commented OpenSeesPy BNWF Python script replicating the
    exact nodes, materials, nonlinear p-y/t-z/q-z springs, raking struts, staged
    construction, and UniformExcitation dynamic run of `OpenSeesBNWFSolver`.
    """
    t_vec = np.asarray(time_arr, dtype=np.float64)
    a_vec = np.asarray(accel_arr, dtype=np.float64)
    if len(t_vec) < 2 or len(t_vec) != len(a_vec):
        raise ValueError("time_arr and accel_arr must have equal length >= 2")
    if num_pile_nodes < 3:
        raise ValueError(f"num_pile_nodes must be >= 3, got {num_pile_nodes}")
    if num_pier_nodes < 2:
        raise ValueError(f"num_pier_nodes must be >= 2, got {num_pier_nodes}")

    out_path = Path(filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    spring_profile = generate_soil_spring_profile(
        pier_pile=model.pier_pile,
        soil=soil,
        slope_angle=slope_angle,
        num_pile_nodes=num_pile_nodes,
    )

    py_data = [
        (int(sp.mat_type), float(sp.p_ult_integrated), float(sp.y_50), float(sp.cd))
        for sp in spring_profile.py_springs
    ]
    tz_data = [
        (float(sp.t_ult_integrated), float(sp.z_50))
        for sp in spring_profile.tz_springs
    ]
    qz_data = (float(spring_profile.qz_spring.q_ult), float(spring_profile.qz_spring.z_50))

    deck_params = {
        "pier_height": float(model.pier_pile.pier_height),
        "pile_length": float(model.pier_pile.pile_length),
        "pile_diameter": float(model.pier_pile.pile_diameter),
        "num_piles_per_pier": int(model.pier_pile.num_piles_per_pier),
        "pier_width": float(model.pier_pile.pier_width),
        "pier_depth": float(model.pier_pile.pier_depth),
        "bay_span": float(model.shell.bay_span),
        "soil_unit_weight": float(soil.unit_weight),
        "slope_angle": float(slope_angle),
        "num_pile_nodes": int(num_pile_nodes),
        "num_pier_nodes": int(num_pier_nodes),
        "concrete_modulus": float(concrete_modulus),
        "damping_ratio": float(damping_ratio),
        "strut_levels": [float(v) for v in model.struts.strut_levels],
        "strut_inclination_angle": float(model.struts.inclination_angle),
        "strut_unbraced_length": float(model.struts.unbraced_length),
        "strut_area": float(model.struts.cross_section_area),
        "strut_modulus": float(model.struts.elastic_modulus),
        "strut_p_cr": float(model.struts.euler_buckling_load),
        "strut_p_0": float(model.struts.pre_stress_load),
        "py_springs": py_data,
        "tz_springs": tz_data,
        "qz_spring": qz_data,
        "dt": float(t_vec[1] - t_vec[0]),
        "time_values": [float(v) for v in t_vec],
        "accel_values": [float(v) for v in a_vec],
    }

    script = f'''#!/usr/bin/env python3
"""
Standalone OpenSeesPy 2D BNWF Seismic Retaining Wall Verification Deck
Generated automatically by orang3D (Phase 9 Reproducible Research Exporter).

Usage:
    python {out_path.name}
    python {out_path.name} --output-json results.json
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import openseespy.opensees as ops


MODEL_PARAMS = {json.dumps(deck_params, indent=4)}


def run_deck() -> dict:
    p = MODEL_PARAMS
    ops.wipe()
    ops.model("basic", "-ndm", 2, "-ndf", 3)

    pier_h = p["pier_height"]
    pile_l = p["pile_length"]
    d_pile = p["pile_diameter"]
    n_piles = p["num_piles_per_pier"]
    b_pier = p["pier_width"]
    d_pier = p["pier_depth"]
    num_pier_nodes = p["num_pier_nodes"]
    num_pile_nodes = p["num_pile_nodes"]
    concrete_modulus = p["concrete_modulus"]

    transf_tag = 1
    ops.geomTransf("Linear", transf_tag)

    a_pier = b_pier * d_pier
    i_pier = (b_pier * (d_pier ** 3)) / 12.0
    a_pile = ((math.pi * (d_pile ** 2)) / 4.0) * n_piles
    i_pile = ((math.pi * (d_pile ** 4)) / 64.0) * n_piles

    rho_c = 2.55  # t/m^3
    pier_mass_per_len = a_pier * rho_c
    pile_mass_per_len = a_pile * rho_c

    node_elevations = {{}}

    # 1. Pier column nodes and beam-column elements (Y = 0 to pier_h)
    pier_y = np.linspace(0.0, pier_h, num_pier_nodes, dtype=np.float64)
    pier_nodes = []
    pier_elements = []
    for idx, y in enumerate(pier_y):
        tag = 100 + idx
        ops.node(tag, 0.0, float(y))
        node_elevations[tag] = float(y)
        pier_nodes.append(tag)
        dy = pier_h / (num_pier_nodes - 1)
        m_node = pier_mass_per_len * dy
        ops.mass(tag, m_node, m_node, 0.0)

    for idx in range(num_pier_nodes - 1):
        ele_tag = 500 + idx
        ops.element(
            "elasticBeamColumn",
            ele_tag,
            pier_nodes[idx],
            pier_nodes[idx + 1],
            a_pier,
            concrete_modulus,
            i_pier,
            transf_tag,
        )
        pier_elements.append(ele_tag)

    crest_node = pier_nodes[-1]
    pile_head_node = pier_nodes[0]

    # 2. Bored pile group nodes and beam-column elements (Y = 0 to -pile_l)
    pile_y = np.linspace(0.0, -pile_l, num_pile_nodes, dtype=np.float64)
    pile_nodes = [pile_head_node]
    pile_elements = []
    for idx in range(1, num_pile_nodes):
        tag = 200 + idx
        y = float(pile_y[idx])
        ops.node(tag, 0.0, y)
        node_elevations[tag] = y
        pile_nodes.append(tag)
        dy = pile_l / (num_pile_nodes - 1)
        m_node = pile_mass_per_len * dy
        ops.mass(tag, m_node, m_node, 0.0)

    for idx in range(num_pile_nodes - 1):
        ele_tag = 600 + idx
        ops.element(
            "elasticBeamColumn",
            ele_tag,
            pile_nodes[idx],
            pile_nodes[idx + 1],
            a_pile,
            concrete_modulus,
            i_pile,
            transf_tag,
        )
        pile_elements.append(ele_tag)

    # 3. Nonlinear Winkler Soil Springs (PySimple1, TzSimple1, QzSimple1)
    for idx, (p_node, (mtype, p_ult, y50, cd), (t_ult, z50)) in enumerate(
        zip(pile_nodes, p["py_springs"], p["tz_springs"])
    ):
        soil_tag = 300 + idx
        ops.node(soil_tag, 0.0, node_elevations[p_node])
        ops.fix(soil_tag, 1, 1, 1)

        py_mat_tag = 1000 + idx
        ops.uniaxialMaterial("PySimple1", py_mat_tag, mtype, p_ult * n_piles, y50, cd)

        tz_mat_tag = 2000 + idx
        ops.uniaxialMaterial("TzSimple1", tz_mat_tag, 1, t_ult * n_piles, z50, 0.0)

        ele_tag = 700 + idx
        if idx == num_pile_nodes - 1:
            qz_mat_tag = 3000
            q_ult, q_z50 = p["qz_spring"]
            ops.uniaxialMaterial("QzSimple1", qz_mat_tag, 1, q_ult * n_piles, q_z50, 0.0)
            parallel_tip_tag = 3001
            ops.uniaxialMaterial("Parallel", parallel_tip_tag, tz_mat_tag, qz_mat_tag)
            ops.element("zeroLength", ele_tag, soil_tag, p_node, "-mat", py_mat_tag, parallel_tip_tag, "-dir", 1, 2)
        else:
            ops.element("zeroLength", ele_tag, soil_tag, p_node, "-mat", py_mat_tag, tz_mat_tag, "-dir", 1, 2)

    # 4. Asymmetric Nonlinear Raking Struts
    alpha_rad = math.radians(p["strut_inclination_angle"])
    l_strut = p["strut_unbraced_length"]
    a_strut = p["strut_area"]
    e_strut = p["strut_modulus"]
    p_cr = p["strut_p_cr"]
    p_0 = p["strut_p_0"]

    sig_cr = p_cr / a_strut
    eps_cr = sig_cr / e_strut
    e_residual = 1e-5 * e_strut
    strains = [-0.05, -eps_cr, 0.0, 0.001, 0.05]
    stresses = [
        -sig_cr - e_residual * (0.05 - eps_cr),
        -sig_cr,
        0.0,
        e_residual * 0.001,
        e_residual * 0.05,
    ]

    strut_node_map = {{}}
    strut_elements = []
    for s_idx, d_lvl in enumerate(p["strut_levels"]):
        target_y = pier_h - d_lvl
        closest_node = min(pier_nodes, key=lambda n: abs(node_elevations[n] - target_y))
        pier_node_y = node_elevations[closest_node]
        anchor_x = -l_strut * math.cos(alpha_rad)
        anchor_y = pier_node_y - l_strut * math.sin(alpha_rad)
        anchor_tag = 400 + s_idx
        ops.node(anchor_tag, anchor_x, anchor_y)
        ops.fix(anchor_tag, 1, 1, 1)

        mat_tag = 4000 + s_idx
        ops.uniaxialMaterial("ElasticMultiLinear", mat_tag, "-strain", *strains, "-stress", *stresses)
        ele_tag = 800 + s_idx
        ops.element("truss", ele_tag, closest_node, anchor_tag, a_strut, mat_tag)
        strut_elements.append(ele_tag)
        strut_node_map[s_idx] = closest_node

    # 5. Staged Construction Sequence
    ops.system("BandGeneral")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.test("NormDispIncr", 1.0e-5, 50, 0)
    ops.algorithm("Newton")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")

    # Stage 0: Gravity self-weight
    ops.timeSeries("Linear", 101)
    ops.pattern("Plain", 201, 101)
    for node in pier_nodes + pile_nodes[1:]:
        y_elev = node_elevations[node]
        if y_elev >= 0.0:
            dy = pier_h / (num_pier_nodes - 1)
            f_g = -25.0 * (b_pier * d_pier) * dy
        else:
            dy = pile_l / (num_pile_nodes - 1)
            a_piles = ((math.pi * (d_pile ** 2)) / 4.0) * n_piles
            f_g = -25.0 * a_piles * dy
        ops.load(node, 0.0, f_g, 0.0)
    if ops.analyze(1) != 0:
        raise RuntimeError("Stage 0 static gravity equilibrium failed.")

    # Stage 1: Active earth pressure after excavation
    ops.loadConst()
    ops.timeSeries("Linear", 102)
    ops.pattern("Plain", 202, 102)
    total_p_active = 0.5 * p["soil_unit_weight"] * (pier_h ** 2) * 0.33 * p["bay_span"]
    f_lat = total_p_active / len(pier_nodes)
    for node in pier_nodes:
        ops.load(node, f_lat, 0.0, 0.0)
    if ops.analyze(1) != 0:
        raise RuntimeError("Stage 1 active earth pressure equilibrium failed.")

    # Stage 2: Lock-off strut prestress
    ops.loadConst()
    ops.timeSeries("Linear", 103)
    ops.pattern("Plain", 203, 103)
    for s_idx, pier_node in strut_node_map.items():
        ops.load(pier_node, -p_0 * math.cos(alpha_rad), -p_0 * math.sin(alpha_rad), 0.0)
    if ops.analyze(1) != 0:
        raise RuntimeError("Stage 2 strut lock-off equilibrium failed.")

    # 6. Dynamic UniformExcitation Analysis
    dt = p["dt"]
    damping_ratio = p["damping_ratio"]
    omega1 = 2.0 * math.pi * 1.5
    omega2 = 2.0 * math.pi * 10.0
    a0 = 2.0 * damping_ratio * (omega1 * omega2) / (omega1 + omega2)
    a1 = 2.0 * damping_ratio / (omega1 + omega2)
    ops.rayleigh(a0, a1, 0.0, 0.0)

    ops.timeSeries("Path", 200, "-dt", dt, "-values", *p["accel_values"], "-factor", 9.81)
    ops.pattern("UniformExcitation", 300, 1, "-accel", 200)

    ops.wipeAnalysis()
    ops.system("BandGeneral")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.test("NormDispIncr", 1.0e-4, 40, 0)
    ops.algorithm("Newton")
    ops.integrator("Newmark", 0.5, 0.25)
    ops.analysis("Transient")

    t_hist = []
    crest_u = []
    converged = True
    for t_val in p["time_values"]:
        ret = ops.analyze(1, dt)
        if ret != 0:
            ops.algorithm("ModifiedNewton")
            ret = ops.analyze(1, dt)
            ops.algorithm("Newton")
        if ret != 0:
            converged = False
            break
        t_hist.append(float(t_val))
        crest_u.append(float(ops.nodeDisp(crest_node, 1)))

    max_crest_cm = float(max(abs(u) for u in crest_u) * 100.0) if crest_u else 0.0
    return {{
        "dynamic_converged": converged,
        "total_steps": len(t_hist),
        "time_history": t_hist,
        "crest_displacement": crest_u,
        "max_crest_disp_cm": max_crest_cm,
    }}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run exported orang3D OpenSeesPy BNWF deck.")
    parser.add_argument("--output-json", type=str, default=None, help="Optional path to write JSON output.")
    args = parser.parse_args()
    out = run_deck()
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("ORANG3D_RESULTS_JSON:" + json.dumps(out))
'''
    out_path.write_text(script, encoding="utf-8")
    return str(out_path)


def export_kratos_deck(
    output_dir: str | Path,
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    time_arr: Optional[Sequence[float] | np.ndarray] = None,
    accel_arr: Optional[Sequence[float] | np.ndarray] = None,
    dt: float = 0.01,
) -> Dict[str, str]:
    """
    Exports standard KratosMultiphysics GeoMechanics input files:
      - `RetainingWallSSI.mdpa` (2D UPwSmallStrainElement2D4N mesh + Lysmer boundary conditions)
      - `ProjectParameters.json` (NewmarkDynamicUPwScheme + SkylineLUFactorizationSolver settings)
      - `ground_motion.csv` (when dynamic waveform arrays are provided)
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    h_wall = float(geom.total_height)
    t_stem = float(max(0.25, geom.stem_thickness_base))
    h_found = float(max(2.0, 0.5 * h_wall))
    l_back = float(max(8.0, 2.2 * h_wall))
    if_thick = max(0.20, 0.35 * t_stem)

    xs = np.array(
        [
            0.0,
            t_stem,
            t_stem + if_thick,
            t_stem + if_thick + 0.33 * (l_back - if_thick),
            t_stem + if_thick + 0.67 * (l_back - if_thick),
            t_stem + l_back,
        ],
        dtype=np.float64,
    )
    ys = np.array([-h_found, 0.0, 0.5 * h_wall, h_wall], dtype=np.float64)
    nx, ny = len(xs), len(ys)

    def _nid(ix: int, iy: int) -> int:
        return ix * ny + iy + 1

    is_wet = seismic.water_table_depth < h_wall
    rho_soil = float((soil.saturated_unit_weight if is_wet else soil.unit_weight) * 1000.0 / 9.81)
    rho_found = float(soil.foundation_unit_weight * 1000.0 / 9.81)
    rho_conc = float(geom.concrete_unit_weight * 1000.0 / 9.81)
    e_soil_pa = float(soil.elastic_modulus) * 1000.0
    tan_phi = math.tan(math.radians(max(10.0, soil.friction_angle)))
    e_iface_pa = e_soil_pa * min(0.85, 0.45 + 0.4 * tan_phi)

    lines = [
        "Begin ModelPartData",
        "    // Generated by orang3D Kratos GeoMechanics Exporter",
        "End ModelPartData",
        "",
    ]

    mat_defs = [
        (1, 25.0e9, 0.20, rho_conc, 1.0e11, 1e-9),
        (2, e_soil_pa, float(min(0.45, max(0.15, soil.poissons_ratio))), rho_soil, 2.2e9 if is_wet else 1.5e8, 1e-4),
        (3, 3.0 * e_soil_pa, float(min(0.45, max(0.15, soil.poissons_ratio))), rho_found, 2.2e9 if is_wet else 5.0e8, 1e-4),
        (4, e_iface_pa, float(min(0.42, max(0.15, soil.poissons_ratio + 0.03))), rho_soil, 2.2e9 if is_wet else 1.5e8, 1e-4),
        (5, e_soil_pa, float(min(0.45, max(0.15, soil.poissons_ratio))), rho_soil, 2.2e9 if is_wet else 1.5e8, 1e-4),
    ]
    for pid, e_pa, nu_v, rho_v, kf_v, perm_v in mat_defs:
        lines.extend([
            f"Begin Properties {pid}",
            f"    YOUNG_MODULUS {e_pa:.6e}",
            f"    POISSON_RATIO {nu_v:.4f}",
            f"    DENSITY {rho_v:.4f}",
            f"    DENSITY_WATER 1000.0",
            f"    DENSITY_SOLID {rho_v / 0.70:.4f}",
            f"    POROSITY 0.30",
            f"    THICKNESS {max(0.5, float(geom.wall_length)):.4f}",
            f"    BIOT_COEFFICIENT 1.0",
            f"    BULK_MODULUS_SOLID 1.0e12",
            f"    BULK_MODULUS_FLUID {kf_v:.6e}",
            f"    PERMEABILITY_XX {perm_v:.4e}",
            f"    PERMEABILITY_YY {perm_v:.4e}",
            f"    CONSTITUTIVE_LAW_NAME GeoLinearElasticPlaneStrain2DLaw",
            "End Properties",
            "",
        ])

    lines.append("Begin Nodes")
    base_nids = []
    top_nids = []
    for ix, xv in enumerate(xs):
        for iy, yv in enumerate(ys):
            nid = _nid(ix, iy)
            lines.append(f"    {nid} {xv:.6f} {yv:.6f} 0.000000")
            if iy == 0:
                base_nids.append(nid)
            if iy == ny - 1 or (not is_wet and yv > 0.01):
                top_nids.append(nid)
    lines.extend(["End Nodes", ""])

    wall_elems, iface_elems, backfill_elems, found_elems = [], [], [], []
    wall_nodes, iface_nodes, backfill_nodes, found_nodes = set(), set(), set(), set()

    lines.append("Begin Elements UPwSmallStrainElement2D4N")
    eid = 1
    for ix in range(nx - 1):
        for iy in range(ny - 1):
            n_conn = [_nid(ix, iy), _nid(ix + 1, iy), _nid(ix + 1, iy + 1), _nid(ix, iy + 1)]
            if iy == 0:
                pid = 3
                found_elems.append(eid)
                found_nodes.update(n_conn)
            elif ix == 0:
                pid = 1
                wall_elems.append(eid)
                wall_nodes.update(n_conn)
            elif ix == 1:
                pid = 4
                iface_elems.append(eid)
                iface_nodes.update(n_conn)
            else:
                pid = 2
                backfill_elems.append(eid)
                backfill_nodes.update(n_conn)
            lines.append(f"    {eid} {pid} {n_conn[0]} {n_conn[1]} {n_conn[2]} {n_conn[3]}")
            eid += 1
    lines.extend(["End Elements", ""])

    lines.append("Begin Conditions UPwLysmerAbsorbingCondition2D2N")
    lys_conds = []
    lys_nodes = set()
    cid = 1
    for iy in range(ny - 1):
        n1, n2 = _nid(nx - 1, iy), _nid(nx - 1, iy + 1)
        lines.append(f"    {cid} 5 {n1} {n2}")
        lys_conds.append(cid)
        lys_nodes.update([n1, n2])
        cid += 1
    lines.append(f"    {cid} 5 {_nid(0, 1)} {_nid(0, 0)}")
    lys_conds.append(cid)
    lys_nodes.update([_nid(0, 1), _nid(0, 0)])
    lines.extend(["End Conditions", ""])

    def _emit_subpart(name: str, nids: Sequence[int], eids: Sequence[int] = (), cids: Sequence[int] = ()):
        lines.append(f"Begin SubModelPart {name}")
        lines.append("    Begin SubModelPartNodes")
        for nid in sorted(set(nids)):
            lines.append(f"        {nid}")
        lines.append("    End SubModelPartNodes")
        if eids:
            lines.append("    Begin SubModelPartElements")
            for eid_v in eids:
                lines.append(f"        {eid_v}")
            lines.append("    End SubModelPartElements")
        if cids:
            lines.append("    Begin SubModelPartConditions")
            for cid_v in cids:
                lines.append(f"        {cid_v}")
            lines.append("    End SubModelPartConditions")
        lines.extend(["End SubModelPart", ""])

    _emit_subpart("WallPart", list(wall_nodes), eids=wall_elems)
    _emit_subpart("InterfacePart", list(iface_nodes), eids=iface_elems)
    _emit_subpart("BackfillPart", list(backfill_nodes), eids=backfill_elems)
    _emit_subpart("FoundationPart", list(found_nodes), eids=found_elems)
    _emit_subpart("LysmerBoundaryPart", list(lys_nodes), cids=lys_conds)
    _emit_subpart("BottomFixedPart", base_nids)
    _emit_subpart("TopDrainagePart", top_nids)

    mdpa_path = out_dir / "RetainingWallSSI.mdpa"
    mdpa_path.write_text("\n".join(lines), encoding="utf-8")

    files_written: Dict[str, str] = {"mdpa": str(mdpa_path)}
    end_time = float(dt) * 100.0
    dt_eff = float(dt)
    if time_arr is not None and accel_arr is not None and len(time_arr) >= 2:
        t_v = np.asarray(time_arr, dtype=np.float64)
        a_v = np.asarray(accel_arr, dtype=np.float64)
        dt_eff = float(t_v[1] - t_v[0])
        end_time = float(t_v[-1])
        gm_path = out_dir / "ground_motion.csv"
        gm_lines = ["Time_s,Acceleration_g"] + [f"{tv:.6e},{av:.6e}" for tv, av in zip(t_v, a_v)]
        gm_path.write_text("\n".join(gm_lines) + "\n", encoding="utf-8")
        files_written["ground_motion"] = str(gm_path)

    proj_params = {
        "problem_data": {
            "problem_name": "RetainingWallSSI",
            "model_part_name": "RetainingWallSSI",
            "domain_size": 2,
            "start_time": 0.0,
            "end_time": end_time,
            "parallel_type": "OpenMP",
            "echo_level": 1,
        },
        "solver_settings": {
            "solver_type": "geomechanics_U_Pw_solver",
            "model_part_name": "RetainingWallSSI",
            "domain_size": 2,
            "model_import_settings": {
                "input_type": "mdpa",
                "input_filename": "RetainingWallSSI",
            },
            "material_import_settings": {
                "materials_filename": "MaterialParameters.json",
            },
            "time_stepping": {"time_step": dt_eff},
            "buffer_size": 2,
            "solution_type": "Dynamic",
            "scheme_type": "Newmark",
            "newmark_beta": 0.25,
            "newmark_gamma": 0.5,
            "newmark_theta": 0.5,
            "strategy_type": "newton_raphson",
            "convergence_criterion": "displacement_criterion",
            "displacement_relative_tolerance": 1.0e-4,
            "displacement_absolute_tolerance": 1.0e-9,
            "max_iteration": 15,
            "linear_solver_settings": {"solver_type": "skyline_lu_factorization"},
            "problem_domain_sub_model_part_list": [
                "WallPart",
                "InterfacePart",
                "BackfillPart",
                "FoundationPart",
            ],
        },
        "processes": {
            "constraints_process_list": [
                {
                    "python_module": "apply_vector_constraint_table_process",
                    "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
                    "Parameters": {
                        "model_part_name": "RetainingWallSSI.BottomFixedPart",
                        "variable_name": "DISPLACEMENT",
                        "active": [True, True, False],
                        "value": [0.0, 0.0, 0.0],
                    },
                },
                {
                    "python_module": "apply_scalar_constraint_table_process",
                    "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
                    "Parameters": {
                        "model_part_name": "RetainingWallSSI.TopDrainagePart",
                        "variable_name": "WATER_PRESSURE",
                        "value": 0.0,
                    },
                },
                {
                    "python_module": "set_absorbing_boundary_parameters_process",
                    "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
                    "Parameters": {
                        "model_part_name": "RetainingWallSSI.LysmerBoundaryPart",
                        "absorbing_factors": [1.0, 1.0],
                        "virtual_thickness": 1.0,
                    },
                },
            ],
            "loads_process_list": [
                {
                    "python_module": "apply_vector_constraint_table_process",
                    "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
                    "Parameters": {
                        "model_part_name": "RetainingWallSSI",
                        "variable_name": "VOLUME_ACCELERATION",
                        "active": [True, True, False],
                        "value": [-float(seismic.horizontal_pga) * 9.81, -9.81, 0.0],
                    },
                }
            ],
        },
        "output_processes": {
            "vtk_output": [
                {
                    "python_module": "vtk_output_process",
                    "kratos_module": "KratosMultiphysics",
                    "Parameters": {
                        "model_part_name": "RetainingWallSSI",
                        "output_path": "vtk_output",
                        "nodal_solution_step_data_variables": [
                            "DISPLACEMENT",
                            "WATER_PRESSURE",
                            "VELOCITY",
                            "ACCELERATION",
                        ],
                        "gauss_point_variables_extrapolated_to_nodes": ["CAUCHY_STRESS_VECTOR"],
                    },
                }
            ]
        },
    }

    params_path = out_dir / "ProjectParameters.json"
    params_path.write_text(json.dumps(proj_params, indent=2), encoding="utf-8")
    files_written["parameters"] = str(params_path)
    return files_written


def export_research_archive(
    output_path: str | Path,
    *,
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    results: AnalysisResults,
    provenance: SolverProvenance | Mapping[str, Any],
    time_arr: Optional[np.ndarray] = None,
    accel_arr: Optional[np.ndarray] = None,
    slip_arr: Optional[np.ndarray] = None,
    pore_arr: Optional[np.ndarray] = None,
    stress_history: Optional[np.ndarray] = None,
    strain_history: Optional[np.ndarray] = None,
    nodal_displacements: Optional[np.ndarray] = None,
    random_seed: Optional[int] = None,
    metadata_extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Exports a reproducible HDF5 time-history tensor archive (`.h5`) paired with a
    companion `metadata.json` containing SolverProvenance, seed, and parameter schemas.
    """
    target = Path(output_path)
    if target.suffix.lower() in (".h5", ".hdf5"):
        h5_path = target
        meta_path = target.with_name(f"{target.stem}_metadata.json")
    else:
        target.mkdir(parents=True, exist_ok=True)
        h5_path = target / "simulation_archive.h5"
        meta_path = target / "metadata.json"

    h5_path.parent.mkdir(parents=True, exist_ok=True)
    prov_dict = provenance.to_dict() if isinstance(provenance, SolverProvenance) else dict(provenance)
    seed_val = random_seed if random_seed is not None else prov_dict.get("random_seed")

    datasets: Dict[str, np.ndarray] = {
        "time_s": np.asarray(time_arr if time_arr is not None else [], dtype=np.float64),
        "acceleration_g": np.asarray(accel_arr if accel_arr is not None else [], dtype=np.float64),
        "displacement_m": np.asarray(slip_arr if slip_arr is not None else [], dtype=np.float64),
        "pore_pressure_kpa": np.asarray(pore_arr if pore_arr is not None else [], dtype=np.float64),
    }
    if stress_history is not None:
        datasets["stress_tensor_kpa"] = np.asarray(stress_history, dtype=np.float64)
    if strain_history is not None:
        datasets["strain_tensor"] = np.asarray(strain_history, dtype=np.float64)
    if nodal_displacements is not None:
        datasets["nodal_displacements_m"] = np.asarray(nodal_displacements, dtype=np.float64)

    with h5py.File(h5_path, "w") as hf:
        hf.attrs["archive_format"] = "orang3d_research_v1"
        hf.attrs["solver_tier"] = str(prov_dict.get("tier", "unknown"))
        if seed_val is not None:
            hf.attrs["random_seed"] = int(seed_val)
        for name, arr in datasets.items():
            if arr.size > 0:
                hf.create_dataset(name, data=arr, compression="gzip")
            else:
                hf.create_dataset(name, data=arr)

    manifest = {
        "archive_format": "orang3d_research_v1",
        "hdf5_file": h5_path.name,
        "random_seed": seed_val,
        "provenance": prov_dict,
        "geometry": geom.__dict__,
        "soil": soil.__dict__,
        "seismic": seismic.__dict__,
        "results": results.__dict__,
        "datasets": {name: list(arr.shape) for name, arr in datasets.items()},
    }
    if metadata_extra:
        manifest["extra"] = dict(metadata_extra)

    meta_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return {"hdf5": str(h5_path), "metadata": str(meta_path)}

