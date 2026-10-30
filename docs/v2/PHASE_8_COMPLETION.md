# v2 Phase 8 Completion Report: Comprehensive Indian Standards (IS Code) Member Design Engine
## IS 456 RC Shell Panels & Piers, IS 2911 Bored Pile Foundation Capacity & Fixity, IS 800 Steel Strut Compressive Buckling & Connections, and Unified Audit Engine

**Status:** Completed  
**Test Suite:** [`tests/test_is_design_codes.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_is_design_codes.py) (9 exhaustive unit, golden SP 16/Table 9c benchmarks, and failure threshold tests)  
**Test Coverage:** **99% statement coverage** across all Phase 8 modules (596 / 601 statements covered; 99% in `is_456.py`, 99% in `is_2911.py`, 99% in `is_800.py`, 98% in `audit_engine.py`)  
**Full Project Regression:** **217 / 217 tests passed** across all 22 test suites in the repository  

---

## 1. Overview & Objectives Achieved

Phase 8 implements the complete structural and geotechnical member design suite strictly conforming to the relevant Indian Standards for the multi-strut piled retaining wall system:

1. **RC Shell Panel & Pier Design Engine ([`src/orang3d/physics/is_codes/is_456.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_codes/is_456.py)):**
   - **Limit State Flexural Design (IS 456:2000 Cl. 38 & Annex G):** Solves exact quadratic strain compatibility equations for singly reinforced sections ($M_u \le M_{u, \lim}$) and sizes tension steel $A_{st}$. Computes compression reinforcement $A_{sc}$ and additional tension steel $A_{st2}$ for doubly reinforced sections ($M_u > M_{u, \lim}$), enforcing the 4% gross section maximum steel limit ($A_{st, \max} = 0.04 b D$).
   - **SP 16 Golden Design Benchmark:** Validates computed reinforcement percentage $p_t = \frac{100 A_{st}}{b d}$ against IS 456 SP 16 design charts within $< 0.5\%$ error (e.g., $M_u / (b d^2) = 2.0\text{ MPa}$ under M30/Fe 500 yields $p_t = 0.502\%$).
   - **Minimum Reinforcement Check (IS 456 Cl. 26.5.2.1):** Enforces $0.12\% b D$ for HYSD rebar (Fe 415, Fe 500, Fe 550) and $0.15\% b D$ for mild steel (Fe 250), as well as beam/pier minimums $\frac{0.85 b d}{f_y}$.
   - **Concrete Shear Design (IS 456 Cl. 40 & Table 19):** Evaluates nominal shear stress $\tau_v = \frac{V_u}{b d}$, design concrete shear capacity $\tau_c(p_t, f_{ck})$ per Table 19 analytical formulation, and maximum shear stress ceiling $\tau_{c, \max} = 0.62 \sqrt{f_{ck}}$ (Table 20). Automatically sizes 2-legged shear stirrups when $\tau_v > \tau_c$.
   - **Crack Width Limitation (IS 456 Annex F / Cl. 35.3.2):** Evaluates flexural surface crack width $w_{cr}$ incorporating concrete tension stiffening reduction $\epsilon_{stiff} = \frac{b (D - x)^2}{3 E_s A_{st} (d - x)}$; enforces $w_{cr} \le 0.20\text{ mm}$ for aggressive/earth-retaining environments and $w_{cr} \le 0.30\text{ mm}$ for mild exposures.
   - **Automated Detailing Callout Generator:** Selects standard bar diameters (10, 12, 16, 20, 25, 32 mm) and rounds spacing down to 25 mm increments, generating professional detailing strings (e.g., `"2-layer T16 @ 125 mm c/c each face"`).

