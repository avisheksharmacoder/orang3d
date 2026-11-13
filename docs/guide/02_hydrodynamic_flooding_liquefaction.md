# Simulation Guide 02: Hydrodynamic Disaster — Groundwater Flooding & Soil Liquefaction
**Reference Literature Benchmark:** Terzaghi, Peck & Mesri (1996), *Soil Mechanics in Engineering Practice*, 3rd Ed.

---

## 1. Engineering Objective
Simulate extreme monsoon inundation leading to an elevated phreatic groundwater table behind the retaining wall, coupled with earthquake-induced excess pore-water pressure generation ($r_u = \Delta u / \sigma'_{v0}$). Demonstrate:
1. Reduction of effective soil stresses ($\sigma' = \sigma - u$) and loss of shear strength ($\tau_f = \sigma' \tan\phi'$).
2. Development of hydrostatic lateral water thrust ($P_w = \frac{1}{2} \gamma_w H_w^2$) and buoyant foundation uplift.
3. Rapid degradation of the sliding safety factor below unity ($FS_{\text{sliding}} < 1.0$), transitioning the wall into active geotechnical failure.
4. Concrete stem cracking at the base junction when tensile bending stress exceeds the concrete modulus of rupture ($f_r$).

---

## 2. Model & Geometry Setup

| Subsystem | Parameter | Variable | Input Value | Unit |
| :--- | :--- | :--- | :---: | :---: |
| **Global** | Structural Mode | `mode` | `Cantilever Wall` | - |
| **Wall Stem** | Stem Clear Height | $H_{\text{stem}}$ | `6.20` | m |
| **Wall Stem** | Crest Thickness | $t_{\text{top}}$ | `0.35` | m |
| **Wall Stem** | Base Junction Thickness | $t_{\text{base}}$ | `0.80` | m |
| **Footing** | Front Toe Width | $B_{\text{toe}}$ | `1.30` | m |
| **Footing** | Rear Heel Width | $B_{\text{heel}}$ | `2.60` | m |
| **Footing** | Footing Thickness | $D_{\text{footing}}$ | `0.85` | m |
| **Footing** | Shear Key Depth | $D_{\text{key}}$ | `0.00` | m *(Disabled)* |
| **Footing** | 3D Wall Length | $L$ | `8.00` | m |

---

## 3. Geotechnical & Environmental Parameters

| Subsystem | Parameter | Variable | Input Value | Unit |
| :--- | :--- | :--- | :---: | :---: |
| **Backfill** | Internal Friction Angle | $\phi$ | `34.0` | deg |
| **Backfill** | Wall-Soil Interface Friction | $\delta$ | `20.0` | deg |
| **Backfill** | Moist Unit Weight | $\gamma$ | `18.5` | kN/m³ |
| **Backfill** | Saturated Unit Weight | $\gamma_{\text{sat}}$ | `20.5` | kN/m³ |
| **Foundation** | Subgrade Friction Angle | $\phi_f$ | `32.0` | deg |
| **Foundation** | Allowable Bearing Capacity | $q_{\text{allow}}$ | `350.0` | kPa |
| **Seismic** | Horizontal PGA | $k_h$ | `0.15` | g |
| **Seismic** | Vertical PGA | $k_v$ | `0.05` | g |
| **Disaster** | Water Table Depth | $d_w$ | `2.00` | m *(Submerging 5.05 m)* |
| **Disaster** | Excess Pore Pressure | $r_u$ | `45` | % |

---

## 4. Step-by-Step Execution in orang3D

1. **Initialize Baseline:**
   * Select **`Cantilever Wall`** from the top toolbar dropdown.
   * Open the left sidebar tab **`Cantilever Wall`** and enter the dimensions from Section 2.
   * Open tab **`Soil Strata`** and input the backfill and foundation properties from Section 3.
2. **Observe Baseline Dry State:**
   * In **`Disaster / Seismic`**, temporarily set **`Water Depth`** to `12.00 m` and **`Liquefaction`** to `0%`.
   * Note the safety badges in the bottom dashboard: all are green (`FS Sliding > 1.50`).
3. **Simulate Phreatic Water Table Rise:**
   * Slowly drag the **`Water Depth`** spinbox down from `12.00 m` to `2.00 m`.
   * Watch the 3D viewport: a translucent blue plane cuts through the soil prism at elevation $y = 5.05\text{ m}$.
   * Observe the lateral thrust readout jump upward by over $120\text{ kN/m}$.
4. **Induce Seismic Backfill Liquefaction:**
   * In the **`Disaster / Seismic`** tab, slide the **`Liquefaction (r_u)`** slider from `0%` to `45%`.
   * Watch the effective friction angle degrade in real time ($\tan\phi' = (1 - r_u)\tan\phi \implies \phi' \approx 20.3^\circ$).
5. **Inspect Dynamic Cracking & Failure:**
   * Switch the 3D viewport scalar to **`Scalar: Von Mises Stress`**.
   * Note the high stress concentration (bright yellow) at the re-entrant corner between stem and footing.
   * Review the bottom tab **`📋 Design Audit (IS / EC7 / AASHTO / ACI)`**.

---

## 5. Expected Visual & Graphical Behavior
* **3D Viewport:**
  * Translucent cyan water table plane rendered through the backfill with dynamic wave ripple perturbations.
  * The concrete stem develops high bending tensile stresses at the base ($> 3.5\text{ MPa}$).
* **Dynamic Safety Badges (Bottom Dashboard):**
  * `FS Sliding` flips to **`Crimson Red [FAIL]`** with value `0.68`.
  * `FS Overturning` degrades to **`Yellow [MARGINAL]`** with value `1.32`.
  * `Stem Base Tension` flashes **`Red [CRACKED]`** with tensile stress exceeding the concrete cracking modulus $f_r = 3.1\text{ MPa}$.

---

## 6. Quantitative Verification Benchmarks

| Metric | Governing Formula | Target Value | Acceptable Tolerance | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Hydrostatic Water Thrust $P_w$** | $\frac{1}{2}\gamma_w (H - d_w)^2$ | `125.1 kN/m` | $\pm 2.0\text{ kN/m}$ | **MATCHED** |
| **Effective Soil Thrust $P'_a$** | $\frac{1}{2}\gamma'(H - d_w)^2 K_a + \frac{1}{2}\gamma d_w^2 K_a$ | `102.4 kN/m` | $\pm 3.0\text{ kN/m}$ | **MATCHED** |
| **Degraded Friction Angle $\phi'$** | $\arctan((1 - r_u)\tan\phi)$ | `20.35°` | $\pm 0.20^\circ$ | **MATCHED** |
| **Combined Driving Force $P_{\text{total}}$** | $P'_a + P_w + P_{\text{seismic}}$ | `265.8 kN/m` | $\pm 5.0\text{ kN/m}$ | **MATCHED** |
| **Sliding Factor of Safety** | $\frac{\sum V' \tan\delta_b}{P_{\text{total}}}$ | `0.68` | $< 1.00$ | 🔴 **FAIL (Sliding)** |
| **Overturning Factor of Safety**| $\frac{\sum M_R}{\sum M_O}$ | `1.32` | $< 1.50$ | 🟡 **MARGINAL** |
| **Stem Tensile Stress $\sigma_t$** | $M_{\text{base}} / Z_{\text{base}}$ | `3.68 MPa` | $> f_r = 3.10\text{ MPa}$ | 🔴 **CRACKED** |

---

## 7. Headless Python Verification

Verify this exact scenario non-interactively via the terminal:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_benchmarks.py -k "test_benchmark_2_terzaghi_submerged_backfill" -v
```

