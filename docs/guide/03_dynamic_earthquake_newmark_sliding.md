# Simulation Guide 03: Dynamic Earthquake Waveform Playback & Newmark Permanent Sliding
**Reference Literature Benchmark:** Kramer, S. L. (1996), *Geotechnical Earthquake Engineering*, Prentice Hall, Chapter 11

---

## 1. Engineering Objective
Simulate real-time 60 FPS seismic ground motion propagation through a retaining wall-soil system. Demonstrate:
1. Computation of the critical limit-equilibrium yield acceleration ($k_y$) at which the wall sliding safety factor reaches $1.0$.
2. Application of the classical Newmark (1965) sliding block double-integration method.
3. Verification of the fundamental sub-yield physical invariant: zero permanent displacement ($u(t) \equiv 0.0\text{ cm}$) when ground motion peak acceleration remains below $k_y$.
4. Progressive irreversible downhill permanent sliding accumulation ($u(t) > 0$) when ground shaking pulses exceed $k_y$.
5. Elevation shift of the dynamic earth pressure resultant centroid according to the Seed & Whitman (1970) formulation ($y_{\text{res}} \to 0.60 H$).

---

## 2. Model & Geometry Setup

| Subsystem | Parameter | Variable | Input Value | Unit |
| :--- | :--- | :--- | :---: | :---: |
| **Global** | Structural Mode | `mode` | `Cantilever Wall` | - |
| **Wall Stem** | Stem Clear Height | $H_{\text{stem}}$ | `5.00` | m |
| **Wall Stem** | Crest Thickness | $t_{\text{top}}$ | `0.35` | m |
| **Wall Stem** | Base Junction Thickness | $t_{\text{base}}$ | `0.60` | m |
| **Footing** | Front Toe Width | $B_{\text{toe}}$ | `0.80` | m |
| **Footing** | Rear Heel Width | $B_{\text{heel}}$ | `2.20` | m |
| **Footing** | Footing Thickness | $D_{\text{footing}}$ | `0.60` | m *(Total $H = 5.60\text{ m}$)* |
| **Footing** | Shear Key Depth | $D_{\text{key}}$ | `0.00` | m |
| **Footing** | 3D Wall Length | $L$ | `8.00` | m |

---

## 3. Geotechnical & Earthquake Waveform Parameters

| Subsystem | Parameter | Variable | Input Value | Unit |
| :--- | :--- | :--- | :---: | :---: |
| **Backfill** | Internal Friction Angle | $\phi$ | `34.0` | deg |
| **Backfill** | Wall Friction Angle | $\delta$ | `17.0` | deg |
| **Backfill** | Unit Weight | $\gamma$ | `18.5` | kN/m³ |
| **Foundation** | Subgrade Friction Angle | $\phi_f$ | `32.0` | deg |
| **Foundation** | Allowable Bearing Capacity | $q_{\text{allow}}$ | `350.0` | kPa |
| **Earthquake** | Synthetic Signal Type | `type` | `Ricker Wavelet` | - |
| **Earthquake** | Peak Ground Acceleration | $\text{PGA}$ | `0.45` | g |
| **Earthquake** | Dominant Frequency | $f_0$ | `2.50` | Hz |
| **Earthquake** | Record Duration | $T$ | `10.0` | s |
| **Earthquake** | Sampling Frequency | $f_s$ | `100.0` | Hz |

---

## 4. Step-by-Step Execution in orang3D

1. **Load Benchmark Preset:**
   * Go to menu **`File -> Load Benchmark Preset... -> Kramer (1996) — Seed-Whitman & Newmark Sliding Wall`**.
   * The geometry, soil, and Ricker waveform parameters populate automatically.
2. **Navigate to the 2D Waveform Dashboard:**
   * Click the bottom tab **`📊 Seismic Waveforms & Dynamics`**.
   * Note the three vertically stacked PyQtGraph plots:
     1. *Top (Cyan):* Acceleration history $a(t)$ in units of $g$.
     2. *Middle (Orange):* Cumulative Newmark permanent sliding displacement $u(t)$ in $\text{cm}$.
     3. *Bottom (Green):* Dynamic pore pressure history $u_w(t)$ in $\text{kPa}$.
3. **Execute 60 FPS Real-Time Simulation:**
   * In the top toolbar, click **`▶ Play Seismic Wave`** (or press Spacebar).
   * Observe the yellow playhead scrub across the time domain.
   * Watch the wall vibrate in the 3D viewport, deflecting outward and sliding forward.
4. **Interactive Playhead Scrubbing:**
   * Click and drag the yellow playhead line on any of the waveform graphs to jump to $t = 2.0\text{ s}$ (the peak acceleration pulse).
   * Notice that the 3D viewport instantaneously morphs to show the exact wall deformation and stress state corresponding to that timestamp.
5. **Adjust Playback Rate:**
   * On the right transport bar below the charts, click the speed dropdown to select `0.5x` (slow motion) or `2.0x`.
   * Click **`Loop`** to observe continuous repetitive earthquake cycles.

---

## 5. Expected Visual & Graphical Behavior
* **3D Viewport:**
  * Active Coulomb failure wedge shears away from the backfill prism, translating forward and downward along the failure angle ($\alpha = 45^\circ + \phi/2 - 20 k_h$).
  * The concrete stem flexes horizontally; color contours animate dynamically showing cyclic stress reversals.
* **2D Waveform Plots:**
  * The top cyan acceleration curve oscillates between $-0.45\text{ g}$ and $+0.45\text{ g}$.
  * The middle orange curve remains strictly at $0.00\text{ cm}$ until $t \approx 1.85\text{ s}$. As the primary shockwave pulse exceeds the critical yield threshold $k_y = 0.244\text{ g}$, the orange line steps upward and plateaus at $u_{\text{final}} \approx 1.36\text{ cm}$.

---

## 6. Quantitative Verification Benchmarks

| Metric | Governing Formula | Target Value | Acceptable Tolerance | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Static Coulomb $K_a$** | Closed-form Coulomb equation | `0.2564` | $\pm 0.0010$ | **MATCHED** |
| **Mononobe-Okabe $K_{ae}$** | M-O equation ($k_h = 0.25$) | `0.4387` | $\pm 0.0050$ | **MATCHED** |
| **Dynamic Thrust Amplification**| $(K_{ae} - K_a) / K_a$ | `+71.1%` | $\pm 2.0\%$ | **MATCHED** |
| **Yield Acceleration $k_y$** | Limit-equilibrium sliding equilibrium | `0.2436 g` | $\pm 0.0050\text{ g}$ | **MATCHED** |
| **Sub-Yield Invariant** | $u(t)$ for $a(t) \le k_y$ | `0.000 cm` | Exactly `0.000` | **VERIFIED** |
| **Final Permanent Slip $u_p$**| $\iint \max(0, a(t) - k_y g) dt^2$ | `1.36 cm` | $\pm 0.15\text{ cm}$ | **MATCHED** |
| **Dynamic Centroid Rise** | Seed & Whitman (1970) | `3.25 m` | $0.55 - 0.60 H$ | **MATCHED** |

---

## 7. Headless Python Verification

Verify this exact scenario non-interactively via the terminal:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_benchmarks.py -k "test_benchmark_3_kramer_seed_whitman_dynamic_thrust or test_benchmark_4_newmark_jibson_sliding_displacement" -v
```

