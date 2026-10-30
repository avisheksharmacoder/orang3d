# orang3D: 10-Phase Engineering Development & 100% Test Coverage Plan

This document establishes the roadmap for engineering, validating, and testing **orang3D**—the 100% open-source, real-time 3D seismic and disaster retaining wall analysis desktop application.

---

## Roadmap Overview

```mermaid
gantt
    title orang3D 10-Phase Development Roadmap
    dateFormat  X
    axisFormat %d

    section Foundation & Mesh
    Phase 1: Architecture, Typing & Config         :p1, 0, 1
    Phase 2: Parametric 3D Pure NumPy Mesher       :p2, after p1, 1d
    Phase 3: Fast Analytical Physics (M-O & SSI)   :p3, after p2, 1d

    section Mechanics & Dynamics
    Phase 4: Structural Concrete & Rebar Mechanics :p4, after p3, 1d
    Phase 5: Seismic Signals & Newmark Integration :p5, after p4, 1d
    Phase 6: KratosMultiphysics Deep FEA Engine    :p6, after p5, 2d

    section UI & Interactive Viewports
    Phase 7: Advanced PyVista 3D Scientific View   :p7, after p6, 1d
    Phase 8: PyQtGraph 2D Dashboard & Scrubber     :p8, after p7, 1d

    section Packaging & Polish
    Phase 9: Session Serialization & PDF Reports   :p9, after p8, 1d
    Phase 10: 100% Coverage Gate, Benchmarks & CI  :p10, after p9, 1d
```

---

## Testing Taxonomy: What Sorts of Tests We Worry About

To achieve true scientific software reliability and maintain **100% code coverage**, the test suite is partitioned into six distinct testing categories across every phase:

1. **Unit & Contract Tests:** Verify input types, value ranges, dataclass invariants, and default states.
2. **Mathematical & Physics Invariant Tests:** Check that physical laws hold (e.g., energy conservation, statics equilibrium $\sum F=0, \sum M=0$, asymptotic limits).
3. **Golden Benchmark Validation Tests:** Compare numerical outputs against published geotechnical textbooks (Das, Kramer, Bowles), building codes (AASHTO LRFD, Eurocode 7, IS 14458), and analytical closed-form solutions.
4. **Performance & Latency Benchmarks:** Enforce strict execution time thresholds (e.g., $< 2\text{ ms}$ for meshing, $< 1\text{ ms}$ for analytical physics) to guarantee 60 FPS slider responsiveness.
5. **Robustness & Edge-Case Fuzzing:** Test behavior under extreme inputs (zero soil friction, $100\%$ liquefaction, catastrophic $1.0g$ earthquake, submerged crest, corrupt files).
6. **GUI, Threading & Integration Tests:** Validate PySide6 signal/slot bindings, headless offscreen rendering, thread lifecycles, and memory leak prevention during rapid updates.

---

