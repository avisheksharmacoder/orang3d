# Simulation Guide 09: Multi-Code International Regulatory Compliance Audit
**Governing Standards:** IS 456 / IS 2911 / IS 800 / IS 1893, Eurocode 2/7/8, AASHTO LRFD, and ACI 318-19

---

## 1. Engineering Objective
Execute a multi-code regulatory design compliance audit on a retaining structure, comparing demand-to-capacity unity ratios ($\text{UR} = \text{Demand} / \text{Capacity} \le 1.00$) simultaneously across four major international building standards. Demonstrate:
1. Limit state flexure and shear reinforcement sizing under Indian Standard IS 456:2000.
2. Bored pile geotechnical and structural capacity checks under IS 2911:2010.
3. Compressive buckling and slenderness checks for raking steel struts under IS 800:2007.
4. Seismic load combination factors under Eurocode 7/8 (Design Approach 1, Combination 2).
5. Foundation eccentricity limits under AASHTO LRFD Bridge Design Specifications ($e \le B/3$).
6. Flexural strength reduction checks ($\phi M_n \ge M_u$) under ACI 318-19.

---

## 2. Model Baseline Configuration

Use the benchmark retaining wall geometry ($H = 6.00\text{ m}, B = 4.25\text{ m}$, M30 Concrete, Fe 500 Rebar, Fe 250 Steel Struts, $\text{PGA} = 0.20\text{ g}$).

---

## 3. Step-by-Step Execution in orang3D

1. **Open the Design Audit Tab:**
   * In the bottom dashboard, click the tab **`📋 Design Audit (IS / EC7 / AASHTO / ACI)`**.
2. **Review Indian Standards (IS Code) Audit:**
   * In the top-left dropdown of the audit tab, ensure **`Indian Standards (IS 456 / 2911 / 800 / 1893)`** is selected.
   * Review the 9-column compliance checklist:
     * *Check 1:* Stem Base Flexure (IS 456 Cl. 38.1)
     * *Check 2:* Stem Concrete Shear (IS 456 Table 19)
     * *Check 3:* Surface Crack Width Limitation (IS 456 Annex F)
     * *Check 4:* Bored Pile Axial Geotechnical Capacity (IS 2911 App. B)
     * *Check 5:* Strut Compressive Buckling (IS 800 Table 9c)
     * *Check 6:* Base Sliding Factor of Safety (IS 14458)
3. **Switch to Eurocode 7 & 8:**
   * Change the dropdown to **`Eurocode (EN 1992 / EN 1997 / EN 1998)`**.
   * Note how the partial safety factors update:
     * Soil shear strength factor: $\gamma_{\phi'} = 1.25$ (DA1-C2).
     * Sliding resistance partial factor: $\gamma_{R;h} = 1.00$ (Seismic combination).
4. **Switch to AASHTO LRFD:**
   * Change the dropdown to **`AASHTO LRFD Bridge Design`**.
   * Inspect the base eccentricity check ($e \le B/3 = 1.41\text{ m}$ on soil foundations).
5. **Switch to ACI 318-19:**
   * Change the dropdown to **`ACI 318-19 / ASCE 7`**.
   * Verify strength reduction factors: $\phi_{\text{flex}} = 0.90, \phi_{\text{shear}} = 0.75$.
6. **Export Formal Calculation Audit Sheet:**
   * Click **`Export Audit Sheet (.md)...`**.
   * Save the generated Markdown report. Open it to review the mathematical equations, input parameters, and clause citations.

---

## 4. Expected Visual & Graphical Behavior
* **Live Audit Checklist:**
  * Clean table with status badges:
    * 🟢 **`PASS`** for $\text{UR} \le 0.90$
    * 🟡 **`WARNING`** for $0.90 < \text{UR} \le 1.00$
    * 🔴 **`FAIL`** for $\text{UR} > 1.00$
  * Rebar detailing callouts are generated automatically (e.g., `"2-layer T16 @ 125 mm c/c each face"`).

---

## 5. Quantitative Verification Benchmarks & Code Citations

| Code Standard | Clause Citation | Design Quantity Checked | Demand | Capacity | Unity Ratio | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **IS 456:2000** | Cl. 38.1 | Stem Base Ultimate Flexure | $184.2\text{ kNm}$ | $245.0\text{ kNm}$ | `0.75` | 🟢 **PASS** |
| **IS 456:2000** | Table 19 | Stem Nominal Shear Stress | $0.42\text{ MPa}$ | $0.51\text{ MPa}$ | `0.82` | 🟢 **PASS** |
| **IS 456:2000** | Annex F | Surface Crack Width $w_{cr}$ | $0.14\text{ mm}$ | $0.20\text{ mm}$ | `0.70` | 🟢 **PASS** |
| **IS 2911:2010**| Part 1/Sec 2 App B| Bored Pile Safe Axial Load | $420.0\text{ kN}$ | $612.6\text{ kN}$ | `0.69` | 🟢 **PASS** |
| **IS 800:2007** | Cl. 7.1.2 Table 9(c)| Strut Compressive Buckling | $184.2\text{ kN}$ | $2626.0\text{ kN}$ | `0.07` | 🟢 **PASS** |
| **Eurocode 7** | EN 1997-1 Cl. 9.4 | Sliding Equilibrium (DA1-C2) | $142.0\text{ kN}$ | $168.0\text{ kN}$ | `0.85` | 🟢 **PASS** |
| **AASHTO LRFD** | Table 11.6.3.2 | Base Eccentricity Kern Limit | $0.41\text{ m}$ | $1.41\text{ m}$ | `0.29` | 🟢 **PASS** |
| **ACI 318-19** | Cl. 11.5.1 | One-Way Shear Strength $\phi V_c$| $95.0\text{ kN}$ | $118.0\text{ kN}$ | `0.81` | 🟢 **PASS** |

---

## 6. Headless Python Verification

Verify this exact scenario non-interactively via the terminal:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_multi_code_and_units.py -v
```

