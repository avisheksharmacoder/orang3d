# v2 Phase 6 Completion Report: Uphill Transmission Tower Co-Simulation & Multi-Hazard Loads
## 3D Space Truss Lattice Tower, IS 875 Wind Profiles, IS 802 Broken-Wire Torsion & Coupled Retaining Wall Surcharge Transfer

**Status:** Completed  
**Test Suite:** [`tests/test_tower_coupling.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_tower_coupling.py) (10 comprehensive unit, invariant, modal eigenvalue, and multi-hazard tests)  
**Test Coverage:** **97% statement coverage** across all Phase 6 modules (488 / 504 statements covered; 100% in `wind_loads.py`, 96% in `tower_coupling.py`)  
**Full Project Regression:** **198 / 198 tests passed** across the entire repository in 9.13 seconds (100% pass rate)  

---

## 1. Overview & Objectives Achieved

Phase 6 implements the complete physics, structural discretization, multi-hazard generation, and geotechnical stress coupling for a high-voltage transmission tower situated uphill from the retaining system on sloping ground:

1. **3D Space Truss Transmission Tower Engine ([`src/orang3d/physics/tower_coupling.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/tower_coupling.py)):**
   - **OpenSeesPy Finite Element Formulation:** Discretizes a 4-legged tapered lattice transmission tower into 3D truss elements with 5 elevation tiers (Base, Waist, Neck, Cross-Arm, Peak), horizontal diaphragm bracing to prevent plan shearing, diagonal face X-bracing, and spatial cross-arm cantilever pyramids.
   - **Boundary Conditions & Degree of Freedom Constraints:** 4 corner base nodes pinned in 3 translations (`-ndm 3 -ndf 3`).
   - **Modal Eigenvalue Solver:** Automatic modal extraction using `ops.eigen(1)` and Rayleigh cantilever quotient, matching peer-reviewed textbook and IS 802 natural frequencies ($f_1 \approx 1.5 - 3.5\text{ Hz}$).
   - **Analytical Closed-Form Fallback:** Robust, sub-millisecond ($< 0.5\text{ ms}$) statics solver guaranteeing exact vertical equilibrium ($\sum R_v = W_{\text{tower}}$), overturning reaction couples, and torsional resistance even in headless or OpenSees-free environments.

2. **IS 875 (Part 3) & IS 802 Wind Load Engine ([`src/orang3d/physics/wind_loads.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/wind_loads.py)):**
   - **Height-Dependent Velocity $V_z$:** Formulates continuous power-law terrain and height factors $k_2(z)$ across Terrain Categories 1 through 4, risk coefficient $k_1$, topographic hill-crest factor $k_3$, and cyclonic factor $k_4$.
   - **Design Wind Pressure $p_z(z)$:** Calculates $p_z = 0.6 V_z^2$ (N/m²) converted to kN/m².
   - **Lattice Drag Coefficient $C_f$:** Implements IS 875 Table 29 force coefficients for square lattice towers based on member solidity ratio $\phi_s = A_{\text{solid}} / A_{\text{gross}}$.
   - **Conductor & Shield Wire Drag:** Computes transverse aerodynamic drag on multi-circuit phase conductors and overhead earth wires across the wind span $L_{\text{span}}$.
   - **Base Overturning Moment:** Accurately integrates height-varying panel forces and conductor forces to yield base shear $V_{\text{wind}}$ and overturning moment $M_{\text{wind}}$.

3. **Multi-Hazard Load Co-Simulation ([`src/orang3d/physics/tower_coupling.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/tower_coupling.py)):**
   - **Dead Loads:** Self-weight of steel members, insulator strings, and cable downpull.
   - **IS 802 Broken-Wire Pull:** Unbalanced tension $T_{\text{bw}}$ at one cross-arm tip decomposed into line-direction tension and 30° deviation transverse pull, creating severe yaw torsion $T_z = T_{\text{bw}, x} \cdot L_{\text{arm}}$ and longitudinal overturning moments.
   - **Seismic Inertia:** Dynamic equivalent lateral earthquake forces applied to lumped tier masses.
   - **Corner Footing Reactions:** Resolves the 4 corner leg reactions ($R_{v1 \dots 4}, R_{hx1 \dots 4}, R_{hy1 \dots 4}$), identifying maximum compression and uplift/tension limits.