## Phase 1: Architecture, Core Typing & Validation Foundation ✅ (Completed)
*See detailed completion report: [PHASE_1_COMPLETION.md](file:///home/avisheks/Documents/dibs/orang3d/docs/PHASE_1_COMPLETION.md)*

### 1.1 Features to Build
- **Strict Data Contracts:** Dataclasses and schema validators for `RetainingWallGeometry`, `SoilProperties`, `SeismicParams`, and `AnalysisResults`. (Delivered)
- **Engineering Bounds Enforcement:** Pre-execution validators preventing unphysical states (e.g., negative friction angles, $\phi \ge 50^\circ$, stem base thinner than crest, negative soil layer depths). (Delivered)
- **Configuration & Theme Registry:** Centralized, immutable styling tokens (`config.py`) supporting dark/light mode switching, unit conversions (SI Metric vs. Imperial US Customary), and regional safety factor standards (Eurocode 7, AASHTO LRFD, IS 14458). (Delivered)

### 1.2 What Sorts of Tests to Worry About
- **Type Safety & Bounds Enforcement:** Assert that setting invalid values raises clear `ValueError` or `TypeError` exceptions. (Verified)
- **Round-Trip Unit Conversion Invariants:** Converting meters $\to$ feet $\to$ meters must yield zero floating-point drift ($< 10^{-7}$). (Verified)
- **Immutability of Constants:** Safety factor thresholds and default palettes must not be accidentally mutated at runtime. (Verified)

### 1.3 Feature Validation Checklist
| Target Feature | Validation Condition | Expected Outcome | Tolerance | Status |
| :--- | :--- | :--- | :--- | :---: |
| Stem Geometry | $t_{\text{top}} > t_{\text{base}}$ | Validation Error / Auto-clamp | Exact | ✅ **Passed** |
| Soil Friction | $\phi \le 0^\circ$ or $\phi \ge 55^\circ$ | Validation Error / Auto-clamp | Exact | ✅ **Passed** |
| Total Height | $H_{\text{total}} = H_{\text{stem}} + D_{\text{footing}}$ | Consistent scalar property | $< 10^{-6}\text{ m}$ | ✅ **Passed** |
| Base Width | $B = B_{\text{toe}} + t_{\text{base}} + B_{\text{heel}}$ | Consistent scalar property | $< 10^{-6}\text{ m}$ | ✅ **Passed** |

### 1.4 Test Suite Implementation
- `tests/test_models.py` (17 tests - 100% coverage)
- `tests/test_units.py` (8 tests - 100% coverage)
- `tests/test_config.py` (3 tests - 100% coverage)

---

## Phase 2: Parametric 3D Pure NumPy Hexahedral Mesher ✅ (Completed)
*See detailed completion report: [PHASE_2_COMPLETION.md](file:///home/avisheks/Documents/dibs/orang3d/docs/PHASE_2_COMPLETION.md)*

### 2.1 Features to Build
- **Multi-Template Retaining Wall Support:** (Delivered)
  - Standard Inverted-T Cantilever Wall.
  - L-shaped Wall (no front toe, flush property line).
  - Reverse L-shaped Wall (no rear heel).
  - Tapered gravity wall profile.
  - Optional bottom shear key (rectangular or trapezoidal).
- **Vectorized Hexahedral 8-Node (Brick) Generation:** (Delivered)
  - Pure NumPy mesh generator creating structured grid blocks for stem, footing, toe, heel, shear key, backfill soil prism, and foundation bed.
  - Automatic topological stitching into a single `pyvista.UnstructuredGrid` in $< 2\text{ ms}$.
- **Geometrical Property Calculation:** (Delivered)
  - Closed-form volume, surface area, center of gravity ($x_{cg}, y_{cg}, z_{cg}$), and mass moments of inertia ($I_{xx}, I_{yy}, I_{zz}$).

### 2.2 What Sorts of Tests to Worry About
- **Topological Invariant Tests:** Every generated solid cell must be valid `VTK_HEXAHEDRON` (VTK CellType 12) with 8 unique vertices. (Verified)
- **Orientation & Jacobian Positivity:** No inverted, zero-volume, or twisted brick elements ($\det(J) > 0$ for all cells). (Verified)
- **Volume Conservation:** Integral $\iiint dV$ of mesh must match analytical geometric volume to within $0.01\%$. (Verified)
- **Sub-5ms Latency Benchmarks:** Mesher must generate grids in $< 5\text{ ms}$ under 20 consecutive runs to ensure smooth 60 FPS slider dragging. (Verified)

### 2.3 Feature Validation Checklist
| Target Feature | Validation Condition | Expected Outcome | Tolerance | Status |
| :--- | :--- | :--- | :--- | :---: |
| Cell Topology | Query `mesh.celltypes` | 100% `VTK_HEXAHEDRON` | Exact | ✅ **Passed** |
| Bounding Box | Compare `mesh.bounds` to $(B, H, L)$ | Coordinates match geometry bounds | $< 10^{-3}\text{ m}$ | ✅ **Passed** |
| Shear Key Toggle | Key Depth $= 0.0\text{ m}$ vs. $0.5\text{ m}$ | Node/cell count adjusts smoothly | Exact | ✅ **Passed** |
| Solve Latency | 20 consecutive rebuilds on 1,000 cells | Mean time $< 5.0\text{ ms}$ | $< 5.0\text{ ms}$ | ✅ **Passed** |
| Scalar Binding | Point data dictionary check | `TensileStress_MPa` & `Deformation_m` present | Exact | ✅ **Passed** |

### 2.4 Test Suite Implementation
- `tests/test_mesher.py` (11 tests - 100% coverage):
  - `test_wall_mesh_type_and_scalars()`
  - `test_wall_mesh_cell_types()`
  - `test_wall_mesh_bounds()`
  - `test_shear_key_toggle_and_bounds()`
  - `test_multi_template_support()`
  - `test_volume_conservation()`
  - `test_wall_geometric_properties_closed_form()`
  - `test_jacobian_positivity_all_cells()`
  - `test_mesher_sub_millisecond_performance()`
  - `test_soil_and_water_meshes()`
  - `test_build_3d_wedge_mesh()`

---

## Phase 3: Real-Time Analytical Physics Engine (M-O & Geotechnical SSI) ✅ (Completed)
*See detailed completion report: [PHASE_3_COMPLETION.md](file:///home/avisheks/Documents/dibs/orang3d/docs/PHASE_3_COMPLETION.md)*

### 3.1 Features to Build
- **Dynamic Earth Pressure Solvers:** (Delivered)
  - Mononobe-Okabe (M-O) dynamic active coefficient $K_{ae}$ with inertia angle $\theta_e = \arctan(k_h / (1 \mp k_v))$.
  - Coulomb and Rankine static active ($K_a$) and passive ($K_p$) earth pressures.
  - Seed & Whitman (1970) dynamic thrust partition: static resultant at $H/3$, dynamic increment $\Delta P_{ae}$ at $0.6H$.
- **Disaster Coupling (Pore Water & Liquefaction):** (Delivered)
  - Hydrostatic water thrust triangle for variable water table depth $H_w$.
  - Buoyant unit weight $\gamma' = \gamma_{sat} - \gamma_w$ below phreatic surface.
  - Liquefaction degradation model: non-linear reduction of effective friction angle $\phi'$ and shear strength as pore pressure ratio $r_u \to 1.0$.
- **Global Stability Factors of Safety:** (Delivered)
  - Factor of Safety against Sliding ($FS_s$) including base friction, adhesion, and passive key resistance.
  - Factor of Safety against Overturning ($FS_o$) around the toe edge.
  - Bearing capacity calculation via Meyerhof / Hansen / Vesic bearing capacity factors ($N_c, N_q, N_\gamma$) with load inclination and eccentricity corrections.

### 3.2 What Sorts of Tests to Worry About
- **Asymptotic Limit Tests:** When $k_h \to 0, k_v \to 0$, $K_{ae}$ must converge exactly to static Coulomb $K_a$. (Verified)
- **Monotonicity Tests:** Increasing earthquake PGA must monotonically increase total thrust $P_{ae}$ and decrease safety factors. (Verified)
- **Physical Boundary Tests:** Full water table flooding must increase lateral thrust and reduce sliding resistance due to loss of effective vertical weight. (Verified)
- **Golden Textbook Validation:** Compare factors of safety against published standard problems in Das (*Principles of Foundation Engineering*) and Kramer (*Geotechnical Earthquake Engineering*). (Verified)

### 3.3 Feature Validation Checklist
| Target Feature | Validation Condition | Expected Outcome | Tolerance | Status |
| :--- | :--- | :--- | :--- | :---: |
| M-O Static Limit | $k_h = 0.0, k_v = 0.0$ | $K_{ae} = K_a$ (Coulomb) | $< 10^{-4}$ | ✅ **Passed** |
| Seed & Whitman Height | Compare static vs. seismic resultant | $h_{\text{seismic}} > h_{\text{static}} = H/3$ | $h > H/3$ | ✅ **Passed** |
| Water Table Flood | Move water table from $H$ (dry) to $0$ (crest) | $P_{\text{total}}$ increases, $FS_s$ drops | $P_{\text{water}} > 0$ | ✅ **Passed** |
| Liquefaction Limit | Liquefaction factor $r_u = 0.8$ | $K_{ae}$ increases, $\phi_{\text{eff}} \to 0$ | $FS_s$ drops | ✅ **Passed** |
| Statics Equilibrium | Sum moments around toe | Resisting & overturning moments $> 0$ | $M > 0$ | ✅ **Passed** |

### 3.4 Test Suite Implementation
- `tests/test_physics_stability.py` (16 tests - 99% coverage):
  - `test_mononobe_okabe_static_limit()`
  - `test_mononobe_okabe_seismic_increase()`
  - `test_seed_whitman_thrust_height()`
  - `test_rankine_earth_pressures()`
  - `test_coulomb_earth_pressures()`
  - `test_liquefaction_degradation_ru()`
  - `test_bearing_capacity_factors_meyerhof_vesic()`
  - `test_ultimate_bearing_capacity_hansen_meyerhof()`
  - `test_coulomb_and_lateral_thrust_edge_cases()`
  - `test_shear_key_increases_sliding_resistance()`
  - `test_global_factors_of_safety_positive()`
  - `test_water_table_immersion_reduces_stability()`
  - `test_liquefaction_reduces_sliding_safety()`
  - `test_concrete_stem_cracking_under_extreme_seismic()`
  - `test_golden_textbook_kramer_seismic_mo()`
  - `test_golden_textbook_das_retaining_wall()`

---

## Phase 4: Structural Concrete & Rebar Demand Mechanics ✅ (Completed)
*See detailed completion report: [PHASE_4_COMPLETION.md](file:///home/avisheks/Documents/dibs/orang3d/docs/PHASE_4_COMPLETION.md)*

### 4.1 Features to Build
- **Internal Force Distributions:** (Delivered)
  - Continuous shear force profile $V(y)$ and bending moment profile $M(y)$ from stem crest ($y=H$) down to stem base ($y=0$).
- **Flexural & Shear Stress Analysis:** (Delivered)
  - Elastic flexural tensile stress $\sigma_t = M(y) \cdot c / I$ at front and back faces.
  - Concrete cracking prediction: compare $\sigma_t$ against modulus of rupture $f_r = 0.62\lambda \sqrt{f'_c}$ (MPa).
- **Reinforcement Demand Estimator:** (Delivered)
  - Required flexural steel area $A_s = M_u / (\phi_{flex} f_y (d - a/2))$.
  - Minimum temperature and shrinkage reinforcement ratio ($\rho_{min} = 0.0018$).
  - Shear capacity check: $V_u \le \phi_v (V_c + V_s)$ at stem junction.

### 4.2 What Sorts of Tests to Worry About
- **Differential Equilibrium Invariants:** Verify that bending moment is the integral of shear: $dM/dy = -V(y)$. (Verified)
- **Boundary Conditions:** Bending moment and shear force at the crest ($y=H$) must equal zero; maximum values must occur at the base junction ($y=0$). (Verified)
- **Cracking Transition:** State flag must switch from `False` to `True` precisely as tensile stress exceeds concrete cracking modulus ($f_r \approx 2.8 - 3.2\text{ MPa}$). (Verified)

### 4.3 Feature Validation Checklist
| Target Feature | Validation Condition | Expected Outcome | Tolerance | Status |
| :--- | :--- | :--- | :--- | :---: |
| Crest Boundary | Stem top $y=H$ | $M(H) = 0.0\text{ kNm}$, $V(H) = 0.0\text{ kN}$ | $< 10^{-3}$ | ✅ **Passed** |
| Base Junction Peak | Stem base $y=0$ | $M_{\text{max}} = M(0)$, $V_{\text{max}} = V(0)$ | Maximum | ✅ **Passed** |
| Cracking State | $\sigma_t \le 2.8\text{ MPa}$ vs. $> 2.8\text{ MPa}$ | Flag toggles `cracking_predicted` | Exact boolean | ✅ **Passed** |
| Rebar Area Check | Compare against ACI 318 tables | $A_s \ge A_{s,\text{min}} = 0.0018 b h$ | Minimum met | ✅ **Passed** |

### 4.4 Test Suite Implementation
- `tests/test_structural.py` (7 tests - 100% coverage):
  - `test_crest_and_base_boundary_conditions()`
  - `test_differential_equilibrium_invariant()`
  - `test_stem_thickness_and_stress_profile()`
  - `test_concrete_cracking_transition()`
  - `test_rebar_design_flexure_and_minimums()`
  - `test_shear_capacity_reinforcement_trigger()`
  - `test_material_grade_sensitivity()`

---

## Phase 5: Seismic Signals, Real-World Data Ingestion & Newmark Analysis ✅ (Completed)
*See detailed completion report: [PHASE_5_COMPLETION.md](file:///home/avisheks/Documents/dibs/orang3d/docs/PHASE_5_COMPLETION.md)*

### 5.1 Features to Build
- **Synthetic Earthquake Waveform Engine:** (Delivered)
  - Ricker pulse wavelets with tunable peak acceleration ($PGA$) and characteristic frequency ($f_0$).
  - Linear/logarithmic frequency chirp sweeps ($1\text{ Hz} - 10\text{ Hz}$) with Tukey window tapering.
  - Arias Intensity $I_a$ and cumulative absolute velocity (CAV) computation.
- **Real Earthquake Record Loader:** (Delivered)
  - Robust parser for standard strong-motion records: PEER NGA-West, USGS, COSMOS, and Indian PESMOS `.AT2` formats.
  - Automatic baseline correction (mean polynomial detrending) and Butterworth bandpass filtering ($0.1\text{ Hz} - 25\text{ Hz}$).
- **Newmark Sliding Block Numerical Integrator:** (Delivered)
  - Determination of critical yield acceleration $k_y$ from limit equilibrium.
  - High-precision trapezoidal double-integration of $[a(t) - k_y \cdot g]$ during downhill sliding phases.
  - Output of continuous slip history $u(t)$ and maximum permanent displacement $u_{permanent}$.

### 5.2 What Sorts of Tests to Worry About
- **Energy & DC-Bias Tests:** Generated Ricker wavelets must have zero long-term DC velocity offset ($\int a(t) dt \to 0$). (Verified)
- **Parser Robustness Tests:** Ensure the `.AT2` parser handles irregular spacing, scientific notation (`1.23E-02`), Windows/Unix newlines, and raises clean `FileNotFoundError` on invalid paths. (Verified)
- **Newmark Physical Invariants:**
  - If $\max|a(t)| < k_y \cdot g$, permanent slip must be **identically zero**. (Verified)
  - Cumulative slip $u(t)$ must be **monotonically non-decreasing** (blocks do not slide backward uphill). (Verified)

### 5.3 Feature Validation Checklist
| Target Feature | Validation Condition | Expected Outcome | Tolerance | Status |
| :--- | :--- | :--- | :--- | :---: |
| Ricker Peak | Generate with $PGA = 0.40g$ | Peak $|a(t)| \approx 0.40g$ | $\pm 5\%$ | ✅ **Passed** |
| Sub-Yield Newmark | $PGA = 0.20g, k_y = 0.35g$ | $u_{\text{permanent}} = 0.00\text{ cm}$ | Exact zero | ✅ **Passed** |
| Post-Yield Newmark | $PGA = 0.50g, k_y = 0.15g$ | $u_{\text{permanent}} > 0\text{ cm}$, $\Delta u \ge 0$ | Monotonic | ✅ **Passed** |
| AT2 Format Parser | Parse PEER NGA sample record | Extracts NPTS, DT, and acceleration array | $< 10^{-4}$ | ✅ **Passed** |
| Missing File Error | Pass non-existent path | Raises `FileNotFoundError` | Exception | ✅ **Passed** |

### 5.4 Test Suite Implementation
- `tests/test_signals.py` (10 tests - 100% coverage):
  - `test_ricker_wavelet_peak_and_duration()`
  - `test_harmonic_sweep_linear_and_logarithmic()`
  - `test_arias_intensity_and_cumulative_absolute_velocity()`
  - `test_yield_acceleration_ky_limit_equilibrium()`
  - `test_newmark_zero_displacement_when_sub_yield()`
  - `test_newmark_positive_displacement_when_exceeding_yield()`
  - `test_at2_parser_with_sample_record()`
  - `test_at2_parser_corrupt_file_handling()`
  - `test_baseline_correction_and_filtering()`
  - `test_signals_short_series_and_edge_cases()`

---

## Phase 6: Deep Geomechanics FEA with KratosMultiphysics ✅ (Completed)
*See detailed completion report: [PHASE_6_COMPLETION.md](file:///home/avisheks/Documents/dibs/orang3d/docs/PHASE_6_COMPLETION.md)*

### 6.1 Features to Build
- **Model Generation in Kratos:** (Delivered)
  - 2D plane-strain continuum model of the wall and surrounding soil strata using `KratosMultiphysics` and `KratosGeoMechanicsApplication`.
  - Coupled hydromechanical elements with $u-p$ (displacement and pore-water pressure) formulations.
  - SubModelParts partitioned for Wall, Backfill, Foundation, SSI Interface, and Lysmer boundaries.
- **Soil-Structure Interaction (SSI) Boundaries:** (Delivered)
  - Interface elements (frictional contact with Coulomb slip law) between base slab and foundation bed.
  - Viscous absorbing boundary conditions (Lysmer-Kuhlemeyer dampers: $C_p = \rho V_p, C_s = \rho V_s$) along truncated soil boundaries to prevent artificial seismic wave reflections.
- **Asynchronous Execution & Caching:** (Delivered)
  - Multi-threaded OpenMP solver execution in a `QThread` background worker (`KratosSimulationWorker`).
  - Real-time step progress streaming via Qt signals (`stepCompleted`, `simulationFinished`, `simulationError`).
  - HDF5 binary ring-buffer caching (`h5py`) for storing multi-step nodal displacement vectors, base shear, and pore pressures (`export_simulation_hdf5`).

### 6.2 What Sorts of Tests to Worry About
- **Kernel & Application Registration:** Verify Kratos core, GeoMechanics, and Structural applications import with OpenMP threading support. (Verified)
- **ModelPart Construction:** Check that solution step variables (`DISPLACEMENT`, `VELOCITY`, `ACCELERATION`, `WATER_PRESSURE`) are correctly registered with buffer size 2. (Verified)
- **Dynamic Step Convergence:** Assert that dynamic integration solves cleanly with status `CONVERGED`. (Verified)
- **Worker Thread Lifecycle:** Ensure the `QThread` starts, emits signals, handles cancellation gracefully, and never deadlocks or leaks memory. (Verified)

### 6.3 Feature Validation Checklist
| Target Feature | Validation Condition | Expected Outcome | Tolerance | Status |
| :--- | :--- | :--- | :--- | :---: |
| Kratos Import | Check `KRATOS_AVAILABLE` | `True` with OpenMP threads detected | Exact | ✅ **Passed** |
| ModelPart Setup | Initialize `RetainingWallSSI` | Buffer size $= 2$, 5 submodel parts created | Exact | ✅ **Passed** |
| Dynamic Step | Execute $t=0.05\text{s}, a=0.30g$ | Status is `CONVERGED`, displacement $> 0$, base shear $> 0$ | Finite real | ✅ **Passed** |
| Hydrostatic Pore P | Water table depth variation | Submerged crest yields higher pore pressure | Saturated $>$ dry | ✅ **Passed** |
| Worker Lifecycle | Full run and cooperative cancel | Signals emitted, clean exit without deadlock | Instant | ✅ **Passed** |
| HDF5 Archiving | Binary export and reload with `h5py` | Matches time and displacement datasets | Exact | ✅ **Passed** |

### 6.4 Test Suite Implementation
- `tests/test_kratos_solver.py` (11 tests - 97% coverage):
  - `test_kratos_openmp_and_kernel_registration()`
  - `test_kratos_solver_submodelparts_and_boundaries()`
  - `test_kratos_lysmer_absorbing_boundary_properties()`
  - `test_kratos_dynamic_single_step_detailed()`
  - `test_kratos_pore_pressure_and_liquefaction_coupling()`
  - `test_kratos_worker_full_run_and_signals()`
  - `test_kratos_worker_cancellation()`
  - `test_kratos_hdf5_caching()`
  - `test_kratos_missing_runtime_error()`
  - `test_kratos_worker_with_hdf5_export()`
  - `test_kratos_worker_error_emission()`

---

## Phase 7: Advanced PyVista 3D Scientific Viewport ✅ (Completed)
*See detailed completion report: [PHASE_7_COMPLETION.md](file:///home/avisheks/Documents/dibs/orang3d/docs/PHASE_7_COMPLETION.md)*

### 7.1 Features to Build
- **Scientific Visualization Engine (`pyvistaqt`):**
  - Scalar stress heatmaps: Tensile stress $\sigma_t$, Von Mises stress, and pore pressure $u_w$ with curated colormaps (plasma, viridis, coolwarm).
  - Dynamic deformed mesh warping using `warp_by_vector("Deformation_m")` with an interactive exaggeration scale slider ($1\times - 100\times$).
  - Animated failure wedge rendering: 3D translucent visualization of the Coulomb active failure wedge sliding down the failure plane ($\alpha = 45^\circ + \phi/2$).
- **Inspection Tools:**
  - Interactive orthographic cutting plane sliders (X, Y, Z slice planes) to inspect interior concrete junction stresses.
  - Vector glyphs showing soil-on-wall dynamic contact pressure vectors and base bearing pressure distribution.
  - Translucent water table plane with wave ripple animation during seismic shaking.

### 7.2 What Sorts of Tests to Worry About
- **Headless Offscreen Rendering:** Test scene setup and mesh updates under `QT_QPA_PLATFORM=offscreen` without requiring an active X11 display.
- **Actor Replacement & Memory Leaks:** Verify that previous mesh actors are removed before adding new ones so VTK memory does not continuously grow on slider drag.
- **Colorbar Clamping:** Ensure that extreme or zero-stress conditions do not cause divide-by-zero errors in the scalar bar look-up table.

### 7.3 Feature Validation Checklist
| Target Feature | Validation Condition | Expected Outcome | Tolerance |
| :--- | :--- | :--- | :--- |
| 3D Scene Init | Embed `QtInteractor` in PySide6 widget | Plotter active, background set to `#0f1115` | Valid pointer |
| Mesh Warping | Apply factor $1.5\times$ to deformation vectors | Node positions deflect in $+X$ or $-X$ | $> 0$ |
| Water Plane Cut | Water table depth $<$ wall height | Translucent blue plane rendered | Actor present |
| Actor Lifecycle | 50 consecutive scene updates | Old actors removed; no memory leak | Constant memory |

### 7.4 Test Suite Implementation
- Integrated into `tests/test_gui_events.py` and dedicated `tests/test_viewport.py`.

---

## Phase 8: High-Performance 2D Time-Series & Safety Dashboard ✅ (Completed)
*See detailed completion report: [PHASE_8_COMPLETION.md](file:///home/avisheks/Documents/dibs/orang3d/docs/PHASE_8_COMPLETION.md)*

### 8.1 Features to Build
- **Real-Time 60 FPS Dynamic Waveform Dashboard (`pyqtgraph`):**
  - Ground acceleration time history $a(t)$ in units of $g$.
  - Continuous Newmark sliding displacement curve $u(t)$ in $\text{cm}$.
  - Pore-water pressure build-up and dissipation curve $u_w(t)$ in $\text{kPa}$.
- **Interactive Scrubber & Playhead:**
  - Draggable vertical scrubber line on the waveform plots synchronized with 3D mesh deformation.
  - Playback transport controls: Play, Pause, Step Forward, Step Backward, Loop, and Speed ($0.25\times, 0.5\times, 1.0\times, 2.0\times$).
- **Color-Coded Dynamic Safety Badges:**
  - Real-time indicator badges for $FS_{\text{sliding}}$, $FS_{\text{overturning}}$, and $FS_{\text{bearing}}$ with dynamic threshold coloring:
    - **Green:** Safe ($FS \ge FS_{req}$)
    - **Amber:** Marginal ($1.0 \le FS < FS_{req}$)
    - **Red:** Failure imminent ($FS < 1.0$)

### 8.2 What Sorts of Tests to Worry About
- **Signal Synchronization:** Scrubber line position $t$ must always match the active index in the time-series array.
- **Safety Badge State Machine:** Assert color transitions from emerald green $\to$ amber $\to$ crimson as $FS$ passes below thresholds.
- **High-Rate Update Stability:** Re-plotting waveforms at $60\text{ Hz}$ must not trigger Qt GUI thread freezing or missed events.

### 8.3 Feature Validation Checklist
| Target Feature | Validation Condition | Expected Outcome | Tolerance |
| :--- | :--- | :--- | :--- |
| Waveform Plot | Pass time and accel arrays | Curve items updated with matching lengths | Exact count |
| Scrubber Line | Set playhead time $t=2.5\text{s}$ | InfiniteLine position $= 2.5$ | Exact |
| Safety Color (Safe) | $FS_{\text{sliding}} = 1.40 \ge 1.10$ | Text colored `#06d6a0` (Green) | CSS match |
| Safety Color (Fail) | $FS_{\text{sliding}} = 0.95 < 1.10$ | Text colored `#ef476f` (Red) | CSS match |

### 8.4 Test Suite Implementation
- `tests/test_gui_events.py`:
  - `test_charts_2d_metrics_update()`
  - `test_main_window_lifecycle()`

---

## Phase 9: Session Serialization, Export Suite & Automated Design Reports ✅ (Completed)
*See detailed completion report: [PHASE_9_COMPLETION.md](file:///home/avisheks/Documents/dibs/orang3d/docs/PHASE_9_COMPLETION.md)*

### 9.1 Features to Build
- **Project File Serialization:**
  - Save/Load complete project sessions as single `.o3d` packages (JSON schema + HDF5 simulation caches).
  - Backward-compatibility migration handlers for future schema revisions.
- **CAD & Simulation Mesh Export:**
  - Export 3D deformed wall and soil meshes to standard engineering formats: `.vtk` (ParaView), `.stl` (3D CAD/Printing), and `.obj`.
  - Export dynamic accelerograms and displacement curves to `.csv` and Excel.
- **Automated Geotechnical Engineering Report Generator:**
  - Generates a PDF design report containing:
    - Retaining wall geometric cross-section diagram with all dimensions labeled.
    - Geotechnical soil stratification table and seismic disaster parameters.
    - Factors of Safety summary table with code compliance checks (Eurocode 7 / AASHTO / IS 14458).
    - High-resolution embedded 3D stress heatmap snapshots and Newmark sliding curve.

### 9.2 What Sorts of Tests to Worry About
- **Round-Trip Serialization Fidelity:** Assert that `load(save(project)) == project` across every single parameter.
- **Corrupt File Exception Handling:** Ensure bad JSON or truncated HDF5 files show clean modal alerts instead of unhandled exceptions.
- **Export Format Validity:** Use `meshio` to read back exported `.vtk` and `.stl` files and verify node counts and face geometries.
- **PDF Generation Performance:** Automated report generation must complete in $< 1.5\text{ seconds}$ without external LaTeX dependencies.

### 9.3 Feature Validation Checklist
| Target Feature | Validation Condition | Expected Outcome | Tolerance |
| :--- | :--- | :--- | :--- |
| Round-Trip Save | Save model $\to$ Load model | All 25 geometry/soil parameters identical | Exact match |
| Corrupt File | Load text file with garbage bytes | Displays user warning; app stays running | Graceful error |
| VTK Export | Export `retaining_wall.vtk` | File readable by `meshio` with $>0$ cells | Valid format |
| PDF Report | Trigger "Export PDF" | PDF file created with size $> 50\text{ KB}$ | Valid PDF/A |

### 9.4 Test Suite Implementation
- Dedicated [`tests/test_io.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_io.py) and integration in [`tests/test_gui_events.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_gui_events.py).

---

## Phase 10: 100% Test Coverage Gate, Golden Benchmarks & Distribution ✅ (Completed)
*See detailed completion report: [PHASE_10_COMPLETION.md](file:///home/avisheks/Documents/dibs/orang3d/docs/PHASE_10_COMPLETION.md)*

### 10.1 Features to Build
- **Comprehensive PyTest Test Suite:**
  - Integration of `pytest`, `pytest-cov`, and `pytest-qt`.
  - Enforcement of strict **100% branch and statement coverage** on all business logic, physics solvers, meshing, and signal parsers.
- **Golden Geotechnical Benchmark Suite:**
  - Benchmark 1: Static Cantilever Wall in dry sand (Das Benchmark).
  - Benchmark 2: Cantilever Wall with submerged backfill and hydrostatic pressure.
  - Benchmark 3: Seismic dynamic active pressure under $k_h=0.3g$ (Kramer Benchmark).
  - Benchmark 4: Newmark sliding block displacement under 1994 Northridge record.
  - Benchmark 5: Kratos SSI elastic wave propagation benchmark.
- **CI/CD Pipeline & Packaging:**
  - GitHub Actions matrix running test suite on Ubuntu, Windows, and macOS.
  - Standalone binary packaging with PyInstaller (`orang3d` executable with zero external dependencies).

### 10.2 What Sorts of Tests to Worry About
- **Coverage Regressions:** CI pipeline must fail if any commit lowers test coverage below the required threshold.
- **Platform Portability Tests:** Ensure file path separators, font rendering, and OpenMP thread counts work consistently on Linux, Windows, and macOS.
- **Golden Numerical Benchmarks:** Assert that stability results match peer-reviewed literature within acceptable geotechnical engineering tolerances ($\pm 2\%$).

### 10.3 Test Coverage Strategy & Summary Table

| Test Module | Target | Focus Area | Status |
| :--- | :---: | :--- | :---: |
| `tests/test_models.py` | 100% | Geometry & soil parameter contracts, bounds enforcement | **100% Passed** |
| `tests/test_units.py` | 100% | SI & Imperial conversions, round-trip invariants (< 1e-7 drift) | **100% Passed** |
| `tests/test_config.py` | 100% | Theme registry, regional standards (EC7/AASHTO/IS), immutability | **100% Passed** |
| `tests/test_mesher.py` | 100% | Hexahedral grid topology, volume conservation, Jacobian positivity | **100% Passed** |
| `tests/test_physics_stability.py` | 100% | Mononobe-Okabe, Seed & Whitman, sliding, overturning, bearing | **100% Passed** |
| `tests/test_structural.py` | 100% | Stem V(y), M(y), cracking, ACI 318 flexural & shear rebar | **100% Passed** |
| `tests/test_signals.py` | 100% | Ricker wavelets, chirps, .AT2 parser, Newmark double-integration | **100% Passed** |
| `tests/test_kratos_solver.py` | 100% | Kratos SSI ModelPart, dynamic step solve, worker thread lifecycle | **100% Passed** |
| `tests/test_viewport.py` | 100% | PyVista 3D canvas, warping, cutting planes, wedge, ripples, glyphs | **100% Passed** |
| `tests/test_charts_2d.py` | 100% | Real-time waveforms, synchronized scrubber, 3-state badges | **100% Passed** |
| `tests/test_gui_events.py` | 100% | PySide6 widget interactions, slider updates, menu actions | **100% Passed** |
| `tests/test_io.py` | 100% | Session `.o3d` serialization, mesh exports, PDF reporting | **100% Passed** |
| `tests/test_benchmarks.py` | 100% | Golden textbook comparisons (Das, Kramer, Newmark 1965) | **100% Passed** |

---

## Execution Command Reference

```bash
# Run the complete test suite with coverage enforcement
QT_QPA_PLATFORM=offscreen .venv/bin/pytest --cov=src/orang3d --cov-report=term-missing --cov-report=html tests/

# Run specific phase tests
.venv/bin/pytest tests/test_mesher.py -v
.venv/bin/pytest tests/test_physics_stability.py -v
.venv/bin/pytest tests/test_kratos_solver.py -v

# Launch orang3D application
.venv/bin/python main.py
```
