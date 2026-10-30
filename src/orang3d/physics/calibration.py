"""
Laboratory Soil Test Calibration Wizard and Parameter Optimizer (Phase 7).

Fits non-linear constitutive parameters to physical laboratory test data:
1. Resonant Column & Cyclic Triaxial: Fits G/G_max(gamma) and D(gamma) curves (gamma_r, a, D_min).
2. Pressure Plate / Dewpoint Potentiometer: Fits Van Genuchten SWCC parameters (alpha, n).
3. Triaxial & Direct Shear: Fits Mohr-Coulomb strength envelopes (c, phi).
Computes goodness-of-fit metrics: R^2 determination coefficient and RMSE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from scipy.optimize import curve_fit

from .cyclic_soil import (
    CyclicSoilParameters,
    compute_modulus_reduction,
    compute_hysteretic_damping,
)
from .unsaturated_soil import (
    VanGenuchtenParams,
)


@dataclass
class CalibrationFitResult:
    """Statistical summary and parameter report for laboratory calibration."""
    test_type: str                       # e.g., "Resonant Column", "SWCC", "Direct Shear"
    fitted_parameters: Dict[str, float]  # Parameter name -> calibrated numerical value
    r_squared: float                     # Coefficient of determination R^2 in [0.0, 1.0]
    rmse: float                          # Root Mean Square Error
    num_data_points: int                 # Sample size N
    is_statistically_significant: bool   # True if R^2 >= 0.95


def _r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculates coefficient of determination R^2."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot < 1e-12:
        return 1.0
    r2 = 1.0 - (ss_res / ss_tot)
    return float(np.clip(r2, 0.0, 1.0))


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculates Root Mean Square Error (RMSE)."""
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def fit_cyclic_modulus_reduction_curve(
    measured_shear_strains: List[float] | np.ndarray,
    measured_g_over_gmax: List[float] | np.ndarray,
    initial_gamma_r: float = 0.0006,
    initial_a: float = 0.95,
) -> Tuple[float, float, CalibrationFitResult]:
    """
    Fits modified hyperbolic modulus degradation parameters (gamma_r, a) to
    resonant column or cyclic simple shear test data using non-linear least squares.

    Model:
    G / G_max = 1 / [1 + (gamma / gamma_r)^a]

    Returns:
    - gamma_r (reference shear strain)
    - a (hyperbolic curvature parameter)
    - CalibrationFitResult container with R^2 and RMSE
    """
    gamma_arr = np.array(measured_shear_strains, dtype=np.float64)
    g_arr = np.array(measured_g_over_gmax, dtype=np.float64)

    if len(gamma_arr) < 3:
        raise ValueError("At least 3 data points required for non-linear curve fitting")
    if len(gamma_arr) != len(g_arr):
        raise ValueError(f"Mismatched array lengths: strains={len(gamma_arr)}, G/G_max={len(g_arr)}")
    if np.any(gamma_arr <= 0):
        raise ValueError("Shear strain data must be strictly positive")
    if np.any(g_arr < 0.0) or np.any(g_arr > 1.05):
        raise ValueError("G/G_max values must be in [0.0, 1.05]")

    def hyperbolic_func(gamma, gamma_r, a):
        return 1.0 / (1.0 + ((gamma / gamma_r) ** a))

    popt, _ = curve_fit(
        f=hyperbolic_func,
        xdata=gamma_arr,
        ydata=g_arr,
        p0=[initial_gamma_r, initial_a],
        bounds=([1e-5, 0.50], [0.05, 2.0]),
        maxfev=5000,
    )

    fitted_gamma_r = float(popt[0])
    fitted_a = float(popt[1])

    y_pred = hyperbolic_func(gamma_arr, fitted_gamma_r, fitted_a)
    r2 = _r_squared(g_arr, y_pred)
    rmse = _rmse(g_arr, y_pred)

    result = CalibrationFitResult(
        test_type="Resonant Column (G/G_max)",
        fitted_parameters={
            "reference_shear_strain_gamma_r": round(fitted_gamma_r, 6),
            "curvature_param_a": round(fitted_a, 4),
        },
        r_squared=round(r2, 4),
        rmse=round(rmse, 4),
        num_data_points=len(gamma_arr),
        is_statistically_significant=(r2 >= 0.95),
    )

    return fitted_gamma_r, fitted_a, result


