"""
Unit and benchmark tests for Seismic Signals, Waveform Engine & Newmark Integration (Phase 5).
Covers:
- Ricker wavelets (peak, duration, DC-bias zero velocity offset)
- Linear and Logarithmic harmonic frequency chirps with Tukey envelope
- Arias Intensity (Ia) and Cumulative Absolute Velocity (CAV)
- Critical yield acceleration (ky) from limit-equilibrium
- Newmark sliding block integration (sub-yield vs post-yield monotonicity)
- PEER NGA / COSMOS .AT2 strong-motion parser (CRLF/LF, scientific notation, corrupt files)
- Baseline polynomial correction and Butterworth bandpass filtering
"""

import pytest
import numpy as np
from pathlib import Path

from orang3d.models.wall_params import RetainingWallGeometry, SoilProperties
from orang3d.signals.synthetic import (
    generate_ricker_wavelet,
    generate_harmonic_sweep,
    compute_arias_intensity,
    compute_cumulative_absolute_velocity,
    compute_newmark_sliding_displacement,
    compute_yield_acceleration_ky,
)
from orang3d.signals.at2_parser import (
    parse_at2_file,
    apply_baseline_correction,
    apply_bandpass_filter,
)


def test_ricker_wavelet_peak_and_duration():
    pga = 0.40
    duration = 5.0
    fs = 100.0

    t, a = generate_ricker_wavelet(pga_g=pga, duration_sec=duration, sampling_rate_hz=fs)

    assert len(t) == int(duration * fs)
    assert len(a) == len(t)
    assert t[0] == 0.0
    assert t[-1] == pytest.approx(duration)
    # Peak must be close to requested PGA (+/- 5%)
    assert np.max(np.abs(a)) == pytest.approx(pga, rel=0.05)

    # Energy & DC-Bias Test: Zero long-term DC velocity offset
    _trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
    dt = t[1] - t[0]
    total_velocity_offset = _trapz(a * 9.81, t)
    assert abs(total_velocity_offset) < 0.05, f"DC velocity drift {total_velocity_offset} too large"


def test_harmonic_sweep_linear_and_logarithmic():
    # Linear sweep
    t_lin, a_lin = generate_harmonic_sweep(
        pga_g=0.30, duration_sec=6.0, f_start_hz=1.0, f_end_hz=8.0, method="linear"
    )
    assert len(t_lin) == len(a_lin)
    assert abs(a_lin[0]) < 1e-4
    assert abs(a_lin[-1]) < 1e-4

    # Logarithmic sweep
    t_log, a_log = generate_harmonic_sweep(
        pga_g=0.30, duration_sec=6.0, f_start_hz=1.0, f_end_hz=8.0, method="logarithmic"
    )
    assert len(t_log) == len(a_log)
    assert abs(a_log[0]) < 1e-4
    assert abs(a_log[-1]) < 1e-4


def test_arias_intensity_and_cumulative_absolute_velocity():
    t, a = generate_ricker_wavelet(pga_g=0.35, duration_sec=8.0)

    # Arias Intensity Ia = (pi / 2g) * integral(a^2 dt)
    ia_curve, total_ia = compute_arias_intensity(t, a)
    assert len(ia_curve) == len(t)
    assert total_ia > 0.0
    assert ia_curve[-1] == pytest.approx(total_ia)
    # Ia must be monotonically non-decreasing
    assert np.all(np.diff(ia_curve) >= -1e-8)

    # Cumulative Absolute Velocity CAV = integral(|a| dt)
    cav_curve, total_cav = compute_cumulative_absolute_velocity(t, a)
    assert len(cav_curve) == len(t)
    assert total_cav > 0.0
    assert cav_curve[-1] == pytest.approx(total_cav)
    # CAV must be monotonically non-decreasing
    assert np.all(np.diff(cav_curve) >= -1e-8)


def test_yield_acceleration_ky_limit_equilibrium():
    geom = RetainingWallGeometry(
        stem_height=6.0,
        stem_thickness_base=0.7,
        toe_length=1.0,
        heel_length=2.5,
    )
    soil = SoilProperties(
        friction_angle=32.0,
        foundation_friction_angle=30.0,
        foundation_cohesion=10.0,
    )

    ky = compute_yield_acceleration_ky(geom, soil)
    assert 0.10 <= ky <= 0.60  # Typical engineering range

    # Increasing base width or friction must increase yield acceleration ky
    geom_wider = RetainingWallGeometry(
        stem_height=6.0,
        stem_thickness_base=0.7,
        toe_length=1.5,
        heel_length=3.5,
    )
    ky_wider = compute_yield_acceleration_ky(geom_wider, soil)
    assert ky_wider > ky


