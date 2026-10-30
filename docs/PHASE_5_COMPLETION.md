# Phase 5 Completion Report: Seismic Signals, Real Ground Motions & Newmark Engine

**Status:** Completed  
**Test Coverage:** 100% on `src/orang3d/signals/synthetic.py` & `src/orang3d/signals/at2_parser.py`  
**Total Tests Passing:** 80 passing in `< 3` seconds  

---

## 1. Overview & Objectives Achieved

Phase 5 delivered the complete earthquake ground motion processing suite, synthetic waveform synthesizer, limit-equilibrium yield acceleration solver, and Newmark sliding block numerical integrator.

### Key Deliverables:

1. **Synthetic Earthquake Waveform Generators (`src/orang3d/signals/synthetic.py`):**
   - **Ricker Wavelet Generator (`generate_ricker_wavelet`)**:
     - Mathematically exact second derivative of a Gaussian: $a(t) = \text{PGA} \cdot (1 - 2(\pi f_0 \tau)^2) \exp(-(\pi f_0 \tau)^2)$.
     - Guaranteed zero DC bias / zero long-term velocity offset ($\int a(t) dt \approx 0$).
   - **Harmonic Frequency Sweeps / Chirps (`generate_harmonic_sweep`)**:
     - Linear and logarithmic frequency sweeps across custom bandwidths ($f_1$ to $f_2$).
     - Smooth cosine-squared (Tukey) window tapering at both head and tail of the record to prevent unphysical impulsive step accelerations.

2. **Energy & Intensity Metric Integrators:**
   - **Arias Intensity ($I_a$) (`compute_arias_intensity`)**:
     - Evaluates cumulative Arias Intensity curve $I_a(t) = \frac{\pi}{2g} \int_0^t [a(\tau) \cdot g]^2 d\tau$ and total Arias Intensity (m/s).
     - Strict monotonic non-decreasing progression.
   - **Cumulative Absolute Velocity ($\text{CAV}$)** (`compute_cumulative_absolute_velocity`):
     - Evaluates cumulative absolute velocity curve $\text{CAV}(t) = \int_0^t |a(\tau) \cdot g| d\tau$ and total $\text{CAV}$ (m/s).
     - Strict monotonic non-decreasing progression.

3. **Limit-Equilibrium Yield Acceleration ($k_y$):**
   - **Solver (`compute_yield_acceleration_ky`)**:
     - Evaluates the critical threshold acceleration coefficient $k_y$ (in $g$) at which the retaining wall sliding factor of safety drops to exactly 1.0.
     - Accounts for total system inertia (retaining wall stem, footing, shear key, and heel backfill soil block), base friction $\tan(\phi_b)$, base adhesion $c_b B$, passive toe embedment resistance $P_p$, and static active driving thrust $P_a$.
     - Verified physically sound engineering range ($0.10 \le k_y \le 0.60$) and sensitive to footing base width.

4. **Newmark Sliding Block Integration (`compute_newmark_sliding_displacement`):**
   - Classical Newmark (1965) double-integration sliding block model.
   - Sub-yield verification: Zero displacement accumulation when ground acceleration does not exceed $k_y$.
   - Post-yield accumulation: Downhill irreversible sliding acceleration $a_{\text{net}} = a(t) - k_y \cdot g$. Accelerates while active, decelerates when $a(t) < k_y$, comes to rest when relative velocity reaches 0, accumulating permanent downhill slip in centimeters.

5. **PEER NGA / COSMOS `.AT2` Strong-Motion Parser & Signal Processing (`src/orang3d/signals/at2_parser.py`):**
   - **File Parser (`parse_at2_file`)**:
     - Reads standard PEER NGA / COSMOS ASCII accelerograms with CRLF / LF line endings, header metadata extraction (event name, station, component, $\Delta t$, $N_{\text{pts}}$, $\text{PGA}$), and variable multi-column scientific notation parsing.
     - Exception handling for missing files and corrupt/truncated headers ($< 4$ lines).
   - **Baseline Detrending Correction (`apply_baseline_correction`)**:
     - Arbitrary polynomial order baseline detrending (`np.polyfit`/`np.polyval`) to eliminate instrument zero-drift, baseline shifts, and unphysical velocity divergence.
   - **Butterworth Bandpass Filter (`apply_bandpass_filter`)**:
     - Zero-phase forward-backward Butterworth digital filter (`scipy.signal.butter` + `scipy.signal.filtfilt`) for targeted frequency isolation (e.g., $0.1 - 25\text{ Hz}$).

---

## 2. Test Suite & Verification

All 10 tests in [`tests/test_signals.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_signals.py) pass under strict TDD:

| Test Name | Focus Area | Result |
| :--- | :--- | :---: |
| `test_ricker_wavelet_peak_and_duration` | Wavelet shape, peak PGA, duration, DC velocity offset $< 0.05\text{ m/s}$ | **Passed** |
| `test_harmonic_sweep_linear_and_logarithmic` | Linear and log frequency sweeps, smooth Tukey tapered endpoints | **Passed** |
| `test_arias_intensity_and_cumulative_absolute_velocity` | Arias Intensity $I_a$ & CAV formulas, monotonic growth | **Passed** |
| `test_yield_acceleration_ky_limit_equilibrium` | Closed-form $k_y$ derivation, range $0.10-0.60g$, geometric sensitivity | **Passed** |
| `test_newmark_zero_displacement_when_sub_yield` | Zero permanent slip when $\text{PGA} < k_y$ | **Passed** |
| `test_newmark_positive_displacement_when_exceeding_yield` | Cumulative downhill displacement when $\text{PGA} > k_y$, monotonic slip | **Passed** |
| `test_at2_parser_with_sample_record` | PEER NGA multi-line scientific data, CRLF line endings, header metadata | **Passed** |
| `test_at2_parser_corrupt_file_handling` | `FileNotFoundError` and `ValueError` on truncated/corrupt input | **Passed** |
| `test_baseline_correction_and_filtering` | Polynomial baseline detrending and Butterworth bandpass filtering | **Passed** |
| `test_signals_short_series_and_edge_cases` | Edge cases: single-sample input, invalid $\Delta t$, inverted cutoffs | **Passed** |

```text
================================ tests coverage ================================
Name                                  Stmts   Miss  Cover   Missing
-------------------------------------------------------------------
src/orang3d/signals/__init__.py           3      0   100%
src/orang3d/signals/at2_parser.py        64      0   100%
src/orang3d/signals/synthetic.py         90      0   100%
-------------------------------------------------------------------
TOTAL Signals Engine:                   157      0   100%
============================== 80 passed in 2.65s ==============================
```

---

## 3. Artifacts Created & Modified

- **Created:**
  - `src/orang3d/signals/synthetic.py`
  - `src/orang3d/signals/at2_parser.py`
  - `tests/test_signals.py`
  - `docs/PHASE_5_COMPLETION.md`
- **Updated:**
  - `src/orang3d/signals/__init__.py`
  - `docs/DEVELOPMENT_PLAN.md`