2. **Bored Cast-in-Situ Pile Design Engine ([`src/orang3d/physics/is_codes/is_2911.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_codes/is_2911.py)):**
   - **Geotechnical Axial Compression Capacity (IS 2911 Part 1/Sec 2: 2010 Appendix B):** Formulates combined base end-bearing $Q_b$ and shaft skin friction $Q_s$ in $c\text{-}\phi$ soil:
     $$Q_u = Q_b + Q_s = A_p \left(c N_c + \sigma'_v N_q + 0.5 \gamma D_p N_\gamma\right) + \sum \left(\alpha c_i + K \sigma'_{vi} \tan\delta\right) A_{si}$$
     Applies overburden critical depth capping at $z_{cr} = 15 D_p$ and factor of safety $FS = 2.5$ for static combinations ($FS = 2.0$ for seismic combinations).
   - **Golden Benchmark Validation:** Verified against textbook golden benchmarks for clay piles ($Q_b = 9 c_u A_p$, $\alpha$ adhesion factor) and sand piles ($N_q, N_\gamma$ from IS 2911 Table 1).
   - **Lateral Pile Capacity & Depth of Fixity (IS 2911 Appendix C):** Computes stiffness factor $T = (E_p I_p / \eta_h)^{1/5}$ for granular soils, evaluates virtual depth of fixity $z_f = 2.0 T$ (fixed-head) or $2.2 T$ (free-head), and solves allowable lateral shear $H_{\text{safe}}$ for permissible head deflection $y_{\text{allow}} = 5\text{ mm}$.
   - **Structural Pile Rebar Cage Detailing (IS 2911 Cl. 6.11):** Enforces minimum longitudinal rebar $A_{st, \min} = 0.4\% A_g$ with $\ge 6$ circular bars, tremie-flow maximum steel limit $1.25\%$, helical binder pitch ($\le 100\text{ mm}$ in top $3 D_p$ zone, $\le 150\text{ mm}$ below), and factored structural axial compression capacity $P_{uz} = 0.40 f_{ck} A_c + 0.67 f_y A_{sc}$.

3. **Structural Steel Strut & Waler Design Engine ([`src/orang3d/physics/is_codes/is_800.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_codes/is_800.py)):**
   - **Axial Compressive Strength (IS 800:2007 Cl. 7.1.2):** Evaluates non-dimensional slenderness $\lambda = \sqrt{f_y / f_{cc}}$, imperfection factor $\alpha_b$ for Buckling Curves a, b, c, d, stress reduction factor $\chi$, and design compressive stress $f_{cd} = \chi \frac{f_y}{\gamma_{m0}}$.
   - **IS 800 Table 9(c) Cross-Check:** Matches Table 9(c) tabulated design compressive stresses across slenderness ratios $KL/r \in [20, 180]$ within $< 1.5\%$ error.
   - **Slenderness Ratio Limits (IS 800 Table 3):** Validates $KL/r \le 180$ for gravity compression members and $KL/r \le 250$ for seismic/wind compression.
   - **Seismic Tension Reversal (IS 800 Cl. 6.2):** Checks tensile yield capacity $T_{dg} = A_g f_y / \gamma_{m0}$ and net section rupture $T_{dn} = 0.9 A_{net} f_u / \gamma_{m1}$.
   - **Connection Detailing (IS 800 Section 10):** Sizes high-strength bolted connections (Grade 8.8 / 4.6 bolt shear $V_{dsb}$, bearing $V_{dpb}$) and fillet welds (throat thickness $t_t = 0.707 s$, required weld length $L_w$).
   - **Biaxial Bending & Axial Interaction (IS 800 Cl. 9.3):** Evaluates combined interaction equation $\frac{P}{P_d} + \frac{M_y}{M_{dy}} \le 1.0$.

