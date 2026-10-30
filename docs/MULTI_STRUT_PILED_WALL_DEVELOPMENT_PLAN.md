# orang3D Advanced Geotechnical Suite: 10-Phase Development Plan
## Pile-Supported Multi-Strut Shell Retaining Walls on Seismic Hill Slopes

---

### Executive Overview & Purpose

This engineering blueprint establishes the rigorous, 10-phase roadmap for extending **orang3D** from a standard cantilever/gravity retaining wall tool into the world's first open-source, multi-fidelity design environment for:
1. **Curved RC Shell-Arching Retaining Panels** spanning between discrete vertical piers.
2. **Multi-Tier Raking Struts & Pre-stressed Anchors** with installation staging, tension slackening, and cyclic compression buckling.
3. **Bored Cast-in-Situ Floating Piles** embedded in unsaturated residual $c\text{-}\phi$ hill soils without a rock stratum.
4. **Hill-Slope Topography & Topographic Seismic Amplification** using imported Digital Elevation Models (DEMs).
5. **Coupled Uphill Transmission Tower Interactions** under multi-hazard wind, broken-wire, and seismic loads.
6. **Full-Chain Indian Standards Design Layer** (IS 1893 Part 3, IS 14458, IS 456, IS 2911, IS 800, IS 802).
7. **Physics-Informed Machine Learning (PINN) Surrogates & Uncertainty Quantification (UQ)** for 60 FPS interactive slider responsiveness.

Every phase adheres to strict test-driven development (TDD), open-source licensing (MIT, BSD, Apache 2.0, LGPL), physical invariant guarantees, and golden benchmark comparisons.

---

## 10-Phase Roadmap Summary

```mermaid
gantt
    title orang3D Advanced Geotechnical Suite Development Roadmap
    dateFormat  X
    axisFormat %d

    section Morphology & Analytical Core
    Phase 1: Advanced Data Contracts, Validation & Invariants        :p1, 0, 1
    Phase 2: 3D Parametric Curved Shell, Pier & Pile Mesher          :p2, after p1, 1d
    Phase 3: Level L0 Analytical Engine (Arching, Piles, IS 1893)   :p3, after p2, 1d

    section Dynamics, BNWF & Topography
    Phase 4: Level L1 BNWF Engine (OpenSeesPy Piles, Struts & Springs):p4, after p3, 2d
    Phase 5: Hill-Slope Topography & DEM Raster Ingestion            :p5, after p4, 1d
    Phase 6: Uphill Transmission Tower Co-Simulation & Multi-Hazard  :p6, after p5, 1d

    section Advanced Physics, Design & AI
    Phase 7: Cyclic Residual Soil Models & Rainfall Infiltration     :p7, after p6, 1d
    Phase 8: Comprehensive Indian Standards (IS Code) Member Design :p8, after p7, 1d
    Phase 9: AI/PINN Fast Surrogates & Uncertainty Quantification    :p9, after p8, 1d
    Phase 10: GUI Integration, CAD Export (ezdxf) & Golden Gate      :p10, after p9, 2d
```

---

## Testing Taxonomy: Six Invariant Verification Pillars

To guarantee scientific fidelity and mathematical rigor across all 10 phases, every module must pass six types of automated tests:

1. **Unit & Data Contract Tests:** Verify input types, physical bounding intervals, and immutability.
2. **Mathematical & Physics Invariant Tests:** Verify physical conservation laws ($\sum F_x = 0$, $\sum F_y = 0$, $\sum M = 0$, non-decreasing plastic dissipation $\dot{D} \ge 0$, and symmetric positive-definite stiffness matrices).
3. **Golden Benchmark Validation Tests:** Cross-compare numerical predictions against peer-reviewed textbook solutions (Das, Bowles, Terzaghi, Reese & Van Impe, Broms), published centrifuge/shake-table experiments, and independent 3D continuum FEA (PLAXIS 3D / Abaqus).
4. **Performance & Latency Threshold Tests:** Analytical and surrogate inference must run in $< 2\text{ ms}$ to maintain the 60 FPS desktop GUI standard.
5. **Robustness & Fuzzing Tests:** Extreme conditions (e.g., zero cohesion $c=0$, catastrophic $1.0g$ PGA, submerged crest, slack struts, missing DEM nodes).
6. **GUI, Threading & Memory Leak Tests:** Verify headless offscreen execution (`QT_QPA_PLATFORM=offscreen`), worker `QThread` cancellation, and zero memory leaks over 10,000 slider morphing events.

---

## Phase 1: Advanced Data Contracts, Validation & Invariants

### 1.1 Objective
Establish typed data contracts, validation schemas, and engineering bounds for curved shell facings, piers, floating bored piles, raking struts, transmission tower superstructures, and Indian Standard design settings.