def fit_hysteretic_damping_curve(
    measured_shear_strains: List[float] | np.ndarray,
    measured_damping_ratios: List[float] | np.ndarray,
    reference_strain: float = 0.0006,
    curvature_a: float = 0.95,
    initial_d_min: float = 0.025,
    initial_d_max: float = 0.28,
) -> Tuple[float, float, CalibrationFitResult]:
    """
    Fits minimum small-strain damping D_min and maximum damping D_max to
    cyclic laboratory damping test data.

    Model:
    D(gamma) = D_min + (D_max - D_min) * [1 - G/G_max(gamma)]^b
    """
    gamma_arr = np.array(measured_shear_strains, dtype=np.float64)
    d_arr = np.array(measured_damping_ratios, dtype=np.float64)

    if len(gamma_arr) < 3:
        raise ValueError("At least 3 data points required for damping curve fitting")
    if len(gamma_arr) != len(d_arr):
        raise ValueError(f"Mismatched array lengths: strains={len(gamma_arr)}, D={len(d_arr)}")

    def damping_func(gamma, d_min, d_max):
        g_ratio = 1.0 / (1.0 + ((gamma / reference_strain) ** curvature_a))
        return d_min + (d_max - d_min) * ((1.0 - g_ratio) ** 1.10)

    popt, _ = curve_fit(
        f=damping_func,
        xdata=gamma_arr,
        ydata=d_arr,
        p0=[initial_d_min, initial_d_max],
        bounds=([0.005, 0.15], [0.10, 0.40]),
        maxfev=5000,
    )

    fitted_d_min = float(popt[0])
    fitted_d_max = float(popt[1])

    y_pred = damping_func(gamma_arr, fitted_d_min, fitted_d_max)
    r2 = _r_squared(d_arr, y_pred)
    rmse = _rmse(d_arr, y_pred)

    result = CalibrationFitResult(
        test_type="Cyclic Triaxial (Damping Ratio)",
        fitted_parameters={
            "min_damping_ratio_D_min": round(fitted_d_min, 4),
            "max_damping_ratio_D_max": round(fitted_d_max, 4),
        },
        r_squared=round(r2, 4),
        rmse=round(rmse, 4),
        num_data_points=len(gamma_arr),
        is_statistically_significant=(r2 >= 0.95),
    )

    return fitted_d_min, fitted_d_max, result


