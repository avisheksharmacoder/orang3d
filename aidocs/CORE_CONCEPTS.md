# Geotechnical, Structural & Numerical Core Concepts

This document summarizes the mathematical formulas, physical conservation laws, geotechnical principles, and numerical mechanics implemented in **orang3D**.

---

## 1. Retaining Wall Anatomy & Multi-Templates

`orang3D` models five distinct retaining wall structural configurations:

```
    Inverted-T            L-Shaped             Reverse-L            Gravity
   ┌──┐                 ┌──┐                        ┌──┐         ┌──┐
   │  │                 │  │                        │  │        /   │
   │  │ (Stem)          │  │ (Flush front)          │  │       /    │
   │  │                 │  │                        │  │      /     │
   │  │                 │  │                        │  │     /      │
┌──┴──┴─────┐           └──┴────────┐        ┌──────┴──┘    └───────┘
│  (Footing)│           │ (Heel only│        │(Toe only)│   
└───────────┘           └───────────┘        └──────────┘   
```

1. **Standard Inverted-T:** Cantilever wall with both a front toe slab and rear heel slab. Most common for highway and municipal earth retention.
2. **L-Shaped:** Flush front toe ($L_{\text{toe}} = 0$). Ideal for property boundary lines where excavation cannot cross into adjacent land.
3. **Reverse L-Shaped:** Flush rear heel ($L_{\text{heel}} = 0$). Used when utility easements or bedrock prevent heel excavation.
4. **Tapered Gravity:** Thick concrete monolith relying primarily on self-weight to resist overturning.
5. **Bottom Shear Key:** Optional rectangular or trapezoidal projection beneath the base slab providing additional passive soil embedment resistance against sliding.

---

## 2. Dynamic Earth Pressures (Mononobe-Okabe Theory)

### 2.1 The Mononobe-Okabe (M-O) Equation

The pseudo-static dynamic active earth pressure coefficient $K_{ae}$ is calculated as:

$$K_{ae} = \frac{\cos^2(\phi - \theta - \beta_w)}{\cos\theta \cos^2\beta_w \cos(\delta + \beta_w + \theta) \left[ 1 + \sqrt{\frac{\sin(\phi + \delta)\sin(\phi - \theta - \beta)}{\cos(\delta + \beta_w + \theta)\cos(\beta - \beta_w)}} \right]^2}$$

Where:
- $\phi$: Internal angle of friction of the backfill soil.
- $\delta$: Wall-soil interface friction angle ($\approx \frac{2}{3}\phi$).
- $\beta$: Backfill slope inclination angle.
- $\beta_w$: Wall backface tilt angle ($= 0$ for vertical backface).
- $\theta$: Seismic inertia angle:
  $$\theta = \arctan\left(\frac{k_h}{1 \mp k_v}\right)$$
  - $k_h$: Horizontal seismic acceleration coefficient ($g$).
  - $k_v$: Vertical seismic acceleration coefficient ($g$).

### 2.2 Asymptotic Static Convergence
When $k_h \to 0$ and $k_v \to 0$, the seismic inertia angle $\theta \to 0$, and the Mononobe-Okabe equation reduces **identically** to the classical Coulomb active earth pressure coefficient $K_a$:

$$K_a = \frac{\cos^2(\phi - \beta_w)}{\cos^2\beta_w \cos(\delta + \beta_w) \left[ 1 + \sqrt{\frac{\sin(\phi + \delta)\sin(\phi - \beta)}{\cos(\delta + \beta_w)\cos(\beta - \beta_w)}} \right]^2}$$

### 2.3 Seed & Whitman (1970) Resultant Partition
The total dynamic thrust $P_{ae}$ is partitioned into two distinct physical components:
1. **Static Active Thrust ($P_a$):** Acts at $h_1 = H/3$ above the footing base.
   $$P_a = \frac{1}{2} \gamma H^2 K_a$$
2. **Dynamic Seismic Increment ($\Delta P_{ae}$):** Acts higher up the stem at $h_2 = 0.6H$ above the base due to dynamic amplification:
   $$\Delta P_{ae} = P_{ae} - P_a = \frac{1}{2} \gamma H^2 (K_{ae} - K_a)$$

---

## 3. Global Stability & Limit-Equilibrium Statics

### 3.1 Factor of Safety against Sliding ($FS_s$)

