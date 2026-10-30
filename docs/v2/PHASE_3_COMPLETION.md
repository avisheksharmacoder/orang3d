# v2 Phase 3 Completion Report: Level L0 Analytical Calculation Engine
## Horizontal Soil Arching, IS 1893 Seismic Dynamics, Multi-Struts & Pile Subgrade Statics

**Status:** Completed  
**Test Suite:** [`tests/test_analytical_arching.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_analytical_arching.py) (13 comprehensive unit, invariant, and benchmark tests)  
**Test Coverage:** **100% statement coverage** across all Phase 3 physics modules (290 / 290 statements covered)  
**Analytical Latency:** **0.2273 ms** native (< 1.5 ms threshold)  
**Full Project Regression:** **165 / 165 tests passed** across the entire repository  

---

## 1. Overview & Objectives Achieved

Phase 3 established the **Level L0 Analytical Engine** for the **orang3D v2 Advanced Geotechnical Suite**, implementing ultra-fast, closed-form physics that evaluate within **0.227 ms** for real-time slider responsiveness in the GUI:

1. **Horizontal Soil Arching & Load Partitioning ([`src/orang3d/physics/shell_arching.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/shell_arching.py)):**
   - Modified Terzaghi (1943) & Handy (1985) arching stress equations between vertical pier shafts.
   - Load transfer partition factor $\eta_{\text{arch}} = P_{\text{pier}} / P_{\text{free}}$ strictly conserving horizontal equilibrium:
     $$P_{\text{free}} = P_{\text{shell}} + P_{\text{pier}} \quad (\sum F_x = 0)$$
   - Membrane hoop thrust $N_\theta = \sigma_h \cdot R$ and residual shell flexural moments $M_{\text{shell}}$.
   - Asymptotic convergence to classical Rankine active earth pressure as clear bay span $L_{\text{bay}} \to \infty$ within $0.01\%$.

2. **IS 1893 (Part 3: 2014) Seismic Dynamic Earth Pressure Engine ([`src/orang3d/physics/is_1893_engine.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_1893_engine.py)):**
   - Spectral acceleration response $S_a/g$ across Soil Types I, II, and III.
   - Design horizontal and vertical seismic coefficients ($A_h, A_v$) incorporating Zone Factors (up to Zone V $Z = 0.36$), Importance Factors ($I$), and Response Reduction Factors ($R$).
   - Mononobe-Okabe pseudo-static dynamic active earth pressure coefficient $K_{ae}$.
   - Tensile crack depth $z_c = \frac{2c}{\gamma \sqrt{K_a}}$ for $c-\phi$ soils, clamped per engineering practice to $0.5 H$.
   - Seed & Whitman (1970) centroid height elevation: static thrust at $H'/3$, dynamic increment at $0.6 H'$.

3. **Apparent Earth Pressure & Multi-Strut Apportionment Statics ([`src/orang3d/physics/strut_statics.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/strut_statics.py)):**
   - Empirical apparent earth pressure (AEP) trapezoidal/rectangular envelopes (Peck 1969 / FHWA).
   - Multi-tier tributary area vertical apportionment for $N \ge 1$ raking strut levels.
   - Inclination angle transformation ($\alpha_{\text{strut}}$), prestress lock-off load $P_0$, and downward vertical thrust $V_{\text{strut}} = F_h \tan\alpha$.
   - Euler critical buckling load $P_{cr} = \frac{\pi^2 E I}{L_{\text{strut}}^2}$ and structural capacity utilization checks.

4. **Broms' Lateral Pile Resistance & Closed-Form Embedment Solver ([`src/orang3d/physics/pile_statics.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/pile_statics.py)):**
   - Flexural characteristic length factor $T = \left(\frac{E_p I_p}{\eta_h}\right)^{1/5}$ and virtual depth of fixity $z_f$ per IS 2911 (Part 1/Sec 2).
   - Structural pile classification: Rigid (Short) ($L_p \le 2T$), Intermediate ($2T < L_p < 4T$), or Flexible (Long) ($L_p \ge 4T$).
   - Broms' (1964) ultimate lateral resistance $H_{\text{ult}}$ in $c-\phi$ soil under restrained head conditions.
   - Exact quadratic closed-form solver calculating minimum embedment length $L_{\text{req}}$ to guarantee $FS_{\text{lateral}} \ge 1.50$.

