# orang3D 🍊🧱

**Real-time 3D Seismic and Disaster Analysis of Retaining Walls**

`orang3D` is a free, 100% open-source desktop engineering application designed for civil and geotechnical researchers to visualize and simulate **Soil-Structure Interaction (SSI)** under earthquake shaking, rising water tables, and liquefaction.

Built with a **Two-Speed Physics Architecture**, it pairs a **sub-2ms vectorized analytical engine (60 FPS)** with high-fidelity scientific 3D visualization.

---

## Architecture Overview

```
                      ┌───────────────────────────────────────┐
                      │             orang3D GUI               │
                      │         (PySide6 / Qt 6)              │
                      └──────────────────┬────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │    3D Viewport Widget     │                   │     2D Plotting Widget    │
   │  (PyVista + pyvistaqt)    │                   │        (PyQtGraph)        │
   │ • Wall & Soil Strata      │                   │ • Dynamic Accel a(t)      │
   │ • Stress Heatmaps         │                   │ • Newmark Permanent Slip  │
   │ • Water Table Plane       │                   │ • Real-time Safety Badges │
   └─────────────▲─────────────┘                   └─────────────▲─────────────┘
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │   Fast Analytical Core    │                   │  Deep Kratos FEA Worker   │
   │   (NumPy / SciPy @ 60fps) │                   │    (KratosMultiphysics)   │
   │ • Mononobe-Okabe (M-O)    │                   │ • Non-linear dynamic SSI  │
   │ • Newmark Sliding Block   │                   │ • Liquefaction analysis   │
   │ • Pure NumPy Hex Mesher   │                   │ • Multi-step time history │
   └───────────────────────────┘                   └───────────────────────────┘
```

---

## Features

- **Pure NumPy Parametric 3D Mesher:** Generates 8-node hexahedral (brick) solid meshes for the wall (stem, footing, toe, heel, shear key) and soil strata in **$<2\text{ ms}$** without external meshing binaries like Gmsh.
- **60 FPS Real-Time Parameter Sliders:** Dynamically morph geometry, soil friction angles, water depth, and PGA with instant visual and numerical feedback.
- **Mononobe-Okabe Dynamic Earth Pressure:** Resolves static Coulomb vs. dynamic active increment ($\Delta K_{ae}$) with Seed & Whitman height partitioning.
- **Global Stability Factors of Safety:**
  - $FS_{\text{sliding}}$ (sliding along base slab)
  - $FS_{\text{overturning}}$ (tipping around toe)
  - $FS_{\text{bearing}}$ (subgrade contact pressure & eccentricity)
- **Structural Demands & Cracking:** Calculates maximum bending moment $M_{\max}$, shear force $V_{\max}$, and tensile stress at the stem base junction.
- **Dynamic Earthquake Waveforms:**
  - Synthetic Ricker wavelets
  - Harmonic frequency sweeps (1–8 Hz chirps)
  - Newmark sliding block double-integration for cumulative permanent displacement $u(t)$
  - Standard PEER/COSMOS `.AT2` strong-motion file parser
- **Timeline Playhead:** Scrubber bar and dynamic play/pause controls to simulate wall shaking and deformation pulsation.
- **1-Click 3D Mesh Export:** Export deformed and stressed meshes to `.vtk` for external post-processing in ParaView.

---

## 100% Free & Open-Source Stack

All dependencies are free, run locally offline, and carry permissive licenses:

| Layer | Tool | License | Purpose |
| :--- | :--- | :--- | :--- |
| **GUI** | `PySide6` | LGPLv3 | Native desktop controls & dockable panels |
| **3D Rendering** | `PyVista` + `pyvistaqt` | MIT | Scientific 3D viewport, stress heatmaps, mesh warping |
| **2D Charts** | `PyQtGraph` | MIT | 60 FPS seismic waveform and displacement curves |
| **Math & Meshing** | `NumPy` + `SciPy` | BSD-3 | Mononobe-Okabe solver, Newmark integration, hex mesher |
| **Deep FEA Solver** | `KratosMultiphysics` + `KratosGeoMechanics` | BSD-4 | Multi-threaded dynamic Soil-Structure Interaction & pore-water FEA |
| **Data Exchange** | `meshio` + `h5py` | MIT / BSD-3 | 3D mesh and time-history export/caching |

---

## Quick Start

### 1. Installation

