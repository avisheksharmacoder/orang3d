# v2 Phase 1 Completion Report: Advanced Data Contracts, Validation & Invariants
## Pile-Supported Multi-Strut Curved Shell Retaining Walls on Seismic Hill Slopes

**Status:** Completed  
**Test Suite:** [`tests/test_advanced_models.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_advanced_models.py) (19 comprehensive unit & invariant tests)  
**Test Coverage:** **100% statement coverage** across all Phase 1 modules (370 / 370 statements covered)  
**Execution Time:** `< 0.7` seconds  

---

## 1. Overview & Objectives Achieved

Phase 1 establishes the mathematical and typed foundational data layer for the **orang3D v2 Advanced Geotechnical Suite**, extending the software to model:
1. **Horizontally Arching Curved RC Shell Panels** spanning between vertical piers.
2. **Vertical Pier Columns rigidly coupled to Bored Cast-in-Situ Floating Piles** in $c\text{-}\phi$ hill soils.
3. **Multi-Tier Raking Steel Struts & Prestressed Anchors** with slenderness and buckling limits.
4. **Uphill Lattice Transmission Towers** subjected to combined wind (IS 875), broken-wire conditions (IS 802), and seismic ground motion.
5. **Full-Chain Indian Standards Configuration** (IS 1893:2016, IS 456:2000, IS 2911:2010, IS 800:2007).

---

## 2. Key Deliverables & Implementation Details

### 2.1 Curved Shell Retaining Panels ([`src/orang3d/models/advanced_wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/advanced_wall_params.py))
- **`CurvedShellGeometry` Dataclass**:
  - Parameterized by cylinder radius $R$, subtended arc angle $2\theta$, panel thickness $t_s$, crown-to-backfill orientation (`crown_to_backfill`), bay span $L_{bay}$, and panel height $H_p$.
  - **Invariants Enforced:**
    - Strictly rejects subtended angles outside $(0^\circ, 180^\circ)$ ($2\theta \ge 180^\circ$ is geometrically invalid for shell arching).
    - Enforces minimum structural RC shell thickness $t_s > 0.05\text{ m}$ ($50\text{ mm}$).
    - Enforces that bay span cannot exceed the cylinder diameter $L_{bay} \le 2R$.
  - **Calculated Properties:**
    - Arc perimeter length $S = R \cdot (2\theta_{\text{rad}})$.
    - Straight chord span $C = 2R \sin(\theta_{\text{rad}})$.
    - Arching crown sagitta (rise) $f = R (1 - \cos(\theta_{\text{rad}}))$.
    - Curved facing surface area, concrete volume, and panel self-weight.

### 2.2 Pier & Bored Floating Pile Substructure ([`src/orang3d/models/advanced_wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/advanced_wall_params.py))
- **`PierAndPileGeometry` Dataclass**:
  - Parameterized by pier width $b_p$, pier depth $d_p$, pier height $H_{pier}$, circular bored pile diameter $D_p$, pile embedment length $L_{pile}$, number of piles per pier $n_{pile}$, center-to-center spacing $s_p$, and pile cap dimensions.
  - **Invariants Enforced:**
    - Rejects non-positive pile embedment length ($L_{pile} \le 0$).
    - Rejects pile spacing $s_p < 2.5 D_p$ for pile groups ($n_{pile} > 1$) to prevent immediate block shear failure per **IS 2911 (Part 1/Sec 2)**.
    - Permits $s_p = 0.0$ for isolated single piles ($n_{pile} = 1$).
  - **Calculated Properties:**
    - Pile cross-sectional area $A_p = \frac{\pi D_p^2}{4}$ and perimeter $\pi D_p$.
    - Pier, cap, and pile group concrete volumes and total substructure self-weight.

