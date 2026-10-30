"""
Parser for standard PEER / COSMOS / PESMOS .AT2 strong motion earthquake files.
"""

import numpy as np
from typing import Tuple, Dict, Any
from pathlib import Path


def parse_at2_file(filepath: str) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Parses a PEER NGA .AT2 accelerogram text file.
    Returns:
    - time_array (seconds)
    - acceleration_array (in units of g)
    - metadata dictionary (event name, station, dt, npts)
    """
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"AT2 record file not found: {filepath}")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    if len(lines) < 4:
        raise ValueError("Invalid AT2 file format: fewer than 4 header lines.")

    header_line_1 = lines[0].strip()
    header_line_2 = lines[1].strip()
    header_line_3 = lines[2].strip()
    line_4 = lines[3].strip()

    # Line 4 typically format: "NPTS=  4000, DT= 0.0100 SEC" or similar
    import re
    npts = 0
    dt = 0.01

    npts_match = re.search(r"NPTS\s*=\s*(\d+)", line_4, re.IGNORECASE)
    if npts_match:
        npts = int(npts_match.group(1))

    dt_match = re.search(r"DT\s*=\s*([\d\.]+)", line_4, re.IGNORECASE)
    if dt_match:
        dt = float(dt_match.group(1))

    # Read acceleration values from line 5 onwards
    accel_values = []
    for line in lines[4:]:
        vals = line.split()
        for v in vals:
            try:
                accel_values.append(float(v))
            except ValueError:
                continue

    accel_arr = np.array(accel_values, dtype=np.float32)
    if npts > 0 and len(accel_arr) > npts:
        accel_arr = accel_arr[:npts]

    duration = len(accel_arr) * dt
    time_arr = np.linspace(0.0, duration, len(accel_arr), endpoint=False)

    metadata = {
        "event": header_line_1,
        "station": header_line_2,
        "component": header_line_3,
        "dt": dt,
        "npts": len(accel_arr),
        "pga_g": float(np.max(np.abs(accel_arr))) if len(accel_arr) > 0 else 0.0,
    }

    return time_arr, accel_arr, metadata


def apply_baseline_correction(
    accel: np.ndarray,
    dt: float = 0.01,
    poly_order: int = 1,
) -> np.ndarray:
    """
    Applies polynomial detrending baseline correction to acceleration time series.
    Removes low-frequency baseline drift, permanent tilt offset, and instrument shift.
    """
    accel_arr = np.asarray(accel, dtype=np.float64)
    n = len(accel_arr)
    if n <= poly_order:
        return accel_arr.copy()

    t = np.arange(n) * dt
    poly_coeffs = np.polyfit(t, accel_arr, deg=poly_order)
    trend = np.polyval(poly_coeffs, t)
    corrected = accel_arr - trend

    return corrected


def apply_bandpass_filter(
    accel: np.ndarray,
    dt: float = 0.01,
    lowcut_hz: float = 0.1,
    highcut_hz: float = 25.0,
    order: int = 4,
) -> np.ndarray:
    """
    Applies zero-phase forward-backward Butterworth bandpass filter.
    Removes very high frequency numerical noise and very long period baseline wander.
    """
    accel_arr = np.asarray(accel, dtype=np.float64)
    n = len(accel_arr)
    if n < 3 * order or dt <= 0.0:
        return accel_arr.copy()

    fs = 1.0 / dt
    nyq = 0.5 * fs

    low = max(1e-4, lowcut_hz) / nyq
    high = min(nyq - 1e-4, highcut_hz) / nyq

    if low >= high or high >= 1.0:
        return accel_arr.copy()

    from scipy.signal import butter, filtfilt

    b, a = butter(order, [low, high], btype="bandpass")
    filtered = filtfilt(b, a, accel_arr)

    return filtered
