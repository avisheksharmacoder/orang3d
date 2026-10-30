# Navigating the orang3D Codebase

This guide provides a practical walkthrough of the directory structure, file responsibilities, key entry points, and step-by-step developer recipes for modifying or extending the software.

---

## 1. Directory Structure Tour

```text
src/orang3d/
├── config.py              # Application settings, theme tokens & design code standards
├── units.py               # Unit system conversions (Metric SI vs Imperial US)
├── main.py                # Standalone entry point script
├── models/
│   ├── __init__.py        # Re-exports models
│   └── wall_params.py     # Dataclasses: RetainingWallGeometry, SoilProperties, SeismicParams
├── mesher/
│   ├── __init__.py        # Re-exports mesher functions
│   └── hex_mesher.py      # Pure NumPy 8-node hex mesh generator & templates
├── physics/
│   ├── __init__.py        # Re-exports physics solvers
│   ├── mononobe_okabe.py  # M-O, Rankine, Coulomb & Seed & Whitman earth pressure
│   ├── stability.py       # Sliding, overturning, bearing capacity & liquefaction
│   ├── structural.py      # Stem V(y), M(y), cracking & ACI 318 Whitney rebar design
│   └── kratos_solver.py   # KratosMultiphysics continuum SSI solver & QThread worker
├── signals/
│   ├── __init__.py        # Re-exports signal processors
│   ├── synthetic.py       # Ricker wavelets, chirps, Arias Intensity, ky & Newmark
│   └── at2_parser.py      # PEER NGA .AT2 parser, baseline correction & bandpass filter
└── gui/
    ├── __init__.py        # Re-exports GUI widgets
    ├── main_window.py     # Central QMainWindow coordinating all docks & viewport
    ├── viewport_3d.py     # Scientific 3D viewport powered by PyVista
    ├── charts_2d.py       # High-performance 2D charts powered by PyQtGraph
    └── panels/
        ├── __init__.py    # Re-exports panels
        ├── geometry_panel.py # Retaining wall geometry sliders & template picker
        ├── soil_panel.py     # Soil strata properties sliders
        └── seismic_panel.py  # Earthquake PGA, water table, playhead controls
```

---

## 2. File-by-File Responsibilities & Key Exports

### Core Foundation & Contracts

#### [`src/orang3d/models/wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py)
- **Primary Exports:**
  - [`RetainingWallGeometry`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L18): Retaining wall dimensions (`stem_height`, `footing_thickness`, `stem_thickness_base`, `stem_thickness_top`, `toe_length`, `heel_length`, `shear_key_depth`, `shear_key_width`, `wall_length`). Enforces physical bounds in `__post_init__`.
  - [`SoilProperties`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L70): Soil properties (`friction_angle`, `cohesion`, `unit_weight`, `saturated_unit_weight`, `wall_friction_angle`, `foundation_friction_angle`, `foundation_cohesion`, `foundation_unit_weight`, `allowable_bearing_capacity`, `elastic_modulus`, `poissons_ratio`).
  - [`SeismicParams`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L125): Earthquake parameters (`horizontal_pga`, `vertical_pga`, `backfill_slope`, `water_table_depth`, `liquefaction_factor`, `pore_pressure_ratio_ru`).
  - [`AnalysisResults`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L169): Output contract storing safety factors, resultant thrusts, moments, stresses, and rebar demands.
  - [`validate_seismic_with_soil`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L158): Checks geotechnical compatibility (e.g., backfill slope $\beta < \phi$).

