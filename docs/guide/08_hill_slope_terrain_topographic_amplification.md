# Simulation Guide 08: Hill-Slope DEM Topography & Eurocode 8 Seismic Amplification
**Regulatory Standards:** Eurocode 8 (EN 1998-5:2004 Annex A) & IS 1893 (Part 1: 2016)

---

## 1. Engineering Objective
Import real-world digital site topography, auto-drape the retaining wall foundation along the ground cut line, and compute the topographic seismic amplification factor ($S_T$) at the slope crest. Demonstrate:
1. Ingestion of ESRI ASCII Grid (`.asc`), XYZ point clouds, or GeoTIFF terrain files.
2. Bilinear sub-pixel ground elevation interpolation and local slope angle ($\beta$) extraction.
3. Computation of Eurocode 8 / IS 1893 topographic amplification $S_T$ and spatial exponential decay away from the crest.
4. Auto-profiling of stepped/variable wall stem elevations matching the terrain profile.

---

## 2. Terrain & Topographic Model Setup

| Parameter | Variable | Input Value | Unit |
| :--- | :--- | :---: | :---: |
| **Terrain Mode** | `type` | `Synthetic Incline` *(or import .asc / GeoTIFF)* | - |
| **Slope Angle** | $\beta$ | `24.0` | deg |
| **Total Hill Height** | $H_{\text{slope}}$ | `25.0` | m |
| **Soil Shear Wave Velocity** | $V_s$ | `220.0` | m/s |
| **Wall Crest Setback Distance**| $x_{\text{crest}}$ | `1.50` | m |
| **Slope Configuration** | `shape` | `Two-Dimensional Ridge / Hill` | - |
| **Base Earthquake PGA** | $\text{PGA}_{\text{base}}$ | `0.25` | g |

---

## 3. Step-by-Step Execution in orang3D

1. **Open the Terrain & Studio Panel:**
   * In the left sidebar, click the tab **`Terrain & Studio`**.
2. **Generate or Ingest Topography:**
   * Under the **Terrain Model** group, click **`Load Synthetic Incline`**.
   * Enter Slope Angle $\beta = 24.0^\circ$, Hill Height $H_{\text{slope}} = 25.0\text{ m}$, and Crest Setback $x_{\text{crest}} = 1.5\text{ m}$.
   * *(Alternatively, click `Browse Terrain File...` to import an external `.asc` or `.tif` file).*
3. **Compute Topographic Seismic Amplification:**
   * Click **`Compute Topographic Amplification (EC8 / IS 1893)`**.
   * View the calculated amplification factor $S_T(x)$ and amplified crest acceleration in the summary card.
4. **Inspect in 3D Viewport:**
   * Check **`Show 3D Draped Terrain in Viewport`**.
   * In the 3D viewport, observe the brown/green triangulated site terrain mesh enveloping the foundation and daylighting in front of the toe.
5. **Switch to Studio Presentation Theme:**
   * In the menu bar, go to **`View -> Theme -> Light Studio`**.
   * Observe the crisp high-contrast white architectural presentation mode.
   * In the top toolbar, click **`Save 4K Viewport Render (.png)...`** to export an image.

---

## 4. Expected Visual & Graphical Behavior
* **3D Viewport:**
  * Displays the retaining wall correctly seated along the sloped mountain excavation cut.
  * Contour lines on the terrain surface visualize elevation gradients and daylighting slopes.
* **Terrain Panel Summary:**
  * Reports local slope angle $\beta = 24.0^\circ$, base amplification $S_{T,\max} = 1.20$, and effective amplified PGA at the wall crest.

---

## 5. Quantitative Verification Benchmarks

| Metric | Governing Formulation | Target Value | Acceptable Tolerance | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Slope Category** | $15^\circ < \beta \le 30^\circ$ | Medium Slope | Exact EC8 Clause | **MATCHED** |
| **Base Amplification $S_{T,\max}$**| EN 1998-5 Annex A Table A.1 | `1.20` | Exact Code Value | **MATCHED** |
| **Spatial Attenuation Factor** | $1.0 + (S_{T,\max} - 1.0) e^{-2 x / H_{\text{slope}}}$ | `1.177` | $\pm 0.005$ | **MATCHED** |
| **Amplified Crest PGA** | $S_T(x) \times \text{PGA}_{\text{base}}$ | `0.294 g` | $\pm 0.005\text{ g}$ | **MATCHED** |
| **Hill Resonant Frequency $f_0$**| $\frac{V_s}{4 H_{\text{slope}}}$ | `2.20 Hz` | $\pm 0.05\text{ Hz}$ | **MATCHED** |
| **Slope-Reduced Passive Coeff.**| $K_{p,\text{level}} \cos^2\beta [1 - \frac{\sin\beta}{\sin\phi}]^2$ | `1.48` | $\pm 0.05$ | **MATCHED** |

---

## 6. Headless Python Verification

Verify this exact scenario non-interactively via the terminal:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_terrain_topography.py -k "test_topographic_amplification_bounds or test_slope_modified_passive_resistance" -v
```