$$FS_s = \frac{\sum R_{\text{resisting}}}{\sum D_{\text{driving}}} = \frac{V_{\text{eff}} \tan(\phi_b) + c_b B + P_p}{P_{ae,h} + P_w}$$

Where:
- $V_{\text{eff}}$: Net effective vertical downward load (dead weight of concrete + weight of soil resting on heel minus uplift).
- $\phi_b$: Base slab-soil interface friction angle ($\approx 0.75 \phi_{\text{fund}}$).
- $c_b$: Base adhesion ($c_b \approx 0.5 - 0.75 c_{\text{fund}}$).
- $P_p$: Passive resistance developed by footing embedment and shear key:
  $$P_p = \frac{1}{2} \gamma_{\text{fund}} D_{\text{embed}}^2 K_p$$
- $P_{ae,h}$: Horizontal component of dynamic soil thrust $= P_{ae} \cos(\delta + \beta_w)$.
- $P_w$: Hydrostatic water thrust.

### 3.2 Factor of Safety against Overturning ($FS_o$)

$$FS_o = \frac{\sum M_{\text{resisting}}}{\sum M_{\text{overturning}}}$$

Calculated about the front bottom toe edge:
- **Resisting Moments ($\sum M_R$):** Wall stem dead weight, footing slab weight, soil prism on heel, and vertical component of active thrust ($P_{ae,v} \cdot B$).
- **Overturning Moments ($\sum M_O$):** Static horizontal thrust $P_{ah} \cdot (H/3)$, dynamic increment $\Delta P_{ae,h} \cdot (0.6H)$, and hydrostatic water thrust $P_w \cdot (h_w/3)$.

### 3.3 Subgrade Bearing Capacity & Eccentricity
The resultant location $x_R$ along the base from the toe is:

$$x_R = \frac{\sum M_R - \sum M_O}{V_{\text{eff}}}$$

The load eccentricity $e = \frac{B}{2} - x_R$. For no base tension (middle third rule), $e \le B/6$.

The effective footing width is $B' = B - 2e$. Ultimate bearing capacity $q_{\text{ult}}$ is evaluated using Meyerhof, Hansen, and Vesic methods:

$$q_{\text{ult}} = c N_c s_c i_c + q N_q s_q i_q + \frac{1}{2} \gamma_{\text{fund}} B' N_\gamma s_\gamma i_\gamma$$

$$FS_{\text{bearing}} = \frac{q_{\text{ult}}}{q_{\max}}$$

---

## 4. Coupled Environmental Disasters (Floods & Liquefaction)

1. **Phreatic Water Surface & Hydrostatic Thrust:**
   For water table depth $H_w$ below the backfill crest, the submerged depth is $h_w = \max(0, H - H_w)$.
   $$P_w = \frac{1}{2} \gamma_w h_w^2 \quad (\gamma_w = 9.81\text{ kN/m}^3)$$
   Below the water table, effective soil unit weight is buoyant: $\gamma' = \gamma_{\text{sat}} - \gamma_w$.

2. **Non-Linear Liquefaction Degradation ($r_u$):**
   Under high pore-water pressure ratio $r_u = \Delta u / \sigma'_{v0} \in [0.0, 1.0]$, effective soil shear strength degrades:
   $$\phi'_{\text{eff}} = \arctan\left( (1.0 - r_u^{0.75}) \tan\phi \right)$$
   As $r_u \to 1.0$, effective friction drops toward zero, driving dynamic earth pressure to fluid-like hydrostatic levels and drastically reducing sliding safety.

---

## 5. Structural Concrete Mechanics & ACI 318 Design

### 5.1 Continuous Shear $V(y)$ and Moment $M(y)$ Distributions
Along the retaining wall stem from crest ($y=H_s$) down to base junction ($y=0$):

$$V(y) = \int_y^{H_s} \left[ p_{\text{soil}}(\eta) + p_{\text{water}}(\eta) + t(\eta)\gamma_c k_h \right] d\eta$$

$$M(y) = \int_y^{H_s} V(\eta) d\eta$$

- **Boundary Invariants:** $M(H_s) = 0.0$, $V(H_s) = 0.0$; peak values occur at the base junction $y=0$.
- **Differential Equilibrium Invariant:** $\frac{dM}{dy} = -V(y)$.