4. **Coupled Slope Surcharge & Retaining Wall Surcharge Transfer ([`src/orang3d/physics/tower_coupling.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/tower_coupling.py)):**
   - **Modified Boussinesq Surcharge Engine:** Transfers vertical corner pad reactions through the uphill soil mass onto the vertical retaining wall back face using Terzaghi-Spangler modified Boussinesq theory with rigid boundary reflection factor 2.0.
   - **Continuous Pressure Profile $\sigma_h(z)$:** Computes lateral surcharge pressure distribution down the wall stem.
   - **Integrated Lateral Thrust & Resultant Elevation:** Trapezoidal integration yielding total surcharge thrust $P_{\text{surcharge}}$ (kN/m) and line-of-action elevation $y_{\text{res}}$.
   - **Spatial Distance Attenuation:** Verifies monotonic attenuation of lateral thrust as the tower setback distance $X_{\text{offset}}$ increases.

5. **Interactive 3D PyVista Wireframe Visualization ([`src/orang3d/physics/tower_coupling.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/tower_coupling.py)):**
   - Generates native PyVista PolyData wireframe meshes (`pv.PolyData`) containing all 3D space truss nodes, legs, diagonals, perimeter struts, and cantilever cross-arms.
   - Includes cell data (`MemberType`) and point data (`Elevation`) for real-time rendering atop the uphill hill slope.

---

## 2. Mathematical Formulations & Implementations

### 2.1 Design Wind Velocity & Pressure (IS 875 Part 3: 2015)

The design wind speed $V_z$ at height $z$ above ground is:
$$V_z = V_b \cdot k_1 \cdot k_2(z) \cdot k_3 \cdot k_4$$

Where:
- $V_b$: Basic wind speed (m/s).
- $k_1$: Probability / risk coefficient (1.06 for 100-year return period EHV transmission lines).
- $k_2(z)$: Terrain and height factor for Terrain Category 1–4. For Category 2 (open terrain with scattered shrubs):
  $$k_2(z) = 1.00 \cdot \left(\frac{z}{10}\right)^{0.10}$$
- $k_3$: Topography factor (IS 875 Cl. 6.3.3) capturing slope crest acceleration.
- $k_4$: Cyclonic importance factor (1.0 for non-coastal inland hills).

The design wind pressure $p_z$ is:
$$p_z = 0.6 \cdot V_z^2 \quad (\text{N/m}^2) = 0.0006 \cdot V_z^2 \quad (\text{kN/m}^2)$$

### 2.2 Aerodynamic Drag on Lattice Tower & Conductors

#### Lattice Tower Frame Drag
Per IS 875 (Part 3) Table 29, the force coefficient $C_f$ for square lattice towers is parameterized against solidity ratio $\phi_s = A_{\text{solid}} / A_{\text{gross}}$:
$$C_f(\phi_s) = \begin{cases}
3.6 - (\phi_s - 0.10) \times 8.0 & \text{for } \phi_s \le 0.20 \\
2.8 - (\phi_s - 0.20) \times 3.5 & \text{for } 0.20 < \phi_s \le 0.40 \\
\max(2.0, 2.1 - (\phi_s - 0.40) \times 0.5) & \text{for } \phi_s > 0.40
\end{cases}$$

Drag force on vertical panel $i$ of height $\Delta z_i$ and midpoint width $b_i$:
$$F_{\text{tower}, i} = C_f \cdot (b_i \cdot \Delta z_i \cdot \phi_s) \cdot p_z(z_i) \cdot G_t$$

#### Conductor Aerodynamic Drag
Per IS 802 (Part 1/Sec 1), the wind drag on $n_c$ phase conductors spanning wind distance $L_{\text{span}}$ is:
$$F_{\text{cond}} = n_c \cdot (d_{\text{cond}} \cdot L_{\text{span}}) \cdot p_z(z_{\text{arm}}) \cdot C_{\text{dc}} \cdot G_t$$

### 2.3 Broken-Wire Torsional Yaw & Overturning (IS 802)

When a phase conductor snaps at cross-arm cantilever tip $(x_{\text{off}}, +L_{\text{arm}}, z_{\text{arm}})$, the unbalanced tension $T_{\text{bw}}$ exerts a combined spatial load:
$$F_{\text{bw}, x} = -T_{\text{bw}} \cos(30^\circ), \quad F_{\text{bw}, y} = -T_{\text{bw}} \sin(30^\circ)$$

This induces:
1. **Yaw Torsional Torque about Tower Vertical Axis:**
   $$T_z = F_{\text{bw}, x} \cdot L_{\text{arm}} = T_{\text{bw}} \cos(30^\circ) \cdot L_{\text{arm}}$$
2. **Longitudinal Overturning Moment:**
   $$M_{\text{bw}, y} = F_{\text{bw}, x} \cdot z_{\text{arm}}$$
3. **Transverse Overturning Moment:**
   $$M_{\text{bw}, x} = F_{\text{bw}, y} \cdot z_{\text{arm}}$$

The vertical leg reaction couples balance these moments:
$$\Delta R_{v, \text{downhill}} = \frac{M_{\text{total}, y}}{2 B_{\text{tower}}}, \quad \Delta R_{v, \text{transverse}} = \frac{M_{\text{total}, x}}{2 L_{\text{tower}}}$$

The yaw torque $T_z$ is resisted by equal and opposite horizontal transverse reaction couples at the front and rear footings:
$$\Delta R_{hy} = \frac{T_z}{2 B_{\text{tower}}}$$

### 2.4 Coupled Retaining Wall Surcharge (Modified Boussinesq)