### 2.3 Multi-Tier Raking Struts & Anchors ([`src/orang3d/models/advanced_wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/advanced_wall_params.py))
- **`StrutSupportSystem` Dataclass**:
  - Parameterized by attachment depths (`strut_levels`), inclination angle $\alpha_{strut} \in [0^\circ, 60^\circ]$, section area $A_s$, moment of inertia $I_s$, steel modulus $E_s$, yield strength $f_y$, pre-stress lock-off load $P_0$, unbraced length $L_{strut}$, and allowable slenderness $\lambda_{max}$ (IS 800).
  - **Invariants Enforced:**
    - `strut_levels` must be non-empty, positive, and strictly increasing with depth.
    - Cross-validation against pier: all strut attachment depths must be strictly less than total pier height ($y_i < H_{pier}$).
  - **Calculated Properties:**
    - Radius of gyration $r = \sqrt{I_s / A_s}$.
    - Compression slenderness ratio $\lambda = L_{strut} / r$.
    - Euler critical buckling load $P_{cr} = \frac{\pi^2 E_s I_s}{L_{strut}^2}$.
    - Plastic squash load $P_y = A_s f_y$.

### 2.4 Composite Retaining System Contract ([`src/orang3d/models/advanced_wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/advanced_wall_params.py))
- **`MultiStrutPiledWallModel` Dataclass**:
  - Unifies `CurvedShellGeometry`, `PierAndPileGeometry`, and `StrutSupportSystem`.
  - Enforces cross-subsystem geometry compatibility ($H_{pier} \ge H_p$ and all struts fit within $H_{pier}$).

### 2.5 Uphill Transmission Tower Multi-Hazard Contract ([`src/orang3d/models/tower_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/tower_params.py))
- **`TransmissionTowerParams` Dataclass**:
  - Parameterized by footprint dimensions $B_{tower} \times L_{tower}$, total height $H_{tower}$, slope crest offset $X_{offset}$, vertical load per leg $P_{leg}$, transverse wind shear per leg $V_{wind}$ (IS 875 Part 3), longitudinal broken-wire unbalanced tension $T_{bw}$ (IS 802), and seismic mass participation ratio.
  - **Mechanics & Invariants:**
    - Computes total vertical dead/live load ($\sum P_v = 4 P_{leg}$) and total wind shear ($\sum V_{wind} = 4 V_{wind}$).
    - Calculates wind overturning moment $M_{wind} = V_{wind,total} \cdot \frac{H_{tower}}{2}$.
    - Calculates broken-wire yaw torsion and longitudinal overturning moment.
    - `compute_leg_vertical_reactions()`: Computes net vertical reactions at all 4 corner footings, accounting for overturning couples and verifying global static equilibrium $\sum R_v = 4 P_{leg}$.

### 2.6 Indian Standards Design Settings Layer ([`src/orang3d/models/is_code_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/is_code_params.py))
- **`IndianDesignStandards`, `SeismicZone`, and `FoundationSoilType`**:
  - **Seismic Zoning Matrix (IS 1893:2016 Table 3):**
    - Zone II: $Z = 0.10$
    - Zone III: $Z = 0.16$
    - Zone IV: $Z = 0.24$
    - Zone V: $Z = 0.36$
  - **Response Spectra Calculation ($S_a / g$):**
    - Analytical continuous formulation for Type I (Rock), Type II (Medium), and Type III (Soft) foundation soils per IS 1893 Clause 6.4.2.
    - Damping multiplying factor $\eta = \sqrt{\frac{10}{5 + 100\xi}}$ for non-5% damping ratios per IS 1893 Table 3.
  - **Design Seismic Coefficients:**
    - Horizontal coefficient $A_h = \left(\frac{Z}{2}\right) \cdot \left(\frac{I}{R}\right) \cdot \left(\frac{S_a}{g}\right)$.
    - Vertical coefficient $A_v = \frac{2}{3} A_h$.
  - **Material Enforcements:**
    - Enforces minimum concrete grade $f_{ck} \ge 25\text{ MPa}$ (M25) for retaining structures per IS 456.
    - Validates reinforcing steel grades (Fe415, Fe500, Fe550, Fe500D) with automatic extraction of characteristic strength $f_y$.

---

## 3. Test Coverage Strategy & Final Verification

The test suite in [`tests/test_advanced_models.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_advanced_models.py) validates all requirements with 100% coverage:

```bash
$ PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/coverage run -m pytest tests/test_advanced_models.py
$ .venv/bin/coverage report -m src/orang3d/models/advanced_wall_params.py src/orang3d/models/tower_params.py src/orang3d/models/is_code_params.py
```

| Component Module | File Path | Statements | Missed | Coverage | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Advanced Wall Models** | [`src/orang3d/models/advanced_wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/advanced_wall_params.py) | 202 | 0 | **100%** | **Passed** |
| **IS Design Standards** | [`src/orang3d/models/is_code_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/is_code_params.py) | 104 | 0 | **100%** | **Passed** |
| **Transmission Tower** | [`src/orang3d/models/tower_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/tower_params.py) | 64 | 0 | **100%** | **Passed** |
| **TOTAL PHASE 1** | **All 3 New Subsystems** | **370** | **0** | **100%** | **PASSED** |