4. **Unified Engineering Audit Engine ([`src/orang3d/physics/is_codes/audit_engine.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_codes/audit_engine.py)):**
   - Aggregates 11 distinct structural and geotechnical design checks across all retaining wall components.
   - Computes demand-to-capacity / unity ratios ($UR = \text{Demand} / \text{Capacity}$).
   - Assigns color-coded compliance status (`PASS` for $UR < 0.90$, `WARNING` for $0.90 \le UR \le 1.00$, `FAIL` for $UR > 1.00$).
   - Automatically generates structured engineering calculation audit sheets in GitHub-Flavored Markdown citing exact Indian Standard clauses.

5. **Integration & API Exports ([`src/orang3d/physics/is_codes/__init__.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_codes/__init__.py), [`src/orang3d/physics/__init__.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/__init__.py)):**
   - Exports all Phase 8 design functions, dataclasses, and the unified audit engine through `orang3d.physics.is_codes` and `orang3d.physics`.

---

## 2. Mathematical Formulations & Implementations

### 2.1 IS 456:2000 Limit State Flexural & Shear Design

#### Flexural Design
The limiting depth of the neutral axis $x_{u, \max}$ per Cl. 38.1 Note is:
$$\frac{x_{u, \max}}{d} = \begin{cases}
0.53 & \text{for Fe 250} \\
0.48 & \text{for Fe 415} \\
0.46 & \text{for Fe 500} \\
0.44 & \text{for Fe 550}
\end{cases}$$

The limiting moment of resistance for a singly reinforced section is:
$$M_{u, \lim} = 0.36 \frac{x_{u, \max}}{d} \left(1 - 0.42 \frac{x_{u, \max}}{d}\right) f_{ck} b d^2$$

For under-reinforced sections ($M_u \le M_{u, \lim}$), required tensile steel area $A_{st}$:
$$A_{st} = \frac{0.5 f_{ck}}{f_y} \left[ 1 - \sqrt{1 - \frac{4.6 M_u}{f_{ck} b d^2}} \right] b d$$

For doubly reinforced sections ($M_u > M_{u, \lim}$), excess moment $M_{u2} = M_u - M_{u, \lim}$:
$$A_{sc} = \frac{M_{u2}}{(f_{sc} - f_{cc}) (d - d')}, \quad A_{st2} = \frac{M_{u2}}{0.87 f_y (d - d')}, \quad A_{st} = A_{st, \lim} + A_{st2}$$
Subject to the maximum rebar limit: $A_{st} + A_{sc} \le 0.04 b D$.

#### Shear Capacity
Design shear strength of concrete $\tau_c$ without shear reinforcement (Table 19):
$$\tau_c = \frac{0.85 \sqrt{0.8 f_{ck}} (\sqrt{1 + 5 \beta} - 1)}{6 \beta}, \quad \beta = \frac{0.8 f_{ck}}{6.89 p_t}$$
Where $p_t = \frac{100 A_{st}}{b d}$. When nominal shear $\tau_v = \frac{V_u}{b d} > \tau_c$, stirrups are sized for $V_{us} = V_u - \tau_c b d$:
$$\frac{A_{sv}}{s_v} = \frac{V_{us}}{0.87 f_y d} \ge \frac{0.4 b}{0.87 f_y}$$

#### Flexural Crack Width
Surface crack width per Annex F:
$$w_{cr} = \frac{3 a_{cr} \epsilon_m}{1 + 2 \frac{a_{cr} - c_{\min}}{D - x}}$$
Where $a_{cr} = \sqrt{(s/2)^2 + c^2} - \phi/2$, and average strain $\epsilon_m$ includes tension stiffening:
$$\epsilon_m = \epsilon_1 - \frac{b (D - x)^2}{3 E_s A_{st} (d - x)} \ge 0$$

---

### 2.2 IS 2911:2010 Bored Cast-in-Situ Pile Design

#### Vertical Axial Load Capacity (Appendix B)
$$Q_u = Q_b + Q_s = A_p \left(c N_c + \sigma'_v N_q + 0.5 \gamma D_p N_\gamma\right) + \sum_{i=1}^n \left(\alpha c_i + K \sigma'_{vi} \tan\delta\right) A_{si}$$
$$Q_{\text{safe}} = \frac{Q_u}{FS}$$
Where:
- $A_p = \frac{\pi D_p^2}{4}$, $A_{si} = \pi D_p \Delta z_i$.
- Overburden pressure $\sigma'_v$ is capped at critical depth $z_{cr} = 15 D_p$.
- Bearing capacity factors $N_c, N_q, N_\gamma$ from IS 2911 Table 1.
- Shaft adhesion factor $\alpha$ from IS 2911 Table 2.
- Interface friction angle $\delta = 0.75 \phi$, earth pressure coefficient $K = 1.0$.
- $FS = 2.5$ for static loads, $FS = 2.0$ for seismic combinations.

#### Lateral Capacity & Fixity (Appendix C)
- Modulus of subgrade reaction stiffness factor: $T = \left(\frac{E_p I_p}{\eta_h}\right)^{1/5}$ (m).
- Virtual depth of fixity: $z_f = 2.0 T$ (fixed head) or $2.2 T$ (free head).
- Allowable lateral load for $y_{\text{allow}} = 5\text{ mm}$:
  $$H_{\text{safe}} = \frac{12 E_p I_p y_{\text{allow}}}{(z_f + e_1)^3}$$

#### Structural Detailing (Clause 6.11)
- Minimum longitudinal steel: $A_{st, \min} = 0.004 \frac{\pi D_p^2}{4}$ (minimum 6 bars).
- Maximum longitudinal steel: $1.25\%$ (tremie concrete placement constraint).
- Factored structural compression capacity: $P_{uz} = 0.40 f_{ck} A_c + 0.67 f_y A_{sc}$.

---

### 2.3 IS 800:2007 Structural Steel Strut Design

#### Compressive Strength (Clause 7.1.2)
Design compressive strength:
$$P_d = A_e \cdot f_{cd}$$
Where design compressive stress $f_{cd}$:
$$f_{cd} = \chi \frac{f_y}{\gamma_{m0}} = \frac{f_y / \gamma_{m0}}{\phi_b + \sqrt{\phi_b^2 - \lambda^2}} \le \frac{f_y}{\gamma_{m0}}$$
Where:
- Euler buckling stress: $f_{cc} = \frac{\pi^2 E}{(K L / r)^2}$.
- Non-dimensional slenderness: $\lambda = \sqrt{f_y / f_{cc}}$.
- Auxiliary parameter: $\phi_b = 0.5 [1 + \alpha_b (\lambda - 0.2) + \lambda^2]$.
- $\alpha_b = 0.49$ for Buckling Curve c (CHS/SHS tubes and built-up struts).
- Partial safety factor $\gamma_{m0} = 1.10$.

#### Slenderness Ratio Limits (Table 3)
- Gravity compression: $KL/r \le 180$.
- Seismic/wind compression: $KL/r \le 250$.

#### Tension Reversal (Clause 6.2)
$$T_{dg} = \frac{A_g f_y}{\gamma_{m0}}, \quad T_{dn} = \frac{0.9 A_{net} f_u}{\gamma_{m1}}, \quad T_d = \min(T_{dg}, T_{dn})$$

---

## 3. Test Coverage Strategy & Verification Results

The dedicated test suite [`tests/test_is_design_codes.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_is_design_codes.py) executes 9 exhaustive tests covering all Phase 8 design modules:

```bash
$ PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/coverage run -m pytest tests/test_is_design_codes.py -v
$ .venv/bin/coverage report -m src/orang3d/physics/is_codes/is_456.py src/orang3d/physics/is_codes/is_2911.py src/orang3d/physics/is_codes/is_800.py src/orang3d/physics/is_codes/audit_engine.py
```

### Coverage Results:

| Component Module | File Path | Statements | Missed | Coverage | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **IS 456 RC Design Engine** | [`is_456.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_codes/is_456.py) | 229 | 1 | **99%** | **Passed** |
| **IS 2911 Bored Pile Engine** | [`is_2911.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_codes/is_2911.py) | 151 | 1 | **99%** | **Passed** |
| **IS 800 Steel Strut Engine** | [`is_800.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_codes/is_800.py) | 136 | 1 | **99%** | **Passed** |
| **Unified Audit Engine** | [`audit_engine.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/is_codes/audit_engine.py) | 85 | 2 | **98%** | **Passed** |
| **TOTAL PHASE 8** | **All 4 Modules Combined** | **601** | **5** | **99%** | **PASSED** |

### Verified Test Cases:

1. `test_is456_singly_reinforced_slab`: Cross-checks computed reinforcement percentage $p_t$ against IS 456 SP 16 design charts within $0.5\%$ error ($p_t = 0.502\%$ for M30/Fe 500 at $M_u/bd^2 = 2.0\text{ MPa}$), verifies limiting moment $M_{u, \lim}$, and validates doubly reinforced compression steel sizing ($A_{sc} > 0$).
2. `test_is456_shear_capacity`: Verifies concrete shear strength $\tau_c$ against Table 19 across grades M25, M30, M35, M40 at $p_t = 0.50\%$ and $1.00\%$ within $0.03\text{ MPa}$; tests stirrup sizing when $\tau_v > \tau_c$ and failure triggering when $\tau_v > \tau_{c, \max}$.
3. `test_is2911_pile_capacity`: Validates end bearing and skin friction against textbook golden benchmarks for clay piles ($Q_b = 353.4\text{ kN}, Q_s = 1178.1\text{ kN}, Q_u = 1531.5\text{ kN}, Q_{\text{safe}} = 612.6\text{ kN}$) and $c\text{-}\phi$ soils; verifies lateral stiffness factor $T$, depth of fixity $z_f = 2.0 T$, and structural cage detailing ($A_{st} \ge 0.4\% A_g$).
4. `test_is800_strut_buckling_curve`: Validates design compressive stress $f_{cd}$ against IS 800 Table 9(c) across slenderness ratios $KL/r \in [20, 180]$ within $1.5\%$ error; verifies Buckling Curve hierarchy ($f_{cd, a} > f_{cd, b} > f_{cd, c} > f_{cd, d}$).
5. `test_unity_ratio_thresholds`: Verifies that any check with $UR > 1.0$ is flagged as `FAIL` with exact clause citations (excessive flexure triggers IS 456 Cl. 38, excessive pile load triggers IS 2911 Appendix B, excessive slenderness triggers IS 800 Table 3).
6. `test_is456_crack_width_and_bar_callouts`: Tests Annex F flexural crack width calculation ($w_{cr} \le 0.20\text{ mm}$) with tension stiffening deduction and validates automated callout generation (`"2-layer T16 @ 125 mm c/c each face"`).
7. `test_is_codes_edge_cases_and_branch_coverage`: Validates physical input bounds (negative dimensions, invalid concrete/steel grades, negative slenderness), free-head pile fixity, bearing capacity interpolation, and markdown audit sheet generation.
8. `test_is456_additional_branches`: Exercises $x_{u, \max}/d$ interpolation across all steel grades (Fe 250 to Fe 550), Table 20 $\tau_{c, \max}$ values, beam nominal stirrup sizing, single-layer callouts, and warning state evaluation.
9. `test_is800_and_is2911_additional_branches`: Validates zero-load strut connections, dataclass serialization (`to_dict()`), and structural pile rebar cage reporting.

---

## 4. Full Repository Regression Test

A full regression run across all 22 test modules was executed:

```bash
$ PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v
============================= 217 passed in 10.15s ==============================
```

- **Total Tests:** 217 (100% pass rate)
- **Regression Failures:** 0
- **Cross-Component OpenMP / Kratos / OpenSees Cleanup:** Clean process termination without memory leaks or OpenGL context conflicts.

---

## 5. Architectural Alignment & Next Steps (Phase 9)

With Phase 8 completed, Orang3D now features full, automated structural and geotechnical code-checking engines strictly conforming to Indian Standards. The repository is ready for:

- **Phase 9: AI/PINN Fast Surrogates & Uncertainty Quantification (UQ):**
  - Parametric database generation via Latin Hypercube Sampling (LHS) across soil parameters, wall geometry, and seismic ground motions.
  - Physics-informed neural network (PINN) and machine-learning surrogates for sub-millisecond ($< 1\text{ ms}$) evaluation of internal moment/shear profiles and strut loads.
  - Probabilistic Monte Carlo simulation for reliability index $\beta$ and seismic fragility curves $P(\text{Exceedance} \mid \text{PGA})$.
