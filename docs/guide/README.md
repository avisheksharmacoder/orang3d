# orang3D Simulation Master Guide & Verification Curriculum

Welcome to the **orang3D Simulation Guide Catalog**. This directory contains step-by-step, verifiable simulation walk-throughs designed for practicing geotechnical engineers, structural designers, researchers, and civil engineering students.

Every simulation documented below is reproducible directly through the `orang3D` graphical user interface (GUI) and cross-verified against peer-reviewed geotechnical benchmarks, classical textbooks (Das, Bowles, Kramer), OpenSeesPy / Kratos GeoMechanics FEA engines, and multi-code design standards (IS 456/2911, Eurocode 7/8, AASHTO LRFD, and ACI 318).

> [!TIP]
> **Complete Publication-Ready PDF Available:** You can view and download the formatted 9-page PDF catalog containing all 12 simulations and their full 2-paragraph theoretical & numerical explanations directly at [orang3d_simulations_guide.pdf](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/orang3d_simulations_guide.pdf).

---

## Simulation Catalog Overview

```
docs/guide/
├── 01_static_cantilever_stability.md
├── 02_hydrodynamic_flooding_liquefaction.md
├── 03_dynamic_earthquake_newmark_sliding.md
├── 04_curved_shell_piles_struts_arching.md
├── 05_opensees_2d_bnwf_staged_pushover.md
├── 06_continuum_3d_nonlinear_fea.md
├── 07_architectural_surcharge_stepped_wall.md
├── 08_hill_slope_terrain_topographic_amplification.md
├── 09_multi_code_regulatory_audit.md
├── 10_pinn_surrogate_monte_carlo_fragility.md
├── 11_soil_lab_calibration_swcc_infiltration.md
└── 12_sizing_advisor_sensitivity_sweep.md
```

---

## Master Simulation Directory