### Verified Test Cases:
1. `test_shell_geometry_defaults`: Verifies canonical default dimensions and properties.
2. `test_shell_geometry_properties`: Validates arc length, chord length, sagitta, volume, and self-weight formulas.
3. `test_shell_geometry_bounds`: Asserts rejection of $2\theta \ge 180^\circ$, $2\theta \le 0^\circ$, $t_s \le 0.05\text{ m}$, and $L_{bay} > 2R$.
4. `test_pile_geometry_defaults`: Verifies pier and bored pile baseline defaults.
5. `test_pile_geometry_properties`: Validates pile cross-section, perimeter, pier volume, cap volume, and group weight.
6. `test_pile_geometry_invariants`: Asserts rejection of $L_{pile} \le 0$ and $s_p < 2.5 D_p$ for group piles (IS 2911 block failure prevention).
7. `test_strut_support_defaults`: Verifies multi-tier strut baseline defaults.
8. `test_strut_support_properties`: Validates radius of gyration, slenderness ratio, Euler buckling, and plastic yield capacity.
9. `test_strut_spacing_bounds`: Validates that strut levels fit within pier height, rejects non-increasing or duplicate depths.
10. `test_composite_system_model_defaults`: Verifies full composite model initialization.
11. `test_composite_system_model_cross_validation`: Asserts cross-checks between strut levels and pier height, and pier height vs panel height.
12. `test_tower_params_defaults`: Verifies uphill transmission tower parameter defaults.
13. `test_tower_params_load_computations`: Validates overturning moments and corner leg reactions under combined dead + wind + broken-wire loads with vertical equilibrium conservation $\sum R_v = 4 P_{leg}$.
14. `test_tower_params_bounds`: Rejects non-positive footprint, height, or invalid mass ratios.
15. `test_is_code_zoning_matrix`: Verifies zone factors for Zone II ($0.10$), Zone III ($0.16$), Zone IV ($0.24$), and Zone V ($0.36$).
16. `test_is_code_spectral_acceleration`: Verifies $S_a/g$ curves across Type I, Type II, and Type III soils and damping factor $\eta$.
17. `test_is_code_seismic_coefficients`: Validates $A_h = \frac{Z}{2} \cdot \frac{I}{R} \cdot \frac{S_a}{g}$ and $A_v = \frac{2}{3} A_h$.
18. `test_is_code_material_validation`: Asserts rejection of concrete grades $< M25$, non-standard steel grades, and parses characteristic strengths $f_{ck}$ and $f_y$.
19. `test_dataclass_serialization`: Enforces exact, lossless round-trip JSON serialization across all dataclasses (`to_dict` $\to$ `json.dumps` $\to$ `json.loads` $\to$ `from_dict`).

---

## 4. Artifacts Summary

### Created:
- [`src/orang3d/models/advanced_wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/advanced_wall_params.py): Data contracts for `CurvedShellGeometry`, `PierAndPileGeometry`, `StrutSupportSystem`, and `MultiStrutPiledWallModel`.
- [`src/orang3d/models/tower_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/tower_params.py): Data contract for `TransmissionTowerParams` with multi-hazard load computation methods.
- [`src/orang3d/models/is_code_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/is_code_params.py): Data contracts for `IndianDesignStandards`, `SeismicZone`, and `FoundationSoilType` (IS 1893, IS 456, IS 2911, IS 800).
- [`tests/test_advanced_models.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_advanced_models.py): Automated test suite with 19 tests and 100% statement coverage.
- [`docs/v2/PHASE_1_COMPLETION.md`](file:///home/avisheks/Documents/dibs/orang3d/docs/v2/PHASE_1_COMPLETION.md): Detailed completion report.

### Updated:
- [`src/orang3d/models/__init__.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/__init__.py): Exported all new data contracts alongside existing baseline models.