### 5.2 Elastic Flexural Tensile Stress & Cracking
Across the linearly tapered stem thickness $t(y) = t_{\text{base}} - \frac{y}{H_s}(t_{\text{base}} - t_{\text{top}})$:

$$\sigma_t(y) = \frac{M(y)}{Z(y)} = \frac{6 M(y)}{b \cdot t(y)^2}$$

Cracking is predicted when peak flexural tensile stress exceeds the ACI 318 modulus of rupture:

$$f_r = 0.62 \lambda \sqrt{f'_c} \quad (\text{MPa})$$

### 5.3 Flexural Reinforcement Demand (Whitney Stress Block)
Factored bending moment $M_u = 1.2 M_{\text{dead}} + 1.6 M_{\text{earth}} + 1.0 M_{\text{seismic}}$.

Required steel area $A_s$ (per meter of wall):

$$A_s = \frac{M_u}{\phi_{\text{flex}} f_y (d - a/2)}, \quad a = \frac{A_s f_y}{0.85 f'_c b}$$

Enforcing minimum code reinforcement:
$$\rho_{\min} = \max\left( \frac{0.25\sqrt{f'_c}}{f_y}, \frac{1.4}{f_y} \right), \quad A_{s,\min} = \rho_{\min} b d$$
Temperature & shrinkage minimum: $A_{s,\text{temp}} = 0.0018 b h$.

---

## 6. Earthquake Signals & Newmark Sliding Block Analysis

### 6.1 Yield Acceleration ($k_y$)
The critical horizontal yield acceleration coefficient $k_y$ (in $g$) at which sliding factor of safety becomes incipient ($FS_s = 1.0$):

$$k_y = \frac{\sum R - P_{ah}}{W_{\text{total}}}$$

Where $W_{\text{total}}$ is the total sliding mass (concrete stem, footing, shear key, and heel backfill soil block).

### 6.2 Newmark (1965) Numerical Double-Integration
During active seismic ground shaking $a(t)$:
- If ground acceleration is sub-yield ($a(t) \le k_y g$), **no permanent displacement accumulates** ($u(t) = 0$).
- When ground acceleration exceeds yield ($a(t) > k_y g$), downhill relative sliding acceleration develops:
  $$\ddot{u}_{\text{rel}}(t) = a(t) - k_y \cdot g$$
  $$\dot{u}_{\text{rel}}(t) = \int (\ddot{u}_{\text{rel}}) dt$$
- When $\dot{u}_{\text{rel}}$ drops to zero, the block comes to rest until the next cycle. Double-integrating relative velocity yields irreversible, **monotonically non-decreasing** cumulative downhill slip $u(t)$ in centimeters.

---

## 7. Deep Continuum FEA with KratosMultiphysics

### 7.1 Coupled Hydromechanical Formulation ($u-p$)
The continuum solver discretizes Biot's equations of dynamic consolidation:

$$\nabla \cdot \boldsymbol{\sigma}' - \nabla p + \rho \mathbf{b} = \rho \ddot{\mathbf{u}}$$

$$\nabla \cdot \dot{\mathbf{u}} + \nabla \cdot \left( -\frac{\mathbf{k}}{\gamma_w} \nabla p \right) = \frac{\dot{p}}{Q}$$

Where:
- $\mathbf{u}$: Solid soil skeleton displacement vector.
- $p$: Pore-water pressure scalar field.
- $\boldsymbol{\sigma}'$: Effective Cauchy stress tensor.
- $\mathbf{k}$: Hydraulic permeability tensor.

### 7.2 Lysmer-Kuhlemeyer Viscous Absorbing Boundaries
To model a semi-infinite soil domain without reflecting artificial boundary shockwaves back into the retaining wall, viscous dashpot stresses are applied at truncated boundaries:

$$\sigma_n = C_p \cdot \dot{u}_n = (\rho V_p) \cdot \dot{u}_n$$

$$\tau_t = C_s \cdot \dot{u}_t = (\rho V_s) \cdot \dot{u}_t$$

Where:
- $V_p = \sqrt{\frac{E(1-\nu)}{\rho(1+\nu)(1-2\nu)}}$ (P-wave velocity).
- $V_s = \sqrt{\frac{E}{2\rho(1+\nu)}}$ (S-wave velocity).
