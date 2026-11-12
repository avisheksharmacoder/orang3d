"""
General Adjacent Building & Traffic Surcharge Engine (Phase 7).

Generalizes `tower_coupling.py` Boussinesq surcharge mechanics to model:
  1. Uniform traffic / live strip surcharges (q_surf, strip width B_f, setback x_f)
  2. Adjacent building shallow strip footings (Q_bld, width B_f, setback x_f, embedment D_f)
  3. Adjacent building isolated 3D pad footings (Q_bld, B_f x L_f, setback x_f, embedment D_f)
  4. 2:1 (2V:1H) elastic stress dispersion & Mononobe-Okabe seismic inertial increments
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import List, Optional, Tuple
import numpy as np

from ..models.wall_params import (
    AnalysisResults,
    RetainingWallGeometry,
    SeismicParams,
    SoilProperties,
)
from .mononobe_okabe import compute_mononobe_okabe
from .stability import evaluate_wall_stability
from .tower_coupling import (
    WallSurchargeProfile,
    _integrate_trapezoid,
    compute_boussinesq_point_surcharge_on_wall,
)


class SurchargeLoadType(str, Enum):
    """Supported surface and adjacent foundation surcharge types."""

    NONE = "none"
    UNIFORM_TRAFFIC = "uniform_traffic"
    BUILDING_STRIP_FOOTING = "building_strip_footing"
    BUILDING_PAD_FOOTING = "building_pad_footing"


@dataclass
class AdjacentSurchargeParams:
    """Parameters defining an adjacent traffic strip or building footing surcharge."""

    load_type: SurchargeLoadType = SurchargeLoadType.NONE
    uniform_q_kpa: float = 15.0
    building_load_kn: float = 450.0
    footing_width_m: float = 2.0
    footing_length_m: float = 4.0
    setback_m: float = 1.2
    embedment_m: float = 0.8
    method: str = "boussinesq"  # "boussinesq" or "elastic_2_to_1"

    def __post_init__(self) -> None:
        self.load_type = SurchargeLoadType(self.load_type)
        if self.uniform_q_kpa < 0.0:
            raise ValueError(f"uniform_q_kpa must be >= 0, got {self.uniform_q_kpa}")
        if self.building_load_kn < 0.0:
            raise ValueError(f"building_load_kn must be >= 0, got {self.building_load_kn}")
        if self.footing_width_m <= 0.0:
            raise ValueError(f"footing_width_m must be > 0, got {self.footing_width_m}")
        if self.footing_length_m <= 0.0:
            raise ValueError(f"footing_length_m must be > 0, got {self.footing_length_m}")
        if self.setback_m < 0.0:
            raise ValueError(f"setback_m must be >= 0, got {self.setback_m}")
        if self.embedment_m < 0.0:
            raise ValueError(f"embedment_m must be >= 0, got {self.embedment_m}")
        if self.method not in ("boussinesq", "elastic_2_to_1"):
            raise ValueError(f"Unsupported surcharge dispersion method: {self.method}")

    @property
    def contact_pressure_kpa(self) -> float:
        """Equivalent vertical bearing / contact intensity q0 (kPa)."""
        if self.load_type == SurchargeLoadType.NONE:
            return 0.0
        if self.load_type == SurchargeLoadType.UNIFORM_TRAFFIC:
            return float(self.uniform_q_kpa)
        area = max(1e-4, self.footing_width_m * self.footing_length_m)
        return float(self.building_load_kn / area)

    @property
    def strip_line_load_kn_per_m(self) -> float:
        """Line load per running meter along wall (kN/m)."""
        if self.load_type == SurchargeLoadType.NONE:
            return 0.0
        if self.load_type == SurchargeLoadType.UNIFORM_TRAFFIC:
            return float(self.uniform_q_kpa * self.footing_width_m)
        return float(self.building_load_kn / max(1e-4, self.footing_length_m))


@dataclass
class SurchargeAnalysisResult:
    """Computed surcharge lateral pressure profile, 2:1 stress, and equilibrium quantities."""

    profile: WallSurchargeProfile
    depths_m: List[float]
    elevations_m: List[float]
    sigma_h_static_kpa: List[float]
    sigma_h_seismic_kpa: List[float]
    sigma_h_total_kpa: List[float]
    sigma_v_2to1_kpa: List[float]
    static_thrust_kn_per_m: float
    seismic_increment_kn_per_m: float
    total_thrust_kn_per_m: float
    resultant_elevation_m: float
    moment_about_base_knm_per_m: float
    equivalent_line_load_kn_per_m: float


def compute_boussinesq_strip_pressure(
    q_kpa: float,
    setback_m: float,
    strip_width_m: float,
    z_eff_m: float,
) -> float:
    """
    Rigid-wall Terzaghi-Spangler / Flamant integrated Boussinesq horizontal pressure (kPa)
    at effective depth z_eff below footing base for uniform strip pressure q_kpa spanning
    x in [setback_m, setback_m + strip_width_m].

        sigma_h(z) = (2 * q / pi) * [beta - sin(beta) * cos(2 * theta_m)]
    """
    if q_kpa <= 0.0 or strip_width_m <= 0.0 or z_eff_m <= 1e-6:
        return 0.0

    x1 = max(1e-3, float(setback_m))
    x2 = x1 + float(strip_width_m)
    alpha1 = math.atan2(x1, z_eff_m)
    alpha2 = math.atan2(x2, z_eff_m)
    beta = alpha2 - alpha1
    theta_m = 0.5 * (alpha1 + alpha2)

    sigma_h = (2.0 * q_kpa / math.pi) * (beta - math.sin(beta) * math.cos(2.0 * theta_m))
    return float(max(0.0, sigma_h))


def _compute_2to1_vertical_stress(
    params: AdjacentSurchargeParams,
    z_eff_m: float,
) -> float:
    """Computes vertical 2V:1H stress dispersion delta_sigma_v(z_eff) in kPa."""
    if params.load_type == SurchargeLoadType.NONE or z_eff_m <= 0.0:
        return 0.0
    b_f = params.footing_width_m
    l_f = params.footing_length_m
    if params.load_type in (
        SurchargeLoadType.UNIFORM_TRAFFIC,
        SurchargeLoadType.BUILDING_STRIP_FOOTING,
    ):
        return float(params.strip_line_load_kn_per_m / (b_f + z_eff_m))
    # Isolated 3D pad footing: Q / ((B + z) * (L + z))
    return float(params.building_load_kn / ((b_f + z_eff_m) * (l_f + z_eff_m)))


def calculate_adjacent_surcharge_profile(
    params: AdjacentSurchargeParams,
    wall_height: float,
    soil: Optional[SoilProperties] = None,
    seismic: Optional[SeismicParams] = None,
    num_eval_points: int = 81,
) -> SurchargeAnalysisResult:
    """
    Evaluates depth-wise static + seismic lateral surcharge pressure on a retaining wall
    of total height `wall_height` using Boussinesq or 2:1 elastic theory and integrates
    equilibrium thrust and overturning moment via trapezoidal quadrature.
    """
    if wall_height <= 0.0:
        raise ValueError(f"wall_height must be positive, got {wall_height}")
    if num_eval_points < 9:
        raise ValueError(f"num_eval_points must be >= 9, got {num_eval_points}")

    depths = np.linspace(0.0, wall_height, num_eval_points, dtype=np.float64)
    elevations = wall_height - depths

    if params.load_type == SurchargeLoadType.NONE:
        zeros = [0.0] * len(depths)
        prof = WallSurchargeProfile(
            depths=[round(float(d), 4) for d in depths],
            elevations=[round(float(e), 4) for e in elevations],
            pressures_kpa=list(zeros),
            total_thrust_kn_per_m=0.0,
            resultant_elevation_m=round(wall_height / 3.0, 4),
        )
        return SurchargeAnalysisResult(
            profile=prof,
            depths_m=prof.depths,
            elevations_m=prof.elevations,
            sigma_h_static_kpa=list(zeros),
            sigma_h_seismic_kpa=list(zeros),
            sigma_h_total_kpa=list(zeros),
            sigma_v_2to1_kpa=list(zeros),
            static_thrust_kn_per_m=0.0,
            seismic_increment_kn_per_m=0.0,
            total_thrust_kn_per_m=0.0,
            resultant_elevation_m=prof.resultant_elevation_m,
            moment_about_base_knm_per_m=0.0,
            equivalent_line_load_kn_per_m=0.0,
        )

    eff_soil = soil if soil is not None else SoilProperties()
    eff_seis = seismic if seismic is not None else SeismicParams(horizontal_pga=0.0, vertical_pga=0.0)
    k_ae, k_a, _ = compute_mononobe_okabe(
        phi_deg=eff_soil.friction_angle,
        delta_deg=eff_soil.wall_friction_angle,
        kh=eff_seis.horizontal_pga,
        kv=eff_seis.vertical_pga,
        beta_deg=eff_seis.backfill_slope,
        liquefaction_factor=eff_seis.liquefaction_factor,
    )
    mo_amp = max(1.0, k_ae / max(1e-4, k_a))

    x_f = max(0.05, params.setback_m)
    b_f = params.footing_width_m
    l_f = params.footing_length_m
    d_f = 0.0 if params.load_type == SurchargeLoadType.UNIFORM_TRAFFIC else params.embedment_m
    q0 = params.contact_pressure_kpa

    # Precompute 8x8 Gauss/midpoint quadrature footprint for 3D pad footings
    n_quad = 8
    dx = b_f / n_quad
    dy = l_f / n_quad
    xq = x_f + (np.arange(n_quad) + 0.5) * dx
    yq = -0.5 * l_f + (np.arange(n_quad) + 0.5) * dy
    x_grid, y_grid = np.meshgrid(xq, yq, indexing="ij")
    d_p = params.building_load_kn / float(n_quad * n_quad)

    sigma_static = np.zeros_like(depths)
    sigma_seismic = np.zeros_like(depths)
    sigma_v_2to1 = np.zeros_like(depths)

    for idx, z in enumerate(depths):
        z_eff = float(z - d_f)
        if z_eff <= 1e-6:
            continue

        sv_21 = _compute_2to1_vertical_stress(params, z_eff)
        sigma_v_2to1[idx] = sv_21

        if params.method == "elastic_2_to_1":
            # Lateral mobilization starts once 2V:1H dispersion wedge reaches wall backface
            overlap_ratio = float(np.clip((0.5 * z_eff - x_f + 0.5 * b_f) / max(0.5, b_f), 0.0, 1.0))
            sh_st = max(0.0, k_a * sv_21 * overlap_ratio)
        else:
            if params.load_type == SurchargeLoadType.BUILDING_PAD_FOOTING:
                sh_st = 0.0
                for xi, yi in zip(x_grid.ravel(), y_grid.ravel()):
                    sh_st += compute_boussinesq_point_surcharge_on_wall(
                        point_load_kn=d_p,
                        x_offset=float(xi),
                        y_offset=float(yi),
                        z_depth=z_eff,
                        wall_height=wall_height,
                    )
            else:
                sh_st = compute_boussinesq_strip_pressure(
                    q_kpa=q0,
                    setback_m=x_f,
                    strip_width_m=b_f,
                    z_eff_m=z_eff,
                )

        sigma_static[idx] = sh_st

        # Seismic increment combines dynamic M-O amplification + horizontal shear transfer kh * q_line
        if eff_seis.horizontal_pga > 0.0:
            v_bld_line = eff_seis.horizontal_pga * params.strip_line_load_kn_per_m
            shear_transfer = (2.0 * v_bld_line / math.pi) * (
                (x_f ** 3) / ((x_f ** 2 + z_eff ** 2) ** 2)
            )
            sigma_seismic[idx] = max(0.0, sh_st * (mo_amp - 1.0) + shear_transfer)

    sigma_total = sigma_static + sigma_seismic

    p_static = _integrate_trapezoid(sigma_static, depths)
    p_seismic = _integrate_trapezoid(sigma_seismic, depths)
    p_total = _integrate_trapezoid(sigma_total, depths)
    moment_base = _integrate_trapezoid(sigma_total * elevations, depths)
    y_bar = (moment_base / p_total) if p_total > 1e-6 else (wall_height / 2.0)

    prof = WallSurchargeProfile(
        depths=[round(float(d), 4) for d in depths],
        elevations=[round(float(e), 4) for e in elevations],
        pressures_kpa=[round(float(p), 4) for p in sigma_total],
        total_thrust_kn_per_m=round(float(p_total), 4),
        resultant_elevation_m=round(float(y_bar), 4),
    )

    return SurchargeAnalysisResult(
        profile=prof,
        depths_m=prof.depths,
        elevations_m=prof.elevations,
        sigma_h_static_kpa=[float(v) for v in sigma_static],
        sigma_h_seismic_kpa=[float(v) for v in sigma_seismic],
        sigma_h_total_kpa=[float(v) for v in sigma_total],
        sigma_v_2to1_kpa=[float(v) for v in sigma_v_2to1],
        static_thrust_kn_per_m=float(p_static),
        seismic_increment_kn_per_m=float(p_seismic),
        total_thrust_kn_per_m=float(p_total),
        resultant_elevation_m=float(y_bar),
        moment_about_base_knm_per_m=float(moment_base),
        equivalent_line_load_kn_per_m=float(params.strip_line_load_kn_per_m),
    )


def evaluate_wall_stability_with_surcharge(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    surcharge: Optional[AdjacentSurchargeParams] = None,
) -> Tuple[AnalysisResults, Optional[SurchargeAnalysisResult]]:
    """
    Evaluates retaining wall stability including adjacent building/traffic surcharge
    thrust, overturning moment, stem bending demand, and any vertical heel overlap load.
    """
    if surcharge is None or surcharge.load_type == SurchargeLoadType.NONE:
        return evaluate_wall_stability(geom, soil, seismic), None

    s_full = calculate_adjacent_surcharge_profile(
        params=surcharge,
        wall_height=geom.total_height,
        soil=soil,
        seismic=seismic,
    )
    s_stem = calculate_adjacent_surcharge_profile(
        params=surcharge,
        wall_height=geom.stem_height,
        soil=soil,
        seismic=seismic,
    )

    # Any surface/shallow strip resting directly over the heel adds stabilizing gravity weight
    x1 = surcharge.setback_m
    x2 = x1 + surcharge.footing_width_m
    heel_overlap = max(0.0, min(geom.heel_length, x2) - x1)
    extra_heel_kn_per_m = 0.0
    if heel_overlap > 0.0 and surcharge.embedment_m <= geom.stem_height:
        extra_heel_kn_per_m = (heel_overlap / surcharge.footing_width_m) * surcharge.strip_line_load_kn_per_m

    results = evaluate_wall_stability(
        geom=geom,
        soil=soil,
        seismic=seismic,
        extra_thrust_kn_per_m=s_full.total_thrust_kn_per_m,
        extra_thrust_height_m=s_full.resultant_elevation_m,
        extra_heel_load_kn_per_m=extra_heel_kn_per_m,
        extra_stem_thrust_kn_per_m=s_stem.total_thrust_kn_per_m,
        extra_stem_moment_knm_per_m=s_stem.moment_about_base_knm_per_m,
    )
    return results, s_full