### 1.2 Features to Implement
* **`CurvedShellGeometry` Dataclass**: Panel radius $R$, subtended arc angle $2\theta$, panel thickness $t_s$, crown-to-backfill orientation, bay span between piers $L_{bay}$, and panel height $H_p$.
* **`PierAndPileGeometry` Dataclass**: Vertical pier width $b_p$, pier depth $d_p$, pier height $H_{pier}$, bored pile diameter $D_p$, pile embedment length $L_{pile}$, number of piles per pier $n_{pile}$, and center-to-center pile spacing $s_p$.
* **`StrutSupportSystem` Dataclass**: Vertical spacing $\Delta y_{strut}$ (e.g. 3.0 m), inclination angle $\alpha_{strut}$, cross-sectional area $A_s$, moment of inertia $I_s$, steel grade $f_y$, pre-stress lock-off load $P_0$, and allowable slenderness ratio $\lambda_{max}$.
* **`TransmissionTowerParams` Dataclass**: Tower base footprint $B_{tower} \times L_{tower}$, total height $H_{tower}$, leg vertical reactions $P_{leg}$, horizontal wind shear per leg $V_{wind}$ (IS 875 Pt 3), broken-wire unbalanced tension $T_{bw}$, and seismic inertia.
* **`IndianDesignStandards` Dataclass**: Seismic Zone V parameters ($Z=0.36$, Importance Factor $I=1.5$, Response Reduction Factor $R=3.0$), rock/soil foundation type (Type I/II/III), concrete grade ($M25-M40$), steel grade ($Fe415-Fe550$).

### 1.3 Implementation Details
* **Target Files**:
  * `src/orang3d/models/advanced_wall_params.py`
  * `src/orang3d/models/tower_params.py`
  * `src/orang3d/models/is_code_params.py`
  * Update `src/orang3d/models/__init__.py`
* **Dependencies**: Python standard library (`dataclasses`, `typing`, `math`).

### 1.4 Test Suite (`tests/test_advanced_models.py`)
* `test_shell_geometry_bounds()`: Rejects $2\theta \ge 180^\circ$ or $t_s \le 0.05\text{ m}$.
* `test_pile_geometry_invariants()`: Rejects $L_{pile} \le 0$ or $s_p < 2.5 D_p$ (violating minimum pile spacing to prevent immediate block failure).
* `test_strut_spacing_bounds()`: Validates that strut levels fit within total pier height $H_{pier}$.
* `test_is_code_zoning_matrix()`: Validates Zone V ($Z=0.36$), Zone IV ($Z=0.24$), Zone III ($Z=0.16$), and Zone II ($Z=0.10$).
* `test_dataclass_serialization()`: Ensures all dataclasses serialize to JSON without loss of precision.

### 1.5 Deliverables
* Fully typed, self-validating data contracts.
* 100% unit test coverage of all validation rules.

---

## Phase 2: 3D Parametric Curved Shell, Pier & Multi-Element Mesher

### 2.1 Objective
Construct a 3D parametric meshing pipeline capable of discretizing curved shell panels, discrete vertical piers, floating pile lines/cylinders, raking struts, and uphill hill slopes into conformal geometric grids.

### 2.2 Features to Implement
* **Curved Shell Facing Discretization**: Mesh cylindrical or parabolic RC shell panels with variable crown displacement toward the backfill.
* **Pier-Pile Subgrade Junction**: Mesh vertical pier columns and connect them rigidly to pile caps and underlying bored piles.
* **3D Strut & Lattice Tower Elements**: Generate structural 1D line elements (`VTK_LINE`) with assigned section properties for struts, walers, and transmission tower legs.
* **Pure NumPy Fast Path ($< 2\text{ ms}$)**: Analytical parametric surface generator for interactive PyVista viewport morphing.
* **Gmsh Conformal Pipeline (Optional High-Fidelity)**: Using `gmsh-sdk` / `pygmsh` for high-density volumetric tetrahedral/hexahedral meshing of soil-shell interfaces.

### 2.3 Implementation Details
* **Target Files**:
  * `src/orang3d/mesher/shell_mesher.py`
  * `src/orang3d/mesher/pile_strut_mesher.py`
  * `src/orang3d/mesher/hybrid_assembler.py`
* **Dependencies**: `numpy`, `pyvista`, `gmsh` (optional high-fidelity).

### 2.4 Test Suite (`tests/test_shell_mesher.py`)
* `test_shell_curvature_geometry()`: Verifies that panel crown coordinates match $z(x) = R - \sqrt{R^2 - x^2}$ within $10^{-6}\text{ m}$.
* `test_mesh_surface_normals()`: Verifies that shell normal vectors point outward toward backfill to ensure correct earth pressure application.
* `test_conformal_pier_pile_junction()`: Ensures nodes at the base of the pier match exactly with the top of the pile cap.
* `test_mesher_latency_benchmark()`: Enforces runtime threshold: full 3-bay retaining wall meshing in $< 5\text{ ms}$.
* `test_jacobian_determinants()`: Guarantees all 3D solid elements have $\det(J) > 0$.

