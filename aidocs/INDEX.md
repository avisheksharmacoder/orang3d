# orang3D Architecture Index & Developer Sitemap

This document serves as the master navigation map for the **orang3D** repository. Use it to instantly locate files, modules, models, solvers, GUI components, and tests.

---

## 1. Top-Level Directory Layout

```text
orang3d/
├── aidocs/                  # Comprehensive AI and human developer documentation
│   ├── README.md            # Onboarding summary & executive overview
│   ├── INDEX.md             # Master sitemap & file index (this file)
│   ├── ARCHITECTURE.md      # Detailed system architecture & data flows
│   ├── NAVIGATING_THE_CODEBASE.md # Folder tour & developer workflows
│   ├── TESTING_AND_TDD_GUIDE.md   # Testing categories, TDD rules, headless runner
│   └── CORE_CONCEPTS.md     # Geotechnical, structural & FEA physics reference
├── docs/                    # Phase-by-phase completion reports & roadmap
│   ├── DEVELOPMENT_PLAN.md  # 10-Phase master engineering development plan
│   ├── PHASE_1_COMPLETION.md# Data contracts, validation & theme registry
│   ├── PHASE_2_COMPLETION.md# Pure NumPy 8-node hex mesher & templates
│   ├── PHASE_3_COMPLETION.md# Mononobe-Okabe, Seed & Whitman, stability statics
│   ├── PHASE_4_COMPLETION.md# Structural continuous V(y), M(y) & ACI 318 rebar
│   ├── PHASE_5_COMPLETION.md# Seismic signals, PEER .AT2 parser & Newmark engine
│   ├── PHASE_6_COMPLETION.md# KratosMultiphysics geomechanics continuum FEA
│   ├── PHASE_7_COMPLETION.md# Advanced PyVista 3D scientific viewport
│   ├── PHASE_8_COMPLETION.md# High-performance 2D time-series & safety dashboard
│   ├── PHASE_9_COMPLETION.md# Session serialization, export suite & PDF reports
│   ├── PHASE_10_COMPLETION.md# Test coverage gate, golden benchmarks & packaging
│   ├── SIMULATION_GUIDE.md  # Comprehensive user & simulation manual for orang3D
│   └── PACKAGING_AND_EXPORT_GUIDE.md # Cross-platform Windows & Linux standalone packaging guide
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI matrix & coverage threshold gate
├── src/
│   └── orang3d/             # Primary Python package
│       ├── __init__.py      # Package metadata
│       ├── config.py        # Centralized theme registry, styling tokens & codes
│       ├── main.py          # Application launch script & Qt event loop
│       ├── units.py         # Unit conversion utilities (Metric SI vs Imperial US)
│       ├── gui/             # Desktop graphical user interface (PySide6)
│       │   ├── charts_2d.py # Real-time 60 FPS PyQtGraph acceleration & slip curves
│       │   ├── main_window.py # Central QMainWindow, dock manager & toolbar
│       │   ├── viewport_3d.py # Scientific PyVista 3D viewport with VTK actors
│       │   └── panels/      # Parameter dock panels
│       │       ├── geometry_panel.py # Retaining wall dimensions & templates
│       │       ├── seismic_panel.py  # Earthquake PGA, water table & playhead
│       │       └── soil_panel.py     # Backfill, subgrade & foundation properties
│       ├── io/              # Session archiving, CAD/Mesh export & reporting
│       │   ├── __init__.py  # I/O package exports
│       │   ├── mesh_export.py # .vtk, .stl, .obj mesh export & .csv waveforms
│       │   ├── report_generator.py # Offscreen geotechnical engineering PDF report generator
│       │   └── serialization.py # Single-file .o3d bundle (JSON manifest + HDF5 caches)
│       ├── mesher/          # Parametric solid mesh generator
│       │   ├── __init__.py  # Mesher exports
│       │   └── hex_mesher.py# Pure NumPy 8-node hex mesher (< 2 ms)
│       ├── models/          # Type contracts & validation schemas
│       │   ├── __init__.py  # Model exports
│       │   └── wall_params.py# RetainingWallGeometry, SoilProperties, SeismicParams
│       ├── physics/         # Geotechnical, structural & FEA calculation engines
│       │   ├── __init__.py  # Physics exports
│       │   ├── kratos_solver.py # KratosMultiphysics GeoMechanics continuum solver
│       │   ├── mononobe_okabe.py# Dynamic active/passive earth pressure engine
│       │   ├── stability.py # Sliding, overturning, bearing capacity safety factors
│       │   └── structural.py# Continuous shear V(y), moment M(y) & ACI 318 rebar
│       └── signals/         # Earthquake signal processing & ingestion
│           ├── __init__.py  # Signal exports
│           ├── at2_parser.py# PEER NGA / COSMOS .AT2 file parser & filters
│           └── synthetic.py # Ricker wavelets, chirps, Arias Intensity & Newmark
├── tests/                   # 100% Automated pytest test suite
│   ├── test_benchmarks.py   # Golden textbook comparisons (Das, Kramer, Newmark, Wolf)
│   ├── test_charts_2d.py    # Real-time 2D waveforms, scrubber & 3-state badge tests
│   ├── test_config.py       # Theme registry & regional design standard tests
│   ├── test_gui_events.py   # Headless PySide6 UI event, slider & panel tests
│   ├── test_kratos_solver.py# Kratos SSI, Lysmer dampers & HDF5 archiving tests
│   ├── test_mesher.py       # Pure NumPy hex mesher, Jacobian & latency tests
│   ├── test_models.py       # Dataclass bounds, validation & schema tests
│   ├── test_physics_stability.py # M-O, Rankine, Coulomb & Das/Kramer golden tests
│   ├── test_signals.py      # Wavelets, chirps, Newmark & AT2 parser tests
│   ├── test_structural.py   # Stem V(y), M(y), cracking & rebar design tests
│   ├── test_units.py        # SI Metric vs Imperial conversion tests
│   ├── test_viewport.py     # Headless PyVista 3D canvas, warping, wedge & glyph tests
│   └── test_io.py           # .o3d session serialization, CAD mesh export & PDF report tests
├── main.py                  # Workspace root launcher
├── orang3d.spec             # Standalone binary PyInstaller build specification
├── pyproject.toml           # Project packaging & build configuration (setuptools)
├── requirements.txt         # Pinned runtime and testing dependencies
└── README.md                # Project overview, architecture & quickstart
```

