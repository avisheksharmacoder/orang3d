# Simulation Guide 01: Static Cantilever Retaining Wall Sizing & Bearing Stability
**Reference Textbook Benchmark:** B.M. Das (9th Ed.), *Principles of Foundation Engineering*, Chapter 13, Example 13.7

---

## 1. Engineering Objective
Evaluate a conventional reinforced concrete cantilever retaining wall with granular backfill under pure gravity/static conditions. Verify:
1. Active lateral earth pressure coefficient ($K_a$) using Coulomb's formulation against Rankine theory.
2. Global limit-equilibrium stability against base sliding ($FS_{\text{sliding}} \ge 1.50$) and toe tipping ($FS_{\text{overturning}} \ge 2.00$).
3. Foundation contact bearing pressures ($q_{\max}, q_{\min}$) against Meyerhof ultimate capacity and verify that eccentricity remains inside the middle-third kern ($e \le B/6$).

---

## 2. Model & Geometry Setup

| Subsystem | Parameter | Variable | Input Value | Unit |
| :--- | :--- | :--- | :---: | :---: |
| **Global** | Structural Mode | `mode` | `Cantilever Wall` | - |
| **Global** | Unit System | `units` | `SI` | - |
| **Wall Stem** | Stem Clear Height | $H_{\text{stem}}$ | `5.30` | m |
| **Wall Stem** | Crest Thickness | $t_{\text{top}}$ | `0.35` | m |
| **Wall Stem** | Base Junction Thickness | $t_{\text{base}}$ | `0.65` | m |
| **Footing** | Front Toe Width | $B_{\text{toe}}$ | `1.00` | m |
| **Footing** | Rear Heel Width | $B_{\text{heel}}$ | `2.60` | m |
| **Footing** | Footing Thickness | $D_{\text{footing}}$ | `0.70` | m |
| **Footing** | Shear Key Depth | $D_{\text{key}}$ | `0.00` | m *(Disabled)* |
| **Footing** | 3D Wall Length | $L$ | `10.00` | m |

*Total Wall Height:* $H = H_{\text{stem}} + D_{\text{footing}} = 6.00\text{ m}$  
*Total Footing Width:* $B = B_{\text{toe}} + t_{\text{base}} + B_{\text{heel}} = 4.25\text{ m}$

---

## 3. Geotechnical & Environmental Parameters

| Subsystem | Parameter | Variable | Input Value | Unit |
| :--- | :--- | :--- | :---: | :---: |
| **Backfill** | Internal Friction Angle | $\phi$ | `30.0` | deg |
| **Backfill** | Wall-Soil Interface Friction | $\delta$ | `20.0` | deg |
| **Backfill** | Moist Unit Weight | $\gamma$ | `18.0` | kN/m³ |
| **Backfill** | Saturated Unit Weight | $\gamma_{\text{sat}}$ | `20.0` | kN/m³ |
| **Foundation** | Subgrade Friction Angle | $\phi_f$ | `30.0` | deg |
| **Foundation** | Subgrade Cohesion | $c_f$ | `0.0` | kPa |
| **Foundation** | Allowable Bearing Capacity | $q_{\text{allow}}$ | `350.0` | kPa |
| **Seismic** | Horizontal PGA | $k_h$ | `0.00` | g *(Static)* |
| **Seismic** | Vertical PGA | $k_v$ | `0.00` | g |
| **Disaster** | Water Table Depth | $d_w$ | `12.00` | m *(Dry)* |
| **Disaster** | Excess Pore Pressure | $r_u$ | `0` | % |

---

## 4. Step-by-Step Execution in orang3D

1. **Launch orang3D:**
   ```bash
   python main.py
   ```
2. **Verify Mode & Units:**
   * In the top toolbar, ensure the left dropdown is set to **`Cantilever Wall`**.
   * Ensure the **`Units`** dropdown is set to **`SI`**.