### 2.5 Deliverables
* Conformal 3D mesh generator rendering curved shell panels, piers, piles, and struts in PyVista.
* Interactive slider updates in the 3D viewport without frame dropping.

---

## Phase 3: Level L0 Analytical Engine (Arching, Piles & IS 1893)

### 3.1 Objective
Deliver the closed-form analytical calculation engine mandated by Dibyendu's supervisor for immediate calculation of horizontal soil arching, dynamic earth pressures, strut loads, pile embedment, and initial stability.

### 3.2 Features to Implement
* **Horizontal Soil Arching Formulation**:
  * Implement modified Terzaghi/Handy arching theory for cylindrical shell panels between piers:
    $$\sigma_h(z) = \frac{\gamma L_{bay}}{2 \tan \phi} \left(1 - e^{-2 K \tan \phi \frac{z}{L_{bay}}}\right)$$
  * Determine the load partition factor $\eta_{arch}$: portion of earth thrust transferred directly to vertical piers vs. residual thrust resisted by shell flexure.
* **Dynamic Earth Pressure per IS 1893 (Part 3)**:
  * Compute horizontal and vertical seismic design coefficients:
    $$A_h = \frac{Z}{2} \cdot \frac{I}{R} \cdot \left(\frac{S_a}{g}\right), \quad A_v = \frac{2}{3} A_h$$
  * Evaluate Mononobe-Okabe active earth thrust with tension cracks in $c\text{-}\phi$ soil and Seed & Whitman dynamic increment partition.
* **Analytical Multi-Strut Load Apportionment**:
  * Tributary area and apparent earth pressure envelopes (Peck, Terzaghi-Peck trapezoidal/rectangular distributions modified for seismic Zone V).
* **Analytical Pile Embedment Depth in $c\text{-}\phi$ Soil**:
  * Broms' method and IS 2911 lateral resistance calculation to determine minimum pile embedment $L_{pile}$ for lateral and rotational equilibrium without a rock socket.

### 3.3 Implementation Details
* **Target Files**:
  * `src/orang3d/physics/shell_arching.py`
  * `src/orang3d/physics/is_1893_engine.py`
  * `src/orang3d/physics/strut_statics.py`
  * `src/orang3d/physics/pile_statics.py`
* **Dependencies**: `numpy`, `scipy`.

### 3.4 Test Suite (`tests/test_analytical_arching.py`)
* `test_arching_planar_limit()`: As shell radius $R \to \infty$ and $L_{bay} \to \infty$, arching stress must asymptotically converge to classical Rankine/Coulomb active pressure.
* `test_equilibrium_conservation()`: Total earth thrust must equal sum of pier reactions plus shell face thrust ($\sum F_x = 0$).
* `test_is1893_seismic_coefficients()`: Verifies $A_h$ calculation against IS 1893 (Pt 3) Table 1 for Zone V ($Z=0.36, I=1.5, R=3.0$).
* `test_pile_embedment_equilibrium()`: Ensures computed pile depth provides $FS_{lateral} \ge 1.5$ against Broms' ultimate lateral soil capacity.
* `test_analytical_latency()`: Entire analytical chain executes in $< 1.5\text{ ms}$.

### 3.5 Deliverables
* Standalone analytical solver covering arching, strut loads, pile embedment, and IS 1893 loads.
* Verification against published benchmark problems from NIT Agartala research papers.

---

## Phase 4: Level L1 BNWF Engine (`OpenSeesPy`) — Soil-Spring Dynamics & Staged Struts

### 4.1 Objective
Construct an intermediate, high-performance **Beam on Nonlinear Winkler Foundation (BNWF)** engine using `OpenSeesPy` to simulate dynamic pile-soil-strut interaction with nonlinear $p\text{-}y, t\text{-}z, q\text{-}z$ springs.

### 4.2 Features to Implement
* **OpenSeesPy Model Builder Pipeline**:
  * Structural Members: Model vertical piers and floating bored piles using `dispBeamColumn` or `forceBeamColumn` with non-linear fiber sections.
  * Lateral Soil Springs: Nonlinear `PySimple1` springs with ultimate lateral resistance $p_{ult}$ and initial subgrade reaction $k_h$ modified for sloping ground.
  * Vertical Soil Springs: `TzSimple1` for pile skin friction and `QzSimple1` for pile end-bearing.
  * Radiation Damping Dashpots: Viscous dampers ($C = \rho V_s A$) in parallel with springs to capture energy dissipation into the far field.
* **Nonlinear Strut Elements**:
  * Model raking struts using `corotTruss` or `inelasticBeamColumn` with slackening under tension and Euler/inelastic buckling under compression.
* **Staged Construction Sequence**:
  1. Stage 0: Soil gravity self-weight initialisation ($K_0$ state).
  2. Stage 1: Excavate to Level 1, activate Pier + Pile.
  3. Stage 2: Install Strut 1 at 3 m depth with pre-stress load $P_0$.
  4. Stage 3: Excavate to full depth, install Strut 2.
  5. Stage 4: Apply earthquake acceleration time-history at base nodes.
