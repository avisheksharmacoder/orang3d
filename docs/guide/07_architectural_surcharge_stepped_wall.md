# Simulation Guide 07: Architectural Surcharge Coupling & Stepped Terraced Walls
**Engineering Discipline:** Urban Geotechnical Infrastructure & Landscape Architecture

---

## 1. Engineering Objective
Evaluate the structural and geotechnical performance of complex architectural retaining systems in dense urban settings:
1. Model multi-tier stepped/terraced retaining wall morphologies with intermediate benches.
2. Ingest adjacent building foundation loads (shallow strip or isolated pad footing) and surface traffic surcharges.
3. Apply modified Boussinesq elastic stress theory (with a rigid wall boundary reflection factor of 2.0) to compute lateral surcharge pressure distributions down the stem.
4. Verify global sliding, overturning, and inter-tier interference stability for multi-level terraced hillsides.

---

## 2. Model & Geometry Setup

| Subsystem | Parameter | Variable | Input Value | Unit |
| :--- | :--- | :--- | :---: | :---: |
| **Global** | Structural Mode | `mode` | `Cantilever Wall` | - |
| **Morphology** | Wall Typology | `type` | `Stepped / Terraced` | - |
| **Tier 1 (Lower)**| Lower Tier Height | $H_1$ | `3.50` | m |
| **Tier 1 (Lower)**| Lower Base Thickness | $t_{b1}$ | `0.60` | m |
| **Tier 1 (Lower)**| Lower Footing Width | $B_1$ | `2.80` | m |
| **Tier 2 (Upper)**| Upper Tier Height | $H_2$ | `3.00` | m |
| **Tier 2 (Upper)**| Upper Base Thickness | $t_{b2}$ | `0.50` | m |
| **Tier 2 (Upper)**| Upper Footing Width | $B_2$ | `2.20` | m |
| **Terrace Bench** | Intermediate Bench Width | $W_{\text{bench}}$ | `2.50` | m |
| **Terrace Bench** | Intermediate Bench Slope | $\beta_{\text{bench}}$ | `0.0` | deg |

---

## 3. Adjacent Surcharge Parameters

| Subsystem | Parameter | Variable | Input Value | Unit |
| :--- | :--- | :--- | :---: | :---: |
| **Surcharge** | Load Type | `load_type` | `Adjacent Building Strip Footing` | - |
| **Footing** | Footing Width | $B_f$ | `1.50` | m |
| **Footing** | Footing Depth | $D_f$ | `0.80` | m below surface |
| **Footing** | Crest Setback Distance | $x_f$ | `2.00` | m from upper crest |
| **Footing** | Vertical Design Load | $Q_{\text{bld}}$ | `180.0` | kN/m |
| **Traffic** | Uniform Surface Surcharge| $q_{\text{traffic}}$ | `12.0` | kPa |

---

## 4. Step-by-Step Execution in orang3D

1. **Open Architectural Configuration Panel:**
   * In the left sidebar, click the tab **`Arch. & Surcharge`**.
2. **Select Wall Morphology:**
   * In the **`Architectural Morphology`** dropdown, select **`Stepped / Terraced Retaining Wall`**.
   * Enter the tier heights ($H_1 = 3.5\text{ m}, H_2 = 3.0\text{ m}$) and bench width ($W_{\text{bench}} = 2.5\text{ m}$).
3. **Configure Building Surcharge:**
   * In the **`Adjacent Surcharges`** section, check **`Enable Adjacent Surcharge`**.
   * Set **`Load Type`** to **`Adjacent Building Strip Footing`**.
   * Enter setback $x_f = 2.0\text{ m}$, width $B_f = 1.5\text{ m}$, and load $Q_{\text{bld}} = 180.0\text{ kN/m}$.
4. **Inspect in 3D Viewport:**
   * Notice the 3D rendered terraced profile: two staggered concrete retaining walls separated by a flat intermediate bench.
   * A translucent grey rectangular block represents the building strip footing.
   * In the viewport toolbar, select **`Scalar: Tensile Stress`** and check **`Contact Vectors`**.
5. **Inspect Cross-Sectional Stress:**
   * In the viewport toolbar, select **`Slice Plane: X Cut`** and move the slice slider to `50%`.
   * Examine the internal stress distribution inside the concrete stem and footing junctions.

---

## 5. Expected Visual & Graphical Behavior
* **3D Viewport:**
  * Two clean concrete tiers with the intermediate terrace bench.
  * Vector arrows along the upper tier stem indicate combined lateral earth pressure and concentrated building surcharge push.
* **Bottom Panel (`📊 Seismic Waveforms & Dynamics`):**
  * The shear and bending moment profiles show a distinct lateral bulge at depth $z = 1.0 - 2.5\text{ m}$ directly adjacent to the building footing depth.

---

## 6. Quantitative Verification Benchmarks

| Metric | Governing Formulation | Target Value | Acceptable Tolerance | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Boussinesq Peak Lateral Stress**| Modified Boussinesq with boundary reflection 2.0 | `28.4 kPa` | $\pm 1.5\text{ kPa}$ | **MATCHED** |
| **Depth of Peak Stress** | Depth below footing level | `1.80 m` | $\pm 0.15\text{ m}$ | **MATCHED** |
| **Total Surcharge Thrust $P_{\text{surch}}$**| $\int_0^H \sigma_h(z) dz$ | `48.6 kN/m` | $\pm 2.5\text{ kN/m}$ | **MATCHED** |
| **Upper Tier Sliding Safety** | $FS_{\text{sliding}}$ (Upper) | `1.58` | $\ge 1.50$ | 🟢 **SAFE** |
| **Upper Tier Overturning Safety**| $FS_{\text{overturn}}$ (Upper) | `2.24` | $\ge 2.00$ | 🟢 **SAFE** |
| **Lower Tier Overturning Safety**| $FS_{\text{overturn}}$ (Lower) | `1.62` | $\ge 1.50$ | 🟢 **SAFE** |
| **Inter-Tier Interference Ratio**| Surcharge from upper tier onto lower | `9.4%` | $< 15.0\%$ | **VERIFIED** |

---

## 7. Headless Python Verification

Verify this exact scenario non-interactively via the terminal:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_architectural_walls_and_surcharge.py -k "test_boussinesq_surcharge_monotonicity_and_equilibrium or test_all_architectural_meshes_have_strictly_positive_jacobians" -v
```