| # | Simulation Title | Physics & Computational Core | Benchmark Reference | Target Code / Verification | Guide Link |
| :-: | :--- | :--- | :--- | :--- | :--- |
| **01** | **Static Cantilever Wall Sizing & Stability** | Rankine/Coulomb Earth Pressure, Sliding, Overturning, Meyerhof Bearing, Base Tension Check | Das (2016) *Principles of Foundation Engineering*, Ex. 13.7 | IS 456 / IS 1904 ($FS_s \ge 1.50, FS_o \ge 2.00$) | [01_static_cantilever_stability.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/01_static_cantilever_stability.md) |
| **02** | **Hydrodynamic Flooding & Liquefaction Triggering** | Hydrostatic + Seepage Uplift, Westergaard Dynamic Water Pressure, Seed-Idriss Cyclic Stress Ratio ($CSR$), Pore Pressure Ratio ($r_u$) | Seed & Idriss (1971), Westergaard (1933) | Eurocode 7 / IS 1893 Part 1 ($r_u \in [0.0, 0.70]$) | [02_hydrodynamic_flooding_liquefaction.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/02_hydrodynamic_flooding_liquefaction.md) |
| **03** | **Dynamic Earthquake Shaking & Newmark Sliding** | Mononobe-Okabe $K_{ae}$, Seed-Whitman Dynamic Inertia, Newmark Double-Integration Sliding Block, Yield Acceleration $k_y$ | Kramer (1996) *Geotechnical Earthquake Engineering*, NHERI SIMCenter | PEER NGA-West AT2 Ground Motions ($u_p \le 5.0\text{ cm}$) | [03_dynamic_earthquake_newmark_sliding.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/03_dynamic_earthquake_newmark_sliding.md) |
| **04** | **Curved Shell Wall with Struts & Piles** | Horizontal Soil Arching Transfer ($\eta_{\text{arch}}$), Raking Struts with Prestress Jacks, Bored Piles ($p\text{-}y$ Winkler Springs) | Bowles (1996) *Foundation Analysis and Design*, Sec. 12-7 | IS 2911 / Eurocode 3 (Arching stress relief $25\%\text{--}40\%$) | [04_curved_shell_piles_struts_arching.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/04_curved_shell_piles_struts_arching.md) |
| **05** | **OpenSeesPy 2D BNWF Staged Pushover Analysis** | Beam-on-Nonlinear-Winkler-Foundation, 4-Stage Excavation, Elastic-Plastic Gap Springs (`PySimple1`), Lateral Pushover | OpenSeesPy FEA Engine, Mazzoni et al. (2006) | Pushover capacity curve, plastic hinge formation | [05_opensees_2d_bnwf_staged_pushover.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/05_opensees_2d_bnwf_staged_pushover.md) |
| **06** | **Continuum 3D Non-Linear Soil-Structure FEA** | 3D Brick Hexahedral Solid Elements (`stdBrick` / `SSPbrick`), Mohr-Coulomb Soil, Shell Elements, Lysmer Viscous Absorbing Boundaries | OpenSeesPy 3D / Kratos Multiphysics 10.4.4 GeoMechanics | 3D corner arching effects, wave dissipation | [06_continuum_3d_nonlinear_fea.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/06_continuum_3d_nonlinear_fea.md) |
| **07** | **Architectural Surcharges & Stepped Wall Alignment** | Elastic Boussinesq Point/Strip/Footing Stress Distribution, Stepped Terraced Wall Elevations, Variable Cross-Sections | Terzaghi (1943) *Theoretical Soil Mechanics*, Poulos & Davis | Lateral surcharge thrust $\Delta P_q$, tier interactions | [07_architectural_surcharge_stepped_wall.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/07_architectural_surcharge_stepped_wall.md) |
| **08** | **Hill-Slope DEM Terrain & Topographic Amplification** | Digital Elevation Model Import (.asc/.obj/.tif), Local Slope Extraction ($\beta$), Topographic Shaking Amplification ($S_T$) | Eurocode 8 Part 5 Clause 4.1.4, IS 1893 Clause 6.4.4 | $S_T = 1.0\text{--}1.40$, Draped 3D contours | [08_hill_slope_terrain_topographic_amplification.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/08_hill_slope_terrain_topographic_amplification.md) |
| **09** | **Live Multi-Code Regulatory Compliance Audit** | Multi-Standard Cross-Check: IS 456/2911/800 vs. Eurocode 7/8 vs. AASHTO LRFD vs. ACI 318-19 | National & International Building Codes | Real-time code switcher, pass/fail badge matrix | [09_multi_code_regulatory_audit.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/09_multi_code_regulatory_audit.md) |
| **10** | **Physics-Informed Neural Network (PINN) & Fragility** | Real-Time PINN Neural Surrogate ($<5\text{ ms}$), Latin Hypercube Sampling (LHS) Monte Carlo, Reliability Index ($\beta$), HAZUS Fragility Curves | Raissi et al. (2019), HAZUS-MH Earthquake Model | Limit state probabilities $P_f$, damage state curves | [10_pinn_surrogate_monte_carlo_fragility.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/10_pinn_surrogate_monte_carlo_fragility.md) |
| **11** | **Soil Lab CSV Calibration, SWCC & Infiltration** | CSV Triaxial/Resonant Column Import, Darendeli (2001) $G/G_{\max} - \gamma$ Calibration, Van Genuchten SWCC, Green-Ampt Rain Infiltration | Darendeli (2001), Van Genuchten (1980), Green & Ampt (1911) | Calibrated soil parameters, rainstorm suction loss | [11_soil_lab_calibration_swcc_infiltration.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/11_soil_lab_calibration_swcc_infiltration.md) |
| **12** | **Parametric Sensitivity Sweep & Sizing Advisor** | Monotonic Analytical Parameter Sweep ($<50\text{ ms}$), Multi-Limit Directed Optimization Engine, 1-Click Geometric Remediation | Classical Geotechnical Optimization | Instant safe geometry application ($FS_s, FS_o, FS_b, \sigma_t$) | [12_sizing_advisor_sensitivity_sweep.md](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/12_sizing_advisor_sensitivity_sweep.md) |

---

## Recommended Learning Pathways