* **Asynchronous Execution Architecture**:
  * Run OpenSeesPy analysis in a dedicated `QThread` (`BNWFSimulationWorker`) with cooperative cancellation and step-by-step progress emission.

### 4.3 Implementation Details
* **Target Files**:
  * `src/orang3d/physics/bnwf_solver.py`
  * `src/orang3d/physics/opensees_assembler.py`
  * `src/orang3d/physics/spring_curves.py`
* **Dependencies**: `openseespy`, `numpy`, `scipy`.

### 4.4 Test Suite (`tests/test_bnwf_opensees.py`)
* `test_single_pile_lateral_pushover()`: Validates $p\text{-}y$ response against Reese & Matlock closed-form solutions.
* `test_strut_slackening_rebound()`: Verifies that when a strut experiences tension beyond lock-off, axial resistance drops to zero (slack behavior) without numerical divergence.
* `test_strut_buckling_limit()`: Verifies that compressive strut force is capped at Euler buckling load $P_{cr} = \frac{\pi^2 E I}{(K L)^2}$.
* `test_staged_equilibrium()`: Ensures intermediate excavation stages satisfy static equilibrium prior to dynamic shaking.
* `test_worker_cancellation()`: Verifies that triggering `worker.cancel()` cleanly terminates OpenSees execution within $100\text{ ms}$.

### 4.5 Deliverables
* Fully operational OpenSeesPy BNWF solver running dynamic earthquake time histories in $< 15\text{ s}$.
* Extraction of time-series: bending moment $M(y, t)$, shear $V(y, t)$, pile deflection $y(z, t)$, and strut force $F_{strut}(t)$.

---

## Phase 5: Hill-Slope Topography & DEM Raster Ingestion

### 5.1 Objective
Enable ingestion of real-world hill terrain rasters (GeoTIFF / DEM) to capture irregular 3D slope geometries, toe drop-offs, and topographic seismic amplification.

### 5.2 Features to Implement
* **DEM Ingestion Engine (`rasterio`)**:
  * Read single-band GeoTIFF, ASCII grid, or XYZ point clouds.
  * Extract 2D slope cross-sections and 3D digital surface meshes surrounding the retaining wall.
* **Terrain Draping & Surface Alignment**:
  * Automatically position retaining wall piers, shell facings, and pile heads onto the sampled slope profile.
* **Slope Stability Invariants**:
  * Compute slope angle $\beta_{slope}$, crest distance $L_{crest}$, and toe daylight slope.
* **Topographic Amplification Estimator**:
  * Implement Eurocode 8 / IS 1893 hill-crest amplification factor $S_T \ge 1.2$ for slope angles $> 15^\circ$:
    $$a_{crest}(t) = S_T \cdot a_{base}(t)$$

### 5.3 Implementation Details
* **Target Files**:
  * `src/orang3d/mesher/terrain.py`
  * `src/orang3d/signals/topography.py`
* **Dependencies**: `rasterio`, `pyvista`, `scipy`.

### 5.4 Test Suite (`tests/test_terrain_topography.py`)
* `test_geotiff_parser()`: Verifies correct reading of elevations, nodata values, and spatial geotransforms.
* `test_synthetic_slope_generation()`: Validates parametric generation of planar, benched, and bilinear slopes.
* `test_topographic_amplification_bounds()`: Checks that $S_T \ge 1.0$ for all valid slopes, peaking at the crest.
* `test_surface_draping_alignment()`: Verifies that pile collar elevations match terrain elevation at every pier location.

### 5.5 Deliverables
* Terrain import panel and 3D surface mesh rendering in PyVista.
* Automatic calculation of slope-modified passive resistance and crest amplification.

---

## Phase 6: Uphill Transmission Tower Co-Simulation & Multi-Hazard Loads

### 6.1 Objective
Model the high-voltage transmission tower located upslope from the wall, applying combined wind, broken-wire, and seismic loads and transmitting leg reactions directly into the hill slope and retaining system.

### 6.2 Features to Implement
* **3D Space Truss Tower Model**:
  * Discretize a 4-legged lattice steel transmission tower (IS 802) using OpenSees elastic truss elements.
* **Multi-Hazard Load Generator**:
  * **Wind Load (IS 875 Part 3)**: Design wind pressure $p_z = 0.6 V_z^2$, force coefficients for lattice frames, and conductor drag.
  * **Broken-Wire Condition (IS 802)**: Unbalanced longitudinal pull causing severe torsional and overturning moments on tower footings.
  * **Seismic Inertia**: Lumped mass dynamic acceleration at tower cross-arms and peak.
* **Coupled Footing Transfer**:
  * Map dynamic tower leg reactions ($R_{v1 \dots 4}, R_{h1 \dots 4}$) into the hill slope soil nodes and retaining wall pile foundations.