Activate your virtual environment and install dependencies:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install orang3D in editable mode
pip install -e .
```

### 2. Launch the Application

```bash
python main.py
# or via console entry point
orang3d
```

---

## 📦 Building Standalone Executables (Windows & Linux)

Anyone can clone this repository and compile a zero-dependency, standalone binary that runs without Python.

### 🐧 On Linux (Ubuntu / Debian / Fedora / Arch)

```bash
# 1. Clone repository
git clone https://github.com/dibs/orang3d.git
cd orang3d

# 2. Install Linux graphics & system libraries (Ubuntu/Debian)
sudo apt-get update && sudo apt-get install -y libgl1-mesa-glx libegl1-mesa

# 3. Create virtual environment and install packaging tools
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pyinstaller build pillow

# 4. Run automated Linux build script
./scripts/build_linux.sh

# 5. Run the standalone binary!
./dist/orang3d/orang3d
```
*Distribution package generated:* `dist/orang3d-linux-x86_64.tar.gz`

---

### 🪟 On Windows (Windows 10 / 11 64-bit)

Open **Command Prompt (`cmd.exe`)** or **PowerShell**:

```cmd
:: 1. Clone repository
git clone https://github.com/dibs/orang3d.git
cd orang3d

:: 2. Create virtual environment and activate
python -m venv .venv
.venv\Scripts\activate

:: 3. Install dependencies and packaging tools
pip install -r requirements.txt pyinstaller build pillow

:: 4. Run automated Windows build script
scripts\build_windows.bat

:: 5. Run the standalone executable!
dist\orang3d\orang3d.exe
```
*Distribution package generated:* `dist\orang3d-windows-x64.zip`

For advanced options (single-file `.exe`, Inno Setup installer, custom icons, GitHub Actions pre-built artifacts), see the **[Packaging & Export Guide](file:///home/avisheks/Documents/dibs/orang3d/docs/PACKAGING_AND_EXPORT_GUIDE.md)**.

---

## Documentation & Simulation Guide

For an in-depth, step-by-step tutorial on performing geotechnical and seismic simulations, consult:
- **[Comprehensive Simulation Guide](file:///home/avisheks/Documents/dibs/orang3d/docs/SIMULATION_GUIDE.md)**: Detailed workflows for static cantilever sizing, flooding/liquefaction, Newmark dynamic earthquake analysis, Kratos continuum SSI finite element analysis, and ACI 318 structural design.
- **[Packaging & Export Guide](file:///home/avisheks/Documents/dibs/orang3d/docs/PACKAGING_AND_EXPORT_GUIDE.md)**: Zero-to-hero instructions for compiling standalone `.exe` and Linux binaries.
- **[Developer & Architecture Sitemap](file:///home/avisheks/Documents/dibs/orang3d/aidocs/INDEX.md)**: Codebase layout, component navigation, and technical references.
- **[10-Phase Development Plan](file:///home/avisheks/Documents/dibs/orang3d/docs/DEVELOPMENT_PLAN.md)**: Architectural specifications and test benchmarks.

---

## Project Structure

```
orang3d/
├── pyproject.toml              # Project metadata and editable install config
├── requirements.txt            # Dependency specification
├── README.md                   # Documentation
├── main.py                     # Root executable script
└── src/
    └── orang3d/
        ├── __init__.py
        ├── config.py           # Colors, themes, engineering thresholds
        ├── main.py             # Application launcher
        ├── models/
        │   ├── __init__.py
        │   └── wall_params.py  # Geometry, Soil, Seismic, Analysis dataclasses
        ├── mesher/
        │   ├── __init__.py
        │   └── hex_mesher.py   # Pure NumPy 3D hexahedral wall & soil mesher
        ├── physics/
        │   ├── __init__.py
        │   ├── mononobe_okabe.py # Dynamic earth pressure & water thrust
        │   └── stability.py    # Sliding, overturning, bearing, stem stress
        ├── signals/
        │   ├── __init__.py
        │   ├── synthetic.py    # Ricker wavelet, chirp sweep, Newmark solver
        │   └── at2_parser.py   # PEER/COSMOS .AT2 earthquake record parser
        └── gui/
            ├── __init__.py
            ├── main_window.py  # Primary window with toolbars & dock splitters
            ├── viewport_3d.py  # PyVistaQt 3D viewport widget
            ├── charts_2d.py    # PyQtGraph 2D waveform dashboard
            └── panels/
                ├── __init__.py
                ├── geometry_panel.py # Wall dimensions sliders
                ├── soil_panel.py     # Geotechnical soil parameters
                └── seismic_panel.py  # Earthquake intensity & disaster triggers
```
