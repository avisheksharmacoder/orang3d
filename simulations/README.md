# orang3D Standalone Engineering Simulation Suite

Welcome to the **orang3D Standalone Simulation Suite**. This directory contains 12 production-grade, verifiable Python simulation scripts that model the complete range of geotechnical and structural phenomena available in orang3D.

All simulations can be run **directly from the terminal** without opening the graphical user interface. Every script is self-contained, parameterized with module-level uppercase `CONSTANTS`, thoroughly commented with classical literature references, and includes self-checking assertions against published benchmarks ($\le 0.5\%$ error tolerance).

---

## Simulation Directory Index

| Script File | Simulation Title | Governing Codes & Benchmark Literature |
| :--- | :--- | :--- |
| [`01_static_cantilever_stability.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/01_static_cantilever_stability.py) | Static Cantilever Stability & Coulomb Validation | Das (2019) Example 13.7, Coulomb (1776), IS 14458 |
| [`02_hydrodynamic_flooding_liquefaction.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/02_hydrodynamic_flooding_liquefaction.py) | Hydrodynamic Flooding, Seepage & Liquefaction | Westergaard (1933), Seed & Idriss (1971), IS 1893:2016 |
| [`03_dynamic_earthquake_newmark_sliding.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/03_dynamic_earthquake_newmark_sliding.py) | Dynamic Earthquake & Newmark Sliding Block | Newmark (1965), Jibson (2007), Eurocode 8 |
| [`04_curved_shell_piles_struts_arching.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/04_curved_shell_piles_struts_arching.py) | Curved Shell & Piled Wall Arching Mechanics | Handy (1985), Terzaghi (1943), CIRIA C760 |
| [`05_opensees_2d_bnwf_staged_pushover.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/05_opensees_2d_bnwf_staged_pushover.py) | OpenSees 2D BNWF Staged Excavation & Pushover | Reese & Matlock (1956), API RP 2A, OpenSeesPy |
| [`06_continuum_3d_nonlinear_fea.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/06_continuum_3d_nonlinear_fea.py) | 3D Continuum Nonlinear Soil-Structure FEA | Kratos GeoMechanics 10.4.4, Mohr-Coulomb Patch Test |
| [`07_architectural_surcharge_stepped_wall.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/07_architectural_surcharge_stepped_wall.py) | Multi-Tier Stepped Wall & Complex Surcharges | Terzaghi-Spangler (1938), Boussinesq, AASHTO LRFD |
| [`08_hill_slope_terrain_topographic_amplification.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/08_hill_slope_terrain_topographic_amplification.py) | Hill-Slope Topography & Passive Wedge Reduction | Eurocode 8 Part 5 ($S_T$), Caquot-Kérisel, IS 1893 |
| [`09_multi_code_regulatory_audit.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/09_multi_code_regulatory_audit.py) | Multi-Code Regulatory Audit & Stress Check | IS 456 / IS 14458, Eurocode 7/8, AASHTO, ACI 318-19 |
| [`10_pinn_surrogate_monte_carlo_fragility.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/10_pinn_surrogate_monte_carlo_fragility.py) | PINN Surrogate, Latin Hypercube & Fragility | Raissi et al. (2019), HAZUS MH, Cornell (1968) |
| [`11_soil_lab_calibration_swcc_infiltration.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/11_soil_lab_calibration_swcc_infiltration.py) | Soil Lab Calibration, SWCC & Rainstorm Infiltration | Darendeli (2001), Van Genuchten (1980), Green-Ampt |
| [`12_sizing_advisor_sensitivity_sweep.py`](file:///home/avisheks/Documents/dibs/orang3d/simulations/12_sizing_advisor_sensitivity_sweep.py) | Real-Time Sizing Advisor & Parametric Sensitivity | Terzaghi (1996), ACI 318-19, IS 14458 Section 11 |

---

## Quick Start: Running Simulations

### Prerequisites
Make sure your Python environment has the project dependencies installed (including OpenSeesPy, Kratos GeoMechanics, NumPy, SciPy, and PySide6).

```bash
cd /home/avisheks/Documents/dibs/orang3d
source .venv/bin/activate
```

### Running the Entire Verification Suite
To execute all 12 simulations in automated sequence and generate a comprehensive verification scorecard:

```bash
PYTHONPATH=src .venv/bin/python3 simulations/run_all_simulations.py
```

### Running Individual Simulations
Each simulation can be run individually. For example:

```bash
# 1. Static Cantilever Stability (Das 2019 Example 13.7)
PYTHONPATH=src .venv/bin/python3 simulations/01_static_cantilever_stability.py

# 3. Dynamic Earthquake & Newmark Sliding Block
PYTHONPATH=src .venv/bin/python3 simulations/03_dynamic_earthquake_newmark_sliding.py

# 5. OpenSees 2D Staged Excavation & Pushover
PYTHONPATH=src .venv/bin/python3 simulations/05_opensees_2d_bnwf_staged_pushover.py

# 6. 3D Continuum Nonlinear Finite Element Analysis
PYTHONPATH=src .venv/bin/python3 simulations/06_continuum_3d_nonlinear_fea.py

# 10. Physics-Informed Neural Network (PINN) & Latin Hypercube Fragility
PYTHONPATH=src .venv/bin/python3 simulations/10_pinn_surrogate_monte_carlo_fragility.py

# 12. Real-Time Sizing Advisor & Parametric Sensitivity Sweep
PYTHONPATH=src .venv/bin/python3 simulations/12_sizing_advisor_sensitivity_sweep.py
```

---

## Modifying Simulation Parameters (`CONSTANTS`)

Every script defines its physical parameters at the top of the file in uppercase `CONSTANTS`. There are **no hardcoded magic numbers** buried inside calculation loops.

For example, to simulate a taller wall or different earthquake intensity in `01_static_cantilever_stability.py`:

```python
# --- Wall Geometry ---
STEM_HEIGHT_M: float = 6.00          # Change to your wall height
STEM_THICKNESS_TOP_M: float = 0.30
STEM_THICKNESS_BASE_M: float = 0.70
BASE_SLAB_THICKNESS_M: float = 0.70
TOE_LENGTH_M: float = 0.90
HEEL_LENGTH_M: float = 1.90

# --- Seismic Demands ---
SEISMIC_PGA_HORIZONTAL_G: float = 0.10  # Change to your design PGA
SEISMIC_PGA_VERTICAL_G: float = 0.05
```

---

## Code Quality & Architecture

- **True Physics**: All calculations use verified governing equations (Mononobe-Okabe, Westergaard, Newmark double integration, Boussinesq stress distribution, Van Genuchten SWCC, Green-Ampt infiltration, Darendeli backbone curves).
- **Standards Compliant**: Direct cross-checks against IS 456, IS 1893, IS 14458, Eurocode 7, Eurocode 8, AASHTO LRFD, and ACI 318-19.
- **Headless Execution**: Compatible with headless continuous integration (CI) servers (`QT_QPA_PLATFORM=offscreen`).
- **Zero Drift Assertion**: Built-in verification asserts that numerical results converge within $0.5\%$ error relative to closed-form classical benchmarks.