### 6.3 Implementation Details
* **Target Files**:
  * `src/orang3d/physics/tower_coupling.py`
  * `src/orang3d/physics/wind_loads.py`
* **Dependencies**: `openseespy`, `numpy`.

### 6.4 Test Suite (`tests/test_tower_coupling.py`)
* `test_tower_static_dead_load()`: Total vertical leg reactions must exactly equal tower self-weight ($\sum R_v = W_{tower}$).
* `test_broken_wire_torsion()`: Verifies asymmetrical foot reaction couples under unbalanced conductor tension.
* `test_coupled_slope_surcharge()`: Ensures Boussinesq / Westergaard stress distribution from tower pads attenuates correctly with depth.
* `test_eigen_frequencies_tower()`: First natural frequency of lattice tower must match analytical cantilever truss frequency ($f_1 \approx 1.5 - 3.0\text{ Hz}$).

### 6.5 Deliverables
* Coupled transmission tower superstructure module with combined wind (IS 875) + broken wire (IS 802) + seismic loads.
* Visual 3D wireframe tower rendered atop the hill slope in the PyVista canvas.

---

## Phase 7: Advanced Cyclic Soil Models & Rainfall Infiltration

### 7.1 Objective
Incorporate non-linear cyclic constitutive modeling for unsaturated residual $c\text{-}\phi$ hill soils and simulate the compound disaster scenario: monsoon rainfall infiltration followed by strong seismic shaking.

### 7.2 Features to Implement
* **Advanced Cyclic Soil Formulations in OpenSees**:
  * `PM4Silt` / `PM4Sand` or `PressureDependMultiYield` (PDMY02) for residual $c\text{-}\phi$ soils.
  * Modulus degradation $G/G_{\max}(\gamma)$ and hysteretic damping $D(\gamma)$ curves.
* **Compound Rainfall-Earthquake Sequencing**:
  * Model matric suction loss and reduction of apparent cohesion $c_{app}(S_r)$ following rainfall:
    $$c_{total} = c' + (u_a - u_w) \tan \phi^b$$
  * Simulate the transition from partially saturated soil to high saturation ($S_r \to 1.0$), triggering increased dynamic lateral pressures during shaking.
* **Laboratory Calibration Utility**:
  * Parameter optimizer fitting model parameters ($G_0, h_{po}, e_{init}$) to direct shear, cyclic triaxial, or resonant column test data using `scipy.optimize.curve_fit`.

### 7.3 Implementation Details
* **Target Files**:
  * `src/orang3d/physics/cyclic_soil.py`
  * `src/orang3d/physics/unsaturated_soil.py`
  * `src/orang3d/physics/calibration.py`
* **Dependencies**: `openseespy`, `scipy`, `numpy`.

### 7.4 Test Suite (`tests/test_cyclic_soil.py`)
* `test_backbone_mashing()`: Verifies that stress-strain curves follow Masing criteria under symmetric cyclic loading.
* `test_hysteretic_damping_bounds()`: Checks that small-strain damping matches target $D_{min} \approx 2-5\%$ and increases monotonically with cyclic shear strain $\gamma$.
* `test_suction_loss_softening()`: Asserts that increasing degree of saturation $S_r$ reduces yield acceleration $k_y$ and increases permanent Newmark slip.
* `test_calibration_curve_fit()`: Fits synthetic resonant column data with $R^2 \ge 0.98$.

### 7.5 Deliverables
* Cyclic residual soil engine and unsaturated rainfall-degradation module.
* Automatic calibration wizard for laboratory soil test data.

---

## Phase 8: Comprehensive Indian Standards (IS Code) Member Design Engine

### 8.1 Objective
Deliver an automated, code-compliant structural and geotechnical design suite enforcing Indian Standards for RC shell panels, piers, bored piles, and structural steel struts.

### 8.2 Features to Implement
* **RC Shell Panel & Pier Design (IS 456:2000)**:
  * Limit State Design in flexure ($M_u = 0.87 f_y A_{st} d [1 - \frac{A_{st} f_y}{b d f_{ck}}]$).
  * Minimum reinforcement check ($0.12\%$ for HYSD bars), crack width check ($w_{cr} \le 0.2\text{ mm}$ for aggressive environments), and concrete shear capacity ($\tau_c$ vs. $\tau_v$).
  * Automated bar callout generator (e.g. `2-layer T16 @ 125 mm c/c each face`).
