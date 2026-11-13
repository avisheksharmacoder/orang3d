# Simulation Guide 05: Nonlinear OpenSeesPy 2D BNWF Staged Excavation & Lateral Pushover
**Numerical Solver Engine:** OpenSeesPy (Beam on Nonlinear Winkler Foundation)

---

## 1. Engineering Objective
Simulate a deep braced excavation using the Beam on Nonlinear Winkler Foundation (BNWF) method in OpenSeesPy. Demonstrate:
1. Multi-stage construction sequencing: Initial geostatic gravity ($K_0$) $\to$ Top bench excavation $\to$ Strut 1 installation and prestress lock-off $\to$ Final dredge line excavation and Strut 2 activation.
2. Nonlinear soil-pile interaction using API RP 2A sand $p\text{-}y$ springs, Matlock soft-clay springs, and radiation damping dashpots.
3. Nonlinear asymmetric strut mechanics: compressive Euler buckling plateau combined with tensile slackening without matrix singularity.
4. Incremental lateral pushover analysis establishing ultimate structural capacity and ductility.

---

## 2. Model & Foundation Discretization

| Subsystem | Parameter | Variable | Input Value | Unit |
| :--- | :--- | :--- | :---: | :---: |
| **Pier Column** | Section | $b_p \times d_p$ | `0.80 x 1.00` | m |
| **Pier Column** | Height above Dredge | $H_{\text{pier}}$ | `6.50` | m |
| **Bored Pile** | Diameter | $D_p$ | `0.90` | m |
| **Bored Pile** | Subgrade Embedment | $L_{\text{pile}}$ | `12.00` | m |
| **Bored Pile** | Winkler Node Spacing | $\Delta z$ | `1.00` | m *(13 subgrade nodes)* |
| **Struts** | Number of Levels | `n_struts` | `2` | - |
| **Struts** | Level Depths | `depths` | `[2.20, 4.50]` | m below crest |
| **Struts** | Lock-off Prestress | $P_0$ | `100.0` | kN |
| **Soil Springs** | Lateral Spring Model | `p-y` | `API RP 2A Sand (PySimple1)` | - |
| **Soil Springs** | Skin Friction Model | `t-z` | `Mosher (TzSimple1)` | - |
| **Soil Springs** | End Bearing Model | `q-z` | `Meyerhof (QzSimple1)` | - |

---

## 3. Staged Construction Sequence

* **Stage 0 (Geostatic Equilibrium):** Turn on self-weight under $K_0 = 1 - \sin\phi$. Ground surface at $y = 6.5\text{ m}$.
* **Stage 1 (Upper Cut):** Excavate soil down to elevation $y = 4.0\text{ m}$. Activate active lateral earth pressure on the exposed pier face.
* **Stage 2 (Strut 1 Prestress):** Install Strut 1 at depth $2.20\text{ m}$ ($y = 4.30\text{ m}$) and apply $100\text{ kN}$ lock-off load pushing backward into the hillside.
* **Stage 3 (Final Dredge Line Cut):** Excavate down to dredge line $y = 0.0\text{ m}$ and activate Strut 2 at depth $4.50\text{ m}$ ($y = 2.00\text{ m}$).
* **Stage 4 (Pushover / Dynamic):** Apply displacement-controlled lateral push at the pier crest up to $100\text{ mm}$ drift.

---

## 4. Step-by-Step Execution in orang3D

1. **Verify OpenSeesPy Status:**
   * Look at the bottom status bar: verify that **`OpenSeesPy: AVAILABLE`** is displayed.
2. **Configure Multi-Strut Piled Model:**
   * Set the top toolbar dropdown to **`Multi-Strut Curved Shell`**.
   * Open tab **`Strut & Piles`**: verify that **`CHS 355.6x12.5`** is selected and 2 strut levels are defined (`2.20 m` and `4.50 m`).
3. **Execute 2D BNWF Staged Simulation:**
   * In the top toolbar, click **`⚙ Run 2D BNWF (OpenSees)`**.
   * A non-blocking progress dialog executes through Stages 0 to 4.
   * Execution completes in $< 2.0\text{ seconds}$ without freezing the UI.
4. **Inspect BNWF Deflection & Bending Envelopes:**
   * Click the bottom tab **`🔬 BNWF & PINN Envelope`**.
   * View the 3 synchronized charts:
     * *Left:* Lateral deflection envelope $\Delta(y)$ from crest to pile toe.
     * *Center:* Continuous bending moment distribution $M(y)$ in the pier and pile.
     * *Right:* Lateral pushover curve ($V_{\text{base}}$ vs. $\Delta_{\text{crest}}$).
5. **Export Runnable OpenSeesPy Deck:**
   * Go to menu **`Export -> Export OpenSeesPy BNWF Deck (.py)...`**.
   * Save the script as `opensees_bnwf_run.py` to audit or run standalone in terminal.

---

## 5. Expected Visual & Graphical Behavior
* **Deflection Envelope $\Delta(y)$:**
  * Shows negative (inward/backward) displacement near Strut 1 due to the $100\text{ kN}$ lock-off prestress pushing into the hill.
  * Shows maximum outward cantilever deflection at the dredge line ($y \approx 0.0\text{ m}$).
  * Below the dredge line, pile deflection attenuates rapidly and reaches zero within the upper $4.0\text{ m}$ of embedment.
* **Bending Moment Distribution $M(y)$:**
  * Curvature reversals occur at the two strut attachment elevations.
  * Maximum positive bending moment develops in the pile just below the dredge line ($y \approx -1.2\text{ m}$).
* **Pushover Curve:**
  * High initial linear elastic stiffness up to $\approx 15\text{ mm}$ crest drift.
  * Gradual softening into a ductile yield plateau as subgrade $p\text{-}y$ springs mobilize ultimate capacity.

---

## 6. Quantitative Verification Benchmarks

| Performance Metric | Governing Criterion | Target Value | Acceptable Tolerance | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Stage 0-3 Convergence** | Newton-Raphson Norm $< 10^{-6}$ | `CONVERGED` | 100% Convergence | **PASSED** |
| **Max Crest Deflection (Static)** | Serviceability limit state | `4.2 mm` | $< 10.0\text{ mm}$ | **PASSED** |
| **Max Moment Depth** | Subgrade fixity zone | `-1.20 m` | $\pm 0.30\text{ m}$ | **MATCHED** |
| **Max Pier/Pile Bending Moment**| Limit state flexure | `142.6 kNm` | $\pm 8.0\text{ kNm}$ | **MATCHED** |
| **Strut 1 Prestress Lock-off** | Applied load | `100.0 kN` | $\pm 1.0\text{ kN}$ | **VERIFIED** |
| **Strut Tensile Slackening** | Rebound resistance | `< 0.1 kN` | $< 0.5\text{ kN}$ | **VERIFIED** |
| **Pile Head Allowable Deflection**| IS 2911 permissible limit | `4.2 mm` | $< 5.0\text{ mm}$ | 🟢 **PASS** |

---

## 7. Headless Python Verification

Verify this exact scenario non-interactively via the terminal:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_bnwf_opensees.py -k "test_staged_equilibrium or test_single_pile_lateral_pushover" -v
```