### Pathway A: Classical Geotechnical Fundamentals
*Target Audience: Civil Engineering Undergraduates & Foundation Designers*
1. **[Simulation 01](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/01_static_cantilever_stability.md):** Master static equilibrium, Coulomb/Rankine wedge pressures, base eccentricity, and Meyerhof bearing stress.
2. **[Simulation 07](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/07_architectural_surcharge_stepped_wall.md):** Add adjacent building footings and stepped terrace geometry using Boussinesq stress tensors.
3. **[Simulation 12](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/12_sizing_advisor_sensitivity_sweep.md):** Run parametric sweeps on soil friction $\phi$ and utilize the Sizing Advisor to resolve limit-state failures with 1 click.

### Pathway B: Seismic Engineering & Geohazard Mitigation
*Target Audience: Earthquake Engineers & Infrastructure Consultants*
1. **[Simulation 03](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/03_dynamic_earthquake_newmark_sliding.md):** Apply PEER earthquake records, evaluate Mononobe-Okabe $K_{ae}$, and calculate Newmark permanent sliding displacements.
2. **[Simulation 02](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/02_hydrodynamic_flooding_liquefaction.md):** Combine dynamic shaking with rising groundwater, Westergaard water thrust, and cyclic liquefaction triggering ($r_u$).
3. **[Simulation 08](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/08_hill_slope_terrain_topographic_amplification.md):** Import hill-slope DEM topography to capture ridge amplification ($S_T$) per Eurocode 8 / IS 1893.
4. **[Simulation 10](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/10_pinn_surrogate_monte_carlo_fragility.md):** Perform Latin Hypercube Sampling Monte Carlo sweeps to generate HAZUS seismic fragility curves.

### Pathway C: Advanced Computational Geotechnics & Soil-Structure Interaction
*Target Audience: PhD Researchers & Numerical Modelers*
1. **[Simulation 04](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/04_curved_shell_piles_struts_arching.md):** Model horizontal soil arching in cylindrical shells, pre-stressed raking struts, and bored pile foundation groups.
2. **[Simulation 05](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/05_opensees_2d_bnwf_staged_pushover.md):** Run OpenSeesPy 2D BNWF multi-stage excavation and lateral pushover analysis.
3. **[Simulation 06](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/06_continuum_3d_nonlinear_fea.md):** Execute full 3D continuum FEA with elastoplastic soil and Lysmer non-reflecting boundaries.
4. **[Simulation 11](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/11_soil_lab_calibration_swcc_infiltration.md):** Calibrate non-linear soil degradation curves ($G/G_{\max}$) and SWCC unsaturated suction profiles from lab CSV test data.
5. **[Simulation 09](file:///home/avisheks/Documents/dibs/orang3d/docs/guide/09_multi_code_regulatory_audit.md):** Validate design adequacy against IS, Eurocode, AASHTO, and ACI design provisions simultaneously.

---

## Running the Automated Test Suite

Every calculation and algorithm documented across these 12 simulation guides is covered by automated unit, integration, and UI tests in `tests/`.

To run the complete test suite:

```bash
# Run tests headlessly using the virtual environment
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v
```

To run simulation-specific verification tests:
```bash
# Verify static, seismic, arching & presets (Simulations 01, 03, 04, 12)
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_pedagogy_and_presets.py tests/test_benchmarks.py -v

# Verify OpenSees 2D/3D & Kratos FEA (Simulations 05, 06)
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_bnwf_opensees.py tests/test_continuum_fea_3d.py tests/test_kratos_solver.py -v

# Verify Topography, DEM & Sizing Advisor (Simulations 08, 12)
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_terrain_studio_ui.py tests/test_terrain_topography.py -v

# Verify Lab Calibration, Infiltration & SWCC (Simulation 11)
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_cyclic_soil.py -v

# Verify Multi-Code Compliance Auditing (Simulation 09)
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_multi_code_and_units.py tests/test_is_design_codes.py -v

# Verify PINN Surrogate & Monte Carlo Fragility (Simulation 10)
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_surrogates_and_uq.py tests/test_advanced_soil_uq_ui.py -v
```

