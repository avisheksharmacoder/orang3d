"""
Synthetic Earthquake Accelerogram & Disaster Scenario Generators (Phase 5).
Generates Ricker wavelets, harmonic frequency sweeps (chirps), Arias Intensity (Ia),
Cumulative Absolute Velocity (CAV), critical yield acceleration (ky),
and Newmark sliding block numerical integration.
"""

from typing import Tuple, Union
import numpy as np

from ..models.wall_params import RetainingWallGeometry, SoilProperties
from ..physics.mononobe_okabe import compute_mononobe_okabe, compute_lateral_thrusts


def generate_ricker_wavelet(
    pga_g: float = 0.35,
    central_freq_hz: float = 2.5,
    duration_sec: float = 10.0,
    sampling_rate_hz: float = 100.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates a Ricker wavelet accelerogram representing a pulse-like earthquake.
    Formula: a(t) = PGA * (1 - 2*(pi*f0*tau)^2) * exp(-(pi*f0*tau)^2)
    Zero long-term DC velocity offset guaranteed.
    Returns: (time_array, acceleration_g_array)
    """
    num_pts = int(duration_sec * sampling_rate_hz)
    t = np.linspace(0.0, duration_sec, num_pts)
    t0 = duration_sec / 2.0  # Center pulse

    tau = t - t0
    f0 = central_freq_hz
    arg = (np.pi * f0 * tau) ** 2
    accel = pga_g * (1.0 - 2.0 * arg) * np.exp(-arg)

    return t, accel


def generate_harmonic_sweep(
    pga_g: float = 0.30,
    f_start_hz: float = 1.0,
    f_end_hz: float = 8.0,
    duration_sec: float = 15.0,
    sampling_rate_hz: float = 100.0,
    method: str = "linear",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generates a linear or logarithmic frequency sweep (chirp) accelerogram
    to test structural resonance and frequency-dependent SSI.
    Applies a smooth cosine-squared (Tukey) tapering window at both ends.
    """
    num_pts = int(duration_sec * sampling_rate_hz)
    t = np.linspace(0.0, duration_sec, num_pts)
    t_end = max(1e-3, duration_sec)

    if method == "logarithmic":
        f1 = max(0.1, f_start_hz)
        f2 = max(f1 + 0.1, f_end_hz)
        phase = 2.0 * np.pi * f1 * ((f2 / f1) ** (t / t_end) - 1.0) / np.log(f2 / f1)
    else:  # linear
        f_rate = (f_end_hz - f_start_hz) / (2.0 * t_end)
        phase = 2.0 * np.pi * (f_start_hz * t + f_rate * (t ** 2))

    # Cosine-squared window envelope
    envelope = np.sin(np.pi * np.clip(t / t_end, 0.0, 1.0)) ** 2
    accel = pga_g * np.sin(phase) * envelope

    return t, accel


def compute_arias_intensity(
    time_arr: np.ndarray,
    accel_g_arr: np.ndarray,
    g_accel: float = 9.81,
) -> Tuple[np.ndarray, float]:
    """
    Computes Arias Intensity time-history Ia(t) and total Arias Intensity (m/s):
    Ia(t) = (pi / (2 * g)) * integral_0^t (a(tau) * g)^2 dtau
    """
    if len(time_arr) < 2:
        return np.zeros_like(time_arr), 0.0

    dt = time_arr[1] - time_arr[0]
    accel_ms2 = accel_g_arr * g_accel
    integrand = accel_ms2 ** 2

    ia_curve = np.zeros_like(time_arr)
    ia_curve[1:] = (np.pi / (2.0 * g_accel)) * np.cumsum(
        0.5 * (integrand[:-1] + integrand[1:]) * dt
    )
    total_ia = float(ia_curve[-1])

    return ia_curve, total_ia


def compute_cumulative_absolute_velocity(
    time_arr: np.ndarray,
    accel_g_arr: np.ndarray,
    g_accel: float = 9.81,
) -> Tuple[np.ndarray, float]:
    """
    Computes Cumulative Absolute Velocity CAV(t) and total CAV (m/s):
    CAV(t) = integral_0^t |a(tau) * g| dtau
    """
    if len(time_arr) < 2:
        return np.zeros_like(time_arr), 0.0

    dt = time_arr[1] - time_arr[0]
    accel_ms2 = np.abs(accel_g_arr * g_accel)

    cav_curve = np.zeros_like(time_arr)
    cav_curve[1:] = np.cumsum(0.5 * (accel_ms2[:-1] + accel_ms2[1:]) * dt)
    total_cav = float(cav_curve[-1])

    return cav_curve, total_cav


def compute_yield_acceleration_ky(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
) -> float:
    """
    Calculates the critical horizontal yield acceleration coefficient ky (in g)
    at which sliding equilibrium becomes incipient (FS_sliding = 1.0).
    Formula from limit equilibrium:
    R = V_eff * tan(phi_b) + c_b * B + P_passive
    D = P_a + W * ky = R ==> ky = (R - P_a) / W
    """
    gamma_c = geom.concrete_unit_weight
    gamma_s = soil.unit_weight

    # Wall dead weights (kN/m)
    w_footing = geom.base_width * geom.footing_thickness * gamma_c
    w_stem = (
        0.5 * (geom.stem_thickness_base + geom.stem_thickness_top) * geom.stem_height * gamma_c
    )
    w_key = geom.shear_key_width * geom.shear_key_depth * gamma_c
    w_concrete = w_footing + w_stem + w_key
    w_soil_heel = geom.heel_length * geom.stem_height * gamma_s
    w_total = w_concrete + w_soil_heel

    # Sliding resistance
    phi_b = np.radians(soil.foundation_friction_angle * 0.75)
    f_friction = np.tan(phi_b)
    c_adhesion = soil.foundation_cohesion * 0.6
    cohesion_force = c_adhesion * geom.base_width

    # Passive resistance
    from ..physics.mononobe_okabe import compute_rankine_earth_pressures
    _, kp_fund = compute_rankine_earth_pressures(soil.foundation_friction_angle)
    depth_embedded = geom.footing_thickness + geom.shear_key_depth
    p_passive = 0.5 * soil.foundation_unit_weight * (depth_embedded ** 2) * kp_fund

    resisting_force = w_total * f_friction + cohesion_force + p_passive

    # Static Coulomb/Rankine thrust P_a
    _, k_a, _ = compute_mononobe_okabe(
        phi_deg=soil.friction_angle,
        delta_deg=soil.wall_friction_angle,
        kh=0.0,
        kv=0.0,
        beta_deg=0.0,
    )
    p_a = 0.5 * soil.unit_weight * (geom.total_height ** 2) * k_a

    net_resistance = resisting_force - p_a
    ky = net_resistance / max(1.0, w_total)

    return float(np.clip(ky, 0.05, 0.90))


def compute_newmark_sliding_displacement(
    time_arr: np.ndarray,
    accel_g_arr: np.ndarray,
    yield_acceleration_ky: float,
    g_accel: float = 9.81,
) -> Tuple[np.ndarray, float]:
    """
    Performs Newmark Sliding Block analysis (Newmark 1965).
    Calculates cumulative permanent downhill sliding displacement of the retaining wall.
    Double integrates (accel - ky * g) during active sliding phases.
    Returns: (displacement_history_cm, max_slip_cm)
    """
    if len(time_arr) < 2:
        return np.zeros_like(time_arr), 0.0

    dt = time_arr[1] - time_arr[0]
    accel_m_s2 = accel_g_arr * g_accel
    a_yield = max(0.01, yield_acceleration_ky) * g_accel

    velocity = np.zeros_like(time_arr)
    displacement = np.zeros_like(time_arr)

    current_vel = 0.0
    current_disp = 0.0

    for i in range(1, len(time_arr)):
        a_net = accel_m_s2[i] - a_yield
        if a_net > 0.0 or current_vel > 0.0:
            current_vel += a_net * dt
            if current_vel < 0.0:
                current_vel = 0.0  # Block comes to rest
        else:
            current_vel = 0.0

        current_disp += current_vel * dt
        velocity[i] = current_vel
        displacement[i] = current_disp * 100.0  # Convert meters to centimeters (cm)

    max_permanent_slip_cm = float(displacement[-1])
    return displacement, max_permanent_slip_cm
