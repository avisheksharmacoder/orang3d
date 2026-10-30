"""
OpenSeesPy BNWF (Beam on Nonlinear Winkler Foundation) 2D Model Assembler.
Assembles vertical RC pier columns, floating bored pile groups, nonlinear p-y/t-z/q-z
soil springs with radiation damping, and nonlinear raking struts with tension slackening
and compressive buckling caps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

try:
    import openseespy.opensees as ops
    OPENSEES_AVAILABLE = True
except (ImportError, Exception):
    ops = None
    OPENSEES_AVAILABLE = False

from ..models.advanced_wall_params import MultiStrutPiledWallModel
from ..models.wall_params import SoilProperties
from .spring_curves import (
    SoilSpringProfile,
    generate_soil_spring_profile,
)


@dataclass
class BNWFModelInfo:
    """Registry and metadata mapping for an assembled OpenSeesPy BNWF model."""
    crest_node_tag: int
    pile_head_node_tag: int
    pile_tip_node_tag: int
    pier_nodes: List[int] = field(default_factory=list)
    pile_nodes: List[int] = field(default_factory=list)
    fixed_soil_nodes: List[int] = field(default_factory=list)
    strut_anchor_nodes: List[int] = field(default_factory=list)
    pier_elements: List[int] = field(default_factory=list)
    pile_elements: List[int] = field(default_factory=list)
    soil_elements: List[int] = field(default_factory=list)
    strut_elements: List[int] = field(default_factory=list)
    strut_materials: List[int] = field(default_factory=list)
    node_elevations: Dict[int, float] = field(default_factory=dict)
    strut_node_map: Dict[int, int] = field(default_factory=dict)  # strut_idx -> pier_node_tag
    p_cr_values: Dict[int, float] = field(default_factory=dict)   # strut_idx -> P_cr (kN)
    lock_off_forces: Dict[int, float] = field(default_factory=dict) # strut_idx -> P_0 (kN)
    num_piles: int = 1


def build_opensees_bnwf_model(
    model: MultiStrutPiledWallModel,
    soil: SoilProperties,
    slope_angle: float = 0.0,
    num_pile_nodes: int = 15,
    num_pier_nodes: int = 10,
    concrete_modulus: float = 30.0e6, # 30 GPa = 30,000,000 kPa
) -> BNWFModelInfo:
    """
    Constructs a complete 2D Beam on Nonlinear Winkler Foundation (BNWF) model in OpenSeesPy:
    - Pier column: elastic beam-column elements from Y=0 to Y=H_pier
    - Bored pile group: elastic beam-column elements from Y=0 to Y=-L_pile
    - Subgrade: PySimple1 (lateral), TzSimple1 (skin friction), QzSimple1 (tip bearing) zeroLength springs
    - Raking struts: ElasticMultiLinear truss elements with slackening under tension and Euler buckling under compression
    """
    if not OPENSEES_AVAILABLE:
        raise RuntimeError(
            "OpenSeesPy is not installed or failed to import. "
            "Run `.venv/bin/pip install openseespy`."
        )

    if num_pile_nodes < 3:
        raise ValueError(f"num_pile_nodes must be >= 3, got {num_pile_nodes}")
    if num_pier_nodes < 2:
        raise ValueError(f"num_pier_nodes must be >= 2, got {num_pier_nodes}")

    ops.wipe()
    ops.model("basic", "-ndm", 2, "-ndf", 3)

    pier_h = model.pier_pile.pier_height
    pile_l = model.pier_pile.pile_length
    d_pile = model.pier_pile.pile_diameter
    n_piles = model.pier_pile.num_piles_per_pier
    b_pier = model.pier_pile.pier_width
    d_pier = model.pier_pile.pier_depth

    # Geometric transformation for 2D beam-columns
    transf_tag = 1
    ops.geomTransf("Linear", transf_tag)

    # 1. Structural Section Properties
    # Pier column (rectangular)
    a_pier = b_pier * d_pier
    i_pier = (b_pier * (d_pier ** 3)) / 12.0

    # Pile group (circular)
    a_pile = ((math.pi * (d_pile ** 2)) / 4.0) * n_piles
    i_pile = ((math.pi * (d_pile ** 4)) / 64.0) * n_piles

    # Unit densities (concrete = 25 kN/m^3 -> mass = 2.55 t/m^3)
    rho_c = 2.55 # t/m^3
    pier_mass_per_len = a_pier * rho_c
    pile_mass_per_len = a_pile * rho_c

    node_elevations: Dict[int, float] = {}

    # 2. Pier Nodes & Elements (Elevation: Y = 0 to Y = pier_h)
    pier_y = np.linspace(0.0, pier_h, num_pier_nodes, dtype=np.float64)
    pier_nodes = []
    pier_elements = []

    # Node at Y=0 is designated tag 100
    for idx, y in enumerate(pier_y):
        tag = 100 + idx
        ops.node(tag, 0.0, float(y))
        node_elevations[tag] = float(y)
        pier_nodes.append(tag)

        # Lumped mass
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
    pile_head_node = pier_nodes[0] # Y = 0.0

    # 3. Pile Nodes & Elements (Elevation: Y = 0 to Y = -pile_l)
    pile_y = np.linspace(0.0, -pile_l, num_pile_nodes, dtype=np.float64)
    pile_nodes = [pile_head_node] # Head node is shared with pier base
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

    pile_tip_node = pile_nodes[-1]

    # 4. Nonlinear Winkler Soil Springs (p-y, t-z, q-z)
    spring_profile = generate_soil_spring_profile(
        pier_pile=model.pier_pile,
        soil=soil,
        slope_angle=slope_angle,
        num_pile_nodes=num_pile_nodes,
    )

    fixed_soil_nodes = []
    soil_elements = []

    for idx, (p_node, py_p, tz_p) in enumerate(
        zip(pile_nodes, spring_profile.py_springs, spring_profile.tz_springs)
    ):
        soil_tag = 300 + idx
        y_coord = node_elevations[p_node]
        ops.node(soil_tag, 0.0, y_coord)
        ops.fix(soil_tag, 1, 1, 1) # Soil far-field support is fixed
        fixed_soil_nodes.append(soil_tag)

        # PySimple1 material (DOF 1 = X lateral)
        py_mat_tag = 1000 + idx
        # Scale p_ult by number of piles in the group
        p_ult_group = py_p.p_ult_integrated * n_piles
        ops.uniaxialMaterial(
            "PySimple1",
            py_mat_tag,
            py_p.mat_type,
            p_ult_group,
            py_p.y_50,
            py_p.cd,
        )

        # TzSimple1 material (DOF 2 = Y skin friction)
        tz_mat_tag = 2000 + idx
        t_ult_group = tz_p.t_ult_integrated * n_piles
        ops.uniaxialMaterial(
            "TzSimple1",
            tz_mat_tag,
            1, # matType
            t_ult_group,
            tz_p.z_50,
            0.0, # c
        )

        ele_tag = 700 + idx
        # Connect pile node and fixed soil node with zeroLength element
        if idx == num_pile_nodes - 1:
            # Tip node: include QzSimple1 end bearing spring in DOF 2
            qz_mat_tag = 3000
            q_ult_group = spring_profile.qz_spring.q_ult * n_piles
            ops.uniaxialMaterial(
                "QzSimple1",
                qz_mat_tag,
                1, # matType
                q_ult_group,
                spring_profile.qz_spring.z_50,
                0.0,
            )
            # Parallel combination of Tz and Qz at tip
            parallel_tip_tag = 3001
            ops.uniaxialMaterial("Parallel", parallel_tip_tag, tz_mat_tag, qz_mat_tag)

            ops.element(
                "zeroLength",
                ele_tag,
                soil_tag,
                p_node,
                "-mat",
                py_mat_tag,
                parallel_tip_tag,
                "-dir",
                1,
                2,
            )
        else:
            ops.element(
                "zeroLength",
                ele_tag,
                soil_tag,
                p_node,
                "-mat",
                py_mat_tag,
                tz_mat_tag,
                "-dir",
                1,
                2,
            )

        soil_elements.append(ele_tag)

    # 5. Nonlinear Raking Struts (Asymmetric ElasticMultiLinear with tension slackening & Euler buckling cap)
    struts = model.struts
    alpha_rad = math.radians(struts.inclination_angle)
    l_strut = struts.unbraced_length
    a_strut = struts.cross_section_area
    e_strut = struts.elastic_modulus
    p_cr = struts.euler_buckling_load # Critical buckling load (kN)
    p_0 = struts.pre_stress_load     # Lock-off prestress (kN)

    # Strut capacity in stress (kPa)
    sig_cr = p_cr / a_strut
    eps_cr = sig_cr / e_strut

    # Asymmetric material response:
    # Strains: [-0.05, -eps_cr, 0.0, 0.001, 0.05]
    # Stresses: [-sig_cr - 1e-4*E*(0.05 - eps_cr), -sig_cr, 0.0, 1e-5*E*0.001, 1e-5*E*0.05]
    # Compressive yielding at P_cr; practically zero resistance in tension (slackening).
    strut_anchor_nodes = []
    strut_elements = []
    strut_materials = []
    strut_node_map = {}
    p_cr_values = {}
    lock_off_forces = {}

    for s_idx, d_lvl in enumerate(struts.strut_levels):
        target_y = pier_h - d_lvl
        # Find closest pier node
        closest_node = min(
            pier_nodes, key=lambda n: abs(node_elevations[n] - target_y)
        )
        pier_node_y = node_elevations[closest_node]

        # Anchor node placed uphill at distance L_strut with inclination angle alpha
        anchor_x = -l_strut * math.cos(alpha_rad)
        anchor_y = pier_node_y - l_strut * math.sin(alpha_rad)

        anchor_tag = 400 + s_idx
        ops.node(anchor_tag, anchor_x, anchor_y)
        ops.fix(anchor_tag, 1, 1, 1) # Strut anchor is fixed into bedrock
        strut_anchor_nodes.append(anchor_tag)

        # Uniaxial material for this strut
        mat_tag = 4000 + s_idx
        e_residual = 1e-5 * e_strut
        strains = [-0.05, -eps_cr, 0.0, 0.001, 0.05]
        stresses = [
            -sig_cr - e_residual * (0.05 - eps_cr),
            -sig_cr,
            0.0,
            e_residual * 0.001,
            e_residual * 0.05,
        ]
        ops.uniaxialMaterial(
            "ElasticMultiLinear",
            mat_tag,
            "-strain",
            *strains,
            "-stress",
            *stresses,
        )
        strut_materials.append(mat_tag)

        ele_tag = 800 + s_idx
        ops.element("truss", ele_tag, closest_node, anchor_tag, a_strut, mat_tag)
        strut_elements.append(ele_tag)

        strut_node_map[s_idx] = closest_node
        p_cr_values[s_idx] = p_cr
        lock_off_forces[s_idx] = p_0

    return BNWFModelInfo(
        crest_node_tag=crest_node,
        pile_head_node_tag=pile_head_node,
        pile_tip_node_tag=pile_tip_node,
        pier_nodes=pier_nodes,
        pile_nodes=pile_nodes,
        fixed_soil_nodes=fixed_soil_nodes,
        strut_anchor_nodes=strut_anchor_nodes,
        pier_elements=pier_elements,
        pile_elements=pile_elements,
        soil_elements=soil_elements,
        strut_elements=strut_elements,
        strut_materials=strut_materials,
        node_elevations=node_elevations,
        strut_node_map=strut_node_map,
        p_cr_values=p_cr_values,
        lock_off_forces=lock_off_forces,
        num_piles=n_piles,
    )