def test_newmark_zero_displacement_when_sub_yield():
    """If ground acceleration never exceeds yield acceleration ky, permanent slip is 0."""
    t, a = generate_ricker_wavelet(pga_g=0.20)
    ky = 0.35  # Well above peak (0.20g)

    slip_arr, max_slip = compute_newmark_sliding_displacement(t, a, yield_acceleration_ky=ky)

    assert max_slip == 0.0
    assert np.all(slip_arr == 0.0)


def test_newmark_positive_displacement_when_exceeding_yield():
    """If acceleration exceeds yield ky, irreversible permanent downhill slip accumulates."""
    t, a = generate_ricker_wavelet(pga_g=0.50)
    ky = 0.15  # Below peak

    slip_arr, max_slip = compute_newmark_sliding_displacement(t, a, yield_acceleration_ky=ky)

    assert max_slip > 0.0
    # Permanent displacement is monotonically non-decreasing
    assert np.all(np.diff(slip_arr) >= -1e-8)


def test_at2_parser_with_sample_record(tmp_path: Path):
    # Tests CRLF line endings, scientific notation, and PEER header
    sample_content = (
        "PEER NGA STRONG MOTION RECORD\r\n"
        "TEST EVENT 1999, COMP 090\r\n"
        "ACCELERATION TIME SERIES IN UNITS OF G\r\n"
        "NPTS= 10, DT= 0.020 SEC\r\n"
        " 1.2000E-02 -3.4000E-02  5.6000E-02  8.9000E-02 -1.0200E-01\r\n"
        " 4.5000E-02  1.1000E-02 -5.0000E-03  1.0000E-03  0.0000E+00\r\n"
    )
    file_path = tmp_path / "sample.AT2"
    file_path.write_bytes(sample_content.encode("utf-8"))

    t, a, meta = parse_at2_file(str(file_path))

    assert len(t) == 10
    assert len(a) == 10
    assert meta["dt"] == pytest.approx(0.02)
    assert meta["npts"] == 10
    assert meta["pga_g"] == pytest.approx(0.102)
    assert a[0] == pytest.approx(0.012)
    assert a[4] == pytest.approx(-0.102)


def test_at2_parser_corrupt_file_handling(tmp_path: Path):
    # Non-existent file
    with pytest.raises(FileNotFoundError):
        _ = parse_at2_file("/non/existent/path/file.AT2")

    # Corrupt truncated file (< 4 lines)
    bad_file = tmp_path / "bad.AT2"
    bad_file.write_text("PEER NGA\nLine 2\n")
    with pytest.raises(ValueError, match="fewer than 4 header lines"):
        _ = parse_at2_file(str(bad_file))


def test_baseline_correction_and_filtering():
    """Verify polynomial baseline detrending and Butterworth bandpass filtering."""
    t = np.linspace(0.0, 10.0, 500)
    dt = t[1] - t[0]
    # Synthetic signal with non-zero DC bias + linear drift
    pure_signal = 0.3 * np.sin(2.0 * np.pi * 2.0 * t)
    drift = 0.05 * t + 0.10
    noisy_accel = pure_signal + drift

    # 1. Baseline correction (linear detrending)
    corrected = apply_baseline_correction(noisy_accel, dt=dt, poly_order=1)
    assert len(corrected) == len(noisy_accel)
    # Mean after detrending should be zero
    assert abs(float(np.mean(corrected))) < 1e-6

    # 2. Bandpass filtering (0.1 Hz to 25 Hz)
    filtered = apply_bandpass_filter(corrected, dt=dt, lowcut_hz=0.1, highcut_hz=20.0)
    assert len(filtered) == len(corrected)
    assert np.max(np.abs(filtered)) > 0.0


def test_signals_short_series_and_edge_cases():
    """Test boundary conditions for single-sample and invalid signal filtering/integrations."""
    t_empty = np.array([0.0])
    a_empty = np.array([0.5])

    ia_arr, total_ia = compute_arias_intensity(t_empty, a_empty)
    assert total_ia == 0.0
    assert len(ia_arr) == 1

    cav_arr, total_cav = compute_cumulative_absolute_velocity(t_empty, a_empty)
    assert total_cav == 0.0
    assert len(cav_arr) == 1

    disp_arr, max_slip = compute_newmark_sliding_displacement(t_empty, a_empty, yield_acceleration_ky=0.2)
    assert max_slip == 0.0
    assert len(disp_arr) == 1

    # Short array baseline correction
    base_short = apply_baseline_correction(np.array([0.5]), dt=0.01, poly_order=1)
    assert len(base_short) == 1

    # Filtering edge cases: short array, invalid dt, or inverted cuts
    f_short = apply_bandpass_filter(np.array([0.1, 0.2]), dt=0.01, order=4)
    assert len(f_short) == 2

    f_bad_dt = apply_bandpass_filter(np.ones(50), dt=0.0)
    assert len(f_bad_dt) == 50

    f_inverted = apply_bandpass_filter(np.ones(50), dt=0.01, lowcut_hz=20.0, highcut_hz=5.0)
    assert len(f_inverted) == 50