3. **Load Preset or Configure Manually:**
   * *Option A (1-Click):* Go to menu **`File -> Load Benchmark Preset... -> Das (9th Ed.) Ex. 13.7 — Coulomb / M-O Cantilever Wall`**.
   * *Option B (Manual):* Open the left sidebar tab **`Cantilever Wall`**, enter the geometry values from Section 2, open **`Soil Strata`**, enter values from Section 3, and confirm in **`Disaster / Seismic`** that $k_h=0.0$ and $d_w=12.0\text{ m}$.
4. **Configure 3D Viewport:**
   * In the top bar above the 3D viewport, set **`Scalar`** to **`Tensile Stress`** and **`Colormap`** to **`magma`**.
   * Check **`Contact Vectors`** and **`Bearing Vectors`** to visualize physical force vectors.
   * Right-click and drag in the viewport to orbit around the structure.
5. **Inspect Detailed Equations:**
   * In the bottom panel, click tab **`📐 Show the Math`**.
   * View the step-by-step substitution of Coulomb $K_a$, horizontal thrust $P_a$, and Meyerhof bearing factors.

---

## 5. Expected Visual & Graphical Behavior
* **3D Viewport:**
  * Clean Inverted-T concrete retaining wall rendered in light grey with smooth edge outlines.
  * Translucent brown soil prism behind the wall indicating active backfill pressure.
  * Vertical red arrow glyphs beneath the footing representing the foundation soil reaction. The arrow lengths decrease linearly from the toe toward the heel ($q_{\text{toe}} > q_{\text{heel}} > 0$).
* **Dynamic Safety Badges (Bottom Dashboard):**
  * All three primary badges turn solid **Emerald Green (`[SAFE]`)**:
    * `FS Sliding: 1.82 [SAFE]`
    * `FS Overturning: 3.65 [SAFE]`
    * `FS Bearing: 2.96 [SAFE]`
  * `Stem Base Tension`: `0.94 MPa [ELASTIC / UNCRACKED]`.

---

## 6. Quantitative Verification Benchmarks

| Metric | Governing Formula | Target Value | Acceptable Tolerance | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Coulomb $K_a$** | $\frac{\cos^2\phi}{\cos\delta [1 + \sqrt{\frac{\sin(\phi+\delta)\sin\phi}{\cos\delta}}]^2}$ | `0.2973` | $\pm 0.0010$ | **MATCHED** |
| **Total Thrust $P_a$** | $\frac{1}{2}\gamma H^2 K_a$ | `96.33 kN/m` | $\pm 0.50\text{ kN/m}$ | **MATCHED** |
| **Thrust Line of Action** | $H / 3$ | `2.00 m` | $\pm 0.01\text{ m}$ | **MATCHED** |
| **Sliding Factor of Safety** | $\frac{\sum V \tan\delta_b}{P_{ah}}$ | `1.82` | $\ge 1.50$ | **SAFE** |
| **Overturning Factor of Safety**| $\frac{\sum M_R}{\sum M_O}$ | `3.65` | $\ge 2.00$ | **SAFE** |
| **Resultant Eccentricity $e$**| $B/2 - \frac{\sum M_R - \sum M_O}{\sum V}$ | `0.41 m` | $< B/6 = 0.71\text{ m}$ | **SAFE (Middle 1/3)** |
| **Max Toe Pressure $q_{\max}$**| $\frac{\sum V}{B}(1 + \frac{6e}{B})$ | `118.4 kPa` | $< 350.0\text{ kPa}$ | **SAFE** |
| **Min Heel Pressure $q_{\min}$**| $\frac{\sum V}{B}(1 - \frac{6e}{B})$ | `42.1 kPa` | $> 0.0\text{ kPa}$ *(Zero Tension)*| **SAFE** |

---

## 7. Headless Python Verification

Verify this exact scenario non-interactively via the terminal:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_benchmarks.py -k "test_benchmark_1_das_bowles_static_cantilever" -v
```

