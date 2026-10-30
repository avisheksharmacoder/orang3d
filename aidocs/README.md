# orang3D AI & Developer Documentation (aidocs)

Welcome to the internal engineering documentation and onboarding guide for **orang3D** 🍊🧱.

This documentation suite is crafted specifically for AI assistants and human software engineers to navigate, understand, extend, and test the codebase with speed and precision.

---

## Documentation Index

| Document | Purpose |
| :--- | :--- |
| **[INDEX.md](file:///home/avisheks/Documents/dibs/orang3d/aidocs/INDEX.md)** | Master sitemap, rapid orientation guide, and technology stack overview. |
| **[ARCHITECTURE.md](file:///home/avisheks/Documents/dibs/orang3d/aidocs/ARCHITECTURE.md)** | Deep dive into the Two-Speed Physics Architecture, data flows, and subsystem interactions. |
| **[NAVIGATING_THE_CODEBASE.md](file:///home/avisheks/Documents/dibs/orang3d/aidocs/NAVIGATING_THE_CODEBASE.md)** | Directory tree, file-by-file responsibilities, key entry points, and developer workflows. |
| **[TESTING_AND_TDD_GUIDE.md](file:///home/avisheks/Documents/dibs/orang3d/aidocs/TESTING_AND_TDD_GUIDE.md)** | Complete guide to the 6 testing categories, running headless tests, and TDD workflow. |
| **[CORE_CONCEPTS.md](file:///home/avisheks/Documents/dibs/orang3d/aidocs/CORE_CONCEPTS.md)** | Geotechnical, structural, and numerical engineering theory implemented in the codebase. |

---

## 30-Second Executive Summary

- **What it is:** A desktop civil and geotechnical engineering application for real-time 3D seismic and disaster analysis of retaining walls (earthquakes, water table fluctuations, and soil liquefaction).
- **Core Technology Stack:**
  - **Language:** Python 3.12+
  - **UI Framework:** [PySide6](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/main_window.py) (Qt 6 with dark/light themes and dockable panels)
  - **3D Visualization:** [PyVista](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/viewport_3d.py) + `pyvistaqt` (Hardware-accelerated VTK, dynamic mesh warping, stress heatmaps)
  - **2D Plotting:** [PyQtGraph](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/charts_2d.py) (High-performance 60 FPS seismic acceleration & Newmark slip charts)
  - **Fast Math & Meshing:** [NumPy](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py) & [SciPy](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/at2_parser.py) (Sub-2ms pure NumPy 8-node hex mesher and analytical physics)
  - **Deep FEA Engine:** [KratosMultiphysics](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py) (`KratosGeoMechanicsApplication` with multi-threaded OpenMP)
  - **Data Storage:** [h5py](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L270) (HDF5 simulation caching) & `meshio` (VTK export)

---

## Two-Speed Physics Architecture

```
                               ┌───────────────────────────────────────────────┐
                               │                 orang3D GUI                   │
                               │        PySide6 / Qt 6 Desktop Window          │
                               └───────────────────────┬───────────────────────┘
                                                       │
                           ┌───────────────────────────┴───────────────────────────┐
                           ▼                                                       ▼
             ┌───────────────────────────┐                           ┌───────────────────────────┐
             │      3D Scientific View   │                           │     2D Fast Dashboards    │
             │     PyVista + pyvistaqt   │                           │         PyQtGraph         │
             │ • Solid Hex Brick Meshes  │                           │ • Real-time Accelerogram  │
             │ • Stress Heatmaps         │                           │ • Newmark Sliding History │
             │ • Dynamic Vector Warping  │                           │ • Safety Factor Meters    │
             └─────────────▲─────────────┘                           └─────────────▲─────────────┘
                           │                                                       │
                           └───────────────────────────┬───────────────────────────┘
                                                       │ (Debounced Signal/Slot)
                                                       │
                           ┌───────────────────────────┴───────────────────────────┐
                           ▼                                                       ▼
             ┌───────────────────────────┐                           ┌───────────────────────────┐
             │    Fast Analytical Core   │                           │    Deep Geomechanics FEA  │
             │  NumPy / SciPy (< 2 ms)   │                           │  Kratos Multiphysics QThread │
             │ • Mononobe-Okabe (M-O)    │                           │ • Non-linear dynamic SSI  │
             │ • Limit Equilibrium Statics│                           │ • Coupled u-p hydromech   │
             │ • ACI 318 Concrete Rebar  │                           │ • Lysmer non-reflecting BC│
             │ • Newmark Sliding Block   │                           │ • Multi-step HDF5 cache   │
             └───────────────────────────┘                           └───────────────────────────┘
```

1. **Analytical Loop (Interactive 60 FPS):** Every slider adjustment (geometry, soil friction, water table, PGA) triggers the pure NumPy mesher and analytical physics in $< 2\text{ ms}$, immediately refreshing the 3D viewport and 2D charts without frame drops.
2. **Deep Simulation Loop (Asynchronous Background):** When initiating dynamic earthquake time histories or continuum FEA, a [KratosSimulationWorker](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L297) runs in a background [QThread](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py#L297), streaming progress via Qt signals and archiving multi-step tensor outputs to HDF5.

---

## Quick Navigation Links

- Need to understand how code is organized? See **[NAVIGATING_THE_CODEBASE.md](file:///home/avisheks/Documents/dibs/orang3d/aidocs/NAVIGATING_THE_CODEBASE.md)**.
- Need to run or write tests? See **[TESTING_AND_TDD_GUIDE.md](file:///home/avisheks/Documents/dibs/orang3d/aidocs/TESTING_AND_TDD_GUIDE.md)**.
- Need the geotechnical formulas or Kratos setup details? See **[CORE_CONCEPTS.md](file:///home/avisheks/Documents/dibs/orang3d/aidocs/CORE_CONCEPTS.md)**.
- Need the system architecture and data flows? See **[ARCHITECTURE.md](file:///home/avisheks/Documents/dibs/orang3d/aidocs/ARCHITECTURE.md)**.