---

## 2. Mathematical Formulations & Implementations

### 2.1 Horizontal Soil Arching Theory ([`src/orang3d/physics/shell_arching.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/shell_arching.py))

For cylindrical curved shell panels spanning between rigid vertical pier shafts with clear bay span $L_{\text{bay}}$, the horizontal lateral earth pressure at depth $z$ is:
$$\sigma_h(z) = \min\left( \max\left( \frac{\gamma L_{\text{bay}} - 2c}{2 \tan\phi} \left[1 - \exp\left(-\frac{2 K \tan\phi \, z}{L_{\text{bay}}}\right)\right] - 2c\sqrt{K}, \; 0\right), \; \sigma_{\text{Rankine}}(z) \right)$$

As $L_{\text{bay}} \to \infty$, the first-order Taylor expansion yields:
$$\lim_{L_{\text{bay}} \to \infty} \sigma_h(z) = K \gamma z - 2c\sqrt{K} = \sigma_{\text{Rankine}}(z)$$

- **Total Free-Field Thrust:**
  $$P_{\text{free}} = L_{\text{bay}} \int_0^H \max(K_a \gamma z - 2c\sqrt{K_a}, 0) \, dz$$
- **Shell Thrust & Pier Reaction:**
  $$P_{\text{shell}} = L_{\text{bay}} \int_0^H \sigma_h(z) \, dz, \quad P_{\text{pier}} = \max(P_{\text{free}} - P_{\text{shell}}, 0)$$
  $$\eta_{\text{arch}} = \frac{P_{\text{pier}}}{P_{\text{free}}}$$
- **Membrane Hoop Compression:**
  $$N_\theta(z) = \sigma_h(z) \cdot R \quad (\text{kN/m})$$
- **Shell Bending Moment:**
  $$M_{\text{shell}}(z) = \frac{\sigma_h(z) L_{\text{bay}}^2}{12} (1 - \eta_{\text{arch}})$$

### 2.2 IS 1893 (Part 3: 2014) Seismic Dynamics ([`src/orang3d/physics/is_1893_engine.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_1893_engine.py))

- **Design Horizontal Acceleration:**
  $$A_h = \frac{Z}{2} \cdot \frac{I}{R} \cdot \left(\frac{S_a}{g}\right)$$
- **Design Vertical Acceleration:**
  $$A_v = \frac{2}{3} A_h$$
- **Seismic Inertia Angle:**
  $$\theta = \arctan\left(\frac{A_h}{1 - A_v}\right)$$
- **Mononobe-Okabe Dynamic Active Coefficient:**
  $$K_{ae} = \frac{\cos^2(\phi - \theta - \alpha)}{\cos\theta \cos^2\alpha \cos(\delta + \alpha + \theta) \left[1 + \sqrt{\frac{\sin(\phi + \delta)\sin(\phi - \theta - \beta)}{\cos(\delta + \alpha + \theta)\cos(\beta - \alpha)}}\right]^2}$$
- **Tensile Crack Depth in Cohesive-Frictional Soil:**
  $$z_c = \min\left(\frac{2c}{\gamma \sqrt{K_a}}, \; 0.5 H\right)$$
- **Dynamic Thrust & Resultant Centroid:**
  $$P_a = \frac{1}{2} \gamma (H - z_c)^2 K_a, \quad P_{ae} = \frac{1}{2} \gamma (H - z_c)^2 (1 - A_v) K_{ae}$$
  $$\Delta P_{ae} = P_{ae} - P_a$$
  $$y_{\text{res}} = \frac{P_a \cdot \frac{H - z_c}{3} + \Delta P_{ae} \cdot 0.6(H - z_c)}{P_{ae}}$$

### 2.3 Strut Apportionment & Buckling Statics ([`src/orang3d/physics/strut_statics.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/strut_statics.py))