def fit_van_genuchten_swcc(
    measured_suctions_kpa: List[float] | np.ndarray,
    measured_degrees_of_saturation: List[float] | np.ndarray,
    residual_saturation: float = 0.15,
    initial_alpha: float = 0.05,
    initial_n: float = 1.60,
) -> Tuple[VanGenuchtenParams, CalibrationFitResult]:
    """
    Fits Van Genuchten (1980) SWCC retention curve parameters (alpha, n) to
    measured pressure-plate or dewpoint potentiometer laboratory data.

    Model:
    S_r(psi) = S_r,res + (1 - S_r,res) * [1 + (alpha * psi)^n]^(-(1 - 1/n))
    """
    psi_arr = np.array(measured_suctions_kpa, dtype=np.float64)
    sr_arr = np.array(measured_degrees_of_saturation, dtype=np.float64)

    if len(psi_arr) < 3:
        raise ValueError("At least 3 data points required for SWCC fitting")
    if len(psi_arr) != len(sr_arr):
        raise ValueError(f"Mismatched array lengths: suctions={len(psi_arr)}, S_r={len(sr_arr)}")
    if np.any(psi_arr < 0):
        raise ValueError("Matric suctions cannot be negative")
    if np.any(sr_arr < 0.0) or np.any(sr_arr > 1.05):
        raise ValueError("Degrees of saturation must be in [0.0, 1.05]")

    def vg_model(psi, alpha, n):
        m = 1.0 - (1.0 / n)
        val = 1.0 + ((alpha * psi) ** n)
        s_e = val ** (-m)
        return residual_saturation + (1.0 - residual_saturation) * s_e

    popt, _ = curve_fit(
        f=vg_model,
        xdata=psi_arr,
        ydata=sr_arr,
        p0=[initial_alpha, initial_n],
        bounds=([0.001, 1.05], [1.0, 5.0]),
        maxfev=5000,
    )

    fitted_alpha = float(popt[0])
    fitted_n = float(popt[1])

    y_pred = vg_model(psi_arr, fitted_alpha, fitted_n)
    r2 = _r_squared(sr_arr, y_pred)
    rmse = _rmse(sr_arr, y_pred)

    fitted_swcc = VanGenuchtenParams(
        alpha_kpa_inv=round(fitted_alpha, 4),
        n_param=round(fitted_n, 3),
        residual_saturation=residual_saturation,
    )

    result = CalibrationFitResult(
        test_type="Soil-Water Characteristic Curve (SWCC)",
        fitted_parameters={
            "alpha_kpa_inv": round(fitted_alpha, 4),
            "n_pore_size_index": round(fitted_n, 3),
            "m_parameter": round(fitted_swcc.m_param, 3),
        },
        r_squared=round(r2, 4),
        rmse=round(rmse, 4),
        num_data_points=len(psi_arr),
        is_statistically_significant=(r2 >= 0.95),
    )

    return fitted_swcc, result


def fit_mohr_coulomb_shear_strength(
    normal_stresses_kpa: List[float] | np.ndarray,
    shear_strengths_kpa: List[float] | np.ndarray,
) -> Tuple[float, float, CalibrationFitResult]:
    """
    Fits classical Mohr-Coulomb shear strength parameters (c, phi) to
    direct shear or triaxial peak failure envelope points using linear regression:
    tau_f = c + sigma_n * tan(phi)
    """
    sig_arr = np.array(normal_stresses_kpa, dtype=np.float64)
    tau_arr = np.array(shear_strengths_kpa, dtype=np.float64)

    if len(sig_arr) < 2:
        raise ValueError("At least 2 stress points required for Mohr-Coulomb envelope fit")
    if len(sig_arr) != len(tau_arr):
        raise ValueError(f"Mismatched array lengths: sigma_n={len(sig_arr)}, tau={len(tau_arr)}")
    if np.any(sig_arr < 0) or np.any(tau_arr < 0):
        raise ValueError("Stresses cannot be negative in shear test data")

    # Linear regression: tau = tan(phi) * sigma + c
    poly = np.polyfit(sig_arr, tau_arr, 1)
    tan_phi = max(0.05, float(poly[0]))
    cohesion_kpa = max(0.0, float(poly[1]))
    phi_deg = math.degrees(math.atan(tan_phi))

    y_pred = cohesion_kpa + sig_arr * tan_phi
    r2 = _r_squared(tau_arr, y_pred)
    rmse = _rmse(tau_arr, y_pred)

    result = CalibrationFitResult(
        test_type="Mohr-Coulomb Failure Envelope",
        fitted_parameters={
            "cohesion_kpa": round(cohesion_kpa, 2),
            "friction_angle_deg": round(phi_deg, 2),
        },
        r_squared=round(r2, 4),
        rmse=round(rmse, 4),
        num_data_points=len(sig_arr),
        is_statistically_significant=(r2 >= 0.95),
    )

    return cohesion_kpa, phi_deg, result
