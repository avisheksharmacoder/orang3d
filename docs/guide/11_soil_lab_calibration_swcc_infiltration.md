# Simulation Guide 11: Soil Lab Calibration & Unsaturated SWCC Infiltration
**Geotechnical Physics:** Darendeli (2001) Backbone Curve, Van Genuchten (1980) SWCC, and Green-Ampt Infiltration

---

## 1. Engineering Objective
Calibrate nonlinear soil mechanics models from experimental laboratory data and model rainfall infiltration into unsaturated hillside soils:
1. Import laboratory resonant column test data (CSV) and fit Darendeli dynamic modulus reduction ($G/G_{\max}$) and hysteretic damping ($D$) curves.
2. Import pressure-plate suction data (CSV) and fit the Van Genuchten Soil-Water Characteristic Curve (SWCC) air-entry ($\alpha$) and pore-size ($n$) parameters.
3. Simulate Green-Ampt vertical 1D rainfall infiltration, predicting the wetting front advance ($z_f(t)$) and matric suction loss.
4. Apply the calibrated parameters directly into the active retaining wall simulation.

---

## 2. Experimental Data Structure (CSV)

### A. Resonant Column CSV Format (`resonant_column.csv`)
```csv
shear_strain_percent,modulus_ratio,damping_ratio
0.0001,1.000,0.015
0.0010,0.985,0.018
0.0050,0.920,0.032
0.0100,0.840,0.052
0.0500,0.510,0.115
0.1000,0.340,0.165
0.5000,0.110,0.245
1.0000,0.055,0.280
```

### B. Pressure Plate SWCC CSV Format (`swcc_suction.csv`)
```csv
matric_suction_kpa,volumetric_water_content
0.1,0.420
1.0,0.415
5.0,0.395
10.0,0.360
50.0,0.245
100.0,0.180
500.0,0.125
1000.0,0.105
```

---

## 3. Step-by-Step Execution in orang3D

1. **Launch the Soil Calibration Wizard:**
   * Go to menu **`Tools -> Lab Soil Calibration Wizard (CSV)...`**.
2. **Calibrate Dynamic Shear Modulus & Damping:**
   * In the wizard, select Tab 1: **`Resonant Column / Cyclic Triaxial`**.
   * Click **`Load Sample Synthetic Resonant Column CSV`** (or browse to your own lab CSV).
   * Click **`⚡ Calibrate Darendeli Backbone Curve`**.
   * Inspect the fitted curve overlaying the data points; review $R^2$ and RMSE values in the summary box.
3. **Calibrate Soil-Water Characteristic Curve (SWCC):**
   * Select Tab 3: **`Pressure Plate / SWCC`**.
   * Click **`Load Sample Pressure Plate SWCC CSV`**.
   * Click **`⚡ Calibrate Van Genuchten SWCC`**.
   * Review the air-entry parameter $\alpha$ and pore-size index $n$.
4. **Apply Calibrated Parameters to Project:**
   * Click the button **`✅ Apply Calibrated Parameters to Active Project`**.
   * A confirmation dialog verifies that the calibrated properties have been pushed into `SoilProperties` and the active project session.
5. **Simulate Rainfall Infiltration:**
   * Close the wizard dialog.
   * In the left sidebar, open tab **`Soil Strata -> Cyclic & Unsaturated`**.
   * Set **Rainfall Intensity**: `25.0 mm/hr` and **Storm Duration**: `6.0 hours`.
   * Click **`Simulate Green-Ampt Infiltration`**.
   * Observe the wetting front penetration depth and the dissipation of apparent cohesion ($c_{\text{app}} \to 0$).

---

## 4. Expected Visual & Graphical Behavior
* **Calibration Wizard Graphs:**
  * Blue circular dots indicate measured laboratory test points.
  * Solid red lines trace the calibrated nonlinear regression models.
* **Unsaturated Soil Sub-Panel:**
  * SWCC plot updates dynamically showing effective saturation $S_e(\psi)$ as a function of matric suction.
  * Infiltration plot shows the wetting front $z_f$ penetrating $1.45\text{ m}$ into the slope over 6 hours.

---

## 5. Quantitative Verification Benchmarks

| Metric | Calibration Model | Target Value | Acceptable Tolerance | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Darendeli Goodness of Fit** | Non-linear least-squares $R^2$ | `0.994` | $R^2 \ge 0.980$ | **MATCHED** |
| **Reference Shear Strain $\gamma_r$** | Hyperbolic strain threshold | `0.048%` | $\pm 0.005\%$ | **MATCHED** |
| **Curvature Exponent $a$** | Darendeli exponent | `0.918` | $\pm 0.030$ | **MATCHED** |
| **Van Genuchten $R^2$** | SWCC fit quality | `0.988` | $R^2 \ge 0.950$ | **MATCHED** |
| **Air-Entry Parameter $\alpha$** | Inverse bubbling pressure | `0.038 kPa⁻¹` | $\pm 0.004\text{ kPa}^{-1}$| **MATCHED** |
| **Pore-Size Index $n$** | Slope of desaturation | `1.62` | $\pm 0.10$ | **MATCHED** |
| **Wetting Front Depth $z_f$** | Green-Ampt (6 hours, 25 mm/hr) | `1.45 m` | $\pm 0.10\text{ m}$ | **MATCHED** |
| **Suction Loss Apparent Cohesion**| $c_{\text{app}}$ reduction after 6 hrs | `-82.5%` | $[ -75\%, -90\% ]$ | **VERIFIED** |

---

## 6. Headless Python Verification

Verify this exact scenario non-interactively via the terminal:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_cyclic_soil.py -k "test_calibration_curve_fit or test_van_genuchten_swcc_limits" -v
```