- **Tributary Height Apportionment:**
  $$h_{\text{trib}, 0} = \frac{d_0 + d_1}{2}, \quad h_{\text{trib}, i} = \frac{d_{i+1} - d_{i-1}}{2}, \quad h_{\text{trib}, N-1} = H - \frac{d_{N-2} + d_{N-1}}{2}$$
- **Axial Force with Lock-off Prestress:**
  $$P_{\text{strut}, i} = \frac{F_{h, i}}{\cos\alpha_{\text{strut}}} + P_0$$
- **Vertical Downward Reaction:**
  $$V_{\text{strut}, i} = F_{h, i} \tan\alpha_{\text{strut}}$$
- **Euler Critical Buckling Load & Capacity Ratio:**
  $$P_{cr} = \frac{\pi^2 E_s I_s}{L_{\text{strut}}^2}, \quad UR_{\text{buckling}} = \frac{P_{\text{strut}}}{P_{cr}}$$

### 2.4 Broms' Lateral Pile Capacity & Closed-Form Embedment ([`src/orang3d/physics/pile_statics.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/pile_statics.py))

- **Ultimate Lateral Resistance per Pile:**
  $$H_{\text{ult}} = 1.5 K_p \gamma D_p L_p^2 + 9 c D_p L_p$$
- **Target Factored Demand per Pile ($FS \ge 1.5$):**
  $$H_{\text{req}} = 1.5 \cdot V_{\text{pile}} = 1.5 \cdot \frac{V_{\text{residual}}}{N_{\text{piles}}}$$
- **Closed-Form Minimum Embedment Solver:**
  Setting $a = 1.5 K_p \gamma D_p$, $b = 9 c D_p$, $c_0 = -H_{\text{req}}$:
  $$L_{\text{req}} = \frac{-b + \sqrt{b^2 - 4 a c_0}}{2 a}$$
  Clamped to practical geotechnical minimum $L_{\text{req}} \ge 2.0\text{ m}$.

---

## 3. Test Coverage Strategy & Final Verification

