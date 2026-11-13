# Simulation Guide 06: Full 3D Continuum Nonlinear Dynamic SSI FEA
**Numerical Solver Engine:** OpenSeesPy 3D / KratosMultiphysics GeoMechanics

---

## 1. Engineering Objective
Execute a rigorous 3D continuum finite element analysis of dynamic Soil-Structure Interaction (SSI) using conformal 8-node hexahedral elements (`stdBrick` / `bbarBrickUP`), thin-layer Coulomb friction interfaces, and Lysmer-Kuhlemeyer absorbing dashpot boundaries. Demonstrate:
1. Verification of the geostatic $K_0$ stress state under pure self-weight with zero spurious lateral movement.
2. Accurate capture of 3D spatial corner effects and end-constraint arching on a finite-length wall.
3. Multi-directional earthquake time-history integration ($X+Y+Z$) with nonlinear soil plasticity (`PressureDependMultiYield02`).
4. Elimination of artificial box wave reflections using Lysmer-Kuhlemeyer radiation damping dashpots.

---

## 2. Continuum Mesh Discretization

| Subsystem | Parameter | Variable | Discretization Specification |
| :--- | :--- | :--- | :--- |
| **Wall Solid** | Elements | `CellType` | 8-Node Hexahedra (`VTK_HEXAHEDRON`) |
| **Wall Dimensions** | $(H, B, L)$ | Geometry | $H = 6.10\text{ m}, B = 4.00\text{ m}, L = 4.00\text{ m}$ *(Short wall)* |
| **Backfill Soil Block**| Dimensions | Extents | $X \in [B_{\text{stem}}, 3.5H], Y \in [0, H], Z \in [-L/2, L/2]$ |
| **Subgrade Bed** | Dimensions | Extents | Depth $\ge 2.5B$, lateral span $\ge 4B$ |
| **Soil-Wall Interface**| Formulation | Contact | Thin-layer Coulomb friction interface ($\mu = \tan\delta$) |
| **Boundaries** | Lateral & Base | Dashpots | Lysmer-Kuhlemeyer viscous dashpots ($C_p = \rho V_p, C_s = \rho V_s$) |

---

## 3. Constitutive & Ground Motion Parameters

| Subsystem | Parameter | Variable | Input Value | Unit |
| :--- | :--- | :--- | :---: | :---: |
| **Concrete Wall** | Elastic Modulus | $E_c$ | `28,500` | MPa |
| **Concrete Wall** | Poisson's Ratio | $\nu_c$ | `0.20` | - |
| **Concrete Wall** | Density | $\rho_c$ | `2,400` | kg/m³ |
| **Soil Constitutive** | Material Model | `mat` | `PressureDependMultiYield02` | - |
| **Soil Properties** | Shear Modulus $G_{\max}$ | $G_0$ | `90.0` | MPa |
| **Soil Properties** | Bulk Modulus $B_{\max}$ | $B_0$ | `220.0` | MPa |
| **Soil Properties** | Friction Angle | $\phi$ | `32.0` | deg |
| **Soil Properties** | Soil Density | $\rho_s$ | `1,850` | kg/m³ |
| **Earthquake** | Horizontal PGA | $k_h$ | `0.30` | g |
| **Earthquake** | Vertical PGA | $k_v$ | `0.10` | g |

---

## 4. Step-by-Step Execution in orang3D

1. **Load 3D Continuum Benchmark Preset:**
   * Go to menu **`File -> Load Benchmark Preset... -> 3D Corner Effect Benchmark — Short Wall (0.30g Shaking)`**.
   * The short 4.0 m wall geometry and 0.30g seismic parameters populate.
2. **Launch 3D FEA Solver:**
   * In the top toolbar, click **`🧱 Run 3D FEA (OpenSees)`** (or **`⚙ Run Kratos GeoMechanics FEA`** on Linux).
   * An asynchronous background worker starts. Progress is displayed in real time without freezing the UI.
   * Time-history displacements, 3D stress tensors, and interface contact pressures are solved and cached.
3. **Inspect 3D Deformation Field:**
   * In the 3D viewport, adjust **`Deform Warp`** slider to `5.0x` magnification.
   * Orbit the camera around the 3D volume.
   * Set **`Scalar`** to **`Von Mises Stress`** to visualize stress flow through the foundation.
4. **Compare Analytical vs. 3D FEA Profiles:**
   * Click the bottom tab **`⚖ Theory vs. FEA`**.
   * Inspect the side-by-side earth pressure profiles comparing Rankine, Mononobe-Okabe, and 3D FEA mid-bay versus corner stresses.
5. **Export Research Archive:**
   * Go to menu **`Export -> Export Research Archive (.h5 + .json)...`**.
   * Saves full HDF5 nodal displacement vectors and Cauchy stress arrays for external scientific processing.

---

## 5. Expected Visual & Graphical Behavior
* **3D Viewport:**
  * Shows the fully deformed 3D continuum mesh with non-glued sliding contact along the backface.
  * Earth pressure contours on the wall back face show 3D corner arching: low lateral pressure at the rigid side edges, rising to peak lateral pressure at mid-span.
* **Bottom Panel (`⚖ Theory vs. FEA`):**
  * The cyan dots (3D FEA) trace a parabolic distribution with depth that curves back toward zero near the footing base, distinct from the linear triangle of Mononobe-Okabe theory.

---

## 6. Quantitative Verification Benchmarks

| Metric | Governing Formulation | Target Value | Acceptable Tolerance | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Geostatic Vertical Stress** | $\sigma_{yy} = \gamma z$ | Linear Depth | Error $< 0.8\%$ | **PASSED** |
| **Geostatic Lateral Drift** | Residual $u_x$ under gravity | `0.000 mm` | $< 0.05\text{ mm}$ | **PASSED** |
| **3D Corner Arching Effect** | Mid-span vs Corner Pressure Ratio | `1.38` | $\pm 0.10$ | **MATCHED** |
| **Plane-Strain Discrepancy** | 3D Total Thrust vs 2D M-O Thrust| `-14.2%` | $[ -10\%, -18\% ]$ | **MATCHED** |
| **Peak 3D Dynamic Base Shear**| Maximum interface shear | `187.9 kN/m` | $\pm 10.0\text{ kN/m}$ | **MATCHED** |
| **Lysmer Absorbing Boundary** | Reflected impulse energy | `< 3.5%` | $< 5.0\%$ of incident | **PASSED** |
| **Dynamic Resultant Height** | Shift from base $h_{\text{res}} / H$ | `0.48 H` | $0.44 - 0.52 H$ | **MATCHED** |

---

## 7. Headless Python Verification

Verify this exact scenario non-interactively via the terminal:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_continuum_fea_3d.py -k "test_geostatic_k0_patch_test or test_3d_corner_finite_length_reduces_midspan_pressure" -v
```