---

## 2. Quick Source File Sitemap

| Symbol / Target Area | File Path | Description |
| :--- | :--- | :--- |
| **App Entry Point** | [`main.py`](file:///home/avisheks/Documents/dibs/orang3d/main.py) | Launches the PySide6 Qt GUI. |
| **Package Entry Point** | [`src/orang3d/main.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/main.py) | Configures Qt attributes, app window, and event loop. |
| **Geometry Contracts** | [`src/orang3d/models/wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L18) | [`RetainingWallGeometry`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L18) dataclass with physical bounds. |
| **Soil Contracts** | [`src/orang3d/models/wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L70) | [`SoilProperties`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L70) dataclass with geotechnical invariants. |
| **Seismic Contracts** | [`src/orang3d/models/wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L125) | [`SeismicParams`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py#L125) dataclass (PGA, water table, $r_u$). |
| **Hex Mesher** | [`src/orang3d/mesher/hex_mesher.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L240) | [`build_3d_wall_mesh`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L240): $< 2\text{ ms}$ NumPy brick mesher. |
| **Failure Wedge & Glyphs** | [`src/orang3d/mesher/hex_mesher.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L485) | [`build_3d_wedge_mesh`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L485), [`build_contact_pressure_glyphs`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py#L559). |
| **Earth Pressure Engine** | [`src/orang3d/physics/mononobe_okabe.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/mononobe_okabe.py#L22) | [`compute_mononobe_okabe`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/mononobe_okabe.py#L22) & Seed & Whitman partition. |
| **Global Stability** | [`src/orang3d/physics/stability.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/stability.py#L78) | [`calculate_stability_factors`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/stability.py#L78): Sliding, overturning & bearing safety. |
| **Continuous Stem Profiles** | [`src/orang3d/physics/structural.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/structural.py#L25) | [`compute_stem_internal_profiles`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/structural.py#L25): $V(y)$, $M(y)$, tensile stress $\sigma_t(y)$. |
| **Rebar Design** | [`src/orang3d/physics/structural.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/structural.py#L90) | [`design_flexural_reinforcement`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/structural.py#L90): ACI 318 / Eurocode 2 Whitney rebar estimator. |
| **Waveform Synthesizer** | [`src/orang3d/signals/synthetic.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L15) | [`generate_ricker_wavelet`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L15) & [`generate_harmonic_sweep`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L39). |
| **Newmark Integrator** | [`src/orang3d/signals/synthetic.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L172) | [`compute_newmark_sliding_displacement`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py#L172): Downhill double-integration. |
| **AT2 Record Parser** | [`src/orang3d/signals/at2_parser.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/at2_parser.py#L10) | [`parse_at2_file`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/at2_parser.py#L10), baseline correction & Butterworth filter. |
| **Kratos SSI Solver** | [`src/orang3d/physics/kratos_solver.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L23) | [`KratosRetainingWallSolver`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L23): 2D continuum $u-p$ dynamic solver. |
| **Asynchronous Worker** | [`src/orang3d/physics/kratos_solver.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L297) | [`KratosSimulationWorker`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L297): Multi-threaded PySide6 `QThread`. |
| **3D Scientific Viewport** | [`src/orang3d/gui/viewport_3d.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/viewport_3d.py#L49) | [`RetainingWall3DView`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/viewport_3d.py#L49): PyVista Qt 3D canvas, heatmaps, warping, wedge & slicing. |
| **2D Dynamic Charts** | [`src/orang3d/gui/charts_2d.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/charts_2d.py#L23) | [`Charts2DWidget`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/charts_2d.py#L23): 60 FPS PyQtGraph acceleration, slip, pore pressure & 3-state badges. |
| **Main Window & UI Shell**| [`src/orang3d/gui/main_window.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/main_window.py#L27) | [`MainWindow`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/main_window.py#L27): Central hub coordinating all signals/slots. |
| **Session Serialization**| [`src/orang3d/io/serialization.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/io/serialization.py#L77) | [`save_project_session`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/io/serialization.py#L77), [`load_project_session`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/io/serialization.py#L138): `.o3d` bundle manager. |
| **CAD & Mesh Export** | [`src/orang3d/io/mesh_export.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/io/mesh_export.py#L22) | [`export_mesh_to_vtk`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/io/mesh_export.py#L22), `.stl`, `.obj`, and `.csv` waveform tables. |
| **Design PDF Reports** | [`src/orang3d/io/report_generator.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/io/report_generator.py#L25) | [`generate_engineering_pdf_report`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/io/report_generator.py#L25): Offscreen Qt PDF report generator. |
| **Golden Benchmarks**  | [`tests/test_benchmarks.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_benchmarks.py) | Peer-reviewed textbook benchmarks (Das, Bowles, Terzaghi, Kramer, Newmark, Wolf). |