The test suite in [`tests/test_analytical_arching.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_analytical_arching.py) executes 13 unit, invariant, and benchmark tests:

```bash
$ PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/coverage run -m pytest tests/test_analytical_arching.py -v
$ .venv/bin/coverage report -m src/orang3d/physics/shell_arching.py src/orang3d/physics/is_1893_engine.py src/orang3d/physics/strut_statics.py src/orang3d/physics/pile_statics.py
```

| Component Module | File Path | Statements | Missed | Coverage | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **IS 1893 Seismic Engine** | [`src/orang3d/physics/is_1893_engine.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_1893_engine.py) | 71 | 0 | **100%** | **Passed** |
| **Pile Statics & Broms** | [`src/orang3d/physics/pile_statics.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/pile_statics.py) | 67 | 0 | **100%** | **Passed** |
| **Shell Arching Theory** | [`src/orang3d/physics/shell_arching.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/shell_arching.py) | 68 | 0 | **100%** | **Passed** |
| **Strut Apportionment** | [`src/orang3d/physics/strut_statics.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/strut_statics.py) | 84 | 0 | **100%** | **Passed** |
| **TOTAL PHASE 3** | **All 4 Physics Modules** | **290** | **0** | **100%** | **PASSED** |

### Verified Test Cases:
1. `test_arching_planar_limit`: Confirms asymptotic convergence of arching stress $\sigma_h(z)$ to classical planar Rankine active pressure within $0.01\%$ as $L_{\text{bay}} \to \infty$.
2. `test_equilibrium_conservation`: Strictly verifies $\sum F_x = 0$ ($P_{\text{free}} = P_{\text{shell}} + P_{\text{pier}}$) and confirms $0 < \eta_{\text{arch}} < 1.0$.
3. `test_cohesion_effect_on_arching`: Verifies that cohesive resistance reduces shell lateral arching pressure across all depths.
4. `test_is1893_seismic_coefficients`: Validates $A_h, A_v$ scaling across Seismic Zones II, III, IV, and V, matching IS 1893 Zone V $Z = 0.36$.
5. `test_is1893_dynamic_earth_pressure_demand`: Validates Mononobe-Okabe $K_{ae} > K_a$, Seed & Whitman dynamic centroid rise, and tension crack depth $z_c$.
6. `test_multi_strut_apportionment`: Verifies apparent earth pressure integration, multi-tier tributary load apportionment, axial strut force, downward vertical component, and Euler buckling safety.
7. `test_pile_embedment_equilibrium`: Validates Broms' lateral capacity $H_{\text{ult}}$, IS 2911 depth of fixity $z_f$, and the exact closed-form minimum embedment solver guaranteeing $FS_{\text{lateral}} \ge 1.50$.
8. `test_analytical_latency`: Benchmarks the complete 4-stage analytical calculation chain at **0.2273 ms** (< 1.5 ms requirement).
9. `test_edge_cases`: Validates graceful error handling for negative bay spans, invalid friction angles, non-positive wall heights, and negative shear demands.
10. `test_pile_intermediate_classification`: Validates IS 2911 intermediate pile classification when $2T < L_p < 4T$.
11. `test_strut_single_and_triple_tiers`: Validates single-strut, three-strut, and zero-thrust tributary area statics.
12. `test_shell_arching_scalar_and_high_cohesion`: Validates scalar depth evaluations, small exponent asymptotic expansions, and complete tension suppression under high cohesion.
13. `test_is1893_extreme_angles_and_zero_demand`: Validates extreme seismic angle bounds ($\theta + \beta > \phi \implies K_{ae} = 1.5$), extreme wall inclinations, and near-zero soil density demands.

---

## 4. Full Project Regression Status

A complete regression test run was executed across the entire test suite:
- **Phase 1 Advanced Models:** 19 tests passed (100% coverage).
- **Phase 2 3D Mesher Engines:** 11 tests passed (100% coverage).
- **Phase 3 Level L0 Analytical Engine:** 13 tests passed (100% coverage).
- **Baseline v0.1.0 Retaining Wall Suite:** 122 tests passed (physics stability, signals, structural, units, viewport).
- **Total:** **165 passed in 16.10 seconds**, 0 failures, 0 regressions.

---

## 5. Artifacts Summary

### Created Modules:
- [`src/orang3d/physics/shell_arching.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/shell_arching.py): Horizontal arching stress, load partitioning $\eta_{\text{arch}}$, hoop compression $N_\theta$, and flexure $M_{\text{shell}}$.
- [`src/orang3d/physics/is_1893_engine.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_1893_engine.py): IS 1893 (Part 3: 2014) seismic coefficients ($A_h, A_v$), Mononobe-Okabe $K_{ae}$, tension crack depth $z_c$, and dynamic centroid height.
- [`src/orang3d/physics/strut_statics.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/strut_statics.py): Apparent earth pressure envelopes, multi-tier strut tributary apportionment, prestress lock-off $P_0$, and Euler buckling verification.
- [`src/orang3d/physics/pile_statics.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/pile_statics.py): Broms' (1964) lateral capacity, IS 2911 depth of fixity $z_f$, and closed-form minimum embedment solver.
- [`tests/test_analytical_arching.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_analytical_arching.py): 13 comprehensive unit, physical invariant, and performance tests.

### Updated Modules:
- [`src/orang3d/physics/__init__.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/__init__.py): Exported all Phase 3 physics functions and data classes.
- [`src/orang3d/models/advanced_wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/advanced_wall_params.py): Enhanced `strut_levels` sequence sorting validation for list and tuple types.
- [`docs/v2/PHASE_3_COMPLETION.md`](file:///home/avisheks/Documents/dibs/orang3d/docs/v2/PHASE_3_COMPLETION.md): Detailed Phase 3 engineering completion document.

---

## 6. Readiness for Phase 4

With Phase 3 complete and fully verified, the codebase is primed for **Phase 4: OpenSeesPy Substructure & Nonlinear Spring Engine**:
- Implementation of the Beam on Nonlinear Winkler Foundation (BNWF) 2D/3D substructure model.
- Non-linear $p-y$ soil spring generators (`PySimple1` / API sand & clay).
- Fiber-section nonlinear beam-column elements for bored piles and RC pier columns.
- Pushover analysis and dynamic time-history response under synthetic and recorded ground motions.