* **Bored Cast-in-Situ Pile Design (IS 2911 Part 1/Sec 2)**:
  * Safe vertical axial load capacity in $c\text{-}\phi$ soil:
    $$Q_{safe} = \frac{1}{FS} \left[A_p \left(c N_c + \sigma'_v N_q + 0.5 \gamma D_p N_\gamma\right) + \sum \alpha c_i A_{si} + \sum K \sigma'_{vi} \tan \delta A_{si}\right]$$
  * Lateral pile load capacity and depth of fixity $z_f$ based on subgrade modulus $k_h$.
  * Pile structural rebar cage design (longitudinal reinforcement $0.4\% - 1.25\%$, helical binder pitch).
* **Steel Strut Design (IS 800:2007)**:
  * Limit state compressive strength $P_d = A_e f_{cd}$ based on non-dimensional slenderness $\lambda$ and buckling curve (class a, b, or c).
  * Check against seismic reversal tension and connection bolt/weld sizing.
* **Engineering Audit Sheet Generator**:
  * Returns structured compliance dictionaries citing specific IS clauses, intermediate calculations, and unity ratios ($UR \le 1.0$).

### 8.3 Implementation Details
* **Target Files**:
  * `src/orang3d/physics/is_codes/is_456.py`
  * `src/orang3d/physics/is_codes/is_2911.py`
  * `src/orang3d/physics/is_codes/is_800.py`
  * `src/orang3d/physics/is_codes/audit_engine.py`
* **Dependencies**: `sympy`, `numpy`, `scipy`.

### 8.4 Test Suite (`tests/test_is_design_codes.py`)
* `test_is456_singly_reinforced_slab()`: Cross-checks computed steel area against IS 456 SP 16 design tables within $0.5\%$.
* `test_is456_shear_capacity()`: Validates $\tau_c$ table interpolation across concrete grades M25, M30, M35, M40.
* `test_is2911_pile_capacity()`: Validates end-bearing and skin friction against textbook golden benchmark (IS 2911 Appendix B).
* `test_is800_strut_buckling_curve()`: Verifies that design compressive stress $f_{cd}$ matches IS 800 Table 9(c) across slenderness ratios $\lambda \in [20, 180]$.
* `test_unity_ratio_thresholds()`: Ensures all components flag $UR > 1.0$ as FAIL with exact clause reference.

### 8.5 Deliverables
* Complete IS 456, IS 2911, and IS 800 member design engine with structured engineering audit reports.

---

## Phase 9: AI/PINN Fast Surrogates & Uncertainty Quantification (UQ)

### 9.1 Objective
Construct physics-informed neural network (PINN) and machine-learning surrogates to enable instant ($< 1\text{ ms}$) interactive slider manipulation, accompanied by probabilistic uncertainty quantification (Monte Carlo / LHS).

### 9.2 Features to Implement
* **Parametric Database Generator**:
  * Automate Latin Hypercube Sampling (LHS) runs across:
    * Soil: $c \in [5, 50]\text{ kPa}$, $\phi \in [20, 42]^\circ$, $\gamma \in [16, 21]\text{ kN/m}^3$.
    * Geometry: $H \in [4, 15]\text{ m}$, $L_{bay} \in [2, 6]\text{ m}$, $D_p \in [0.6, 1.5]\text{ m}$, $L_{pile} \in [6, 25]\text{ m}$.
    * Seismic: $\text{PGA} \in [0.1g, 0.6g]$.
* **PINN / ML Surrogate Engine (`PyTorch` / `DeepXDE`)**:
  * Multi-layer perceptron (MLP) trained with physics loss enforcing static/dynamic equilibrium:
    $$\mathcal{L} = \mathcal{L}_{data} + \lambda_{physics} \|\sum F\|^2$$
  * Predicts full continuous envelopes of bending moment $M(y)$, shear $V(y)$, strut loads, and crest displacement in $< 1\text{ ms}$.
* **Uncertainty Quantification & Fragility (`chaospy` / `UQpy`)**:
  * Monte Carlo sampling of soil properties to compute reliability index $\beta$ and probability of failure $P_f = P(FS < 1.0)$.
  * Generate seismic fragility curves $P(\text{Exceedance} \mid \text{PGA})$ for damage states (Slight, Moderate, Extensive, Collapse).

### 9.3 Implementation Details
* **Target Files**:
  * `src/orang3d/physics/surrogate_engine.py`
  * `src/orang3d/physics/pinn_trainer.py`
  * `src/orang3d/physics/uncertainty.py`
* **Dependencies**: `torch`, `deepxde`, `scikit-learn`, `chaospy`, `UQpy`.

### 9.4 Test Suite (`tests/test_surrogates_and_uq.py`)
* `test_surrogate_inference_latency()`: Enforces runtime threshold: single prediction in $< 1\text{ ms}$ on CPU.
* `test_surrogate_accuracy()`: Verifies that surrogate output achieves $R^2 \ge 0.98$ and Mean Absolute Percentage Error (MAPE) $< 3\%$ against OpenSees test splits.
* `test_physics_loss_conservation()`: Asserts that surrogate predictions satisfy horizontal equilibrium within $2\%$.
* `test_lhs_distribution_uniformity()`: Verifies Kolmogorov-Smirnov test on generated random soil fields.
* `test_fragility_monotonicity()`: Asserts that failure probability increases monotonically with PGA.

### 9.5 Deliverables
* Pre-trained PyTorch surrogate engine delivering 60 FPS real-time feedback during GUI slider interactions.
* Probabilistic reliability and seismic fragility dashboard.

---

## Phase 10: GUI Integration, CAD Export (`ezdxf`), Golden Gate & CI

### 10.1 Objective
Assemble all newly built modules into the PySide6 desktop GUI shell, deliver automated AutoCAD `.dxf` construction drawing export, enforce the golden benchmark test gate, and package cross-platform releases.

### 10.2 Features to Implement
* **PySide6 Dock Panels**:
  * `ShellAndPierPanel`: Sliders for panel curvature $R$, arc angle $2\theta$, pier dimensions $b_p \times d_p$, bay width $L_{bay}$.
  * `StrutAndPilePanel`: Sliders for strut levels, inclination $\alpha$, pile diameter $D_p$, embedment depth $L_{pile}$.
  * `TowerAndTerrainPanel`: DEM file chooser, slope angle, tower footing load inputs.
  * `ISDesignAuditTab`: Live compliance checklist displaying IS 456, IS 2911, and IS 800 unity checks with color-coded badges (Green $\le 0.9$, Yellow $\le 1.0$, Red $> 1.0$).
* **3D PyVista Viewport Updates**:
  * Visualizes curved shell stress heatmaps, pile lateral deflection shapes, strut axial force colors (blue = compression, red = tension, dashed = slack), and wireframe transmission tower.
* **Automated CAD Detailing (`ezdxf`)**:
  * Generates clean, layered `.dxf` drawings:
    * Layer `WALL_OUTLINE`: Front elevation and plan view of shell arches and piers.
    * Layer `REBAR_REINFORCEMENT`: Longitudinal bars, shear ties, and pile reinforcement cages.
    * Layer `STRUT_DETAILS`: Steel strut sections, end gusset plates, and anchor brackets.
    * Layer `DIMENSIONS_AND_TEXT`: Engineering callouts and title blocks.
* **Golden Benchmark Gate**:
  * Complete comparison against published NIT Agartala test cases, PLAXIS 3D numerical models, and centrifuge benchmarks.
* **Packaging & CI Pipeline**:
  * GitHub Actions matrix for Linux and Windows builds (`.github/workflows/ci.yml`).
  * Standalone binary compilation via PyInstaller ([orang3d.spec](file:///home/avisheks/Documents/dibs/orang3d/orang3d.spec)).

### 10.3 Implementation Details
* **Target Files**:
  * `src/orang3d/gui/panels/shell_panel.py`
  * `src/orang3d/gui/panels/strut_pile_panel.py`
  * `src/orang3d/gui/panels/audit_tab.py`
  * `src/orang3d/io/dxf_export.py`
  * Update `src/orang3d/gui/main_window.py`
  * Update `tests/test_benchmarks.py`
* **Dependencies**: `PySide6`, `pyvista`, `pyvistaqt`, `pyqtgraph`, `ezdxf`, `pytest`.

### 10.4 Test Suite (`tests/test_gui_integration_and_cad.py`)
* `test_dxf_export_validity()`: Verifies that exported `.dxf` files open cleanly in `ezdxf` with correct layers, text entities, and closed polyline boundaries.
* `test_gui_dock_synchronization()`: Adjusting the shell curvature slider triggers immediate updates in both the 3D PyVista canvas and 2D charts without lag.
* `test_golden_textbook_benchmarks()`: Validates full-chain outputs against peer-reviewed published papers from NIT Agartala within $5\%$ tolerance.
* `test_headless_ci_render()`: Runs the complete GUI and CAD export suite headless under `QT_QPA_PLATFORM=offscreen`.
* `test_code_coverage_threshold()`: Enforces $\ge 90\%$ branch and line coverage across the entire expanded repository.

### 10.5 Deliverables
* Complete, unified desktop application with all 10 phases integrated.
* Automated CAD `.dxf` generator for construction drawings.
* 100% automated test coverage with passing GitHub Actions CI pipeline.

---

## Ph.D. Publication & Milestones Mapping

| Phase | Milestone Deliverable | Targeted Academic Output / Publication |
| :---: | :--- | :--- |
| **Phases 1–3** | Open-source L0 analytical solver for shell walls with arching and IS 1893 seismic loads. | **Paper 1 (Q1 Journal)**: *"Closed-form analytical formulation and arching mechanics for pile-supported curved shell retaining walls under seismic excitation."* |
| **Phases 4–6** | OpenSeesPy BNWF framework with raking struts, floating piles, hill slope, and tower interaction. | **Paper 2 (Q1 Journal)**: *"Dynamic soil-structure interaction of multi-strut pile-supported retaining systems on seismic hill slopes: A multi-fidelity BNWF approach."* |
| **Phases 7–8** | Cyclic soil degradation with rainfall suction loss + IS 456 / IS 2911 / IS 800 design engine. | **Paper 3 (Q1 Journal)**: *"Compound rainfall-earthquake performance and code-based limit state design of deep retaining walls in unsaturated residual soils."* |
| **Phases 9–10** | PyTorch/DeepXDE PINN surrogate + open-source desktop software release with CAD export. | **Paper 4 (Q1 Journal / SoftwareX)**: *"orang3D: An open-source, AI-accelerated software for 3D seismic analysis and design of complex retaining systems."* |

---

## Directory Structure After 10 Phases

```text
orang3d/
├── aidocs/                          # Comprehensive developer & AI documentation
│   ├── ARCHITECTURE.md              # System architecture & two-speed data flow
│   ├── INDEX.md                     # File sitemap & symbol index
│   └── CORE_CONCEPTS.md             # Geotechnical, structural & FEA physics
├── docs/                            # Development plans & completion reports
│   ├── DEVELOPMENT_PLAN.md          # Original 10-phase base plan
│   └── MULTI_STRUT_PILED_WALL_DEVELOPMENT_PLAN.md # This 10-phase advanced blueprint
├── src/
│   └── orang3d/
│       ├── config.py                # Themes, palettes & regional codes
│       ├── main.py                  # Application entry point
│       ├── gui/                     # Desktop GUI (PySide6)
│       │   ├── charts_2d.py         # 60 FPS PyQtGraph dynamic telemetry
│       │   ├── main_window.py       # Central docking window
│       │   ├── viewport_3d.py       # PyVista 3D scientific canvas
│       │   └── panels/              # Dock panels (Geometry, Soil, Strut, Pile, Tower)
│       ├── io/                      # I/O Suite
│       │   ├── dxf_export.py        # Automated AutoCAD .dxf construction drawings
│       │   ├── mesh_export.py       # .vtk, .stl, .obj mesh export
│       │   ├── report_generator.py  # Offscreen PDF engineering report
│       │   └── serialization.py     # .o3d bundle manager (JSON + HDF5)
│       ├── mesher/                  # 3D Solid & Surface Meshing
│       │   ├── hex_mesher.py        # Pure NumPy 8-node brick mesher (< 2 ms)
│       │   ├── shell_mesher.py      # Curved shell & pier mesher
│       │   └── terrain.py           # DEM / GeoTIFF slope surface generator
│       ├── models/                  # Data contracts & validation schemas
│       │   ├── advanced_wall_params.py # Shell, pier, strut, pile dataclasses
│       │   ├── is_code_params.py    # Indian Standards configuration
│       │   └── tower_params.py      # Lattice transmission tower contracts
│       ├── physics/                 # Solvers & Mechanics Engines
│       │   ├── bnwf_solver.py       # OpenSeesPy L1 dynamic BNWF solver
│       │   ├── cyclic_soil.py       # PM4Silt / PDMY02 residual soil models
│       │   ├── kratos_solver.py     # KratosMultiphysics 2D continuum solver
│       │   ├── shell_arching.py     # 3D horizontal soil arching statics
│       │   ├── surrogate_engine.py  # PyTorch / DeepXDE sub-ms PINN surrogate
│       │   ├── tower_coupling.py    # Uphill transmission tower 3D frame
│       │   ├── uncertainty.py       # UQpy / chaospy Monte Carlo & fragility
│       │   └── is_codes/            # Indian Standards Design Modules
│       │       ├── is_456.py        # Concrete shell & pier limit state design
│       │       ├── is_800.py        # Steel strut buckling design
│       │       ├── is_1893.py       # Seismic earth pressures (Zone V)
│       │       ├── is_2911.py       # Bored pile vertical & lateral capacity
│       │       └── is_14458.py      # Hill area retaining wall criteria
│       └── signals/                 # Earthquake Signals
│           ├── at2_parser.py        # PEER .AT2 parser & bandpass filter
│           ├── synthetic.py         # Wavelets, Newmark sliding displacement
│           └── topography.py        # Crest amplification & slope kinematics
├── tests/                           # 100% Automated Pytest Suite
│   ├── test_advanced_models.py      # Contracts, invariants & typing tests
│   ├── test_analytical_arching.py   # Arching, pile embedment & IS 1893 tests
│   ├── test_benchmarks.py           # Golden textbook comparisons
│   ├── test_bnwf_opensees.py        # OpenSees dynamic springs, struts & piles
│   ├── test_cyclic_soil.py          # Hysteresis, damping & suction loss tests
│   ├── test_dxf_export.py           # AutoCAD .dxf validity & layers tests
│   ├── test_is_design_codes.py      # IS 456, IS 2911, IS 800 compliance tests
│   ├── test_shell_mesher.py         # Curved shell mesh & Jacobian tests
│   ├── test_surrogates_and_uq.py    # PyTorch surrogate latency & accuracy tests
│   ├── test_terrain_topography.py   # DEM raster & topographic amplification tests
│   └── test_tower_coupling.py       # Transmission tower wind & seismic tests
├── orang3d.spec                     # PyInstaller standalone build spec
├── pyproject.toml                   # Packaging & build configuration
└── requirements.txt                 # Pinned dependencies
```
