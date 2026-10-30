# orang3D Comprehensive Simulation Guide

**Real-Time 3D Seismic, Hydrodynamic, Geotechnical SSI, and Structural Code Design for Retaining Systems**

---

## Table of Contents

1. [Introduction & Multi-Tier Physics Architecture](#1-introduction--multi-tier-physics-architecture)
2. [Installation & Launching the Application](#2-installation--launching-the-application)
3. [User Interface Anatomy & Workspaces](#3-user-interface-anatomy--workspaces)
4. [Step-by-Step Simulation Workflows](#4-step-by-step-simulation-workflows)
   - [Workflow 1: Static Cantilever Wall Sizing & Bearing Stability](#workflow-1-static-cantilever-wall-sizing--bearing-stability)
   - [Workflow 2: Groundwater Flooding, Infiltration & Liquefaction](#workflow-2-groundwater-flooding-infiltration--liquefaction)
   - [Workflow 3: Real-Time Earthquake Waveform Playback & Newmark Sliding](#workflow-3-real-time-earthquake-waveform-playback--newmark-sliding)
   - [Workflow 4: Multi-Bay Curved Cylindrical Shell & Bored Pile Foundation Design](#workflow-4-multi-bay-curved-cylindrical-shell--bored-pile-foundation-design)
   - [Workflow 5: Live Indian Standards Code Audit (IS 456 / 2911 / 800)](#workflow-5-live-indian-standards-code-audit-is-456--2911--800)
   - [Workflow 6: Deep Continuum Soil-Structure Interaction (Kratos FEA)](#workflow-6-deep-continuum-soil-structure-interaction-kratos-fea)
   - [Workflow 7: Automated AutoCAD DXF & Engineering PDF Report Generation](#workflow-7-automated-autocad-dxf--engineering-pdf-report-generation)
5. [3D Viewport Controls, Visualization & Slicing Tools](#5-3d-viewport-controls-visualization--slicing-tools)
6. [2D Waveform Dashboard & Dynamic Safety Badges](#6-2d-waveform-dashboard--dynamic-safety-badges)
7. [Project Archiving, CAD Mesh Export & PDF Reports](#7-project-archiving-cad-mesh-export--pdf-reports)
8. [Engineering Reference & Governing Equations](#8-engineering-reference--governing-equations)
9. [Troubleshooting & Frequently Asked Questions (FAQs)](#9-troubleshooting--frequently-asked-questions-faqs)

---

## 1. Introduction & Multi-Tier Physics Architecture

**orang3D** is a scientific desktop engineering workstation designed for geotechnical and structural engineers, infrastructure developers, and researchers. It evaluates the physical stability, structural integrity, and dynamic response of retaining structures subjected to earthquake ground motions, rising water tables, rainfall infiltration, and hillside slope pressures.

The software supports two structural paradigms:
1. **Conventional Reinforced Concrete Cantilever Retaining Walls** (T-shaped stem, base footing slab, and shear key).
2. **Advanced Multi-Bay Multi-Strut Piled Curved Cylindrical Retaining Walls** (cylindrical shell panels, vertical concrete piers, bored cast-in-situ piles with rock socketing, and multi-tier raking structural steel struts).

Unlike traditional software that forces an engineer to choose between simplified spreadsheets or slow, cumbersome finite element software, orang3D features a **Multi-Tier Physics Architecture**:

```
+--------------------------------------------------------------------------------------------------+
|                                    orang3D Physics Architecture                                  |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   Tier 1: Ultra-Fast Vectorized Analytical Engine (< 1 ms @ 60 FPS)                              |
|   -----------------------------------------------------------------                              |
|   • Coulomb (1776) and Rankine (1857) static active and passive earth pressures                  |
|   • Mononobe-Okabe (1929) dynamic earth pressure coefficients (K_ae, K_pe)                       |
|   • Seed & Whitman (1970) dynamic thrust height partitioning (0.33H static vs 0.60H dynamic)     |
|   • Terzaghi/Handy (1985) 3D horizontal soil arching between vertical piers                      |
|   • Meyerhof, Hansen, and Vesic ultimate bearing capacity with dynamic eccentricity checks      |
|   • Differential beam equilibrium (dM/dy = -V) for continuous stem bending moments & shears       |
|   • Newmark (1965) downhill double-integration for permanent seismic sliding displacements       |
|   • Pure NumPy 8-node hexahedral solid mesh generator (1,000+ brick elements in < 1.5 ms)        |
|                                                                                                  |
|   Tier 2: AI / PINN Fast Surrogates & Uncertainty Quantification (< 0.2 ms)                     |
|   -------------------------------------------------------------------------                      |
|   • Physics-Informed Neural Network (PINN) with horizontal equilibrium projection (∑Fx = 0)      |
|   • Latin Hypercube Sampling (LHS) with Kolmogorov-Smirnov uniformity verification               |
|   • Monte Carlo structural reliability (Cornell reliability index β and failure probability Pf)   |
|   • Monotonic HAZUS-calibrated seismic fragility curves (Slight, Moderate, Extensive, Collapse)  |
|                                                                                                  |
|   Tier 3: Nonlinear Soil-Structure Interaction (BNWF via OpenSeesPy)                             |
|   ------------------------------------------------------------------                             |
|   • Beam on Nonlinear Winkler Foundation (BNWF) modeling pile-soil contact                       |
|   • Matlock soft-clay and API sand p-y lateral springs, Mosher t-z skin friction, q-z end bearing|
|   • Broms lateral pile capacity and minimum embedment depth calculation                          |
|                                                                                                  |
|   Tier 4: Deep Continuum Soil-Structure Interaction FEA (Multi-Threaded Kratos Worker)           |
|   ------------------------------------------------------------------------------------           |
|   • Powered by KratosMultiphysics (KratosGeoMechanicsApplication & StructuralMechanics)          |
|   • 2D Plane-Strain coupled hydromechanical u-p continuum formulation                            |
|   • Lysmer-Kuhlemeyer radiation damping dampers preventing artificial wave box reflections       |
|   • Step-by-step transient dynamic integration under historical earthquake accelerograms         |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Installation & Launching the Application

### 2.1 Virtual Environment Setup & Launch

orang3D runs on **Python 3.10+** (tested on Python 3.12) using PySide6, PyVista, pyqtgraph, NumPy, SciPy, OpenSeesPy, ezdxf, and KratosMultiphysics.

Follow these exact commands in your terminal:

```bash
# 1. Navigate to the orang3d directory
cd /home/avisheks/Documents/dibs/orang3d

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Launch the desktop graphical application
python main.py
```

### 2.2 Headless Verification & Testing

To verify all analytical models, GUI panels, and CAD exporters without starting the full graphical interface:

```bash
# Run complete test suite (232 tests across 24 modules)
PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest tests/ -v

# Run with statement coverage report
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/coverage run --source=src/orang3d -m pytest -p no:cov tests/ && .venv/bin/coverage report -m
```

### 2.3 Standalone Executable Packaging

To build a zero-dependency portable binary:
- **Linux:** Run `./scripts/build_linux.sh`
- **Windows:** Run `scripts\build_windows.bat`
- Refer to the detailed **[Packaging & Export Guide](file:///home/avisheks/Documents/dibs/orang3d/docs/PACKAGING_AND_EXPORT_GUIDE.md)** for distribution details.

---

## 3. User Interface Anatomy & Workspaces

The orang3D graphical user interface is divided into functional workspaces designed for productive structural and geotechnical engineering:

```
+--------------------------------------------------------------------------------------------------+
| Top Menu: File (Open Ctrl+O, Save Ctrl+S, PDF Report Ctrl+P, Exit) | Export (DXF, VTK, STL, OBJ) |
| Top Bar:  [📂 Open] [💾 Save] [📄 PDF Report] [📐 AutoCAD DXF] [Reset Cam] [▶ Play] [Slider] [⚙]  |
+---------------------------------------------------+----------------------------------------------+
| LEFT PANEL: PARAMETER CONTROLS                   | RIGHT UPPER: 3D SCIENTIFIC VIEWPORT          |
| ────────────────────────────────                  | ────────────────────────────────────         |
| ┌─────────┬────────┬────────┬───────┬─────────┐   | • Real-Time 3D Mesh (Hexahedral / Curved)    |
| │Cantilvr │ Shell  │ Struts │ Soil  │ Seismic │   | • Colormap Heatmaps:                         |
| └─────────┴────────┴────────┴───────┴─────────┘   |   - Tensile Stress (MPa)                     |
|                                                   |   - Von Mises Stress (MPa)                   |
| [Cantilever Wall Tab]                             |   - Hydrostatic & Dynamic Pore Pressure      |
| • Stem Height (2.0 - 15.0 m)                      | • Deformation Warp Factor (1x - 50x)         |
| • Stem Base / Top Thickness (m)                   | • Toggles: [☑ Soil] [☑ Water] [☑ Wedge]      |
| • Toe & Heel Widths (m) & Footing Thickness       | • Pressure Vector Glyphs (Contact & Bearing) |
| • Shear Key Depth & Width (m)                     | • Orthogonal Slicing Plane Tool (X, Y, Z)    |
|                                                   +----------------------------------------------+
| [Curved Shell & Pier Tab]                         | RIGHT LOWER: TABBED DYNAMICS & CODE AUDIT    |
| • Curvature Radius R (2.0 - 10.0 m)               | ───────────────────────────────────────────  |
| • Bay Span L_bay (2.0 - 6.0 m) & Number of Bays   | ┌─────────────────────────┬────────────────┐ |
| • Pier Width b_p, Pier Depth d_p, Pier Height     | │📊 Dynamic Waveforms     │📋 IS Code Audit│ |
|                                                   | └─────────────────────────┴────────────────┘ |
| [Strut & Piles Tab]                               | [Waveforms Tab]                              |
| • Bored Pile Diameter D_p (0.6 - 2.0 m)           | • a(t) Accelerogram with live playhead       |
| • Embedment Depth L_pile (4.0 - 30.0 m)           | • u(t) Newmark Cumulative Sliding Slip (cm)  |
| • Rock Socket Length (0.5 - 6.0 m)                | • u_w(t) Dynamic Pore Pressure (kPa)         |
| • Steel Strut Catalog (CHS / ISMB) & Rake Angle   | • Live Geotechnical Safety Cards:            |
|                                                   |   - FS Sliding [SAFE / MARGINAL / FAIL]      |
| [Soil Strata Tab]                                 |   - FS Overturning & FS Bearing              |
| • Backfill Friction Angle (phi), Cohesion, Weight |   - Total Thrust P_ae & Stem Tension [CRACK] |
| • Foundation Friction, Cohesion, Allow. Bearing   |                                              |
|                                                   | [IS Code Audit Tab]                          |
| [Disaster / Seismic Tab]                          | • 9-Column Indian Standards Checklist        |
| • Peak Ground Acceleration kh (g), kv (g)         | • IS 456 (Flexure, Shear, Crack Width)       |
| • Groundwater Table Depth (m)                     | • IS 2911 (Bored Pile Axial/Lateral Fixity)  |
| • Liquefaction Excess Ratio r_u (0 - 100%)        | • IS 800 (Strut Compressive Buckling)        |
| • Waveform Selector (.AT2 / Synthetic Ricker)     | • [Export Audit Sheet (.md)...] Button       |
+---------------------------------------------------+----------------------------------------------+
| Bottom Status Bar: Analytical Solve (< 1 ms @ 60 FPS) | Background Tasks | Execution Diagnostics  |
+--------------------------------------------------------------------------------------------------+
```

---

## 4. Step-by-Step Simulation Workflows

### Workflow 1: Static Cantilever Wall Sizing & Bearing Stability

**Objective:** Validate a conventional reinforced concrete cantilever wall against sliding, overturning, and soil bearing capacity failure in dry granular soil.

1. **Configure Wall Geometry:**
   - Click the **Cantilever Wall** tab on the left sidebar.
   - Set **Stem Height** to `6.00 m`.
   - Set **Stem Base Thick** to `0.70 m` and **Stem Top Thick** to `0.35 m`.
   - Set **Toe Width** to `1.20 m` and **Heel Width** to `2.60 m` (total base width $B = 4.50\text{ m}$).
   - Set **Footing Thick** to `0.80 m`.
   - Leave **Shear Key Depth** at `0.00 m`.
2. **Assign Soil & Subgrade Properties:**
   - Switch to the **Soil Strata** tab.
   - Set **Friction Angle $\phi$** to `34.0°` and **Unit Weight $\gamma$** to `18.5 kN/m³`.
   - Set **Wall Friction $\delta$** to `22.0°` (typically $\approx \frac{2}{3}\phi$).
   - In the **Foundation Soil Bed** section, set **Found. Friction** to `30.0°`, **Found. Cohesion** to `20.0 kPa`, and **Allow. Bearing** to `350.0 kPa`.
3. **Set Static Operating State:**
   - Switch to the **Disaster / Seismic** tab.
   - Ensure **Horizontal $k_h$** is set to `0.00 g` and **Vertical $k_v$** to `0.00 g`.
   - Set **Water Depth** to `10.00 m` (well below the foundation).
4. **Evaluate Stability Badges:**
   - Look at the bottom-right safety card in the **📊 Seismic Waveforms & Dynamics** tab:
     - **Sliding Factor of Safety ($FS_{\text{sliding}}$):** Green badge ($FS \ge 1.50$, typically $\approx 2.10$).
     - **Overturning Factor of Safety ($FS_{\text{overturning}}$):** Green badge ($FS \ge 2.00$, typically $\approx 3.20$).
     - **Bearing Capacity ($FS_{\text{bearing}}$):** Green badge ($FS \ge 2.50$, typically $\approx 3.10$).
5. **Inspect Contact Pressure Distribution:**
   - Peak toe pressure $q_{\max} \approx 135\text{ kPa} \le 350\text{ kPa}$ (allowable bearing capacity).
   - Heel pressure $q_{\min} \approx 65\text{ kPa} > 0$ (no foundation uplift / tension detachment).
   - The resultant line of action lies strictly inside the middle-third ($e \le B/6$).

---

### Workflow 2: Groundwater Flooding, Infiltration & Liquefaction

**Objective:** Simulate an extreme flood event where the groundwater table rises to $2.0\text{ m}$ below the crest with partial backfill liquefaction.

1. **Raise Groundwater Table:**
   - Navigate to the **Disaster / Seismic** tab.
   - Adjust the **Water Depth** spinbox from `10.0 m` down to `2.00 m`.
   - In the 3D viewport, observe the translucent blue **Water Table Plane** cut across the soil and wall.
2. **Observe Hydrostatic Thrust Surcharge:**
   - Notice that total lateral thrust nearly doubles from $\approx 105\text{ kN/m}$ to $\approx 220\text{ kN/m}$ due to hydrostatic water pressure:
     $$P_w = \frac{1}{2}\gamma_w (H - z_w)^2 = \frac{1}{2}(9.81)(6.8 - 2.0)^2 \approx 113.0\text{ kN/m}$$
   - Soil submerged beneath the phreatic surface experiences buoyant unit weight reduction:
     $$\gamma' = \gamma_{\text{sat}} - \gamma_w \approx 19.5 - 9.81 = 9.69\text{ kN/m}^3$$
3. **Simulate Backfill Liquefaction:**
   - Drag the **Liquefaction** slider from `0%` to `40%` ($r_u = 0.40$).
   - The effective internal friction angle degrades automatically:
     $$\phi_{\text{eff}} = \arctan\left((1 - r_u)\tan\phi\right)$$
4. **Inspect Safety Degradation:**
   - The **Sliding Badge** transitions from **SAFE (Green)** to **FAIL (Crimson Red)** ($FS_{\text{sliding}} < 1.0$).
   - The status bar displays a stability warning.
5. **Mitigation via Shear Key:**
   - Switch back to the **Cantilever Wall** tab and set **Shear Key Depth** to `0.80 m` and **Shear Key Width** to `0.50 m`.
   - Passive resistance on the shear key base restores sliding resistance back to $FS_{\text{sliding}} \ge 1.20$.

---

### Workflow 3: Real-Time Earthquake Waveform Playback & Newmark Sliding

**Objective:** Ingest an earthquake accelerogram, simulate dynamic Mononobe-Okabe earth pressures, and track permanent sliding displacement in real time.

1. **Select Waveform Input:**
   - On the **Disaster / Seismic** tab, locate the **Earthquake Waveform Input** group:
     - **Synthetic Ricker Wavelet:** Select `Synthetic: Ricker Wavelet (2.5 Hz)` for impulsive near-fault shaking.
     - **Harmonic Sweep:** Select `Synthetic: Harmonic Sweep (1 - 8 Hz)` for resonance testing.
     - **Historical Earthquake Record:** Select `Load Historical .AT2 Record...`, click **Select .AT2 Record File**, and open any standard PEER record (e.g. 1994 Northridge, 1995 Kobe, or El Centro).
2. **Set Seismic Acceleration Intensity:**
   - Set **Horizontal $k_h$** to `0.30 g` and **Vertical $k_v$** to `0.15 g`.
   - The dynamic active earth pressure coefficient $K_{ae}$ increases according to Mononobe-Okabe:
     $$\theta_e = \arctan\left(\frac{k_h}{1 - k_v}\right) = \arctan\left(\frac{0.30}{0.85}\right) = 19.4^\circ$$
   - The dynamic thrust application height moves upwards from $0.33H \to 0.58H$ per Seed & Whitman.
3. **Review 2D Dynamic Signal Plots:**
   - Switch to the bottom **📊 Seismic Waveforms & Dynamics** tab:
     - **Plot 1 ($a(t)$):** Ground acceleration in units of $g$ (cyan line).
     - **Plot 2 ($u(t)$):** Permanent downhill sliding displacement in $\text{cm}$ (orange line).
     - **Plot 3 ($u_w(t)$):** Dynamic pore-water pressure buildup in $\text{kPa}$ (green line).
4. **Start Seismic Wave Playback:**
   - Click **▶ Play Seismic Wave** on the top toolbar.
   - The button switches to **⏸ Pause** and the timeline scrubber moves smoothly across the record at 60 FPS:
     - **3D Wall Deformation:** The concrete wall flexes under dynamic inertial pushing ($\pm m \cdot a(t)$).
     - **Physical Sliding:** Whenever ground acceleration exceeds the wall's yield acceleration $k_y$, the 3D wall and active failure wedge physically slide forward along the foundation interface.
     - **Water Ripples:** The water table surface oscillates with dynamic wave ripples.
     - **Stress Heatmaps:** The stem base stress flashes between low stress and high tensile bending stress.
5. **Interactive Investigation:**
   - Drag the horizontal **Timeline Slider** with your mouse to scrub directly to the peak shockwave pulse.
   - Use **`⏮ Step`** and **`Step ⏭`** buttons to advance frame-by-frame (16 ms increments).
   - Adjust the **Speed** dropdown (`0.25×`, `0.5×`, `1.0×`, `2.0×`) to observe high-frequency seismic oscillations in slow motion.

---

### Workflow 4: Multi-Bay Curved Cylindrical Shell & Bored Pile Foundation Design

**Objective:** Model an advanced retaining system using cylindrical concrete shell panels between vertical piers socketed into bedrock with raking steel struts.

1. **Tune Curved Shell & Pier Geometry:**
   - Click the **Curved Shell** tab on the left sidebar.
   - Set **Panel Height $H$** to `7.00 m`.
   - Set **Bay Span $L_{\text{bay}}$** to `3.50 m`.
   - Set **Curvature Radius $R$** to `4.50 m`.
   - Set **Shell Thickness $t$** to `0.40 m`.
   - Set **Number of Bays** to `3` or `4`.
   - In the **Vertical Pier Dimensions** group, set **Pier Width $b_p$** to `0.80 m`, **Pier Depth $d_p$** to `1.20 m`, and **Pier Height $h_p$** to `7.50 m`.
2. **Observe Horizontal Soil Arching Relief:**
   - Because $L_{\text{bay}} / R \le 1.0$, horizontal arching develops between the rigid piers.
   - The effective lateral pressure pushing against the center of the curved shell panel is reduced by **$30\% - 65\%$** compared to a flat wall (Handy/Terzaghi modified arching).
   - Bending moments in the thin shell panel drop, allowing a much thinner concrete section ($0.35\text{ m} - 0.45\text{ m}$) than a conventional cantilever wall of the same height.
3. **Configure Bored Pile Substructure:**
   - Switch to the **Strut & Piles** tab.
   - Set **Pile Diameter $D_p$** to `1.00 m`.
   - Set **Embedment Length $L_{\text{pile}}$** to `14.00 m`.
   - Set **Rock Socketing Length** to `2.50 m` (securing the pile toe into sound bedrock).
   - Notice the automatic center-to-center spacing enforcement ($s_p \ge 2.5 D_p = 2.50\text{ m}$) ensuring no group block shear failure.
4. **Configure Multi-Tier Raking Steel Struts:**
   - Select **Steel Section** from the catalog: `CHS 355.6x12.5 (Fe 250)`.
   - Set **Number of Strut Levels** to `2`.
   - Set **Level 1 Elevation** to `2.50 m` (measured from base) and **Level 2 Elevation** to `5.00 m`.
   - Set **Strut Rake Angle** to `25.0°`.
   - Raking struts transfer lateral earth forces into deep passive anchor blocks, relieving flexural demands on the vertical piers.

---

### Workflow 5: Live Indian Standards Code Audit (IS 456 / 2911 / 800)

**Objective:** Perform a real-time regulatory compliance audit verifying concrete flexure, shear, crack widths, bored pile fixity, and steel strut buckling.

1. **Open the Compliance Dashboard:**
   - In the lower right panel, switch to the **📋 IS Design Audit (IS 456 / 2911 / 800)** tab.
2. **Interpret the Live Audit Checklist:**
   The table displays 9 structured engineering columns:
   - **Component:** Structure being checked (`RC Shell Panel`, `Bored Pile Foundation`, `Steel Strut`).
   - **Design Check:** Specific failure mode examined (`Flexural Moment Resistance`, `Transverse Shear Stress`, `Surface Crack Width Limit`, `Axial Compression Capacity`, `Lateral Deflection & Fixity`, `Compressive Buckling Resistance`, `Slenderness Ratio Limit`).
   - **IS Clause:** Specific legal reference (e.g. `IS 456:2000 Cl. 38.1 & Annex G`, `IS 2911:2010 Appendix B & C`, `IS 800:2007 Cl. 7.1.2 & Table 9c`).
   - **Demand vs. Capacity:** Direct comparison with engineering units ($\text{kNm/m}$, $\text{kN}$, $\text{MPa}$, $\text{mm}$).
   - **Unity Ratio (UR = Demand / Capacity):**
     - **Green (`PASS`):** $\text{UR} \le 0.90$ (Adequate safety margin).
     - **Orange (`WARNING`):** $0.90 < \text{UR} \le 1.00$ (High utilization; monitor section).
     - **Red (`FAIL`):** $\text{UR} > 1.00$ (Code violation; redesign required).
   - **Detailing / Remarks:** Exact bar sizing callouts (e.g. `2-layer T16 @ 125 mm c/c`, `12-T25 Cage with T10 helical @ 100 mm pitch`).
3. **Export Audit Calculation Sheet:**
   - Click **"Export Audit Sheet (.md)..."** in the top right of the audit tab.
   - Choose a save destination (e.g. `is_compliance_audit.md`).
   - The generated Markdown file contains complete calculation formulas, input parameters, code citations, and summary tables suitable for formal submission to regulatory review bodies.

---

### Workflow 6: Deep Continuum Soil-Structure Interaction (Kratos FEA)

**Objective:** Execute multi-threaded finite element continuum dynamics with viscous radiation boundary damping using KratosMultiphysics.

1. **Verify Geometric & Soil Setup:**
   - Ensure wall dimensions and soil layers are set as desired.
2. **Launch the Kratos Solver:**
   - Click **"⚙ Run Kratos GeoMechanics FEA"** on the top toolbar.
   - The button switches to **"⏳ Kratos Solving..."** and disables to prevent concurrent solver collisions.
3. **Monitor Execution:**
   - The FEA solver runs on a dedicated background `QThread` without freezing the desktop user interface.
   - The bottom status bar reports step-by-step progress:
     ```
     Kratos FEA Step 120/400 (t=2.40s | Crest Deflection=2.15 cm | Pore Pressure=48.2 kPa)
     ```
4. **Review FEA Results:**
   - A completion dialog presents the summary:
     - Total dynamic steps integrated.
     - Maximum crest deflection in $\text{cm}$.
     - Maximum dynamic pore-water pressure generation in $\text{kPa}$.
     - Convergence confirmation (`CONVERGED`).

---

### Workflow 7: Automated AutoCAD DXF & Engineering PDF Report Generation

**Objective:** Export production-ready CAD drawings with standardized layers and a formal engineering calculation PDF report.

#### 1. Exporting Layered AutoCAD DXF Drawings:
1. Click **"📐 AutoCAD DXF"** on the top toolbar (or select **Export → Export AutoCAD DXF (.DXF)...**).
2. Choose a file path (e.g. `retaining_wall_cad.dxf`).
3. In $< 0.1\text{ seconds}$, a layered AutoCAD DXF file is generated conforming to civil engineering CAD standards:
   - **`WALL_OUTLINE` (Color 7: White/Black):** Concrete perimeter of curved shell panels, pier columns, and bored piles.
   - **`REBAR_REINFORCEMENT` (Color 1: Red):** Circumferential mesh, longitudinal pile rebar cages, and helical ties.
   - **`STRUT_DETAILS` (Color 4: Cyan):** Raking steel struts, bracket connections, and centerline axes.
   - **`DIMENSIONS_AND_TEXT` (Color 3: Green):** Elevation markers, bay span dimensions, curvature radii, and formal title block.
4. Open the generated file in **AutoCAD**, **Civil 3D**, or **LibreCAD** for final drafting and construction plan integration.

#### 2. Generating Geotechnical PDF Reports:
1. Click **"📄 PDF Report"** on the top toolbar (or press `Ctrl+P`).
2. Choose a file path (e.g. `retaining_wall_calculation_report.pdf`).
3. In $< 0.4\text{ seconds}$, a multi-page PDF document is generated containing:
   - **Executive Header:** Project metadata, date, and software version.
   - **Dimensioned Cross-Section Diagram:** Vector graphics diagram of stem, footing, shear key, water table, active thrust $P_{ae}$, and bearing pressure trapezoid.
   - **Summary Tables:** Geometry, soil strata, seismic inputs, and safety factors.
   - **Code Verification Checklist:** Automatic pass/fail checks against **IS 14458**, **Eurocode 7**, and **AASHTO LRFD**.

---

## 5. 3D Viewport Controls, Visualization & Slicing Tools

The 3D scientific viewport is powered by PyVista and VTK for hardware-accelerated rendering:

### Camera Navigation
- **Left-Click + Drag:** Orbit / rotate 3D camera around the structure.
- **Right-Click + Drag (or Mouse Wheel):** Smooth zoom in / out.
- **Middle-Click + Drag (or Shift + Left-Click):** Pan camera across the scene.
- **Reset 3D Camera Button:** Restores standard isometric framing.

### Visualization Controls Bar
Located directly above the 3D viewport:
- **Field Selector:** Switch between **Tensile Stress (MPa)**, **Von Mises Stress (MPa)**, and **Pore Pressure (kPa)**.
- **Colormap:** Choose between `plasma`, `viridis`, `coolwarm`, and `magma`.
- **Warp Factor:** Adjust the spinbox ($0\times$ to $50\times$) to visually exaggerate dynamic flexural bending and sliding displacements.
- **Feature Toggles:**
  - **☑ Soil:** Show/hide semi-transparent backfill and foundation soil beds.
  - **☑ Water:** Show/hide the translucent blue water table plane with dynamic waves.
  - **☑ Failure Wedge:** Render the active Coulomb/Mononobe-Okabe failure wedge propagating from the wall heel.
  - **☑ Pressure Glyphs:** Display 3D directional arrow cones indicating lateral earth thrust and base bearing pressure.
- **Orthographic Cutting Plane (Slice Tool):**
  - Select **X Cut**, **Y Cut**, or **Z Cut** from the slice dropdown.
  - Move the **Slice Slider** ($0\%$ to $100\%$) to cut a cross-section through the wall core and inspect internal stresses.

---

## 6. 2D Waveform Dashboard & Dynamic Safety Badges

Located on the **📊 Seismic Waveforms & Dynamics** tab:

### 3-State Geotechnical Safety Badges
Safety factors evaluate in real time against code thresholds:
- 🟢 **SAFE (Green):** $FS \ge FS_{\text{req}}$ (e.g. $FS_{\text{sliding}} \ge 1.12$, $FS_{\text{overturn}} \ge 1.20$, $FS_{\text{bearing}} \ge 2.00$).
- 🟡 **MARGINAL (Yellow):** $1.00 \le FS < FS_{\text{req}}$. Design operates close to capacity.
- 🔴 **FAIL (Red):** $FS < 1.00$. Active structural failure or sliding instability.

### Structural Integrity Monitors
- **$P_{ae}$ Dynamic Thrust:** Total instantaneous lateral load in $\text{kN/m}$.
- **Stem Base Tension:** Peak tensile bending stress in concrete. Flashes red with **`[CRACKED]`** if tension exceeds the concrete rupture modulus ($f_{cr} = 0.7\sqrt{f_{ck}}$), or green with **`[ELASTIC]`** if uncracked.

---

## 7. Project Archiving, CAD Mesh Export & PDF Reports

### Unified Project Sessions (`.o3d` Bundles)
orang3D sessions save as single `.o3d` archive bundles containing:
- `project.json`: All geometry, soil strata, seismic inputs, analysis results, and schema version metadata.
- `simulation.h5`: GZIP-compressed HDF5 arrays for time, ground acceleration, sliding displacement, and pore pressure.

- **To Save a Session:** Press `Ctrl+S` or click **💾 Save** on the toolbar.
- **To Open a Session:** Press `Ctrl+O` or click **📂 Open** on the toolbar.

### 3D CAD Mesh Export Formats
From the top **Export** menu:
- **`.vtk` (ParaView / VisIt):** 3D solid mesh with nodal coordinates, element connectivity, and scalar stress fields.
- **`.stl` (3D CAD / 3D Printing):** Boundary triangulated surface mesh for SolidWorks, Inventor, or 3D printers.
- **`.obj` (Wavefront Polygonal Mesh):** Standard 3D polygonal mesh with surface normals for Blender or WebGL digital twins.
- **`.csv` (RFC-4180 Waveform Table):** Dynamic time-history curves ($t$, $a(t)$, $u(t)$, $u_w(t)$) in 8-decimal scientific notation.

---

## 8. Engineering Reference & Governing Equations

### 8.1 Mononobe-Okabe Dynamic Active Thrust

$$K_{ae} = \frac{\cos^2(\phi - \theta_e - \theta)}{\cos\theta_e \cos^2\theta \cos(\delta + \theta + \theta_e) \left[1 + \sqrt{\frac{\sin(\phi + \delta)\sin(\phi - \theta_e - \beta)}{\cos(\delta + \theta + \theta_e)\cos(\beta - \theta)}}\right]^2}$$

Where:
- $\phi$: Soil internal friction angle.
- $\delta$: Wall-soil interface friction angle ($\approx \frac{2}{3}\phi$).
- $\theta$: Wall backface inclination from vertical ($0^\circ$ for vertical).
- $\beta$: Backfill slope angle from horizontal.
- $\theta_e = \arctan\left(\frac{k_h}{1 - k_v}\right)$: Seismic inertia angle.

### 8.2 Modified Terzaghi/Handy Horizontal Soil Arching

$$\sigma_h(z) = \left[\frac{\gamma L_{\text{bay}} - 2c}{2 \tan\phi}\right] \left[1 - \exp\left(-\frac{2 K_a \tan\phi \cdot z}{L_{\text{bay}}}\right)\right]$$

Between vertical piers spaced at $L_{\text{bay}} / R \le 1.0$, soil arching reduces active lateral thrust by $30\% - 65\%$.

### 8.3 Newmark (1965) Permanent Sliding Block Integration

$$\ddot{u}(t) = \begin{cases} [a(t) - k_y \cdot g] & \text{if } a(t) > k_y \cdot g \text{ or } \dot{u}(t) > 0 \\ 0 & \text{otherwise} \end{cases}$$

$$u(t) = \int_0^t \dot{u}(\tau)\,d\tau \quad \text{where } \dot{u}(t) = \int_0^t \ddot{u}(\tau)\,d\tau \ge 0$$

### 8.4 IS 456:2000 Concrete Limit States

- **Ultimate Flexural Resistance (Cl. 38.1):**
  $$M_{u,\text{lim}} = 0.36 \frac{x_{u,\max}}{d} \left(1 - 0.42 \frac{x_{u,\max}}{d}\right) b d^2 f_{ck}$$
- **Nominal Shear Stress (Cl. 40):**
  $$\tau_v = \frac{V_u}{b d} \le \tau_c \quad \text{and} \quad \tau_v \le \tau_{c,\max}$$
- **Surface Crack Width Limit (Annex F):**
  $$w_{cr} = \frac{3 a_{cr} \epsilon_m}{1 + 2\left(\frac{a_{cr} - c_{\min}}{h - x}\right)} \le 0.10\text{ mm} \text{ (aggressive environmental exposure)}$$

### 8.5 IS 2911:2010 Bored Pile Capacities

- **Static Axial Compression (Appendix B):**
  $$Q_u = Q_b + Q_s = \frac{\pi D_p^2}{4} \left(c N_c + \sigma'_v N_q\right) + \pi D_p \sum \alpha c_a \Delta L$$
- **Depth of Virtual Fixity (Appendix C):**
  $$T = \left(\frac{E_p I_p}{\eta_h}\right)^{1/5} \quad \implies \quad L_f \approx 2.0 T \text{ to } 2.4 T$$

### 8.6 IS 800:2007 Structural Steel Strut Buckling

- **Design Compressive Strength (Cl. 7.1.2):**
  $$P_d = A_e f_{cd} \quad \text{where } f_{cd} = \frac{f_y / \gamma_{m0}}{\phi + \left[\phi^2 - \lambda^2\right]^{0.5}}$$
  $$\phi = 0.5 \left[1 + \alpha(\lambda - 0.2) + \lambda^2\right], \quad \lambda = \sqrt{\frac{f_y}{f_{cr}}}, \quad f_{cr} = \frac{\pi^2 E}{(KL/r)^2}$$
  For Circular Hollow Sections (CHS), Buckling Class 'a' applies with imperfection factor $\alpha = 0.21$.

---

## 9. Troubleshooting & Frequently Asked Questions (FAQs)

### Q1: The 3D Viewport is completely blank or black on Linux. How do I fix it?
- **Cause:** Some Linux environments running Wayland or running without discrete GPU drivers have issues with hardware OpenGL initialization in PyVista.
- **Fix:** Launch orang3D using software rendering fallback:
  ```bash
  LIBGL_ALWAYS_SOFTWARE=1 python main.py
  ```

### Q2: Why is the Sliding Safety Badge showing red "FAIL"?
- **Cause:** High seismic acceleration $k_h$, a rising groundwater table causing buoyancy loss, or insufficient foundation friction.
- **Fix:** 
  1. Increase **Heel Width** in the Cantilever tab (adding stabilizing soil dead weight).
  2. Add a **Shear Key** ($0.5\text{ m} - 1.0\text{ m}$ depth) in the Cantilever tab.
  3. If using the curved wall system, increase bored pile embedment length $L_{\text{pile}}$ and rock socketing depth.

### Q3: When I click "▶ Play Seismic Wave", nothing seems to move. Why?
- **Cause 1:** Ground acceleration might be very low ($k_h \le 0.05\text{ g}$), so wall bending is too small to see with the naked eye.
  - **Fix:** Increase the **Warp:** spinbox in the viewport toolbar from `1.0×` to `5.0×` or `10.0×` to visually exaggerate oscillations.
- **Cause 2:** The playhead may have reached the end of the record and looping is turned off.
  - **Fix:** Check **🔁 Loop** in the transport bar or click **⏮ Step** to rewind to $t = 0$.

### Q4: How do I load my own earthquake ground motion data?
- **Yes.** On the **Disaster / Seismic** tab, select **Load Historical .AT2 Record...** and click **Select .AT2 Record File**. orang3D automatically parses PEER NGA/COSMOS `.AT2` files, extracts the sampling interval $dt$, removes linear baselines, and applies a Butterworth bandpass filter ($0.1 - 25\text{ Hz}$).

### Q5: Can I open the exported `.dxf` file in AutoCAD or Civil 3D?
- **Yes.** The exported `.dxf` file is formatted to the standard AutoCAD R2000 (`AC1015`) specification with standard AutoCAD Color Index (ACI) codes. All layers (`WALL_OUTLINE`, `REBAR_REINFORCEMENT`, `STRUT_DETAILS`, `DIMENSIONS_AND_TEXT`) are fully preserved and editable in AutoCAD, Civil 3D, SolidWorks, and LibreCAD.

### Q6: How do I know if the Kratos FEA simulation has converged?
- Look at the bottom status bar and completion popup dialog. It will report `Kratos FEA Completed: 400 steps solved! Max Crest Deflection: X.XX cm`. If divergent, an alert will display the physical non-convergence step and reason.
