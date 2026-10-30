"""
Non-Linear Cyclic Soil Constitutive Models, Modulus Degradation G/G_max,
Hysteretic Damping D(gamma), and Masing Hysteresis Loop Engine (Phase 7).

Implements:
1. Darendeli (2001) / Modified Hyperbolic modulus reduction curve G/G_max(gamma).
2. Hysteretic damping ratio curve D(gamma) with small-strain damping bounds.
3. Extended Masing (1926) cyclic stress-strain hysteresis loops and plastic energy dissipation.
4. Parameter generator for OpenSees PressureDependMultiYield (PDMY02) and PM4Silt materials.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


@dataclass
class CyclicSoilParameters:
    """
    Parametric constitutive inputs for non-linear cyclic residual soil behavior
    under dynamic earthquake shaking.
    """
    max_shear_modulus_gmax_kpa: float = 85000.0 # G_max: Small-strain shear modulus (kPa) ~ 85 MPa
    reference_shear_strain: float = 0.0006      # gamma_r: Reference shear strain where G/G_max = 0.5 (decimal)
    curvature_param_a: float = 0.95             # a: Hyperbolic curvature parameter (typically 0.85 - 1.1)
    min_damping_ratio: float = 0.025            # D_min: Small-strain hysteretic damping (2.5%)
    max_damping_ratio: float = 0.28             # D_max: Large-strain limiting damping (28%)
    damping_exponent_b: float = 1.10            # b: Scaling exponent for damping growth
    friction_angle_deg: float = 32.0            # phi': Peak internal friction angle (deg)
    cohesion_kpa: float = 15.0                  # c': Cohesion intercept (kPa)
    poissons_ratio: float = 0.30                # nu: Poisson's ratio
    mass_density_tonnes_m3: float = 1.95        # rho: Mass density (Mg/m^3 or t/m^3)

    def __post_init__(self):
        if self.max_shear_modulus_gmax_kpa <= 0:
            raise ValueError(f"max_shear_modulus_gmax_kpa must be positive, got {self.max_shear_modulus_gmax_kpa}")
        if self.reference_shear_strain <= 0:
            raise ValueError(f"reference_shear_strain must be positive, got {self.reference_shear_strain}")
        if not (0.5 <= self.curvature_param_a <= 2.0):
            raise ValueError(f"curvature_param_a must be in [0.5, 2.0], got {self.curvature_param_a}")
        if not (0.005 <= self.min_damping_ratio <= 0.10):
            raise ValueError(f"min_damping_ratio must be in [0.005, 0.10], got {self.min_damping_ratio}")
        if not (self.min_damping_ratio < self.max_damping_ratio <= 0.40):
            raise ValueError(f"max_damping_ratio must be in (min_damping, 0.40], got {self.max_damping_ratio}")
        if not (0.0 < self.friction_angle_deg < 55.0):
            raise ValueError(f"friction_angle_deg must be in (0, 55), got {self.friction_angle_deg}")
        if not (0.0 < self.poissons_ratio < 0.50):
            raise ValueError(f"poissons_ratio must be in (0, 0.5), got {self.poissons_ratio}")
        if self.mass_density_tonnes_m3 <= 0:
            raise ValueError(f"mass_density_tonnes_m3 must be positive, got {self.mass_density_tonnes_m3}")

    @property
    def shear_wave_velocity_mps(self) -> float:
        """Small-strain shear wave velocity V_s = sqrt(G_max / rho) in m/s."""
        # G_max in kPa -> Pa (x 1000), rho in tonnes/m^3 -> kg/m^3 (x 1000)
        # V_s = sqrt(G_max_kPa / rho_t_m3)
        return float(math.sqrt(self.max_shear_modulus_gmax_kpa / self.mass_density_tonnes_m3))

    @property
    def max_bulk_modulus_kmax_kpa(self) -> float:
        """Elastic bulk modulus K_max = 2 * G_max * (1 + nu) / [3 * (1 - 2 * nu)]."""
        nu = self.poissons_ratio
        return float((2.0 * self.max_shear_modulus_gmax_kpa * (1.0 + nu)) / (3.0 * (1.0 - 2.0 * nu)))


@dataclass
class CyclicDegradationCurves:
    """
    Continuous strain-dependent modulus degradation and damping curves.
    """
    strains: List[float]                  # Cyclic shear strain amplitudes gamma (decimal)
    strain_percentages: List[float]       # Cyclic shear strain in percent (%)
    modulus_reduction_ratios: List[float] # Normalized modulus G / G_max in [0.0, 1.0]
    secant_shear_moduli_kpa: List[float]  # Secant shear modulus G(gamma) in kPa
    damping_ratios: List[float]           # Hysteretic damping ratio D(gamma) in decimal (e.g. 0.05 = 5%)
    damping_percentages: List[float]      # Hysteretic damping in percent (%)


@dataclass
class MasingHysteresisLoop:
    """
    Stress-strain hysteresis loop under cyclic shear strain amplitude gamma_c
    following extended Masing rules.
    """
    strain_amplitude: float               # Peak cyclic strain amplitude gamma_c
    peak_shear_stress_kpa: float          # Peak shear stress tau_c (kPa)
    strains: List[float]                  # Strain trajectory forming the closed loop
    shear_stresses_kpa: List[float]       # Shear stress trajectory tau(gamma) (kPa)
    loop_energy_dissipation_kpa: float    # Dissipated hysteretic energy Delta_W = int(tau d_gamma) (kPa)
    equivalent_damping_ratio: float       # D = Delta_W / (4 * pi * W_elastic) in decimal


def compute_modulus_reduction(
    shear_strain: float,
    reference_strain: float = 0.0006,
    curvature_a: float = 0.95,
) -> float:
    """
    Computes normalized secant shear modulus reduction ratio G / G_max:
    G / G_max = 1 / [1 + (gamma / gamma_r)^a]
    """
    gamma = abs(float(shear_strain))
    if gamma <= 1e-9:
        return 1.0
    g_ratio = 1.0 / (1.0 + ((gamma / reference_strain) ** curvature_a))
    return float(np.clip(g_ratio, 0.0, 1.0))


def compute_hysteretic_damping(
    shear_strain: float,
    reference_strain: float = 0.0006,
    curvature_a: float = 0.95,
    d_min: float = 0.025,
    d_max: float = 0.28,
    exponent_b: float = 1.10,
) -> float:
    """
    Computes hysteretic damping ratio D(gamma) in decimal:
    D(gamma) = D_min + (D_max - D_min) * [1 - G/G_max(gamma)]^b
    """
    gamma = abs(float(shear_strain))
    if gamma <= 1e-9:
        return d_min
    g_ratio = compute_modulus_reduction(gamma, reference_strain, curvature_a)
    d = d_min + (d_max - d_min) * ((1.0 - g_ratio) ** exponent_b)
    return float(np.clip(d, d_min, d_max))


def generate_cyclic_degradation_curves(
    params: CyclicSoilParameters,
    num_points: int = 50,
    min_strain: float = 1e-6,
    max_strain: float = 0.10,
) -> CyclicDegradationCurves:
    """
    Generates standard log-spaced G/G_max and damping curves across shear strain
    amplitudes from 10^-6 (0.0001%) up to 10^-1 (10%).
    """
    if num_points < 5:
        raise ValueError(f"num_points must be >= 5, got {num_points}")
    if min_strain <= 0 or max_strain <= min_strain:
        raise ValueError(f"Invalid strain range: min={min_strain}, max={max_strain}")

    strains_arr = np.logspace(np.log10(min_strain), np.log10(max_strain), num_points)
    strains: List[float] = []
    strains_pct: List[float] = []
    g_ratios: List[float] = []
    g_secant: List[float] = []
    dampings: List[float] = []
    dampings_pct: List[float] = []

    for gamma in strains_arr:
        g_ratio = compute_modulus_reduction(
            shear_strain=float(gamma),
            reference_strain=params.reference_shear_strain,
            curvature_a=params.curvature_param_a,
        )
        d = compute_hysteretic_damping(
            shear_strain=float(gamma),
            reference_strain=params.reference_shear_strain,
            curvature_a=params.curvature_param_a,
            d_min=params.min_damping_ratio,
            d_max=params.max_damping_ratio,
            exponent_b=params.damping_exponent_b,
        )
        g_sec = g_ratio * params.max_shear_modulus_gmax_kpa

        strains.append(float(gamma))
        strains_pct.append(float(gamma * 100.0))
        g_ratios.append(round(g_ratio, 4))
        g_secant.append(round(g_sec, 2))
        dampings.append(round(d, 4))
        dampings_pct.append(round(d * 100.0, 2))

    return CyclicDegradationCurves(
        strains=strains,
        strain_percentages=strains_pct,
        modulus_reduction_ratios=g_ratios,
        secant_shear_moduli_kpa=g_secant,
        damping_ratios=dampings,
        damping_percentages=dampings_pct,
    )


def compute_backbone_shear_stress(
    shear_strain: float,
    params: CyclicSoilParameters,
) -> float:
    """
    Computes non-linear backbone shear stress tau_bb(gamma) in kPa:
    tau_bb(gamma) = G_max * gamma * G/G_max(gamma)
    """
    gamma = float(shear_strain)
    sign = 1.0 if gamma >= 0 else -1.0
    abs_gamma = abs(gamma)
    g_ratio = compute_modulus_reduction(
        shear_strain=abs_gamma,
        reference_strain=params.reference_shear_strain,
        curvature_a=params.curvature_param_a,
    )
    tau = sign * params.max_shear_modulus_gmax_kpa * abs_gamma * g_ratio
    return float(tau)


def generate_masing_hysteresis_loop(
    params: CyclicSoilParameters,
    strain_amplitude: float = 0.002, # 0.2% cyclic shear strain
    num_points_per_branch: int = 50,
) -> MasingHysteresisLoop:
    """
    Constructs a closed cyclic stress-strain hysteresis loop under cyclic strain amplitude
    gamma_c adhering to Masing (1926) criteria:
    1. Loading branch: tau(gamma) = -tau_c + 2 * tau_bb[(gamma + gamma_c) / 2]
    2. Unloading branch: tau(gamma) = +tau_c - 2 * tau_bb[(gamma_c - gamma) / 2]
    3. Guarantees Masing anti-symmetry: tau(-gamma) = -tau(gamma).
    4. Evaluates loop energy dissipation Delta_W and equivalent damping ratio D.
    """
    if strain_amplitude <= 0:
        raise ValueError(f"strain_amplitude must be positive, got {strain_amplitude}")
    if num_points_per_branch < 5:
        raise ValueError(f"num_points_per_branch must be >= 5, got {num_points_per_branch}")

    gamma_c = float(strain_amplitude)
    tau_c = compute_backbone_shear_stress(gamma_c, params)

    # Branch 1: Loading from -gamma_c to +gamma_c
    gammas_load = np.linspace(-gamma_c, gamma_c, num_points_per_branch)
    taus_load = []
    for g in gammas_load:
        arg = (g + gamma_c) / 2.0
        tau = -tau_c + 2.0 * compute_backbone_shear_stress(arg, params)
        taus_load.append(float(tau))

    # Branch 2: Unloading from +gamma_c back to -gamma_c
    gammas_unload = np.linspace(gamma_c, -gamma_c, num_points_per_branch)
    taus_unload = []
    for g in gammas_unload:
        arg = (gamma_c - g) / 2.0
        tau = tau_c - 2.0 * compute_backbone_shear_stress(arg, params)
        taus_unload.append(float(tau))

    # Combined loop trajectory
    loop_gammas = list(gammas_load) + list(gammas_unload[1:]) # omit duplicate peak
    loop_taus = list(taus_load) + list(taus_unload[1:])

    # Numerical integration of hysteretic area Delta_W = int(tau d_gamma)
    # Using trapezoidal rule on closed loop
    gamma_arr = np.array(loop_gammas)
    tau_arr = np.array(loop_taus)
    # Area by Green's theorem / polygon trapezoid formula
    delta_w = float(
        0.5 * np.abs(np.dot(gamma_arr[:-1], tau_arr[1:]) - np.dot(gamma_arr[1:], tau_arr[:-1]))
    )

    # Elastic strain energy W_e = 0.5 * tau_c * gamma_c
    w_elastic = 0.5 * tau_c * gamma_c

    # Equivalent viscous damping ratio D = Delta_W / (4 * pi * W_e)
    d_equiv = (delta_w / (4.0 * math.pi * w_elastic)) if w_elastic > 0 else params.min_damping_ratio

    return MasingHysteresisLoop(
        strain_amplitude=gamma_c,
        peak_shear_stress_kpa=round(float(tau_c), 2),
        strains=[round(float(g), 6) for g in loop_gammas],
        shear_stresses_kpa=[round(float(t), 2) for t in loop_taus],
        loop_energy_dissipation_kpa=round(float(delta_w), 4),
        equivalent_damping_ratio=round(float(d_equiv), 4),
    )


def generate_opensees_pdmy02_parameters(
    params: CyclicSoilParameters,
    reference_pressure_kpa: float = 100.0,
    number_of_yield_surfaces: int = 20,
) -> Dict[str, Any]:
    """
    Synthesizes calibrated constitutive inputs for the OpenSees
    `PressureDependMultiYield02` (PDMY02) material for residual c-phi hill soils.
    """
    g_max = params.max_shear_modulus_gmax_kpa
    k_max = params.max_bulk_modulus_kmax_kpa
    rho = params.mass_density_tonnes_m3
    phi = params.friction_angle_deg
    c = params.cohesion_kpa

    # Phase transformation angle (typically 2-4 deg below peak friction)
    phi_pt = max(10.0, phi - 4.0)

    # Contraction and dilation parameters calibrated for residual soils
    c1 = 0.065 # Shear-induced contraction rate
    c2 = 5.0   # Contraction rate limiter
    d1 = 0.40  # Peak dilation rate
    d2 = 10.0  # Dilation rate limiter

    return {
        "material_type": "PressureDependMultiYield02",
        "ndm": 2,
        "rho": round(rho, 3),
        "refShearModul": round(g_max, 1),
        "refBulkModul": round(k_max, 1),
        "frictionAng": round(phi, 1),
        "peakShearStra": round(params.reference_shear_strain * 10.0, 4),
        "refPress": round(reference_pressure_kpa, 1),
        "pressDependCoe": 0.50,
        "PTAng": round(phi_pt, 1),
        "contrac_c1": c1,
        "contrac_c2": c2,
        "dilat_d1": d1,
        "dilat_d2": d2,
        "liquefac_l1": 0.0, # Pure non-liquefiable cohesive-frictional soil
        "liquefac_l2": 0.0,
        "noYieldSurf": number_of_yield_surfaces,
        "cohesion": round(c, 2),
    }
