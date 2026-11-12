"""
Cross-Platform 3D Nonlinear Continuum Dynamic SSI Solver powered by OpenSeesPy (Phase 3).

Models retaining wall soil-structure interaction in full 3D using:
  - 8-node hexahedral solid continuum elements (`stdBrick` or coupled u-p `brickUP`)
  - Zero-length wall-soil Coulomb friction & no-tension gapping interface elements
  - Lysmer-Kuhlemeyer viscous absorbing boundary dashpots (`Cp = rho * Vp * A`, `Cs = rho * Vs * A`)
  - Selectable constitutive models (`ElasticIsotropic`, `PressureDependMultiYield02`, `PressureIndependMultiYield`)
  - Multi-directional 1D (X), 2D (X+Y), and 3D (X+Z+Y) `UniformExcitation` seismic loading
  - HDF5 time-history caching and cooperative PySide6 QThread worker execution
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pyvista as pv
from PySide6.QtCore import QThread, Signal

try:
    import openseespy.opensees as ops
    OPENSEES_AVAILABLE = True
except (ImportError, Exception):
    OPENSEES_AVAILABLE = False
    ops = None

from ..models.wall_params import RetainingWallGeometry, SoilProperties, SeismicParams
from ..models.advanced_wall_params import MultiStrutPiledWallModel, WallSystemMode
from ..mesher.continuum_fea_mesher import (
    ContinuumFEAMesh,
    ContinuumInterfacePair,
    build_continuum_fea_mesh,
)
from .solver_registry import SolverProvenance, SolverTier, build_provenance


class ConstitutiveModelType(str, Enum):
    """Selectable 3D continuum soil constitutive models."""

    ELASTIC_ISOTROPIC = "ElasticIsotropic"
    PDMY02 = "PressureDependMultiYield02"
    PIMY = "PressureIndependMultiYield"


@dataclass
class ContinuumFEAResult:
    """Complete 3D continuum SSI dynamic simulation outputs."""

    time: np.ndarray
    displacement_field: np.ndarray            # (n_steps, n_nodes, 3) in m
    backface_coords: np.ndarray               # (n_bf, 3) in m
    backface_normal_stress_kpa: np.ndarray    # (n_steps, n_bf) compression positive kPa
    backface_shear_stress_kpa: np.ndarray     # (n_steps, n_bf) vertical shear kPa
    total_thrust_kn_m: np.ndarray             # (n_steps,) P_ae,3D(t) normalized per m width
    total_thrust_3d_kn: np.ndarray            # (n_steps,) total integrated 3D thrust kN
    thrust_elevation_m: np.ndarray            # (n_steps,) h_res(t) above footing base
    corner_concentration_ratio: float         # Ratio of corner-zone to midspan pressure
    octahedral_shear_strain: np.ndarray       # (n_steps, n_elems)
    excess_pore_pressure_ratio_ru: np.ndarray # (n_steps, n_nodes)
    foundation_bearing_stress_kpa: np.ndarray # (n_steps, n_base)
    max_crest_disp_cm: float
    mesh: Optional[ContinuumFEAMesh] = None
    mesh_grid: Optional[pv.UnstructuredGrid] = None
    provenance: Optional[SolverProvenance] = None
    hdf5_path: Optional[str] = None
    status: str = "CONVERGED"

    def grid_at_timestep(self, step_idx: int = -1) -> pv.UnstructuredGrid:
        """Returns a PyVista UnstructuredGrid populated with scalar/vector fields for step `step_idx`."""
        if self.mesh is None and self.mesh_grid is None:
            raise ValueError("No 3D mesh attached to ContinuumFEAResult.")
        grid = self.mesh.to_pyvista_grid() if self.mesh is not None else self.mesh_grid.copy()
        n_steps = len(self.time)
        idx = (n_steps - 1) if step_idx < 0 else max(0, min(step_idx, n_steps - 1))

        disp_step = self.displacement_field[idx]
        grid.point_data["Displacement_m"] = disp_step.astype(np.float32)

        n_pts = grid.n_points
        wall_stress_pts = np.zeros(n_pts, dtype=np.float32)
        if self.mesh is not None and len(self.mesh.interface_pairs) > 0:
            bf_pairs = [p for p in self.mesh.interface_pairs if p.zone == "backface"]
            stresses = self.backface_normal_stress_kpa[idx]
            for i_pair, pair in enumerate(bf_pairs):
                if i_pair < len(stresses):
                    wall_stress_pts[pair.wall_node_id] = float(stresses[i_pair])
                    wall_stress_pts[pair.soil_node_id] = float(stresses[i_pair])
        grid.point_data["WallNormalStress_kPa"] = wall_stress_pts

        ru_step = self.excess_pore_pressure_ratio_ru[idx]
        if len(ru_step) == n_pts:
            grid.point_data["ExcessPorePressureRatio_ru"] = ru_step.astype(np.float32)
        else:
            grid.point_data["ExcessPorePressureRatio_ru"] = np.zeros(n_pts, dtype=np.float32)

        if self.octahedral_shear_strain.shape[1] == grid.n_cells:
            grid.cell_data["OctahedralShearStrain"] = self.octahedral_shear_strain[idx].astype(np.float32)
        else:
            grid.cell_data["OctahedralShearStrain"] = np.zeros(grid.n_cells, dtype=np.float32)

        return grid


def _require_opensees() -> None:
    if not OPENSEES_AVAILABLE:
        raise RuntimeError(
            "OpenSeesPy is not installed. 3D continuum FEA requires `openseespy>=3.5.0`."
        )


def _compute_wave_properties(soil: SoilProperties) -> Dict[str, float]:
    """Computes mass density, elastic wave speeds Vp/Vs, and unit-area Lysmer coefficients."""
    rho = max(0.5, soil.unit_weight / 9.81)  # Mg/m^3 (= tonnes/m^3, kN/m^3 -> kN*s^2/m^4)
    e_kpa = max(1000.0, float(soil.elastic_modulus))
    nu = min(0.49, max(0.05, float(soil.poissons_ratio)))
    g_kpa = e_kpa / (2.0 * (1.0 + nu))
    m_kpa = (e_kpa * (1.0 - nu)) / ((1.0 + nu) * (1.0 - 2.0 * nu))
    vs = math.sqrt(g_kpa / rho)
    vp = math.sqrt(m_kpa / rho)
    return {
        "rho": rho,
        "G_kPa": g_kpa,
        "K_kPa": e_kpa / (3.0 * (1.0 - 2.0 * nu)),
        "Vs": vs,
        "Vp": vp,
        "cp_unit": rho * vp,  # kN*s/m per m^2
        "cs_unit": rho * vs,
    }


def _compute_octahedral_shear_strain(elem_nodes: np.ndarray, elem_disp: np.ndarray) -> float:
    """Computes element-center octahedral shear strain gamma_oct from 8-node hex displacements."""
    p = elem_nodes  # (8, 3)
    d_xi = 0.125 * ((p[1] + p[2] + p[5] + p[6]) - (p[0] + p[3] + p[4] + p[7]))
    d_eta = 0.125 * ((p[2] + p[3] + p[6] + p[7]) - (p[0] + p[1] + p[4] + p[5]))
    d_zeta = 0.125 * ((p[4] + p[5] + p[6] + p[7]) - (p[0] + p[1] + p[2] + p[3]))
    jac = np.column_stack([d_xi, d_eta, d_zeta])
    det = abs(float(np.linalg.det(jac)))
    if det < 1e-12:
        return 0.0
    u = elem_disp  # (8, 3)
    du_xi = 0.125 * ((u[1] + u[2] + u[5] + u[6]) - (u[0] + u[3] + u[4] + u[7]))
    du_eta = 0.125 * ((u[2] + u[3] + u[6] + u[7]) - (u[0] + u[1] + u[4] + u[5]))
    du_zeta = 0.125 * ((u[4] + u[5] + u[6] + u[7]) - (u[0] + u[1] + u[2] + u[3]))
    grad_u = np.column_stack([du_xi, du_eta, du_zeta]) @ np.linalg.inv(jac).T
    eps = 0.5 * (grad_u + grad_u.T)
    e11, e22, e33 = eps[0, 0], eps[1, 1], eps[2, 2]
    g12, g23, g31 = 2.0 * eps[0, 1], 2.0 * eps[1, 2], 2.0 * eps[2, 0]
    term = (e11 - e22) ** 2 + (e22 - e33) ** 2 + (e33 - e11) ** 2 + 1.5 * (g12 ** 2 + g23 ** 2 + g31 ** 2)
    return float((2.0 / 3.0) * math.sqrt(max(0.0, term)))


def export_continuum_hdf5(filepath: str, result: ContinuumFEAResult) -> None:
    """Archives full 3D continuum time-history arrays to an HDF5 binary dataset."""
    import h5py

    with h5py.File(filepath, "w") as f:
        f.attrs["solver"] = "OpenSeesPy 3D Continuum SSI"
        f.attrs["status"] = result.status
        f.attrs["n_steps"] = int(len(result.time))
        f.attrs["max_crest_disp_cm"] = float(result.max_crest_disp_cm)
        f.attrs["corner_concentration_ratio"] = float(result.corner_concentration_ratio)
        f.create_dataset("time", data=np.asarray(result.time, dtype=np.float64))
        f.create_dataset("displacement_field", data=np.asarray(result.displacement_field, dtype=np.float32))
        f.create_dataset("backface_coords", data=np.asarray(result.backface_coords, dtype=np.float64))
        f.create_dataset("backface_normal_stress_kpa", data=np.asarray(result.backface_normal_stress_kpa, dtype=np.float32))
        f.create_dataset("backface_shear_stress_kpa", data=np.asarray(result.backface_shear_stress_kpa, dtype=np.float32))
        f.create_dataset("total_thrust_kn_m", data=np.asarray(result.total_thrust_kn_m, dtype=np.float64))
        f.create_dataset("total_thrust_3d_kn", data=np.asarray(result.total_thrust_3d_kn, dtype=np.float64))
        f.create_dataset("thrust_elevation_m", data=np.asarray(result.thrust_elevation_m, dtype=np.float64))
        f.create_dataset("octahedral_shear_strain", data=np.asarray(result.octahedral_shear_strain, dtype=np.float32))
        f.create_dataset("excess_pore_pressure_ratio_ru", data=np.asarray(result.excess_pore_pressure_ratio_ru, dtype=np.float32))
        f.create_dataset("foundation_bearing_stress_kpa", data=np.asarray(result.foundation_bearing_stress_kpa, dtype=np.float32))


def load_continuum_hdf5(filepath: str, mesh: Optional[ContinuumFEAMesh] = None) -> ContinuumFEAResult:
    """Reloads cached 3D continuum FEA time histories from an HDF5 archive."""
    import h5py

    with h5py.File(filepath, "r") as f:
        res = ContinuumFEAResult(
            time=np.array(f["time"], dtype=np.float64),
            displacement_field=np.array(f["displacement_field"], dtype=np.float32),
            backface_coords=np.array(f["backface_coords"], dtype=np.float64),
            backface_normal_stress_kpa=np.array(f["backface_normal_stress_kpa"], dtype=np.float32),
            backface_shear_stress_kpa=np.array(f["backface_shear_stress_kpa"], dtype=np.float32),
            total_thrust_kn_m=np.array(f["total_thrust_kn_m"], dtype=np.float64),
            total_thrust_3d_kn=np.array(f["total_thrust_3d_kn"], dtype=np.float64),
            thrust_elevation_m=np.array(f["thrust_elevation_m"], dtype=np.float64),
            corner_concentration_ratio=float(f.attrs["corner_concentration_ratio"]),
            octahedral_shear_strain=np.array(f["octahedral_shear_strain"], dtype=np.float32),
            excess_pore_pressure_ratio_ru=np.array(f["excess_pore_pressure_ratio_ru"], dtype=np.float32),
            foundation_bearing_stress_kpa=np.array(f["foundation_bearing_stress_kpa"], dtype=np.float32),
            max_crest_disp_cm=float(f.attrs["max_crest_disp_cm"]),
            mesh=mesh,
            hdf5_path=filepath,
            status=str(f.attrs.get("status", "CONVERGED")),
        )
    if mesh is not None:
        res.mesh_grid = res.grid_at_timestep(-1)
    return res


class OpenSees3DContinuumSolver:
    """
    True 3D Nonlinear Continuum Dynamic Soil-Structure Interaction Solver using OpenSeesPy.
    Supports both 3-DOF `stdBrick` total-stress models and 4-DOF `brickUP` coupled u-p models.
    """

    def __init__(
        self,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        wall_mode: WallSystemMode = WallSystemMode.CANTILEVER,
        multi_strut_model: Optional[MultiStrutPiledWallModel] = None,
    ):
        _require_opensees()
        self.geom = geom
        self.soil = soil
        self.seismic = seismic
        self.wall_mode = wall_mode
        self.multi_strut_model = multi_strut_model
        self.wave_props = _compute_wave_properties(soil)

    def _register_soil_material(
        self,
        mat_tag: int,
        model_type: ConstitutiveModelType,
        poisson_override: Optional[float] = None,
        cohesion_override: Optional[float] = None,
    ) -> None:
        """Defines selected 3D nDMaterial in the active OpenSees domain."""
        rho = self.wave_props["rho"]
        e_kpa = max(1000.0, float(self.soil.elastic_modulus))
        nu = float(poisson_override if poisson_override is not None else self.soil.poissons_ratio)
        nu = min(0.48, max(0.05, nu))
        g_ref = e_kpa / (2.0 * (1.0 + nu))
        k_ref = e_kpa / (3.0 * (1.0 - 2.0 * nu))
        phi = max(10.0, float(self.soil.friction_angle))
        coh = float(cohesion_override if cohesion_override is not None else max(0.05, self.soil.cohesion))

        if model_type == ConstitutiveModelType.PDMY02:
            # PressureDependMultiYield02 (3D solid)
            ops.nDMaterial(
                "PressureDependMultiYield02",
                mat_tag, 3, rho, g_ref, k_ref,
                phi, 0.1, 80.0, 0.5,
                max(5.0, phi - 5.0),
                0.067, 0.23, 0.06, 0.27,
                20, 0.5, 1.0, 0.0, 0.5, 0.3, coh,
            )
        elif model_type == ConstitutiveModelType.PIMY:
            su = max(5.0, coh if coh > 1.0 else 0.35 * self.soil.unit_weight * self.geom.total_height)
            ops.nDMaterial(
                "PressureIndependMultiYield",
                mat_tag, 3, rho, g_ref, k_ref,
                su, 0.1, phi, 80.0, 0.0, 20,
            )
        else:
            ops.nDMaterial("ElasticIsotropic", mat_tag, e_kpa, nu, rho)

    def _add_interface_and_lysmer_elements(
        self,
        mesh: ContinuumFEAMesh,
        start_ele_tag: int,
        start_dummy_tag: int,
        ndf: int,
        interface_friction_deg: float,
        use_lysmer_faces: Tuple[str, ...] = ("right", "left", "front_z", "back_z"),
    ) -> Tuple[List[Tuple[int, ContinuumInterfacePair]], int, int]:
        """
        Adds zero-length wall-soil Coulomb/ENT interfaces and Lysmer viscous boundary dashpots.
        Returns (backface_link_pairs, next_ele_tag, next_dummy_tag).
        """
        ele_tag = start_ele_tag
        dummy_tag = start_dummy_tag
        bf_links: List[Tuple[int, ContinuumInterfacePair]] = []

        # Interface normal ENT + tangential ElasticPP Coulomb materials per pair
        mu = math.tan(math.radians(max(0.0, interface_friction_deg)))
        h_total = float(mesh.geometry_meta.get("H_wall", self.geom.total_height))
        t_foot = float(mesh.geometry_meta.get("t_footing", self.geom.footing_thickness))
        mat_tag = 2000

        # Switch to 3-DOF builder if continuum uses 4-DOF u-p nodes because OpenSees ZeroLength expects 3-DOF nodes.
        dof3_map: Dict[int, int] = {}
        if ndf == 4:
            ops.model("basic", "-ndm", 3, "-ndf", 3)

        def _ensure_3dof_node(master_tag: int, node_idx: int) -> int:
            nonlocal dummy_tag
            if ndf == 3:
                return master_tag
            if master_tag not in dof3_map:
                slave_tag = dummy_tag
                dummy_tag += 1
                c = mesh.nodes[node_idx]
                ops.node(slave_tag, float(c[0]), float(c[1]), float(c[2]))
                ops.equalDOF(master_tag, slave_tag, 1, 2, 3)
                dof3_map[master_tag] = slave_tag
            return dof3_map[master_tag]

        # Stiff compression-only normal contact material with tiny regularization to prevent zero-pivot
        k_n_unit = max(1e5, self.soil.elastic_modulus * 20.0)  # kPa/m
        k_t_unit = max(1e4, self.soil.elastic_modulus * 5.0)
        for pair in mesh.interface_pairs:
            depth = max(0.25, h_total - pair.coord[1]) if pair.zone == "backface" else h_total
            sigma_n_est = max(2.0, 0.5 * self.soil.unit_weight * depth)
            f_y = max(0.01, sigma_n_est * pair.area_trib * mu)

            mat_ent = mat_tag
            mat_reg = mat_tag + 1
            mat_n = mat_tag + 2
            mat_t = mat_tag + 3
            mat_tag += 4
            ops.uniaxialMaterial("ENT", mat_ent, k_n_unit * pair.area_trib)
            ops.uniaxialMaterial("Elastic", mat_reg, 1.0)
            ops.uniaxialMaterial("Parallel", mat_n, mat_ent, mat_reg)
            if mu <= 1e-6:
                ops.uniaxialMaterial("Elastic", mat_t, 1.0)
            else:
                ops.uniaxialMaterial("ElasticPP", mat_t, k_t_unit * pair.area_trib, f_y / (k_t_unit * pair.area_trib))

            w_tag = _ensure_3dof_node(pair.wall_node_id + 1, pair.wall_node_id)
            s_tag = _ensure_3dof_node(pair.soil_node_id + 1, pair.soil_node_id)
            if pair.zone == "backface":
                ops.element("zeroLength", ele_tag, w_tag, s_tag, "-mat", mat_n, mat_t, mat_t, "-dir", 1, 2, 3)
                bf_links.append((ele_tag, pair))
            else:
                ops.element("zeroLength", ele_tag, s_tag, w_tag, "-mat", mat_t, mat_n, mat_t, "-dir", 1, 2, 3)
                bf_links.append((ele_tag, pair))
            ele_tag += 1

        # Lysmer-Kuhlemeyer viscous dashpots on truncated soil boundaries
        if use_lysmer_faces:
            cp_u = self.wave_props["cp_unit"]
            cs_u = self.wave_props["cs_unit"]
            for lnode in mesh.lysmer_nodes:
                if lnode.face_name not in use_lysmer_faces:
                    continue
                n_tag = _ensure_3dof_node(lnode.node_id + 1, lnode.node_id)
                coord = mesh.nodes[lnode.node_id]
                d_tag = dummy_tag
                dummy_tag += 1
                ops.node(d_tag, float(coord[0]), float(coord[1]), float(coord[2]))
                ops.fix(d_tag, 1, 1, 1)

                # Assign Cp along boundary outward normal direction, Cs along orthogonal tangent directions
                nx, ny, nz = lnode.normal
                cx = cp_u * lnode.area_trib if abs(nx) > 0.5 else cs_u * lnode.area_trib
                cy = cp_u * lnode.area_trib if abs(ny) > 0.5 else cs_u * lnode.area_trib
                cz = cp_u * lnode.area_trib if abs(nz) > 0.5 else cs_u * lnode.area_trib

                mx, my, mz = mat_tag, mat_tag + 1, mat_tag + 2
                mat_tag += 3
                ops.uniaxialMaterial("Viscous", mx, cx, 1.0)
                ops.uniaxialMaterial("Viscous", my, cy, 1.0)
                ops.uniaxialMaterial("Viscous", mz, cz, 1.0)
                ops.element("zeroLength", ele_tag, n_tag, d_tag, "-mat", mx, my, mz, "-dir", 1, 2, 3)
                ele_tag += 1

        if ndf == 4:
            ops.model("basic", "-ndm", 3, "-ndf", 4)

        return bf_links, ele_tag, dummy_tag

    def run_geostatic_patch_test(
        self,
        nx: int = 3,
        ny: int = 4,
        nz: int = 2,
        use_k0_poisson: bool = True,
    ) -> Dict[str, Any]:
        """
        Patch Test & Geostatic K0 Equilibrium Verification:
        Gravity turn-on on a conformal 3D brick soil column with lateral rollers and fixed base.
        Returns vertical stress error, horizontal K0 stress error, and max lateral drift (m).
        """
        ops.wipe()
        ops.model("basic", "-ndm", 3, "-ndf", 3)

        k0_target = max(0.25, 1.0 - math.sin(math.radians(self.soil.friction_angle)))
        nu_eff = (k0_target / (1.0 + k0_target)) if use_k0_poisson else float(self.soil.poissons_ratio)
        k0_expected = nu_eff / (1.0 - nu_eff)

        self._register_soil_material(1, ConstitutiveModelType.ELASTIC_ISOTROPIC, poisson_override=nu_eff)

        lx, ly, lz = 6.0, float(self.geom.total_height), max(2.0, float(self.geom.wall_length))
        xs = np.linspace(0.0, lx, nx + 1)
        ys = np.linspace(0.0, ly, ny + 1)
        zs = np.linspace(0.0, lz, nz + 1)

        def nid(ix: int, iy: int, iz: int) -> int:
            return ix * (ny + 1) * (nz + 1) + iy * (nz + 1) + iz + 1

        for ix, x in enumerate(xs):
            for iy, y in enumerate(ys):
                for iz, z in enumerate(zs):
                    tag = nid(ix, iy, iz)
                    ops.node(tag, float(x), float(y), float(z))
                    fx = 1 if (ix == 0 or ix == nx or iy == 0) else 0
                    fy = 1 if iy == 0 else 0
                    fz = 1
                    ops.fix(tag, fx, fy, fz)

        eid = 1
        elem_centers_y: List[float] = []
        for ix in range(nx):
            for iy in range(ny):
                yc = 0.5 * (ys[iy] + ys[iy + 1])
                for iz in range(nz):
                    n1 = nid(ix, iy, iz)
                    n2 = nid(ix + 1, iy, iz)
                    n3 = nid(ix + 1, iy + 1, iz)
                    n4 = nid(ix, iy + 1, iz)
                    n5 = nid(ix, iy, iz + 1)
                    n6 = nid(ix + 1, iy, iz + 1)
                    n7 = nid(ix + 1, iy + 1, iz + 1)
                    n8 = nid(ix, iy + 1, iz + 1)
                    ops.element("stdBrick", eid, n1, n2, n3, n4, n5, n6, n7, n8, 1, 0.0, -self.soil.unit_weight, 0.0)
                    elem_centers_y.append(float(yc))
                    eid += 1

        ops.timeSeries("Constant", 1)
        ops.pattern("Plain", 1, 1)
        ops.constraints("Plain")
        ops.numberer("RCM")
        ops.system("BandGeneral")
        ops.integrator("LoadControl", 1.0)
        ops.algorithm("Linear")
        ops.analysis("Static")
        ok = ops.analyze(1)

        sigma_yy_errs = []
        sigma_xx_errs = []
        max_lat_drift = 0.0
        for e in range(1, eid):
            st = np.asarray(ops.eleResponse(e, "stresses"), dtype=np.float64).reshape(-1, 6)
            s_xx = float(np.mean(st[:, 0]))
            s_yy = float(np.mean(st[:, 1]))
            depth = ly - elem_centers_y[e - 1]
            expected_v = -self.soil.unit_weight * depth
            expected_h = k0_expected * expected_v
            sigma_yy_errs.append(abs(s_yy - expected_v) / max(1e-6, abs(expected_v)))
            sigma_xx_errs.append(abs(s_xx - expected_h) / max(1e-6, abs(expected_h)))

        for tag in range(1, (nx + 1) * (ny + 1) * (nz + 1) + 1):
            u = ops.nodeDisp(tag)
            max_lat_drift = max(max_lat_drift, abs(float(u[0])), abs(float(u[2])))

        return {
            "converged": ok == 0,
            "k0_expected": float(k0_expected),
            "max_sigma_yy_rel_error": float(max(sigma_yy_errs)),
            "max_sigma_xx_rel_error": float(max(sigma_xx_errs)),
            "max_lateral_drift_m": float(max_lat_drift),
        }

    def run_static_active_transition(
        self,
        delta_x_m: float = -0.0020,
        interface_friction_deg: float = 0.0,
        nx: int = 4,
        ny: int = 4,
        nz: int = 2,
    ) -> Dict[str, Any]:
        """
        Static Active Transition Benchmark:
        Applies geostatic K0 gravity (PDMY02 stage 0 -> stage 1) behind a retaining wall
        interface (smooth delta=0 or rough delta>0), then translates the wall outward
        (`delta_x_m < 0`) to trigger active earth pressure drop.
        """
        ops.wipe()
        ops.model("basic", "-ndm", 3, "-ndf", 3)
        self._register_soil_material(1, ConstitutiveModelType.PDMY02, cohesion_override=0.05)

        h_col = min(5.0, float(self.geom.total_height))
        l_back = 2.0 * h_col
        l_z = 2.0
        xs = np.linspace(0.0, l_back, nx + 1)
        ys = np.linspace(0.0, h_col, ny + 1)
        zs = np.linspace(0.0, l_z, nz + 1)
        dy_vals, dz_vals = np.diff(ys), np.diff(zs)

        def nid(ix: int, iy: int, iz: int) -> int:
            return ix * (ny + 1) * (nz + 1) + iy * (nz + 1) + iz + 1

        # Create soil nodes (x=0 interface soil nodes are free in X/Y and linked to wall actuator)
        for ix, x in enumerate(xs):
            for iy, y in enumerate(ys):
                for iz, z in enumerate(zs):
                    tag = nid(ix, iy, iz)
                    ops.node(tag, float(x), float(y), float(z))
                    fx = 1 if (ix == nx or (ix == 0 and iy == 0)) else 0
                    fy = 1 if iy == 0 else 0
                    fz = 1
                    ops.fix(tag, fx, fy, fz)

        eid = 1
        for ix in range(nx):
            for iy in range(ny):
                for iz in range(nz):
                    n1 = nid(ix, iy, iz)
                    n2 = nid(ix + 1, iy, iz)
                    n3 = nid(ix + 1, iy + 1, iz)
                    n4 = nid(ix, iy + 1, iz)
                    n5 = nid(ix, iy, iz + 1)
                    n6 = nid(ix + 1, iy, iz + 1)
                    n7 = nid(ix + 1, iy + 1, iz + 1)
                    n8 = nid(ix, iy + 1, iz + 1)
                    ops.element("stdBrick", eid, n1, n2, n3, n4, n5, n6, n7, n8, 1, 0.0, -self.soil.unit_weight, 0.0)
                    eid += 1

        # Wall actuator + Coulomb interface at x = 0 for iy >= 1
        k_act = 1e8
        ops.uniaxialMaterial("Elastic", 2, k_act)
        ops.uniaxialMaterial("ENT", 3, 1e6)
        ops.uniaxialMaterial("Elastic", 4, 1.0)
        ops.uniaxialMaterial("Parallel", 5, 3, 4)
        mu = math.tan(math.radians(max(0.0, interface_friction_deg)))
        mat_id = 10
        wall_links: List[int] = []
        act_nodes: List[int] = []

        for iy in range(1, ny + 1):
            dy_t = 0.5 * (dy_vals[iy - 1] + (dy_vals[iy] if iy < ny else 0.0))
            depth = h_col - ys[iy]
            sigma_est = max(2.0, 0.45 * self.soil.unit_weight * depth)
            for iz in range(nz + 1):
                dz_t = 0.5 * ((dz_vals[iz - 1] if iz > 0 else 0.0) + (dz_vals[iz] if iz < nz else 0.0))
                area = max(1e-3, float(dy_t * dz_t))
                t = nid(0, iy, iz)
                d_free = 10000 + t
                d_fix = 20000 + t
                ops.node(d_free, 0.0, float(ys[iy]), float(zs[iz]))
                ops.fix(d_free, 0, 1, 1)  # Controlled in X via actuator spring force
                ops.node(d_fix, 0.0, float(ys[iy]), float(zs[iz]))
                ops.fix(d_fix, 1, 1, 1)
                act_nodes.append(d_free)

                ops.element("zeroLength", eid, d_fix, d_free, "-mat", 2, "-dir", 1)
                eid += 1

                if mu <= 1e-6:
                    ops.uniaxialMaterial("Elastic", mat_id, 1.0)
                else:
                    fy_s = max(0.05, sigma_est * area * mu)
                    kt_s = 1e4 * area
                    ops.uniaxialMaterial("ElasticPP", mat_id, kt_s, fy_s / kt_s)
                ops.element("zeroLength", eid, d_free, t, "-mat", 5, mat_id, "-dir", 1, 2)
                wall_links.append(eid)
                mat_id += 1
                eid += 1

        # Stage 0: Elastic K0 gravity
        ops.updateMaterialStage("-material", 1, "-stage", 0)
        ops.timeSeries("Constant", 1)
        ops.pattern("Plain", 1, 1)
        ops.constraints("Transformation")
        ops.test("NormDispIncr", 1e-4, 25, 0)
        ops.algorithm("Newton")
        ops.numberer("RCM")
        ops.system("BandGeneral")
        ops.integrator("LoadControl", 1.0)
        ops.analysis("Static")
        ok0 = ops.analyze(1)
        p_k0 = sum(max(0.0, float(ops.eleResponse(e, "force")[0])) for e in wall_links) / l_z

        # Stage 1: Plastic gravity settle, then freeze load time before outward push
        ops.updateMaterialStage("-material", 1, "-stage", 1)
        ok1 = ops.analyze(1)
        ops.loadConst("-time", 0.0)

        ops.timeSeries("Linear", 2)
        ops.pattern("Plain", 2, 2)
        for d_free in act_nodes:
            ops.load(d_free, k_act * delta_x_m, 0.0, 0.0)
        ops.integrator("LoadControl", 0.1)
        ops.algorithm("KrylovNewton")
        ok2 = 0
        for _ in range(10):
            step_ok = ops.analyze(1)
            if step_ok != 0:
                ok2 = step_ok
                break

        p_active = sum(max(0.0, float(ops.eleResponse(e, "force")[0])) for e in wall_links) / l_z
        # Compare interior soil element horizontal/vertical stress ratio near wall
        s_elem = np.asarray(ops.eleResponse(1, "stresses"), dtype=np.float64).reshape(-1, 6)
        ratio_sxx_syy = abs(float(np.mean(s_elem[:, 0]))) / max(1e-6, abs(float(np.mean(s_elem[:, 1]))))

        return {
            "converged": (ok0 == 0 and ok1 == 0 and ok2 == 0),
            "k0_thrust_kn_m": float(p_k0),
            "active_thrust_kn_m": float(p_active),
            "thrust_reduction_factor": float(p_active / max(1e-6, p_k0)),
            "soil_k_ratio": float(ratio_sxx_syy),
            "interface_friction_deg": float(interface_friction_deg),
        }

    def run_lysmer_absorbing_test(
        self,
        use_lysmer: bool = True,
        bar_length_m: float = 12.0,
        n_steps: int = 180,
        dt: float = 0.002,
    ) -> Dict[str, Any]:
        """
        Lysmer-Kuhlemeyer Viscous Absorbing Boundary Test:
        Sends an outgoing P/S wave impulse along a 3D soil prism of length `bar_length_m`
        truncated with either Lysmer dashpots (`Cp = rho*Vp*A`, `Cs = rho*Vs*A`) or a rigid
        fixed boundary, and computes late-time reflected residual energy ratio (< 0.05 expected).
        """
        ops.wipe()
        ops.model("basic", "-ndm", 3, "-ndf", 3)
        self._register_soil_material(1, ConstitutiveModelType.ELASTIC_ISOTROPIC, poisson_override=0.25)

        nx = 12
        xs = np.linspace(0.0, bar_length_m, nx + 1)
        ys = np.array([0.0, 1.0])
        zs = np.array([0.0, 1.0])

        def nid(ix: int, iy: int, iz: int) -> int:
            return ix * 4 + iy * 2 + iz + 1

        for ix, x in enumerate(xs):
            for iy, y in enumerate(ys):
                for iz, z in enumerate(zs):
                    tag = nid(ix, iy, iz)
                    ops.node(tag, float(x), float(y), float(z))
                    ops.mass(tag, 0.25 * self.wave_props["rho"] * (bar_length_m / nx), 0.25 * self.wave_props["rho"] * (bar_length_m / nx), 0.25 * self.wave_props["rho"] * (bar_length_m / nx))
                    if ix == nx and not use_lysmer:
                        ops.fix(tag, 1, 1, 1)
                    else:
                        ops.fix(tag, 0, 1, 1)

        eid = 1
        for ix in range(nx):
            n1 = nid(ix, 0, 0); n2 = nid(ix + 1, 0, 0); n3 = nid(ix + 1, 1, 0); n4 = nid(ix, 1, 0)
            n5 = nid(ix, 0, 1); n6 = nid(ix + 1, 0, 1); n7 = nid(ix + 1, 1, 1); n8 = nid(ix, 1, 1)
            ops.element("stdBrick", eid, n1, n2, n3, n4, n5, n6, n7, n8, 1)
            eid += 1

        if use_lysmer:
            area_face = 1.0
            cp_node = 0.25 * self.wave_props["cp_unit"] * area_face
            cs_node = 0.25 * self.wave_props["cs_unit"] * area_face
            ops.uniaxialMaterial("Viscous", 10, cp_node, 1.0)
            ops.uniaxialMaterial("Viscous", 11, cs_node, 1.0)
            d_base = 1000
            for ix_end in (0, nx):
                for iy in (0, 1):
                    for iz in (0, 1):
                        n_end = nid(ix_end, iy, iz)
                        d_tag = d_base
                        d_base += 1
                        ops.node(d_tag, float(xs[ix_end]), float(ys[iy]), float(zs[iz]))
                        ops.fix(d_tag, 1, 1, 1)
                        ops.element("zeroLength", eid, n_end, d_tag, "-mat", 10, 11, 11, "-dir", 1, 2, 3)
                        eid += 1

        # Half-sine compression impulse at source face x = 0 (first 25 steps)
        pulse_steps = 25
        pulse_vals = [
            25.0 * math.sin(math.pi * k / pulse_steps) if k <= pulse_steps else 0.0
            for k in range(n_steps + 5)
        ]
        ops.timeSeries("Path", 1, "-dt", dt, "-values", *pulse_vals)
        ops.pattern("Plain", 1, 1)
        for iy in (0, 1):
            for iz in (0, 1):
                ops.load(nid(0, iy, iz), 1.0, 0.0, 0.0)

        ops.constraints("Plain")
        ops.numberer("RCM")
        ops.system("BandGeneral")
        ops.test("NormDispIncr", 1e-6, 15)
        ops.algorithm("Linear")
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")

        ke_hist = []
        all_nodes = [nid(ix, iy, iz) for ix in range(nx + 1) for iy in (0, 1) for iz in (0, 1)]
        for _ in range(n_steps):
            ops.analyze(1, dt)
            ke = sum(float(ops.nodeVel(t, 1)) ** 2 for t in all_nodes)
            ke_hist.append(ke)

        peak_ke = max(1e-12, max(ke_hist))
        late_ke = float(np.mean(ke_hist[int(0.8 * n_steps):]))
        return {
            "use_lysmer": use_lysmer,
            "peak_energy_proxy": float(peak_ke),
            "late_energy_proxy": late_ke,
            "reflected_energy_ratio": float(late_ke / peak_ke),
        }

    def run_3d_corner_effect_study(
        self,
        short_length_m: float = 3.5,
        long_length_m: float = 18.0,
    ) -> Dict[str, Any]:
        """
        3D Corner / Finite-Length Effect Test:
        Compares mid-height midspan earth pressure under 3D seismic lateral loading
        between a short wall bounded by stiff corner returns and an unrestrained long wall.
        """
        t_arr = np.linspace(0.0, 0.12, 7)
        a_x = np.array([0.0, 0.05, 0.12, 0.18, 0.15, 0.08, 0.0])

        geom_short = RetainingWallGeometry(
            stem_height=self.geom.stem_height,
            stem_thickness_base=self.geom.stem_thickness_base,
            stem_thickness_top=self.geom.stem_thickness_top,
            toe_length=self.geom.toe_length,
            heel_length=self.geom.heel_length,
            footing_thickness=self.geom.footing_thickness,
            wall_length=short_length_m,
        )
        solver_short = OpenSees3DContinuumSolver(geom_short, self.soil, self.seismic)
        res_short = solver_short.run_dynamic_seismic(
            t_arr, a_x, corner_restraint=True, z_buffer_m=0.0, nx_backfill=4, ny_wall=4, nz_wall=4
        )

        geom_long = RetainingWallGeometry(
            stem_height=self.geom.stem_height,
            stem_thickness_base=self.geom.stem_thickness_base,
            stem_thickness_top=self.geom.stem_thickness_top,
            toe_length=self.geom.toe_length,
            heel_length=self.geom.heel_length,
            footing_thickness=self.geom.footing_thickness,
            wall_length=long_length_m,
        )
        solver_long = OpenSees3DContinuumSolver(geom_long, self.soil, self.seismic)
        res_long = solver_long.run_dynamic_seismic(
            t_arr, a_x, corner_restraint=False, z_buffer_m=0.0, nx_backfill=4, ny_wall=4, nz_wall=4
        )

        mid_short = self._midspan_midheight_pressure(res_short)
        mid_long = self._midspan_midheight_pressure(res_long)
        return {
            "short_midspan_pressure_kpa": mid_short,
            "long_midspan_pressure_kpa": mid_long,
            "corner_reduction_ratio": float(mid_short / max(1e-6, mid_long)),
            "short_corner_concentration": float(res_short.corner_concentration_ratio),
        }

    @staticmethod
    def _midspan_midheight_pressure(res: ContinuumFEAResult) -> float:
        """Extracts peak mid-height midspan backface normal stress (kPa)."""
        if res.backface_coords.shape[0] == 0:
            return 0.0
        coords = res.backface_coords
        y_mid = 0.5 * (coords[:, 1].min() + coords[:, 1].max())
        z_mid = 0.5 * (coords[:, 2].min() + coords[:, 2].max())
        dist = np.hypot(coords[:, 1] - y_mid, coords[:, 2] - z_mid)
        idx = int(np.argmin(dist))
        return float(np.max(res.backface_normal_stress_kpa[:, idx]))

    def run_dynamic_seismic(
        self,
        time_arr: np.ndarray,
        accel_x_g: np.ndarray,
        accel_y_g: Optional[np.ndarray] = None,
        accel_z_g: Optional[np.ndarray] = None,
        constitutive_model: ConstitutiveModelType = ConstitutiveModelType.ELASTIC_ISOTROPIC,
        use_up: bool = False,
        use_lysmer: bool = True,
        corner_restraint: bool = False,
        z_buffer_m: float = 1.0,
        nx_backfill: int = 5,
        ny_wall: int = 4,
        nz_wall: int = 4,
        ny_found: int = 2,
        hdf5_path: Optional[str] = None,
        progress_cb: Optional[Callable[[int, float, float, float], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ContinuumFEAResult:
        """
        Executes full 3D dynamic soil-structure interaction FEA under 1D, 2D (X+Y),
        or 3D (X+Z+Y) seismic excitation.
        """
        t_start = time.perf_counter()
        time_arr = np.asarray(time_arr, dtype=np.float64)
        ax_g = np.asarray(accel_x_g, dtype=np.float64)
        n_steps = len(time_arr)
        dt = float(time_arr[1] - time_arr[0]) if n_steps > 1 else 0.01

        mesh = build_continuum_fea_mesh(
            self.geom,
            soil=self.soil,
            wall_mode=self.wall_mode,
            multi_strut_model=self.multi_strut_model,
            z_buffer_m=z_buffer_m,
            nx_backfill=nx_backfill,
            ny_wall=ny_wall,
            nz_wall=nz_wall,
            ny_found=ny_found,
            nx_toe_pad=2,
            separate_interfaces=True,
        )

        ndf = 4 if use_up else 3
        ops.wipe()
        ops.model("basic", "-ndm", 3, "-ndf", ndf)

        # Materials: Tag 1 = Concrete Wall, Tag 2 = Backfill Soil, Tag 3 = Foundation Subgrade (stiffer bearing layer)
        rho_conc = 2.45
        ops.nDMaterial("ElasticIsotropic", 1, 25.0e6, 0.20, rho_conc)
        effective_model = constitutive_model
        if use_up and constitutive_model == ConstitutiveModelType.ELASTIC_ISOTROPIC:
            effective_model = ConstitutiveModelType.ELASTIC_ISOTROPIC
        self._register_soil_material(2, effective_model)
        e_found = max(4000.0, 4.0 * float(self.soil.elastic_modulus))
        ops.nDMaterial("ElasticIsotropic", 3, e_found, min(0.45, max(0.15, self.soil.poissons_ratio)), self.wave_props["rho"])

        # Add nodes and boundary conditions
        fixed_set = set(mesh.fixed_base_nodes)
        lat_x_set = set(mesh.lateral_x_nodes)
        lat_z_set = set(mesh.lateral_z_nodes)
        top_set = set(mesh.top_surface_nodes)
        l_wall = float(mesh.geometry_meta["L_wall"])
        z_tol = 1e-4
        corner_fixed_set = set()

        for nid in range(mesh.n_nodes):
            x, y, z = mesh.nodes[nid]
            ops.node(nid + 1, float(x), float(y), float(z))
            if nid in fixed_set:
                corner_fixed_set.add(nid)
                if ndf == 4:
                    ops.fix(nid + 1, 1, 1, 1, 0)
                else:
                    ops.fix(nid + 1, 1, 1, 1)
            elif corner_restraint and mesh.node_domain_ids[nid] == 1 and (abs(z) < z_tol or abs(z - l_wall) < z_tol):
                # Rigid end-return corner walls / stiff abutment piers at z=0 and z=L_wall
                corner_fixed_set.add(nid)
                if ndf == 4:
                    ops.fix(nid + 1, 1, 1, 1, 0)
                else:
                    ops.fix(nid + 1, 1, 1, 1)
            elif not use_lysmer and nid in lat_z_set:
                corner_fixed_set.add(nid)
                if ndf == 4:
                    ops.fix(nid + 1, 0, 0, 1, 1 if nid in top_set else 0)
                else:
                    ops.fix(nid + 1, 0, 0, 1)
            elif not use_lysmer and nid in lat_x_set:
                corner_fixed_set.add(nid)
                if ndf == 4:
                    ops.fix(nid + 1, 1, 0, 1, 1 if nid in top_set else 0)
                else:
                    ops.fix(nid + 1, 1, 0, 1)
            elif ndf == 4 and (nid in top_set or (self.geom.total_height - y) <= self.seismic.water_table_depth):
                ops.fix(nid + 1, 0, 0, 0, 1)

        # Create 8-node hexahedral continuum elements
        bulk_fluid = 2.2e6  # kPa
        perm = max(1e-6, min(1e-2, float(getattr(self.soil, "permeability", 1e-4))))
        for e_idx in range(mesh.n_elements):
            n_tags = [int(i) + 1 for i in mesh.elements[e_idx]]
            dom = int(mesh.element_domain_ids[e_idx])
            mat_tag = 1 if dom == 1 else (3 if dom == 3 else 2)
            unit_wt = self.geom.concrete_unit_weight if dom == 1 else (
                self.soil.foundation_unit_weight if dom == 3 else self.soil.unit_weight
            )
            if use_up:
                ops.element(
                    "brickUP", e_idx + 1, *n_tags, mat_tag,
                    bulk_fluid if dom != 1 else 1e7,
                    1.0,
                    perm if dom != 1 else 1e-10,
                    perm if dom != 1 else 1e-10,
                    perm if dom != 1 else 1e-10,
                    0.0, -unit_wt / 9.81, 0.0,
                )
            else:
                ops.element("stdBrick", e_idx + 1, *n_tags, mat_tag, 0.0, -unit_wt, 0.0)

        # Insert wall-soil zero-length interface and Lysmer boundary dashpots
        lys_faces = ("right", "left", "front_z", "back_z") if use_lysmer else ()
        all_links, next_ele_tag, _ = self._add_interface_and_lysmer_elements(
            mesh,
            start_ele_tag=mesh.n_elements + 1,
            start_dummy_tag=mesh.n_nodes + 10000,
            ndf=ndf,
            interface_friction_deg=min(self.soil.friction_angle, 0.67 * self.soil.friction_angle),
            use_lysmer_faces=lys_faces,
        )
        bf_links = [(e_t, pr) for (e_t, pr) in all_links if pr.zone == "backface"]
        base_links = [(e_t, pr) for (e_t, pr) in all_links if pr.zone == "base"]

        # Gravity initialization step with temporary lateral rollers if Lysmer faces are free dynamically
        if effective_model != ConstitutiveModelType.ELASTIC_ISOTROPIC:
            ops.updateMaterialStage("-material", 2, "-stage", 0)

        ops.timeSeries("Constant", 1)
        ops.pattern("Plain", 1, 1)
        temp_sp_nodes: List[Tuple[int, int]] = []
        if use_lysmer:
            ops.pattern("Plain", 99, 1)
            for nid in sorted(lat_x_set - corner_fixed_set):
                ops.sp(nid + 1, 1, 0.0)
                temp_sp_nodes.append((nid + 1, 1))
            for nid in sorted(lat_z_set - corner_fixed_set):
                ops.sp(nid + 1, 3, 0.0)
                temp_sp_nodes.append((nid + 1, 3))

        ops.constraints("Penalty", 1e12, 1e12) if (use_up or use_lysmer) else ops.constraints("Transformation")
        ops.numberer("RCM")
        ops.system("BandGeneral")
        ops.test("NormDispIncr", 5e-4, 30)
        ops.algorithm("KrylovNewton")
        if use_up:
            ops.integrator("Newmark", 1.5, 1.0)
            ops.analysis("Transient")
            ops.analyze(2, 5.0)
        else:
            ops.integrator("LoadControl", 1.0)
            ops.analysis("Static")
            ops.analyze(1)

        if effective_model != ConstitutiveModelType.ELASTIC_ISOTROPIC:
            ops.updateMaterialStage("-material", 2, "-stage", 1)
            if not use_up:
                ops.analyze(1)

        if use_lysmer and temp_sp_nodes:
            ops.reactions()
            ops.pattern("Plain", 98, 1)
            seen_loads: Dict[int, List[float]] = {}
            for n_tag, dof in temp_sp_nodes:
                if n_tag not in seen_loads:
                    seen_loads[n_tag] = [0.0] * ndf
                seen_loads[n_tag][dof - 1] += float(ops.nodeReaction(n_tag, dof))
            for n_tag, fvec in seen_loads.items():
                ops.load(n_tag, *fvec)
            ops.remove("loadPattern", 99)

        ops.loadConst("-time", 0.0)

        # Configure dynamic UniformExcitation loading (1D, 2D X+Y, or 3D X+Z+Y)
        ops.wipeAnalysis()
        ops.timeSeries("Path", 10, "-dt", dt, "-values", *(-ax_g * 9.81).tolist())
        ops.pattern("UniformExcitation", 10, 1, "-accel", 10)
        if accel_y_g is not None:
            ay_g = np.asarray(accel_y_g, dtype=np.float64)
            ops.timeSeries("Path", 11, "-dt", dt, "-values", *(-ay_g * 9.81).tolist())
            ops.pattern("UniformExcitation", 11, 2, "-accel", 11)
        if accel_z_g is not None:
            az_g = np.asarray(accel_z_g, dtype=np.float64)
            ops.timeSeries("Path", 12, "-dt", dt, "-values", *(-az_g * 9.81).tolist())
            ops.pattern("UniformExcitation", 12, 3, "-accel", 12)

        # Rayleigh damping ~3% across 1-10 Hz
        zeta = 0.03
        w1, w2 = 2.0 * math.pi * 1.5, 2.0 * math.pi * 10.0
        alpha_m = (2.0 * zeta * w1 * w2) / (w1 + w2)
        beta_k = (2.0 * zeta) / (w1 + w2)
        ops.rayleigh(alpha_m, 0.0, 0.0, beta_k)

        ops.constraints("Penalty", 1e12, 1e12) if use_up else ops.constraints("Transformation")
        ops.numberer("RCM")
        ops.system("BandGeneral")
        # 4-DOF u-p models include pore pressures (kPa) alongside displacements (m),
        # so NormDispIncr requires a pore-pressure-consistent tolerance vs 3-DOF stdBrick.
        primary_tol = 2e-3 if use_up else 5e-4
        fallback_tol = 1e-2 if use_up else 2e-3
        ops.test("NormDispIncr", primary_tol, 25)
        ops.algorithm("KrylovNewton")
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")

        # Time-history recording arrays
        n_bf = len(bf_links)
        n_base = len(base_links)
        disp_hist = np.zeros((n_steps, mesh.n_nodes, 3), dtype=np.float32)
        bf_norm_hist = np.zeros((n_steps, max(1, n_bf)), dtype=np.float32)
        bf_shear_hist = np.zeros((n_steps, max(1, n_bf)), dtype=np.float32)
        base_stress_hist = np.zeros((n_steps, max(1, n_base)), dtype=np.float32)
        oct_strain_hist = np.zeros((n_steps, mesh.n_elements), dtype=np.float32)
        ru_hist = np.zeros((n_steps, mesh.n_nodes), dtype=np.float32)
        thrust_3d_hist = np.zeros(n_steps, dtype=np.float64)
        thrust_knm_hist = np.zeros(n_steps, dtype=np.float64)
        elev_hist = np.zeros(n_steps, dtype=np.float64)

        bf_coords = np.asarray([pr.coord for (_, pr) in bf_links], dtype=np.float64) if n_bf > 0 else np.zeros((1, 3))
        bf_areas = np.asarray([pr.area_trib for (_, pr) in bf_links], dtype=np.float64) if n_bf > 0 else np.ones(1)

        completed = 0
        h_total = float(mesh.geometry_meta["H_wall"])
        status = "CONVERGED"

        for step in range(n_steps):
            if cancel_check is not None and cancel_check():
                status = "CANCELLED"
                break

            ok = ops.analyze(1, dt)
            if ok != 0:
                ops.algorithm("SecantNewton")
                ok = ops.analyze(1, dt)
                if ok != 0:
                    ops.test("NormDispIncr", fallback_tol, 35)
                    ops.algorithm("KrylovNewton")
                    ok = ops.analyze(1, dt)
                    ops.test("NormDispIncr", primary_tol, 25)
                ops.algorithm("KrylovNewton")
                if ok != 0:
                    status = "PARTIAL_CONVERGENCE"

            # Record 3D displacements and pore pressures
            u_step = np.zeros((mesh.n_nodes, 3), dtype=np.float64)
            ru_step = np.zeros(mesh.n_nodes, dtype=np.float64)
            for nid in range(mesh.n_nodes):
                u = ops.nodeDisp(nid + 1)
                u_step[nid, 0] = float(u[0])
                u_step[nid, 1] = float(u[1])
                u_step[nid, 2] = float(u[2])
                if ndf == 4 and len(u) >= 4:
                    depth_wt = max(0.5, h_total - float(mesh.nodes[nid, 1]))
                    sigma_v_eff = max(5.0, (self.soil.unit_weight - 9.81) * depth_wt)
                    ru_step[nid] = float(np.clip(abs(float(u[3])) / sigma_v_eff, 0.0, 1.0))

            disp_hist[step] = u_step.astype(np.float32)
            if not use_up and self.seismic.pore_pressure_ratio_ru > 0.0:
                ru_step[:] = float(self.seismic.pore_pressure_ratio_ru)
            ru_hist[step] = ru_step.astype(np.float32)

            # Record wall backface normal/shear stresses and integrated 3D thrust
            if n_bf > 0:
                for i_l, (e_tag, pr) in enumerate(bf_links):
                    f = ops.eleResponse(e_tag, "force")
                    # Axial compression on iNode (wall) is positive when soil pushes in -X
                    comp_force = max(0.0, float(f[0]))
                    shear_force = float(f[1]) if len(f) > 1 else 0.0
                    bf_norm_hist[step, i_l] = comp_force / pr.area_trib
                    bf_shear_hist[step, i_l] = shear_force / pr.area_trib

                forces_step = bf_norm_hist[step].astype(np.float64) * bf_areas
                p_tot = float(np.sum(forces_step))
                thrust_3d_hist[step] = p_tot
                thrust_knm_hist[step] = p_tot / max(0.5, l_wall)
                elev_hist[step] = (
                    float(np.sum(forces_step * bf_coords[:, 1]) / p_tot)
                    if p_tot > 1e-6 else (h_total / 3.0)
                )

            if n_base > 0:
                for i_b, (e_tag, pr) in enumerate(base_links):
                    fb = ops.eleResponse(e_tag, "force")
                    comp_b = max(0.0, float(fb[1])) if len(fb) > 1 else max(0.0, float(fb[0]))
                    base_stress_hist[step, i_b] = comp_b / pr.area_trib

            # Soil octahedral shear strains per element
            for e_idx in range(mesh.n_elements):
                enodes = mesh.elements[e_idx]
                oct_strain_hist[step, e_idx] = _compute_octahedral_shear_strain(
                    mesh.nodes[enodes], u_step[enodes]
                )

            completed = step + 1
            if progress_cb is not None and (step % 2 == 0 or step == n_steps - 1):
                crest_u = (
                    float(np.max(np.abs(u_step[mesh.wall_crest_nodes, 0])))
                    if mesh.wall_crest_nodes else float(np.max(np.abs(u_step[:, 0])))
                )
                progress_cb(step, float(time_arr[step]), crest_u, float(thrust_knm_hist[step]))

        # Slice down if cancelled early
        n_rec = max(1, completed)
        t_rec = time_arr[:n_rec]
        disp_rec = disp_hist[:n_rec]
        bf_norm_rec = bf_norm_hist[:n_rec]
        bf_shear_rec = bf_shear_hist[:n_rec]
        thrust_3d_rec = thrust_3d_hist[:n_rec]
        thrust_knm_rec = thrust_knm_hist[:n_rec]
        elev_rec = elev_hist[:n_rec]
        oct_rec = oct_strain_hist[:n_rec]
        ru_rec = ru_hist[:n_rec]
        base_rec = base_stress_hist[:n_rec]

        # Corner-to-midspan pressure concentration ratio on wall backface
        corner_ratio = 1.0
        if n_bf >= 3:
            z_vals = bf_coords[:, 2]
            z_center = 0.5 * l_wall
            mid_mask = np.abs(z_vals - z_center) <= (0.20 * l_wall + 1e-4)
            end_mask = (z_vals <= 0.20 * l_wall + 1e-4) | (z_vals >= 0.80 * l_wall - 1e-4)
            peak_p = np.max(bf_norm_rec, axis=0)
            p_mid = float(np.mean(peak_p[mid_mask])) if np.any(mid_mask) else float(np.mean(peak_p))
            p_end = float(np.mean(peak_p[end_mask])) if np.any(end_mask) else p_mid
            corner_ratio = float(p_end / max(1e-6, p_mid))

        crest_ids = mesh.wall_crest_nodes if mesh.wall_crest_nodes else list(range(mesh.n_nodes))
        max_crest_cm = float(np.max(np.abs(disp_rec[:, crest_ids, 0]))) * 100.0

        provenance = build_provenance(
            SolverTier.L2_OPENSEES_3D_FEA,
            element_types=["brickUP" if use_up else "stdBrick", "zeroLength (ENT+ElasticPP)", "zeroLength (Viscous Lysmer)"],
            constitutive_model=effective_model.value,
            damping_model="Rayleigh 3% + Lysmer-Kuhlemeyer" if use_lysmer else "Rayleigh 3%",
            runtime_ms=(time.perf_counter() - t_start) * 1000.0,
            converged=(status == "CONVERGED"),
            extra={
                "n_nodes": mesh.n_nodes,
                "n_elements": mesh.n_elements,
                "seismic_axes": [
                    ax for ax, arr in (("X", accel_x_g), ("Y", accel_y_g), ("Z", accel_z_g)) if arr is not None
                ],
                "wall_mode": self.wall_mode.value,
            },
        )

        result = ContinuumFEAResult(
            time=t_rec,
            displacement_field=disp_rec,
            backface_coords=bf_coords,
            backface_normal_stress_kpa=bf_norm_rec,
            backface_shear_stress_kpa=bf_shear_rec,
            total_thrust_kn_m=thrust_knm_rec,
            total_thrust_3d_kn=thrust_3d_rec,
            thrust_elevation_m=elev_rec,
            corner_concentration_ratio=corner_ratio,
            octahedral_shear_strain=oct_rec,
            excess_pore_pressure_ratio_ru=ru_rec,
            foundation_bearing_stress_kpa=base_rec,
            max_crest_disp_cm=max_crest_cm,
            mesh=mesh,
            provenance=provenance,
            hdf5_path=hdf5_path,
            status=status,
        )
        result.mesh_grid = result.grid_at_timestep(-1)

        if hdf5_path and n_rec > 0 and status != "CANCELLED":
            export_continuum_hdf5(hdf5_path, result)

        return result


class OpenSees3DFEAWorker(QThread):
    """
    Cooperative background worker thread executing 3D OpenSeesPy Continuum FEA
    without freezing the PySide6 desktop GUI.
    """

    stepCompleted = Signal(int, float, float, float)  # (step, time, crest_disp_m, thrust_kn_m)
    simulationFinished = Signal(dict)
    simulationError = Signal(str)

    def __init__(
        self,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        time_arr: np.ndarray,
        accel_x_g: np.ndarray,
        accel_y_g: Optional[np.ndarray] = None,
        accel_z_g: Optional[np.ndarray] = None,
        constitutive_model: ConstitutiveModelType = ConstitutiveModelType.ELASTIC_ISOTROPIC,
        use_up: bool = False,
        wall_mode: WallSystemMode = WallSystemMode.CANTILEVER,
        multi_strut_model: Optional[MultiStrutPiledWallModel] = None,
        output_hdf5_path: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.geom = geom
        self.soil = soil
        self.seismic = seismic
        self.time_arr = np.asarray(time_arr, dtype=np.float64)
        self.accel_x_g = np.asarray(accel_x_g, dtype=np.float64)
        self.accel_y_g = accel_y_g
        self.accel_z_g = accel_z_g
        self.constitutive_model = constitutive_model
        self.use_up = use_up
        self.wall_mode = wall_mode
        self.multi_strut_model = multi_strut_model
        self.output_hdf5_path = output_hdf5_path
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            solver = OpenSees3DContinuumSolver(
                self.geom,
                self.soil,
                self.seismic,
                wall_mode=self.wall_mode,
                multi_strut_model=self.multi_strut_model,
            )
            result = solver.run_dynamic_seismic(
                self.time_arr,
                self.accel_x_g,
                accel_y_g=self.accel_y_g,
                accel_z_g=self.accel_z_g,
                constitutive_model=self.constitutive_model,
                use_up=self.use_up,
                hdf5_path=self.output_hdf5_path,
                progress_cb=lambda s, t, u, p: self.stepCompleted.emit(s, t, u, p),
                cancel_check=lambda: self._is_cancelled,
            )
            self.simulationFinished.emit(
                {
                    "status": result.status,
                    "total_steps": int(len(result.time)),
                    "max_crest_disp_cm": float(result.max_crest_disp_cm),
                    "peak_thrust_kn_m": float(np.max(result.total_thrust_kn_m)) if len(result.total_thrust_kn_m) else 0.0,
                    "corner_concentration_ratio": float(result.corner_concentration_ratio),
                    "result": result,
                }
            )
        except Exception as exc:
            self.simulationError.emit(str(exc))

