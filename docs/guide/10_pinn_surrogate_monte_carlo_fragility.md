# Simulation Guide 10: AI / PINN Fast Surrogates & Monte Carlo Fragility Curves
**AI Architecture:** Multi-Objective Physics-Informed Neural Network (PINN) + Latin Hypercube Sampling (LHS)

---

## 1. Engineering Objective
Perform probabilistic reliability analysis and seismic vulnerability assessment of a retaining system:
1. Leverage a vectorized Physics-Informed Neural Network (PINN) surrogate to evaluate internal bending moments and shear forces in $< 0.2\text{ ms}$ on CPU.
2. Verify the physics equilibrium projection layer enforcing strict horizontal force conservation ($\sum F_x = 0$).
3. Execute a 1,000-sample Latin Hypercube Sampling (LHS) Monte Carlo simulation across uncertain soil strength parameters and seismic demands.
4. Calculate the Cornell structural reliability index ($\beta$) and failure probability ($P_f$).
5. Generate HAZUS-calibrated seismic fragility curves for four discrete damage states (Slight, Moderate, Extensive, Collapse).

---

## 2. Stochastic Parameter Distributions

| Parameter | Symbol | Distribution Type | Mean ($\mu$) | Dispersion ($\sigma$ / COV) | Range | Unit |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| **Friction Angle** | $\phi$ | Normal | `32.0` | `3.0` | $[22.0, 42.0]$ | deg |
| **Cohesion** | $c$ | Lognormal | `5.0` | $\text{COV} = 0.30$ | $[0.5, 30.0]$ | kPa |
| **Unit Weight** | $\gamma$ | Normal | `18.5` | `1.0` | $[16.0, 21.0]$ | kN/m³ |
| **Seismic PGA** | $k_h$ | Uniform | - | - | $[0.10, 0.45]$ | g |
| **Wall Resistance**| $R$ | Lognormal | `1.0` | $\text{COV} = 0.15$ | $[0.5, 2.0]$ | - |

---

## 3. Step-by-Step Execution in orang3D

1. **Open UQ & Seismic Fragility Dashboard:**
   * In the bottom dashboard, click the tab **`📈 UQ & Seismic Fragility`**.
2. **Configure Monte Carlo Settings:**
   * In the **Surrogate Engine** dropdown, select **`Fast PINN Surrogate (< 1 ms)`**.
   * Set **`Number of Samples N`** to `1000`.
   * In the random variable distribution table, verify the mean and dispersion values from Section 2.
3. **Execute Latin Hypercube Sampling:**
   * Click **`⚡ Run Monte Carlo UQ (LHS)`**.
   * An asynchronous `UQSimulationWorker` executes 1,000 full structural evaluations in $< 0.8\text{ seconds}$ on CPU without freezing the GUI.
4. **Inspect Factor of Safety Histogram:**
   * Look at the left PyQtGraph plot: a continuous probability density histogram displays the distribution of sliding safety factors ($FS$).
   * A vertical dashed red line marks the limit state threshold $FS = 1.0$. The area to the left of this line represents the probability of failure ($P_f$).
5. **Generate Seismic Fragility Curves:**
   * Click **`Generate HAZUS Fragility Curves`**.
   * Look at the right PyQtGraph plot: four smooth lognormal cumulative distribution curves are plotted against PGA.

---

## 4. Expected Visual & Graphical Behavior
* **Left Plot (Histogram):**
  * Bell-shaped distribution centered around $\mu_{FS} \approx 1.42$.
  * Summary metrics card displays: $\mu = 1.42$, $\sigma = 0.22$, $\text{COV} = 0.15$, Cornell $\beta = 1.91$, $P_f = 2.8\%$.
* **Right Plot (Fragility):**
  * Four smooth, non-intersecting, monotonically non-decreasing curves:
    * 🟢 **Slight Damage ($u \ge 25\text{ mm}$):** Steepest rise, reaching $50\%$ probability at $\text{PGA} \approx 0.18\text{ g}$.
    * 🟡 **Moderate Damage ($u \ge 50\text{ mm}$):** Median capacity at $\text{PGA} \approx 0.32\text{ g}$.
    * 🟠 **Extensive Damage ($u \ge 100\text{ mm}$):** Median capacity at $\text{PGA} \approx 0.48\text{ g}$.
    * 🔴 **Collapse ($u \ge 200\text{ mm}$ or $FS < 1.0$):** Flattest rise, reaching median at $\text{PGA} \approx 0.68\text{ g}$.

---

## 5. Quantitative Verification Benchmarks

| Metric | Governing Formulation | Target Value | Acceptable Tolerance | Status |
| :--- | :--- | :---: | :---: | :---: |
| **PINN Forward Pass Latency** | CPU inference time | `< 0.20 ms` | $< 1.00\text{ ms}$ | **PASSED** |
| **Physics Equilibrium Invariant**| $\Delta F_x = \frac{\|P_{ae} - \sum F_i\|}{P_{ae}}$ | `0.00%` | $< 0.01\%$ | **CONSERVED** |
| **LHS Distribution Uniformity** | Kolmogorov-Smirnov $p$-value | $p > 0.05$ | Statistically Uniform | **VERIFIED** |
| **Mean Factor of Safety $\mu_{FS}$**| Sample mean over 1,000 runs | `1.42` | $\pm 0.05$ | **MATCHED** |
| **Cornell Reliability Index $\beta$**| $\frac{\mu_{FS} - 1.0}{\sigma_{FS}}$ | `1.91` | $\pm 0.15$ | **MATCHED** |
| **Probability of Failure $P_f$** | $N(FS < 1.0) / 1000$ | `2.8%` | $[ 1.5\%, 4.0\% ]$ | **MATCHED** |
| **Fragility Monotonicity** | $P(\text{PGA}_2) \ge P(\text{PGA}_1)$ | Strictly Monotonic | Non-decreasing | **VERIFIED** |
| **Fragility Damage Hierarchy** | $P(\text{Slight}) \ge P(\text{Mod}) \ge P(\text{Ext}) \ge P(\text{Col})$ | Strict Ordering | No Curve Crossing | **VERIFIED** |

---

## 6. Headless Python Verification

Verify this exact scenario non-interactively via the terminal:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_surrogates_and_uq.py -v
```

