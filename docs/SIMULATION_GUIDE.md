# orang3D Comprehensive Simulation Guide

**Real-Time 3D Seismic, Hydrodynamic, and Geotechnical Soil-Structure Interaction Analysis**

---

## Table of Contents

1. [Introduction & Two-Speed Physics Architecture](#1-introduction--two-speed-physics-architecture)
2. [Installation & Launching the Application](#2-installation--launching-the-application)
3. [User Interface Anatomy](#3-user-interface-anatomy)
4. [Step-by-Step Simulation Workflows](#4-step-by-step-simulation-workflows)
   - [Workflow 1: Static Cantilever Sizing & Bearing Stability](#workflow-1-static-cantilever-sizing--bearing-stability)
   - [Workflow 2: Groundwater Flooding & Backfill Liquefaction](#workflow-2-groundwater-flooding--backfill-liquefaction)
   - [Workflow 3: Dynamic Earthquake & Newmark Permanent Sliding](#workflow-3-dynamic-earthquake--newmark-permanent-sliding)
   - [Workflow 4: Deep Continuum Soil-Structure Interaction (Kratos FEA)](#workflow-4-deep-continuum-soil-structure-interaction-kratos-fea)
   - [Workflow 5: Structural Stem Reinforcement Design (ACI 318 / EC2)](#workflow-5-structural-stem-reinforcement-design-aci-318--ec2)
5. [3D Viewport Controls, Visualization & Cutting Planes](#5-3d-viewport-controls-visualization--cutting-planes)
6. [2D Waveform Dashboard & Transport Controls](#6-2d-waveform-dashboard--transport-controls)
7. [Project Archiving, CAD Mesh Export & PDF Reports](#7-project-archiving-cad-mesh-export--pdf-reports)
8. [Engineering Reference & Governing Equations](#8-engineering-reference--governing-equations)
9. [Troubleshooting & FAQs](#9-troubleshooting--faqs)

---

## 1. Introduction & Two-Speed Physics Architecture

**orang3D** is a scientific desktop engineering application designed to evaluate the physical stability, structural integrity, and dynamic response of cantilever retaining walls subjected to earthquake ground shaking, rising water tables, and backfill liquefaction.

Unlike traditional software that forces an engineer to choose between simplified spreadsheets or cumbersome finite element tools, orang3D features a **Two-Speed Physics Architecture**:

```
+--------------------------------------------------------------------------------------------------+
|                                    orang3D Physics Engine                                        |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   Tier 1: Ultra-Fast Vectorized Analytical Core (< 2 ms @ 60 FPS)                                |
|   ---------------------------------------------------------------                                |
|   • Mononobe-Okabe (1929) dynamic earth pressure coefficients (K_ae, K_pe)                       |
|   • Seed & Whitman (1970) seismic thrust height partitioning (0.33H static vs 0.60H dynamic)     |
|   • Coulomb (1776) and Rankine (1857) static earth pressures                                     |
|   • Meyerhof, Hansen, and Vesic ultimate bearing capacity with eccentricity checks               |
|   • Differential beam equilibrium (dM/dy = -V) for continuous stem bending moments & shears       |
|   • Newmark (1965) downhill double-integration for permanent sliding displacements u(t)          |
|   • Pure NumPy 8-node hexahedral solid mesh generator (1,000+ brick elements in < 1.5 ms)        |
|                                                                                                  |
|   Tier 2: Deep Continuum Soil-Structure Interaction FEA (Multi-Threaded OpenMP Worker)           |
|   ------------------------------------------------------------------------------------           |
|   • Powered by KratosMultiphysics (KratosGeoMechanicsApplication & StructuralMechanics)          |
|   • 2D Plane-Strain coupled hydromechanical u-p continuum formulation                            |
|   • Lysmer-Kuhlemeyer radiation damping dampers preventing artificial wave box reflections       |
|   • Step-by-step transient dynamic integration under historical accelerograms                    |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Installation & Launching the Application

### 2.1 Virtual Environment Activation

orang3D runs on Python 3.10+ (tested on Python 3.12) using PySide6, PyVista, pyqtgraph, NumPy, SciPy, and KratosMultiphysics.

Activate the local virtual environment and install dependencies:

```bash
# Navigate to the workspace
cd /home/avisheks/Documents/dibs/orang3d

# Activate virtual environment
source .venv/bin/activate

# Launch orang3D GUI
python3 main.py
```

### 2.2 Headless / Offscreen Execution (Testing & CI)

To run automated benchmarks or headless report generation in Linux servers without an active X11 display:

```bash
# Run complete test suite (122 tests across 12 modules)
PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/ -v

# Run with test coverage report
PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest --cov=src/orang3d --cov-report=term tests/
```

### 2.3 Compiling Standalone Executables (Windows & Linux)

To export and package orang3D as a zero-dependency standalone `.exe` (Windows) or binary (Linux):
- Run `./scripts/build_linux.sh` on Linux or `scripts\build_windows.bat` on Windows.
- Detailed step-by-step instructions from `git clone` to distribution are provided in the **[Packaging & Export Guide](file:///home/avisheks/Documents/dibs/orang3d/docs/PACKAGING_AND_EXPORT_GUIDE.md)**.

---

## 3. User Interface Anatomy

The orang3D graphical interface is organized into three primary workspaces designed for ergonomic pair-engineering:

```
+--------------------------------------------------------------------------------------------------+
| Top Menu: File (Open Ctrl+O, Save Ctrl+S, Report Ctrl+P) | Export (VTK, STL, OBJ, CSV)          |
| Toolbar:  [📂 Open] [💾 Save] [📄 PDF Report] [Reset Cam] [▶ Play] [Scrubber Slider] [⚙ Kratos] |
+---------------------------------------------------+----------------------------------------------+
| LEFT PANEL: PARAMETER CONTROLS                   | RIGHT UPPER: 3D SCIENTIFIC VIEWPORT          |
| ────────────────────────────────                  | ────────────────────────────────────         |
| ┌──────────┬─────────────┬────────────────────┐   | • Real-time 3D Hexahedral Solid Mesh         |
| │ Geometry │ Soil Strata │ Disaster / Seismic │   | • Colormap Heatmaps:                         |
| └──────────┴─────────────┴────────────────────┘   |   - Von Mises Elastic Stress                 |
| • Stem Height (2.0 - 15.0 m)                      |   - Hydrostatic Pore Pressure                |
| • Stem Base / Top Thickness (m)                   |   - Active Coulomb Failure Wedge Overlay     |
| • Toe & Heel Slab Widths (m)                      |   - Vector Glyphs: Contact & Bearing Shear   |
| • Footing Slab Thickness (m)                      |   - Orthographic Cutting Planes (X, Y, Z)    |
| • Shear Key Depth & Width (m)                     |   - Dynamic Mesh Warping (1x - 50x Scale)    |
| • Backfill Friction Angle (phi)                   +----------------------------------------------+
| • Wall-Soil Friction (delta)                      | RIGHT LOWER: 2D WAVEFORM & SAFETY DASHBOARD  |
| • Subgrade Friction, Cohesion & Bearing Capacity  | ───────────────────────────────────────────  |
| • Seismic Acceleration (kh, kv)                   | [Plot 1] a(t) Accelerogram (g)               |
| • Groundwater Table Elevation (m)                 | [Plot 2] u(t) Newmark Permanent Slip (cm)    |
| • Liquefaction Excess Ratio (r_u: 0 - 100%)       | [Plot 3] u_w(t) Dynamic Pore Pressure (kPa)  |
| • Earthquake Input Selector (.AT2 / Synthetic)    | [Badges] [SAFE / MARGINAL / FAIL] Status     |
+---------------------------------------------------+----------------------------------------------+
| Bottom Status Bar: Physical Invariants, FEA Step Progress, and Execution Diagnostics            |
+--------------------------------------------------------------------------------------------------+
```

---

## 4. Step-by-Step Simulation Workflows

### Workflow 1: Static Cantilever Sizing & Bearing Stability

**Objective:** Validate a concrete cantilever wall against sliding, overturning, and soil bearing capacity failure in dry sand.

1. **Configure Wall Geometry:**
   - Switch to the **Geometry** tab on the left panel.
   - Set **Stem Height** to `6.00 m`.
   - Set **Stem Base Thick** to `0.70 m` and **Stem Top Thick** to `0.35 m`.
   - Set **Toe Width** to `1.20 m` and **Heel Width** to `2.60 m` (total base width $B = 4.50\text{ m}$).
   - Set **Footing Thick** to `0.80 m`.
   - Leave **Shear Key Depth** at `0.00 m`.
2. **Assign Soil & Subgrade Properties:**
   - Switch to the **Soil Strata** tab.
   - Set backfill **Friction Angle $\phi$** to `34.0°` and **Unit Weight $\gamma$** to `18.5 kN/m³`.
   - Set interface **Wall Friction $\delta$** to `22.0°` (approximately $\frac{2}{3}\phi$).
   - In the **Foundation Soil Bed** section, set **Found. Friction** to `30.0°`, **Found. Cohesion** to `20.0 kPa`, and **Allow. Bearing** to `350.0 kPa`.
3. **Set Static Operating State:**
   - Switch to the **Disaster / Seismic** tab.
   - Ensure **Horizontal $k_h$** is set to `0.00 g` and **Vertical $k_v$** to `0.00 g`.
   - Set **Water Depth** to `10.00 m` (below foundation level).
4. **Evaluate Stability Badges:**
   - Look at the bottom-right safety card on the 2D dashboard:
     - **Sliding Factor of Safety ($FS_{\text{sliding}}$):** Green badge ($FS \ge 1.50$, typically $\approx 2.10$).
     - **Overturning Factor of Safety ($FS_{\text{overturning}}$):** Green badge ($FS \ge 2.00$, typically $\approx 3.20$).
     - **Bearing Capacity ($FS_{\text{bearing}}$):** Green badge ($FS \ge 2.50$).
5. **Inspect Eccentricity & Contact Pressure:**
   - Note the base contact pressure distribution:
     - Peak toe pressure $q_{\max} \approx 135\text{ kPa} \le 350\text{ kPa}$ (allowable).
     - Heel pressure $q_{\min} \approx 65\text{ kPa} > 0$ (no foundation uplift / tension detachment).
     - The resultant vector falls strictly inside the middle-third ($e = \frac{B}{2} - \frac{M_{\text{net}}}{V} \le \frac{B}{6}$).

---

### Workflow 2: Groundwater Flooding & Backfill Liquefaction

**Objective:** Simulate an extreme flood event where the groundwater table rises to $2.0\text{ m}$ below the crest with partial soil liquefaction.

1. **Raise Groundwater Table:**
   - Navigate to the **Disaster / Seismic** tab.
   - Adjust the **Water Depth** spinbox from `10.0 m` down to `2.00 m`.
   - In the 3D viewport, observe the translucent cyan **Water Table Plane** cut across the soil and wall.
2. **Review Analytical Thrust Increase:**
   - Notice that total lateral thrust nearly doubles from $\approx 105\text{ kN/m}$ to $\approx 220\text{ kN/m}$ due to hydrostatic water pressure:
     $$P_w = \frac{1}{2}\gamma_w (H - z_w)^2 = \frac{1}{2}(9.81)(6.8 - 2.0)^2 \approx 113.0\text{ kN/m}$$
   - Buoyancy reduces the effective vertical dead weight:
     $$\sigma'_v = \gamma z_w + (\gamma_{\text{sat}} - \gamma_w)(z - z_w)$$
3. **Simulate Backfill Liquefaction:**
   - Drag the **Liquefaction** slider from `0%` to `40%` ($r_u = 0.40$).
   - The effective internal friction angle degrades:
     $$\phi_{\text{eff}} = \arctan\left((1 - r_u)\tan\phi\right)$$
4. **Inspect Safety Degradation:**
   - The **Sliding Badge** transitions from **SAFE (Green)** to **FAIL (Crimson Red)** ($FS_{\text{sliding}} < 1.0$).
   - The status bar displays a stability warning.
5. **Mitigation via Shear Key:**
   - Switch back to the **Geometry** tab and set **Shear Key Depth** to `0.80 m` and **Shear Key Width** to `0.50 m`.
   - Observe how passive key resistance increases base shear capacity, restoring $FS_{\text{sliding}} \ge 1.20$.

---

### Workflow 3: Dynamic Earthquake & Newmark Permanent Sliding

**Objective:** Ingest an earthquake accelerogram, calculate dynamic Mononobe-Okabe earth pressures, and integrate Newmark permanent sliding displacement.

1. **Select Waveform Input:**
   - On the **Disaster / Seismic** tab, locate the **Earthquake Waveform Input** group:
     - **Synthetic Ricker Pulse:** Select `Synthetic: Ricker Pulse (2.5 Hz)` for impulsive near-fault shaking.
     - **Harmonic Chirp Sweep:** Select `Synthetic: Harmonic Chirp (1 - 8 Hz)` for resonance sweeping.
     - **Real PEER Strong-Motion Record:** Select `Load Historical .AT2 Record...`, click **Select .AT2 Record File**, and choose any PEER NGA/COSMOS `.AT2` file (e.g. 1994 Northridge or 1995 Kobe).
2. **Set Seismic Acceleration Intensity:**
   - Set **Horizontal $k_h$** to `0.30 g` and **Vertical $k_v$** to `0.15 g`.
   - Note the dynamic active earth pressure coefficient $K_{ae}$ increases according to Mononobe-Okabe:
     $$\theta_e = \arctan\left(\frac{k_h}{1 - k_v}\right) = \arctan\left(\frac{0.30}{0.85}\right) = 19.4^\circ$$
   - The dynamic thrust application height climbs upwards from $0.33H \to 0.58H$.
3. **Inspect 2D Waveforms:**
   - Look at the three synchronized plots on the 2D dashboard:
     - **Plot 1 ($a(t)$):** Ground acceleration in units of $g$ (cyan-blue line).
     - **Plot 2 ($u(t)$):** Permanent downhill sliding displacement in $\text{cm}$ (orange line).
     - **Plot 3 ($u_w(t)$):** Coupled dynamic pore-water pressure in $\text{kPa}$ (emerald line).
   - If peak acceleration exceeds the critical yield acceleration $k_y$, permanent sliding $u(t)$ accumulates monotonically during exceedance pulses.
4. **Animate Dynamic Response:**
   - Click **▶ Play Seismic Wave** in the top toolbar or transport bar.
   - The vertical playhead scrubs forward at 60 FPS:
     - The 3D wall slides forward proportionally to $u(t)$.
     - Translucent groundwater ripples with dynamic phase oscillations.
     - Stress colormaps pulsate with instantaneous inertial thrust.
   - Use the **Speed Multiplier** dropdown ($0.25\times, 0.5\times, 1.0\times, 2.0\times$) to inspect transient peaks in slow motion.

---

### Workflow 4: Deep Continuum Soil-Structure Interaction (Kratos FEA)

**Objective:** Execute multi-threaded finite element continuum dynamics with viscous radiation boundary damping using KratosMultiphysics.

1. **Prepare Model Parameters:**
   - Set wall geometry, soil stratification, and seismic PGA to the desired target state.
2. **Launch Kratos FEA Solver:**
   - Click the toolbar button: **"⚙ Run Kratos GeoMechanics FEA"**.
   - The button text changes to **"⏳ Kratos Solving..."** and disables to prevent concurrent solver collisions.
3. **Background Execution Monitoring:**
   - The FEA solver runs on a dedicated background `QThread` without freezing the Qt user interface.
   - The status bar reports step-by-step progress:
     ```
     Kratos FEA Step 120/400 (t=2.40s | Crest Deflection=2.15 cm | Pore Pressure=48.2 kPa)
     ```
4. **Completion Diagnostics:**
   - When finished, a completion modal displays:
     - Total time steps integrated.
     - Maximum dynamic crest deflection in $\text{cm}$.
     - Maximum pore-water pressure generation in $\text{kPa}$.
     - Convergence status (`CONVERGED`).

---

### Workflow 5: Structural Stem Reinforcement Design (ACI 318 / EC2)

**Objective:** Inspect internal shear and bending moment distributions along the wall stem and verify flexural reinforcement sizing.

1. **Review Stem Force Profiles:**
   - Lateral earth pressures are integrated from stem crest down to base:
     $$V(y) = \int_y^H p_{\text{lateral}}(z)\,dz \quad \text{and} \quad M(y) = \int_y^H V(z)\,dz$$
   - The maximum bending moment $M_{\max}$ and shear force $V_{\max}$ occur at the base junction ($y = 0$).
2. **Evaluate Concrete Tensile Stress & Cracking:**
   - Extreme-fiber tensile stress is computed:
     $$\sigma_t = \frac{M_{\max} \cdot (t_{\text{base}} / 2)}{I_{\text{base}}} - \frac{N_{\text{stem}}}{A_{\text{base}}}$$
   - Compared against the modulus of rupture $f_r = 0.62\lambda\sqrt{f'_c}\text{ MPa}$ ($2.31\text{ MPa}$ for $28\text{ MPa}$ concrete):
     - If $\sigma_t < f_r$: Classified as **`[ELASTIC]`** (uncracked section).
     - If $\sigma_t \ge f_r$: Classified as **`[CRACKED]`** (flexural cracks develop; tension shifted to rebar).
3. **Verify Rebar Detailing:**
   - The design engine sizes required tension steel:
     $$A_s = \frac{M_u}{\phi f_y (d - a/2)}$$
   - Enforces minimum shrinkage and temperature steel ($A_{s,\min} = 0.0018 b h$).
   - Calculates concrete shear capacity $\phi V_c = \phi 0.17\sqrt{f'_c} b d$ and flags whether shear stirrups are required.

---

## 5. 3D Viewport Controls, Visualization & Cutting Planes

The 3D scientific viewport uses PyVista and VTK for hardware-accelerated scientific rendering:

```
+--------------------------------------------------------------------------------------------------+
| Viewport Controls Toolbar:                                                                       |
| [Colormap: Viridis ▼] [Field: Von Mises Stress ▼] [Warp: 10x ───○───] [☑ Wedge] [☑ Glyphs]      |
| [Slice: Orthogonal X Cut ▼] [Reset Camera]                                                       |
+--------------------------------------------------------------------------------------------------+
```

### Camera Navigation

- **Left-Click + Drag:** Orbit / rotate 3D camera around the wall center.
- **Right-Click + Drag (or Scroll Wheel):** Smooth zoom in / out.
- **Middle-Click + Drag (or Shift + Left-Click):** Pan camera across the scene.
- **Reset 3D Camera Button:** Re-centers and frames the retaining wall within standard isometric view.

### Visualization Features

1. **Scalar Field Colormaps:**
   - **Von Mises Stress:** Visualizes equivalent stress concentrations at the stem base toe-heel junction using standard color palettes (`Viridis`, `Plasma`, `Inferno`, `Coolwarm`, `Jet`).
   - **Pore-Water Pressure:** Displays hydrostatic and excess dynamic pore pressure gradients.
2. **Deformation Mesh Warping:**
   - Adjust the **Warp Slider** ($1\times$ to $50\times$) to exaggerate lateral stem bending and foundation sliding.
3. **Active Failure Wedge Overlay:**
   - Toggle **☑ Failure Wedge** to render the theoretical planar Coulomb active failure wedge propagating upward from the wall heel at angle $\alpha_A = \phi + \arctan\left[\dots\right]$.
4. **Vector Glyphs (Contact & Bearing Pressure):**
   - Toggle **☑ Vector Glyphs** to render 3D conical arrows along the back of the stem (lateral thrust direction) and along the base slab (bearing reaction pressure).
5. **Orthographic Cutting Planes:**
   - Select **X Cut**, **Y Cut**, or **Z Cut** from the slice dropdown to inspect internal hexahedral stress distributions within the wall core.

---

## 6. 2D Waveform Dashboard & Transport Controls

The bottom dashboard displays real-time time-series plots using `pyqtgraph`:

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
| Transport: [▶ Play / ⏸ Pause] [⏮ Step Back] [⏭ Step Fwd] [🔁 Loop] [Speed: 1.0x ▼] [t = 2.45 s]   |
+────────────────────────────────────────────────────────┬─────────────────────────────────────────+
| Ground Acceleration a(t) [g]                          | 3-STATE GEOTECHNICAL SAFETY STATUS      |
| ──/\──\/──/\──────── (Cyan: #00a6fb)                  | ─────────────────────────────────────── |
| Permanent Sliding Displacement u(t) [cm]               | Base Sliding:     1.42 [SAFE] (Green)   |
| ─────────/─────────── (Orange: #ff6b35)               | Overturning:      2.18 [SAFE] (Green)   |
| Coupled Pore Pressure u_w(t) [kPa]                     | Bearing Capacity: 2.85 [SAFE] (Green)   |
| ────/─────────────── (Green: #06d6a0)                 | Dynamic Thrust:   148.5 kN/m            |
| Vertical Playhead Line: Interactive Scrubber           | Stem State:       ELASTIC (1.85 MPa)    |
+────────────────────────────────────────────────────────┴─────────────────────────────────────────+
```

### 3-State Safety Badge Machine

Safety metrics evaluate in real time against international code thresholds (Eurocode 7, AASHTO, IS 14458):

- **SAFE (Emerald Green `#06d6a0`):** $FS \ge FS_{\text{req}}$ (e.g. $FS_{\text{sliding}} \ge 1.10$, $FS_{\text{overturn}} \ge 1.50$, $FS_{\text{bearing}} \ge 2.00$).
- **MARGINAL (Amber Yellow `#ffd166`):** $1.00 \le FS < FS_{\text{req}}$. Design requires monitoring or structural tuning.
- **FAIL (Crimson Red `#ef476f`):** $FS < 1.00$. Active structural failure or sliding instability predicted.

---

## 7. Project Archiving, CAD Mesh Export & PDF Reports

### 7.1 Unified Project Sessions (`.o3d` Packages)

orang3D projects save as single `.o3d` archive bundles containing:
- `project.json`: All geometry, soil strata, seismic inputs, analysis results, and schema version metadata.
- `simulation.h5`: GZIP-compressed HDF5 arrays for time, ground acceleration, sliding displacement, and pore pressure.

**To Save a Session:**
- Press `Ctrl+S` or click **💾 Save** on the toolbar. Choose a destination filename (e.g., `project_site_a.o3d`).

**To Open a Session:**
- Press `Ctrl+O` or click **📂 Open** on the toolbar. Select any `.o3d` file. orang3D automatically deserializes all parameters, synchronizes dock panels, updates 2D waveform curves, and reconstructs the 3D scene.

### 7.2 CAD & Simulation Mesh Export Suite

From the top **Export** menu, export models to standard engineering formats:

- **`.vtk` (ParaView / VisIt):** Exports 3D hexahedral solid meshes with nodal coordinates, cell connectivity, and scalar stress fields for scientific post-processing.
- **`.stl` (3D CAD / 3D Printing):** Extracts the external boundary triangulated surface for import into SolidWorks, AutoCAD, or 3D printers.
- **`.obj` (Wavefront Polygonal Mesh):** Standard 3D polygonal mesh with surface normals for Blender, WebGL, or digital twins.
- **`.csv` (RFC-4180 Waveform Table):** Exports dynamic time-history curves ($t$, $a(t)$, $u(t)$, $u_w(t)$) in 8-decimal scientific notation (`.8e`).

### 7.3 Automated Geotechnical PDF Report Generation

orang3D generates publication-grade calculation reports offscreen without requiring external LaTeX installations:

1. Click **📄 PDF Report** on the toolbar or press `Ctrl+P`.
2. Select output path (e.g. `retaining_wall_calculation_report.pdf`).
3. In $< 0.4\text{ seconds}$, a multi-page PDF ($> 75\text{ KB}$) is generated containing:
   - **Executive Metadata Header:** Project name, timestamp, and schema version.
   - **Dimensioned Cross-Section Diagram:** High-resolution embedded vector diagram showing stem, toe, heel, footing, shear key, groundwater elevation, dynamic active thrust $P_{ae}$ with application height, and bearing pressure distribution.
   - **Input Parameters Tables:** Geometry, Backfill properties, Foundation subgrade, Seismic PGA.
   - **Factors of Safety Summary:** Sliding, overturning, and bearing safety factors.
   - **Code Compliance Verification:** Automated pass/fail checks against **Eurocode 7**, **AASHTO LRFD**, and **IS 14458**.

---

## 8. Engineering Reference & Governing Equations

### 8.1 Mononobe-Okabe Dynamic Active Thrust

$$K_{ae} = \frac{\cos^2(\phi - \theta_e - \theta)}{\cos\theta_e \cos^2\theta \cos(\delta + \theta + \theta_e) \left[1 + \sqrt{\frac{\sin(\phi + \delta)\sin(\phi - \theta_e - \beta)}{\cos(\delta + \theta + \theta_e)\cos(\beta - \theta)}}\right]^2}$$

Where:
- $\phi$: Internal soil friction angle.
- $\delta$: Wall-soil interface friction angle ($\approx \frac{2}{3}\phi$).
- $\theta$: Wall backface inclination from vertical ($0^\circ$ for vertical).
- $\beta$: Backfill slope angle from horizontal.
- $\theta_e = \arctan\left(\frac{k_h}{1 - k_v}\right)$: Seismic inertia angle.

### 8.2 Seed & Whitman Dynamic Partitioning

$$\Delta K_{ae} = K_{ae} - K_a \approx \frac{3}{4} k_h$$

$$P_{ae} = P_a + \Delta P_{ae} = \frac{1}{2}\gamma H^2 K_a + \frac{1}{2}\gamma H^2 \Delta K_{ae}(1 - k_v)$$

Thrust application height:
$$h_{ae} = \frac{P_a \cdot (H / 3) + \Delta P_{ae} \cdot (0.60 H)}{P_{ae}}$$

### 8.3 Newmark Permanent Sliding Block Double Integration

$$\ddot{u}(t) = \begin{cases} [a(t) - k_y \cdot g] & \text{if } a(t) > k_y \cdot g \text{ or } \dot{u}(t) > 0 \\ 0 & \text{otherwise} \end{cases}$$

$$u(t) = \int_0^t \dot{u}(\tau)\,d\tau \quad \text{where } \dot{u}(t) = \int_0^t \ddot{u}(\tau)\,d\tau \ge 0$$

### 8.4 Meyerhof Ultimate Bearing Capacity

$$q_{\text{ult}} = c N_c s_c i_c + q N_q s_q i_q + \frac{1}{2}\gamma B' N_\gamma s_\gamma i_\gamma$$

$$e = \frac{B}{2} - \frac{M_R - M_O}{V} \quad \implies \quad B' = B - 2e$$

$$q_{\max,\min} = \frac{V}{B} \left(1 \pm \frac{6e}{B}\right) \quad (\text{for } e \le B/6)$$

---

## 9. Troubleshooting & FAQs

### Q1: Why does the 3D Viewport show a black or blank screen on Linux?
- **Cause:** Some Linux distributions require Mesa software rendering when running under Wayland or virtualized environments.
- **Fix:** Launch with software OpenGL fallback:
  ```bash
  LIBGL_ALWAYS_SOFTWARE=1 python3 main.py
  ```

### Q2: What causes the Sliding Safety Badge to show "FAIL" (Red)?
- **Cause:** Either seismic acceleration $k_h$ is too severe, the water table has caused hydrostatic thrust and buoyancy loss, or base width $B$ is too narrow.
- **Fix:** Increase heel length $B_{\text{heel}}$ to add stabilizing dead weight of soil, add a shear key ($0.5\text{ m}$ to $1.0\text{ m}$ depth), or improve foundation friction $\phi_f$.

### Q3: How do I know if the Kratos FEA simulation converged?
- Look at the bottom status bar and final popup dialog. It will state `Kratos FEA Completed: 400 steps solved! Max Crest Deflection: X.XX cm`. If divergent, an alert will display the physical non-convergence point.

### Q4: Can I import my own recorded earthquake data?
- **Yes.** Select `Load Historical .AT2 Record...` from the Disaster tab. orang3D parses standard PEER Ground Motion Database `.AT2` files, automatically parsing time-step $dt$, performing linear baseline correction, and applying a 4th-order Butterworth filter ($0.1\text{ Hz} - 25\text{ Hz}$).
