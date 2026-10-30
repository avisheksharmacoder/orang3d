"""
Unsaturated Soil Mechanics, Soil-Water Characteristic Curves (SWCC),
and Compound Monsoon Rainfall Infiltration Engine (Phase 7).

Implements:
1. Van Genuchten (1980) Soil-Water Retention / Characteristic Curve (SWCC).
2. Fredlund & Rahardjo (1993) matric suction-dependent apparent cohesion c_app(psi).
3. Saturation-dependent soil bulk unit weight gamma(S_r).
4. Green-Ampt 1D rainfall infiltration and wetting front propagation.
5. Compound disaster sequencing: Rainfall infiltration -> matric suction loss -> Newmark sliding degradation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from ..models.wall_params import SoilProperties, RetainingWallGeometry
from ..signals.synthetic import (
    compute_yield_acceleration_ky,
    compute_newmark_sliding_displacement,
)


@dataclass
class VanGenuchtenParams:
    """
    Parametric parameters for Van Genuchten (1980) Soil-Water Retention Curve (SWRC/SWCC).
    theta(psi) = theta_r + (theta_s - theta_r) / [1 + (alpha * psi)^n]^m
    where m = 1 - 1/n.
    """
    alpha_kpa_inv: float = 0.05          # alpha: Inverse of air-entry suction (1/kPa)
    n_param: float = 1.60                # n: Pore-size distribution index (n > 1)
    theta_res: float = 0.08              # theta_r: Residual volumetric water content (m^3/m^3)
    theta_sat: float = 0.42              # theta_s: Saturated volumetric water content / porosity (m^3/m^3)
    residual_saturation: float = 0.15    # S_r,res: Minimum residual degree of saturation

    def __post_init__(self):
        if self.alpha_kpa_inv <= 0:
            raise ValueError(f"alpha_kpa_inv must be positive, got {self.alpha_kpa_inv}")
        if self.n_param <= 1.0:
            raise ValueError(f"n_param must be > 1.0, got {self.n_param}")
        if not (0.0 <= self.theta_res < self.theta_sat <= 1.0):
            raise ValueError(
                f"Invalid water contents: theta_res={self.theta_res}, theta_sat={self.theta_sat}"
            )
        if not (0.0 <= self.residual_saturation < 1.0):
            raise ValueError(
                f"residual_saturation must be in [0, 1), got {self.residual_saturation}"
            )

    @property
    def m_param(self) -> float:
        """m = 1 - 1/n parameter per Mualem-Van Genuchten."""
        return 1.0 - (1.0 / self.n_param)

    def effective_saturation(self, matric_suction_kpa: float) -> float:
        """
        Computes normalized effective saturation S_e in [0.0, 1.0]:
        S_e = [1 + (alpha * psi)^n]^(-m)
        """
        psi = max(0.0, float(matric_suction_kpa))
        if psi <= 1e-6:
            return 1.0
        val = 1.0 + ((self.alpha_kpa_inv * psi) ** self.n_param)
        s_e = val ** (-self.m_param)
        return float(np.clip(s_e, 0.0, 1.0))

    def degree_of_saturation(self, matric_suction_kpa: float) -> float:
        """
        Computes physical degree of saturation S_r(psi) in [S_r,res, 1.0]:
        S_r = S_r,res + (1 - S_r,res) * S_e(psi)
        """
        s_e = self.effective_saturation(matric_suction_kpa)
        s_r = self.residual_saturation + (1.0 - self.residual_saturation) * s_e
        return float(np.clip(s_r, self.residual_saturation, 1.0))

    def volumetric_water_content(self, matric_suction_kpa: float) -> float:
        """
        Computes volumetric water content theta(psi):
        theta = theta_r + (theta_s - theta_r) * S_e(psi)
        """
        s_e = self.effective_saturation(matric_suction_kpa)
        theta = self.theta_res + (self.theta_sat - self.theta_res) * s_e
        return float(np.clip(theta, self.theta_res, self.theta_sat))


@dataclass
class UnsaturatedSoilParameters:
    """
    Geotechnical contracts for unsaturated residual c-phi hill soils.
    """
    effective_cohesion: float = 12.0     # c': Effective Mohr-Coulomb cohesion (kPa)
    effective_friction_angle: float = 32.0 # phi': Effective angle of internal friction (deg)
    phi_b_angle: float = 18.0            # phi^b: Friction angle with respect to matric suction (deg)
    dry_unit_weight: float = 16.5        # gamma_d: Dry unit weight (kN/m^3)
    initial_matric_suction: float = 50.0 # psi_0: Initial antecedent matric suction (kPa)
    saturated_conductivity_mps: float = 1.5e-5 # k_sat: Saturated hydraulic conductivity (m/s)
    swcc: VanGenuchtenParams = field(default_factory=VanGenuchtenParams)

    def __post_init__(self):
        if self.effective_cohesion < 0:
            raise ValueError(f"effective_cohesion cannot be negative, got {self.effective_cohesion}")
        if not (0.0 < self.effective_friction_angle < 55.0):
            raise ValueError(f"effective_friction_angle must be in (0, 55), got {self.effective_friction_angle}")
        if not (0.0 <= self.phi_b_angle <= self.effective_friction_angle):
            raise ValueError(f"phi_b_angle ({self.phi_b_angle}) cannot exceed effective_friction_angle ({self.effective_friction_angle})")
        if self.dry_unit_weight <= 0:
            raise ValueError(f"dry_unit_weight must be positive, got {self.dry_unit_weight}")
        if self.initial_matric_suction < 0:
            raise ValueError(f"initial_matric_suction cannot be negative, got {self.initial_matric_suction}")
        if self.saturated_conductivity_mps <= 0:
            raise ValueError(f"saturated_conductivity_mps must be positive, got {self.saturated_conductivity_mps}")

    def compute_apparent_cohesion(self, matric_suction_kpa: float) -> float:
        """
        Computes apparent cohesion c_app (kPa) contributed by matric suction:
        c_app = psi * S_e(psi) * tan(phi_b)
        Per Fredlund & Rahardjo (1993) / Lu & Likos (2004).
        """
        psi = max(0.0, float(matric_suction_kpa))
        s_e = self.swcc.effective_saturation(psi)
        tan_phi_b = math.tan(math.radians(self.phi_b_angle))
        c_app = psi * s_e * tan_phi_b
        return float(c_app)

    def compute_total_cohesion(self, matric_suction_kpa: float) -> float:
        """
        Total apparent shear cohesion: c_total = c' + c_app(psi).
        """
        return self.effective_cohesion + self.compute_apparent_cohesion(matric_suction_kpa)

    def compute_bulk_unit_weight(self, matric_suction_kpa: float) -> float:
        """
        Bulk unit weight as a function of degree of saturation S_r(psi):
        gamma_bulk = gamma_d + S_r * n_porosity * gamma_w
        """
        s_r = self.swcc.degree_of_saturation(matric_suction_kpa)
        gamma_w = 9.81 # kN/m^3
        porosity = self.swcc.theta_sat
        gamma_bulk = self.dry_unit_weight + s_r * porosity * gamma_w
        return float(gamma_bulk)

    @property
    def saturated_unit_weight(self) -> float:
        """Bulk unit weight under 100% saturation (psi = 0)."""
        return self.compute_bulk_unit_weight(0.0)


@dataclass
class RainfallInfiltrationResult:
    """
    Simulation result for a monsoon rainfall storm event on a hill slope.
    """
    rainfall_duration_hours: float       # Duration of rainfall event (hours)
    rainfall_intensity_mm_hr: float      # Intensity of precipitation (mm/hr)
    cumulative_rainfall_mm: float        # Total precipitation depth (mm)
    wetting_front_depth_m: float         # Depth of infiltrated saturated zone z_w (m)
    initial_cohesion_kpa: float          # Apparent cohesion prior to rainfall (kPa)
    degraded_cohesion_kpa: float         # Depth-averaged degraded cohesion after rainfall (kPa)
    initial_unit_weight_kpa: float       # Initial soil unit weight (kN/m^3)
    degraded_unit_weight_kpa: float      # Depth-averaged soil unit weight after rainfall (kN/m^3)
    percent_cohesion_loss: float         # Percentage drop in apparent cohesion (%)
    initial_yield_acceleration_ky: float # Newmark ky before rainfall (g)
    degraded_yield_acceleration_ky: float# Newmark ky after rainfall (g)
    percent_ky_reduction: float          # Percentage drop in critical yield acceleration (%)


@dataclass
class CompoundDisasterResult:
    """
    Combined compound disaster sequencing result:
    Antecedent Monsoon Rainfall -> Infiltration & Suction Loss -> Strong Seismic Motion.
    """
    rainfall_summary: RainfallInfiltrationResult
    initial_permanent_displacement_cm: float # Newmark permanent slip before rain (cm)
    compound_permanent_displacement_cm: float# Newmark permanent slip under compound disaster (cm)
    slip_amplification_ratio: float          # u_compound / u_dry (> 1.0)
    time_series_s: List[float]
    dry_slip_history_cm: List[float]
    compound_slip_history_cm: List[float]


def simulate_rainfall_infiltration(
    soil_params: UnsaturatedSoilParameters,
    wall_geometry: RetainingWallGeometry,
    rainfall_intensity_mm_hr: float = 25.0, # 25 mm/hr heavy monsoon downpour
    rainfall_duration_hours: float = 24.0,   # 24-hour storm
) -> RainfallInfiltrationResult:
    """
    Simulates Green-Ampt 1D vertical rainfall infiltration into the hill backfill
    and retaining wall active wedge.

    Calculates:
    - Wetting front propagation depth z_w
    - Suction loss and apparent cohesion drop in the infiltrated zone
    - Increase in backfill bulk unit weight
    - Resulting drop in critical yield acceleration ky
    """
    if rainfall_intensity_mm_hr < 0:
        raise ValueError(f"rainfall_intensity_mm_hr cannot be negative, got {rainfall_intensity_mm_hr}")
    if rainfall_duration_hours <= 0:
        raise ValueError(f"rainfall_duration_hours must be positive, got {rainfall_duration_hours}")

    h_wall = wall_geometry.total_height
    cumulative_rainfall_mm = rainfall_intensity_mm_hr * rainfall_duration_hours
    rainfall_intensity_mps = (rainfall_intensity_mm_hr / 1000.0) / 3600.0
    t_seconds = rainfall_duration_hours * 3600.0

    # Soil moisture deficit: Delta_theta = theta_sat - theta_initial
    theta_0 = soil_params.swcc.volumetric_water_content(soil_params.initial_matric_suction)
    theta_s = soil_params.swcc.theta_sat
    delta_theta = max(0.02, theta_s - theta_0)

    # Infiltration rate is limited by saturated hydraulic conductivity k_sat
    actual_flux_mps = min(rainfall_intensity_mps, soil_params.saturated_conductivity_mps)

    # Green-Ampt wetting front depth: z_w = (flux * t) / delta_theta
    # Incorporates matric suction potential suction_head psi_0 / gamma_w
    psi_head = soil_params.initial_matric_suction / 9.81 # meters of water
    z_w_approx = math.sqrt(
        (2.0 * soil_params.saturated_conductivity_mps * psi_head * t_seconds) / delta_theta
    ) + (actual_flux_mps * t_seconds) / delta_theta

    z_wetting_front = float(np.clip(z_w_approx, 0.0, h_wall))

    # Initial states before rain
    c_initial = soil_params.compute_total_cohesion(soil_params.initial_matric_suction)
    gamma_initial = soil_params.compute_bulk_unit_weight(soil_params.initial_matric_suction)

    # Infiltrated zone properties (suction psi -> 0)
    c_saturated = soil_params.effective_cohesion # c_app drops to 0
    gamma_saturated = soil_params.saturated_unit_weight

    # Depth-weighted average properties across wall active wedge (height H)
    frac_saturated = z_wetting_front / h_wall if h_wall > 0 else 0.0
    c_degraded = frac_saturated * c_saturated + (1.0 - frac_saturated) * c_initial
    gamma_degraded = frac_saturated * gamma_saturated + (1.0 - frac_saturated) * gamma_initial

    pct_cohesion_drop = ((c_initial - c_degraded) / c_initial) * 100.0 if c_initial > 0 else 0.0

    # Calculate yield acceleration ky before and after rainfall
    sat_unit_w = max(gamma_saturated, gamma_degraded + 0.5)
    soil_dry_model = SoilProperties(
        friction_angle=soil_params.effective_friction_angle,
        cohesion=c_initial,
        unit_weight=gamma_initial,
        saturated_unit_weight=sat_unit_w,
        foundation_friction_angle=soil_params.effective_friction_angle,
        foundation_cohesion=c_initial,
        foundation_unit_weight=gamma_initial,
    )
    soil_wet_model = SoilProperties(
        friction_angle=soil_params.effective_friction_angle,
        cohesion=c_degraded,
        unit_weight=gamma_degraded,
        saturated_unit_weight=sat_unit_w,
        foundation_friction_angle=soil_params.effective_friction_angle,
        foundation_cohesion=c_degraded,
        foundation_unit_weight=gamma_degraded,
    )

    ky_initial = compute_yield_acceleration_ky(wall_geometry, soil_dry_model)
    ky_degraded = compute_yield_acceleration_ky(wall_geometry, soil_wet_model)
    pct_ky_drop = ((ky_initial - ky_degraded) / ky_initial) * 100.0 if ky_initial > 0 else 0.0

    return RainfallInfiltrationResult(
        rainfall_duration_hours=round(float(rainfall_duration_hours), 2),
        rainfall_intensity_mm_hr=round(float(rainfall_intensity_mm_hr), 2),
        cumulative_rainfall_mm=round(float(cumulative_rainfall_mm), 2),
        wetting_front_depth_m=round(float(z_wetting_front), 3),
        initial_cohesion_kpa=round(float(c_initial), 2),
        degraded_cohesion_kpa=round(float(c_degraded), 2),
        initial_unit_weight_kpa=round(float(gamma_initial), 2),
        degraded_unit_weight_kpa=round(float(gamma_degraded), 2),
        percent_cohesion_loss=round(float(pct_cohesion_drop), 2),
        initial_yield_acceleration_ky=round(float(ky_initial), 4),
        degraded_yield_acceleration_ky=round(float(ky_degraded), 4),
        percent_ky_reduction=round(float(pct_ky_drop), 2),
    )


def simulate_compound_rainfall_earthquake(
    soil_params: UnsaturatedSoilParameters,
    wall_geometry: RetainingWallGeometry,
    time_arr: np.ndarray,
    accel_g_arr: np.ndarray,
    rainfall_intensity_mm_hr: float = 25.0,
    rainfall_duration_hours: float = 24.0,
) -> CompoundDisasterResult:
    """
    Simulates the cascading compound disaster scenario:
    1. Monsoon storm occurs, inducing soil saturation, suction loss, and higher unit weight.
    2. Strong earthquake strikes the softened, water-laden retaining system.
    3. Evaluates Newmark permanent sliding displacement under dry vs. compound state.
    """
    # 1. Infiltration simulation
    rain_res = simulate_rainfall_infiltration(
        soil_params=soil_params,
        wall_geometry=wall_geometry,
        rainfall_intensity_mm_hr=rainfall_intensity_mm_hr,
        rainfall_duration_hours=rainfall_duration_hours,
    )

    # 2. Dry state Newmark analysis
    u_dry_history, u_dry_max = compute_newmark_sliding_displacement(
        time_arr=time_arr,
        accel_g_arr=accel_g_arr,
        yield_acceleration_ky=rain_res.initial_yield_acceleration_ky,
    )

    # 3. Degraded compound state Newmark analysis
    u_compound_history, u_compound_max = compute_newmark_sliding_displacement(
        time_arr=time_arr,
        accel_g_arr=accel_g_arr,
        yield_acceleration_ky=rain_res.degraded_yield_acceleration_ky,
    )

    amplification = (
        (u_compound_max / u_dry_max)
        if u_dry_max > 1e-4
        else (1.0 if u_compound_max <= 1e-4 else 999.0)
    )

    return CompoundDisasterResult(
        rainfall_summary=rain_res,
        initial_permanent_displacement_cm=round(float(u_dry_max), 3),
        compound_permanent_displacement_cm=round(float(u_compound_max), 3),
        slip_amplification_ratio=round(float(amplification), 2),
        time_series_s=[round(float(t), 4) for t in time_arr],
        dry_slip_history_cm=[round(float(u), 4) for u in u_dry_history],
        compound_slip_history_cm=[round(float(u), 4) for u in u_compound_history],
    )