#### [`src/orang3d/units.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/units.py)
- **Primary Exports:**
  - [`UnitSystem`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/units.py#L12): Enum for `METRIC_SI` ($m, kN, kPa$) vs `IMPERIAL_US` ($ft, kips, psf$).
  - [`UnitConverter`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/units.py#L18): Bidirectional conversion functions for length, force, stress, unit weight, acceleration, and rebar area.

#### [`src/orang3d/config.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/config.py)
- **Primary Exports:**
  - [`ThemeColors`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/config.py#L13): Dark and light theme color palettes (backgrounds, panels, accent orange `#f97316`, safe green, warning yellow, failure red).
  - [`DesignCodeStandard`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/config.py#L32): Regional building codes (`EUROCODE_7`, `AASHTO_LRFD`, `IS_14458`).
  - [`get_required_safety_factors`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/config.py#L40): Minimum allowable factors of safety for static and seismic load combinations under each code standard.

---

### Meshing & Geometry

#### [`src/orang3d/mesher/hex_mesher.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py)
- **Primary Exports:**
  - [`WallTemplate`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L25): Structural wall template enum (`INVERTED_T`, `L_SHAPED`, `REVERSE_L`, `GRAVITY`).
  - [`build_retaining_wall_hex_mesh`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L42): Pure NumPy 8-node hex mesher creating structured solid bricks for stem, footing, toe, heel, and shear key. Generates a `pyvista.UnstructuredGrid` in $< 2\text{ ms}$.
  - [`compute_hex_jacobian_determinants`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L220): Verifies that all hexahedral cells have positive volume ($\det(J) > 0$).
  - [`compute_wall_geometric_properties`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L250): Closed-form volume, surface area, center of gravity ($x_{cg}, y_{cg}, z_{cg}$), and mass moments of inertia ($I_{xx}, I_{yy}, I_{zz}$).
  - [`build_soil_and_water_meshes`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L320): Generates backfill soil prism, subgrade foundation bed, and translucent phreatic water surface.
  - [`build_3d_failure_wedge_mesh`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L380): Builds 3D failure wedge geometry along the Coulomb active failure plane ($\alpha = 45^\circ + \phi/2$).

---

### Physics, Geotechnics & Structural Analysis

#### [`src/orang3d/physics/mononobe_okabe.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/mononobe_okabe.py)
- **Primary Exports:**
  - [`compute_mononobe_okabe`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/mononobe_okabe.py#L22): Total active coefficient $K_{ae}$, horizontal component $K_{ah}$, and vertical component $K_{av}$.
  - [`compute_rankine_earth_pressures`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/mononobe_okabe.py#L85): Rankine static active $K_a$ and passive $K_p$.
  - [`compute_coulomb_earth_pressures`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/mononobe_okabe.py#L110): Coulomb static active $K_a$ with wall friction.
  - [`compute_lateral_thrusts`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/mononobe_okabe.py#L135): Static vs. dynamic thrust partition via Seed & Whitman (static resultant at $H/3$, dynamic increment $\Delta P_{ae}$ at $0.6H$).

#### [`src/orang3d/physics/stability.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/stability.py)
- **Primary Exports:**
  - [`calculate_stability_factors`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/stability.py#L78): Sliding safety factor $FS_s$, overturning safety factor $FS_o$, and ultimate bearing capacity safety factor $FS_b$.
  - [`compute_bearing_capacity_factors`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/stability.py#L25): Meyerhof/Vesic factors ($N_c, N_q, N_\gamma$).
  - [`compute_ultimate_bearing_capacity`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/stability.py#L45): Hansen/Meyerhof bearing capacity with effective footing width $B' = B - 2e$ and load inclination factors.
  - [`compute_liquefaction_reduction`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/stability.py#L18): Non-linear soil degradation curve as pore pressure ratio $r_u \to 1.0$.

#### [`src/orang3d/physics/structural.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/structural.py)
- **Primary Exports:**
  - [`compute_stem_internal_profiles`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/structural.py#L25): Evaluates continuous shear force $V(y)$, bending moment $M(y)$, and elastic tensile stress $\sigma_t(y)$ along stem height. Predicts cracking if $\sigma_{t,\max} > 0.62\sqrt{f'_c}$.
  - [`design_flexural_reinforcement`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/structural.py#L90): ACI 318 / Eurocode 2 Whitney rectangular stress block rebar area $A_s$, minimum steel $A_{s,\min}$, shear capacity check ($\phi V_c$), and practical bar callout strings.

#### [`src/orang3d/physics/kratos_solver.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py)
- **Primary Exports:**
  - [`KratosRetainingWallSolver`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L23): 2D continuum SSI finite element solver. Constructs `RetainingWallSSI` ModelPart with SubModelParts (`WallPart`, `BackfillPart`, `FoundationPart`, `InterfacePart`, `LysmerBoundaryPart`).
  - [`get_lysmer_coefficients`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L182): Calculates Lysmer viscous boundary dashpot coefficients ($C_p, C_s, V_p, V_s$).
  - [`run_dynamic_step`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L213): Coupled dynamic integration step returning crest deflection, base shear, pore-water pressure, and Cauchy stress tensor $[\sigma_{xx}, \sigma_{yy}, \tau_{xy}]$.
  - [`export_simulation_hdf5`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L270): Serializes simulation time histories directly to HDF5 binary via `h5py`.
  - [`KratosSimulationWorker`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L297): Multi-threaded PySide6 `QThread` running simulations in the background with progress signals and cooperative cancellation.

---

### Signals & Dynamics

#### [`src/orang3d/signals/synthetic.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py)
- **Primary Exports:**
  - [`generate_ricker_wavelet`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L15): Pulse-like earthquake generator with zero DC velocity offset.
  - [`generate_harmonic_sweep`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L39): Linear/logarithmic frequency chirp with Tukey tapering window.
  - [`compute_arias_intensity`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L71): Cumulative $I_a(t)$ and total Arias Intensity (m/s).
  - [`compute_cumulative_absolute_velocity`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L96): Cumulative $\text{CAV}(t)$ and total CAV (m/s).
  - [`compute_yield_acceleration_ky`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L118): Limit-equilibrium critical horizontal yield acceleration $k_y$.
  - [`compute_newmark_sliding_displacement`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L172): Double-integrates excess acceleration during active downhill sliding phases to compute permanent displacement $u(t)$ in cm.

#### [`src/orang3d/signals/at2_parser.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/at2_parser.py)
- **Primary Exports:**
  - [`parse_at2_file`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/at2_parser.py#L10): Reads standard PEER NGA / COSMOS strong-motion files, extracting metadata, $N_{\text{pts}}$, $\Delta t$, and accelerations.
  - [`apply_baseline_correction`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/at2_parser.py#L75): Polynomial detrending baseline correction.
  - [`apply_bandpass_filter`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/at2_parser.py#L96): Zero-phase forward-backward Butterworth bandpass filtering.

---

### Graphical User Interface (GUI)

#### [`src/orang3d/gui/main_window.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/main_window.py)
- **Class:** [`RetainingWallMainWindow`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/main_window.py#L38)
- Coordinates all dock widgets, central 3D viewport, 2D charts, menu bar, and status badges.
- Slot [`on_parameters_changed()`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/main_window.py#L170): Main reactive trigger that rebuilds the mesh and updates physics.

#### [`src/orang3d/gui/viewport_3d.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/viewport_3d.py)
- **Class:** [`RetainingWall3DView`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/viewport_3d.py#L27)
- Manages the `pyvistaqt.QtInteractor` instance.
- Method [`update_wall_geometry()`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/viewport_3d.py#L65): Re-renders wall mesh, warps by `Deformation_m`, applies scalar colormap (`plasma`), and manages backfill/foundation actors.

#### [`src/orang3d/gui/charts_2d.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/charts_2d.py)
- **Class:** [`SeismicCharts2DWidget`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/charts_2d.py#L20)
- Manages `pyqtgraph.PlotWidget` instances for ground acceleration $a(t)$ and Newmark sliding slip $u(t)$.
- Updates real-time playhead scrubber line during simulation playback.

---

## 3. Developer Workflows & Recipes

### Recipe 1: Adding a New Retaining Wall Template (e.g. Counterfort Wall)
1. In [`src/orang3d/mesher/hex_mesher.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L25), add `COUNTERFORT = "counterfort"` to the [`WallTemplate`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L25) enum.
2. In [`build_retaining_wall_hex_mesh()`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L42), add the node topology and cell connectivity block for the counterfort rib elements.
3. In [`compute_wall_geometric_properties()`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L250), add the analytical volume and centroid formulas for the counterfort rib.
4. In [`src/orang3d/gui/panels/geometry_panel.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/panels/geometry_panel.py), add "Counterfort Cantilever" to the template combo box.
5. In [`tests/test_mesher.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_mesher.py), add a unit test validating volume conservation and Jacobian positivity ($\det(J) > 0$).

### Recipe 2: Adding a New Soil Property
1. In [`src/orang3d/models/wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L70), add the new field with default value and type annotation to [`SoilProperties`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L70).
2. Add physical bounds validation inside `SoilProperties.__post_init__()`.
3. In [`src/orang3d/gui/panels/soil_panel.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/panels/soil_panel.py), add the corresponding labeled slider and numeric spinbox.
4. In [`tests/test_models.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_models.py), add contract validation tests checking lower/upper bounds.

### Recipe 3: Adding a Regional Building Code Standard
1. In [`src/orang3d/config.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/config.py#L32), add the new code standard enum value to [`DesignCodeStandard`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/config.py#L32).
2. In [`get_required_safety_factors()`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/config.py#L40), define the static and seismic minimum safety factor dictionary for the new code.
3. In [`tests/test_config.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_config.py), add a test verifying the new standard returns the expected safety thresholds.