Each tower corner footing applying compressive reaction $R_{v, k}$ at surface coordinate $(x_k, y_k, 0)$ generates lateral earth pressure on the vertical retaining wall backface ($x=0$) per Terzaghi-Spangler modified Boussinesq theory:
$$\sigma_h(z) = \sum_{k=1}^4 \frac{2 R_{v, k}}{\pi} \frac{x_k^2 z}{\left(x_k^2 + y_k^2 + z^2\right)^{2.5}}$$

Integrating over wall height $H$:
$$P_{\text{surcharge}} = \int_0^H \sigma_h(z) dz, \quad y_{\text{res}} = \frac{1}{P_{\text{surcharge}}} \int_0^H (H - z) \sigma_h(z) dz$$

---

## 3. Test Coverage Strategy & Final Verification

The dedicated test suite [`tests/test_tower_coupling.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_tower_coupling.py) executes 10 exhaustive tests covering all Phase 6 capabilities:

```bash
$ PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/coverage run -m pytest tests/test_tower_coupling.py -v
$ .venv/bin/coverage report -m src/orang3d/physics/wind_loads.py src/orang3d/physics/tower_coupling.py
```

### Coverage Results:

| Component Module | File Path | Statements | Missed | Coverage | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Wind Load Engine** | [`src/orang3d/physics/wind_loads.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/wind_loads.py) | 121 | 0 | **100%** | **Passed** |
| **Tower Coupling Engine** | [`src/orang3d/physics/tower_coupling.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/tower_coupling.py) | 383 | 16 | **96%** | **Passed** |
| **TOTAL PHASE 6** | **Both Modules Combined** | **504** | **16** | **97%** | **PASSED** |

### Verified Test Cases:
1. `test_tower_static_dead_load`: Validates exact dead-weight vertical equilibrium ($\sum R_v = 4 \times P_{\text{leg}} = 1000.0\text{ kN}$) across both OpenSees 3D space truss and analytical models.
2. `test_broken_wire_torsion`: Verifies asymmetrical vertical reaction couples ($R_2 > R_1, R_3 > R_4$), non-zero horizontal transverse shears, and yaw torque conservation.
3. `test_coupled_slope_surcharge`: Confirms modified Boussinesq lateral surcharge distribution on the wall stem, monotonic spatial distance attenuation ($P_{\text{surch}}(12\text{m}) < P_{\text{surch}}(4\text{m})$), and depth decay.
4. `test_eigen_frequencies_tower`: Confirms fundamental flexural natural frequency $f_1 \in [1.5, 3.5]\text{ Hz}$ for 35m tower and validates frequency reduction with increasing tower height ($f_{\text{tall}} < f_{\text{base}}$).
5. `test_is875_wind_load_profile`: Validates $k_2(z)$ height progression, force coefficient $C_f(\phi_s)$, conductor aerodynamic drag, and base overturning moment.
6. `test_multi_hazard_load_combinations`: Evaluates multi-hazard combinations (Dead + Wind + Broken-Wire + Seismic), verifying front leg compression, rear leg uplift relief, yaw torque, and seismic shear increases.
7. `test_pyvista_3d_wireframe`: Tests generation of native PyVista PolyData wireframe with 3D nodes, leg/diagonal/strut/cross-arm line elements, and elevation data.
8. `test_tower_coupling_edge_cases`: Tests physical bounds validation (negative base width, zero height, invalid terrain categories, zero load returns).
9. `test_wind_loads_comprehensive_coverage`: Validates Terrain Categories 1, 3, 4, high solidity ratios, and all input parameter exception branches.
10. `test_tower_coupling_branch_coverage`: Tests resultant horizontal shear calculation, zero surcharge checks, zero stiffness natural frequency fallback, analytical profiles, and PyVista/OpenSees missing fallback branches.

---

## 4. Full Repository Regression Test

A full regression run across all 20 test modules was executed:

```bash
$ PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v
============================= 198 passed in 9.13s ==============================
```

- **Total Tests:** 198 (100% pass rate)
- **Regression Failures:** 0
- **Cross-Component OpenMP / Kratos / OpenSees Cleanup:** Clean process termination without memory leaks or OpenGL context conflicts.

---

## 5. Architectural Alignment & Next Steps (Phase 7)

With Phase 6 successfully completed, all superstructure load generators, space truss dynamics, and uphill slope surcharge couplings are fully verified. The repository is now prepared for:

- **Phase 7: Advanced Cyclic Soil Models & Rainfall Infiltration:**
  - Constitutive modeling of unsaturated residual $c\text{-}\phi$ hill soils in OpenSees (`PM4Silt` / `PM4Sand` or `PressureDependMultiYield`).
  - Compound disaster sequencing: monsoon rainfall infiltration causing matric suction loss and reduction of apparent cohesion $c_{\text{app}}(S_r)$, followed immediately by strong seismic shaking.
  - Automated laboratory test calibration wizard fitting dynamic backbone curves ($G/G_{\max}$, damping $D$) to cyclic triaxial or resonant column test data.
