"""
Topographic Seismic Amplification and Slope Invariant Estimator.
Implements Eurocode 8 (EN 1998-5: 2004 Annex A) and IS 1893 (Part 1: 2016)
topographic crest amplification factors (S_T >= 1.2 for slopes > 15 deg),
spatial attenuation from the crest, resonant frequency estimators, and
slope-modified passive earth pressure resistance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
import numpy as np


@dataclass
class TopographicAmplificationResult:
    """Seismic topographic amplification results at a specific hill-slope location."""
    st_factor: float                    # S_T: Topographic amplification factor (>= 1.0)
    slope_angle_deg: float              # beta: Local ground slope angle in degrees
    crest_distance: float               # L_crest: Distance from wall to the crest/ridge (m)
    hill_height: float                  # H_slope: Total height of the hill slope (m)
    shear_wave_velocity: float          # V_s: Average shear wave velocity in the hill (m/s)
    resonant_frequency_hz: float        # f_0: Fundamental resonant frequency = V_s / (4 * H) (Hz)
    peak_ground_acceleration_base: float # PGA_base: Peak ground acceleration at base (g)
    peak_ground_acceleration_crest: float # PGA_crest: Topographically amplified PGA = S_T * PGA_base (g)
    amplified_acceleration: np.ndarray  # a_amp(t): Time-history array scaled by S_T


def compute_topographic_amplification_factor(
    slope_angle_deg: float,
    crest_distance: float = 0.0,
    hill_height: float = 20.0,
    feature_type: str = "ridge",
) -> float:
    """
    Computes topographic amplification factor S_T per Eurocode 8 (EN 1998-5 Annex A)
    and IS 1893 (Part 1: 2016 Clause 6.4.4):
    - Slopes <= 15 deg: S_T = 1.0 (negligible topographic effect)
    - Slopes 15 deg < beta <= 30 deg: S_T,crest = 1.2
    - Slopes beta > 30 deg:
      - S_T,crest = 1.2 for isolated cliffs and slopes
      - S_T,crest = 1.4 for ridges with crest width << base width
    - Spatial attenuation: S_T(x) = 1.0 + (S_T,crest - 1.0) * exp(-2 * |x| / H_slope)
    """
    if hill_height <= 0:
        raise ValueError(f"hill_height must be positive, got {hill_height}")

    beta = abs(slope_angle_deg)
    x = abs(crest_distance)

    # 1. Peak amplification at the crest S_T,crest
    if beta <= 15.0:
        st_crest = 1.0
    elif beta <= 30.0:
        st_crest = 1.2
    else:
        # beta > 30 deg
        if feature_type.lower() == "ridge":
            st_crest = 1.4
        else:
            # Cliff / isolated slope
            st_crest = 1.2

    # 2. Spatial attenuation with distance from crest
    # Attenuates back to 1.0 within distance ~ H_slope / 2
    decay_length = max(0.5 * hill_height, 1.0)
    st_x = 1.0 + (st_crest - 1.0) * math.exp(-x / decay_length)

    # Enforce physical bounds: 1.0 <= S_T <= S_T,crest
    st_x = max(min(st_x, st_crest), 1.0)
    return float(st_x)


def apply_topographic_amplification(
    time_arr: np.ndarray,
    accel_arr: np.ndarray,
    slope_angle_deg: float,
    crest_distance: float = 0.0,
    hill_height: float = 20.0,
    shear_wave_velocity: float = 250.0,
    feature_type: str = "ridge",
) -> TopographicAmplificationResult:
    """
    Applies Eurocode 8 / IS 1893 topographic amplification to an input ground motion:
        a_crest(t) = S_T * a_base(t)
    Computes hill resonant frequency f_0 = V_s / (4 * H_slope).
    """
    if len(accel_arr) == 0:
        raise ValueError("accel_arr cannot be empty")
    if shear_wave_velocity <= 0:
        raise ValueError(f"shear_wave_velocity must be positive, got {shear_wave_velocity}")

    st = compute_topographic_amplification_factor(
        slope_angle_deg=slope_angle_deg,
        crest_distance=crest_distance,
        hill_height=hill_height,
        feature_type=feature_type,
    )

    pga_base = float(np.max(np.abs(accel_arr)))
    pga_crest = float(pga_base * st)
    amplified_accel = accel_arr * st

    # Fundamental quarter-wavelength resonant frequency f_0 = V_s / (4 * H)
    f_0 = float(shear_wave_velocity / (4.0 * hill_height))

    return TopographicAmplificationResult(
        st_factor=st,
        slope_angle_deg=slope_angle_deg,
        crest_distance=crest_distance,
        hill_height=hill_height,
        shear_wave_velocity=shear_wave_velocity,
        resonant_frequency_hz=f_0,
        peak_ground_acceleration_base=pga_base,
        peak_ground_acceleration_crest=pga_crest,
        amplified_acceleration=amplified_accel,
    )


def compute_slope_modified_passive_resistance(
    kp_level: float,
    slope_angle_deg: float,
    soil_friction_angle_deg: float,
) -> float:
    """
    Computes slope-modified passive earth pressure coefficient K_p,slope
    for retaining structures with ground sloping downward in front of the wall
    (Caquot & Kerisel / Coulomb / IS 1893 Part 3 Table 2):
        K_p,slope = K_p,level * cos^2(beta) * [1 - sin(beta) / sin(phi)]^2
    """
    if kp_level <= 0:
        raise ValueError(f"kp_level must be positive, got {kp_level}")
    if soil_friction_angle_deg <= 0 or soil_friction_angle_deg >= 90:
        raise ValueError(f"soil_friction_angle_deg must be in (0, 90), got {soil_friction_angle_deg}")

    beta_deg = abs(slope_angle_deg)
    if beta_deg >= soil_friction_angle_deg:
        # Slope daylight angle exceeds friction angle -> passive wedge unstable
        return 0.1 * kp_level

    beta_rad = math.radians(beta_deg)
    phi_rad = math.radians(soil_friction_angle_deg)

    reduction = (math.cos(beta_rad) ** 2) * ((1.0 - (math.sin(beta_rad) / math.sin(phi_rad))) ** 2)
    kp_slope = kp_level * max(reduction, 0.05)
    return float(kp_slope)
