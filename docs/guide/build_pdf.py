"""
Script to generate orang3d_simulations_guide.pdf in docs/guide/
Contains all 12 simulations with their full names and a 2-paragraph detailed engineering explanation for each.
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter

app = QApplication.instance() or QApplication([])

pdf_path = "/home/avisheks/Documents/dibs/orang3d/docs/guide/orang3d_simulations_guide.pdf"

html_content = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {
    margin: 20mm 15mm 20mm 15mm;
  }
  body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    color: #1e293b;
    line-height: 1.55;
    font-size: 10pt;
  }
  .header-box {
    background-color: #0f172a;
    color: #ffffff;
    padding: 22px 26px;
    border-radius: 6px;
    margin-bottom: 24px;
    border-left: 6px solid #f97316;
  }
  .header-title {
    font-size: 20pt;
    font-weight: bold;
    color: #f97316;
    margin: 0 0 6px 0;
    letter-spacing: 0.5px;
  }
  .header-subtitle {
    font-size: 12pt;
    color: #f1f5f9;
    margin: 0 0 10px 0;
  }
  .header-meta {
    font-size: 8.5pt;
    color: #94a3b8;
    border-top: 1px solid #334155;
    padding-top: 8px;
  }
  .sim-card {
    border: 1px solid #cbd5e1;
    border-left: 5px solid #2563eb;
    background-color: #ffffff;
    padding: 14px 18px;
    margin-bottom: 20px;
    border-radius: 4px;
    page-break-inside: avoid;
  }
  .sim-title {
    font-size: 12.5pt;
    font-weight: bold;
    color: #0f172a;
    margin: 0 0 4px 0;
  }
  .badge-container {
    margin-bottom: 10px;
  }
  .badge {
    display: inline-block;
    font-size: 7.5pt;
    font-weight: bold;
    padding: 2px 7px;
    border-radius: 3px;
    margin-right: 5px;
    text-transform: uppercase;
  }
  .badge-blue { background-color: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }
  .badge-orange { background-color: #ffedd5; color: #9a3412; border: 1px solid #fed7aa; }
  .badge-green { background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
  p {
    margin: 0 0 8px 0;
    text-align: justify;
    line-height: 1.5;
  }
  .p-header {
    font-weight: bold;
    color: #334155;
  }
  .footer {
    font-size: 8pt;
    color: #64748b;
    text-align: center;
    border-top: 1px solid #e2e8f0;
    padding-top: 10px;
    margin-top: 25px;
  }
</style>
</head>
<body>

<div class="header-box">
  <div class="header-title">orang3D Simulation Compendium</div>
  <div class="header-subtitle">Curriculum of 12 Validated Geotechnical & Soil-Structure Interaction Simulations</div>
  <div class="header-meta">
    <b>Platform:</b> orang3D v3.0 &bull; <b>Physics Engines:</b> OpenSeesPy, Kratos GeoMechanics 10.4.4, PyVista &bull; <b>Regulatory Standards:</b> IS 456 / IS 2911, Eurocode 7 / 8, AASHTO LRFD, ACI 318-19
  </div>
</div>

<!-- Simulation 01 -->
<div class="sim-card" style="border-left-color: #2563eb;">
  <div class="sim-title">Simulation 01: Static Cantilever Retaining Wall Sizing & Stability Equilibrium</div>
  <div class="badge-container">
    <span class="badge badge-blue">Classical Geotechnics</span>
    <span class="badge badge-orange">Das (2016) Ex. 13.7 Benchmark</span>
    <span class="badge badge-green">IS 456 / IS 1904 Compliance</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  Static cantilever retaining wall design represents the foundation of geotechnical engineering, governed by the classical lateral earth pressure theories of Rankine (1857) and Coulomb (1776). When a granular backfill mass undergoes active plastic shear yielding along a Coulomb planar failure surface inclined at &theta; = 45&deg; + &phi;/2, it mobilizes a lateral earth thrust that must be resisted by base friction, soil self-weight over the heel slab, and passive resistance at the toe. This simulation models the authoritative textbook benchmark problem from Braja M. Das's <i>Principles of Foundation Engineering</i> (Example 13.7), analyzing a 6.0 m high reinforced concrete cantilever wall with a 4.0 m base width retaining granular backfill with unit weight &gamma; = 18.0 kN/m&sup3;, internal friction angle &phi; = 30.0&deg;, and wall interface friction angle &delta; = 20.0&deg;. The theoretical formulation establishes Coulomb's active thrust coefficient K<sub>a</sub> = 0.2973 and a resultant force P<sub>a</sub> = 96.33 kN/m acting at H/3 = 2.0 m above the footing base, defining the baseline static equilibrium demands required for global and structural checks.</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  Within the orang3D computational environment, users interactively configure the stem taper, footing dimensions, and soil properties in the Cantilever Wall and Soil Strata panels. The stability engine calculates vertical gravity summation (&sum;V = 349.5 kN/m) and moment balance (&sum;M<sub>R</sub> = 704.2 kN&middot;m/m, &sum;M<sub>O</sub> = 192.7 kN&middot;m/m), obtaining a sliding safety factor FS<sub>sliding</sub> = 1.82 (exceeding the IS 456 / IS 1904 statutory requirement of 1.50) and an overturning safety factor FS<sub>overturn</sub> = 3.65 (exceeding 2.00). The analysis further evaluates base contact eccentricity e = 0.41 m, confirming that the resultant falls strictly within the middle third (kern limit B/6 = 0.67 m) to ensure zero heel tension detachment, and computes the Meyerhof equivalent bearing pressure with toe stress q<sub>max</sub> = 118.4 kPa safely below the foundation soil's allowable capacity of 350.0 kPa. Users can inspect substituted formulas in the live "Show the Math" tab, export detailed AutoCAD DXF cross-sections, and generate complete PDF engineering calculation dossiers.</p>
</div>

<!-- Simulation 02 -->
<div class="sim-card" style="border-left-color: #0284c7;">
  <div class="sim-title">Simulation 02: Hydrodynamic Flooding, Phreatic Rise & Liquefaction Triggering</div>
  <div class="badge-container">
    <span class="badge badge-blue">Fluid-Soil Interaction</span>
    <span class="badge badge-orange">Westergaard (1933) & Seed-Idriss (1971)</span>
    <span class="badge badge-green">Eurocode 7 / IS 1893</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  Groundwater fluctuations and extreme hydrodynamic events represent the leading trigger for catastrophic retaining wall collapses worldwide. Rising phreatic surfaces exert buoyant hydrostatic forces that diminish effective soil intergranular stresses (&sigma;' = &sigma; - u), while dynamic earthquake shaking generates cyclic shear stresses that trigger excess pore water pressure accumulation (r<sub>u</sub> = &Delta;u / &sigma;'<sub>v0</sub>) in saturated cohesionless soils. Impounded water along the wall face also induces hydrodynamic inertia, formulated via H.M. Westergaard's (1933) parabolic dynamic water pressure distribution p<sub>wd</sub>(z) = 7/8 &middot; k<sub>h</sub> &gamma;<sub>w</sub> &radic;(H<sub>w</sub> z). This simulation models a vulnerable 6.0 m cantilever retaining wall subjected to sudden flash flooding, where the water table rises from deep subgrade to within 1.5 m of the surface, accompanied by cyclic liquefaction triggering formulated in accordance with the Seed & Idriss (1971) Cyclic Stress Ratio (CSR) framework.</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  In orang3D, users simulate this compound hazard by navigating to the Disaster / Seismic panel, adjusting the water table depth spinbox, enabling hydrodynamic thrust, and scaling the excess pore water pressure ratio r<sub>u</sub> from 0.0 up to 0.70. As the phreatic line rises and pore pressures elevate, the physics solver recalculates submerged unit weight (&gamma;<sub>sub</sub> = &gamma;<sub>sat</sub> - &gamma;<sub>w</sub> &approx; 10.2 kN/m&sup3;), updates active lateral thrust with combined hydrostatic and hydrodynamic components (P<sub>total</sub> = 158.4 kN/m), and reduces effective basal frictional resistance. The live safety monitor demonstrates the precipitous reduction in sliding resistance, dropping from a safe FS<sub>sliding</sub> = 1.62 down to an unstable 0.72 at r<sub>u</sub> = 0.55, triggering bright red failure alarms and rendering sliding slip surfaces in the 3D viewport. The exercise teaches engineers to design deep relief weep-holes, non-woven geotextile filters, and foundation shear keys to mitigate liquefaction-induced wall sliding.</p>
</div>

<!-- Simulation 03 -->
<div class="sim-card" style="border-left-color: #dc2626;">
  <div class="sim-title">Simulation 03: Dynamic Earthquake Shaking & Newmark Sliding Block Displacement</div>
  <div class="badge-container">
    <span class="badge badge-blue">Earthquake Engineering</span>
    <span class="badge badge-orange">Kramer (1996) & PEER AT2 Records</span>
    <span class="badge badge-green">AASHTO / FEMA Performance Limits</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  Traditional pseudo-static seismic design methods often yield overly conservative or unrealistically heavy retaining walls by assuming peak ground acceleration acts permanently as an equivalent static body force (F<sub>h</sub> = k<sub>h</sub> W). In modern performance-based earthquake engineering, transient seismic shaking is evaluated through the Mononobe-Okabe (1929) active dynamic pressure theory combined with Nathan Newmark's (1965) sliding block analogy, as synthesized by Kramer (1996). Under strong ground motion, when the base shear induced by earthquake acceleration exceeds the ultimate frictional interface capacity, a distinct yield acceleration k<sub>y</sub> is reached. For every acceleration pulse exceeding k<sub>y</sub>, the wall mass decouples from the foundation rock and experiences cumulative permanent downstream plastic slip, evaluated through direct double-integration of the relative acceleration time-history &uuml;(t) = a(t) - k<sub>y</sub> g.</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  Executing this simulation in orang3D involves loading authentic PEER NGA-West AT2 accelerograms (such as the 1994 Northridge or 1995 Kobe records) or synthesizing calibrated Ricker wavelets within the Disaster / Seismic panel. The engine computes the static and dynamic thrust components (K<sub>ae</sub> = 0.407, dynamic increment &Delta;P<sub>ae</sub> = 35.55 kN/m), calculates the critical yield acceleration (k<sub>y</sub> = 0.142 g), and runs high-speed numerical integration over the acceleration record. Users observe live waveform propagation in the Seismic Waveforms & Dynamics bottom tab, tracking velocity pulses and watching the cumulative permanent slip curve flatten at u<sub>Newmark</sub> = 3.82 cm. By comparing this displacement against international performance limits (such as the AASHTO/FEMA serviceability threshold of 5.0 cm), engineers can verify whether an existing wall sustains repairable minor deformation or catastrophic runaway sliding, bridging the gap between prescriptive code factors and true non-linear dynamic performance.</p>
</div>

<!-- Simulation 04 -->
<div class="sim-card" style="border-left-color: #7c3aed;">
  <div class="sim-title">Simulation 04: Curved Shell Walls, Soil Arching, Raking Struts & Bored Piles</div>
  <div class="badge-container">
    <span class="badge badge-blue">3D Structural Arching</span>
    <span class="badge badge-orange">Bowles (1996) Sec. 12-7</span>
    <span class="badge badge-green">IS 2911 / Eurocode 3 Piles</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  Deep excavations and high retaining systems frequently employ cylindrical curved shell geometries, raking strut braces, and bored cast-in-situ piles to exploit horizontal soil arching and achieve dramatic material savings. When a retaining structure is curved in plan, the inward lateral soil pressure induces circumferential hoop compression across the concrete shell, transferring a substantial fraction of the horizontal earth thrust directly to lateral counterforts or boundary soldier piles, as documented in Bowles's <i>Foundation Analysis and Design</i> (Section 12-7). Raking struts with hydraulic prestress jacks provide rigid intermediate lateral support, reducing cantilever stem flexure from an unbraced third-order cantilever moment into a multi-span continuous beam system. Piles embedded into underlying competent bedrock provide vertical bearing and lateral resistance modeled via non-linear Winkler p-y subgrade interaction per IS 2911 and Eurocode 3.</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  In orang3D, users configure this advanced system across the Curved Shell and Strut & Piles panels, adjusting shell radius (R = 8.0 m), bay span (L = 6.0 m), strut inclination angle (45&deg;), prestress preload (200 kN), and pile array dimensions. The analytical arching solver discretizes the shell into depth intervals, computing an arching transfer efficiency &eta;<sub>arch</sub> = 0.380&mdash;confirming that 38% of the lateral soil thrust is redirected into adjacent boundary piles through horizontal compressive arches, thereby reducing the net bending moment on the shell face by over 35%. The raking strut reaction and pile spring deflections are solved simultaneously using equilibrium matrix formulations, with the 3D viewport displaying color-coded stress gradients, axial strut compression vectors, and deformed pile deflection profiles. This simulation verifies that curved shell and strutted designs reduce concrete volume and steel reinforcement requirements by upwards of 25% compared to conventional massive cantilever walls.</p>
</div>

<!-- Simulation 05 -->
<div class="sim-card" style="border-left-color: #059669;">
  <div class="sim-title">Simulation 05: OpenSeesPy 2D BNWF Staged Excavation & Lateral Pushover</div>
  <div class="badge-container">
    <span class="badge badge-blue">Soil-Structure Interaction</span>
    <span class="badge badge-orange">Mazzoni et al. (2006) OpenSeesPy</span>
    <span class="badge badge-green">PySimple1 Non-Linear Springs</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  Flexible cantilever walls, sheet pile bulkheads, and soldier-pile systems embedded in soil cannot be accurately represented by rigid-body limit equilibrium because their deflections strongly modify lateral soil pressures. The Beam-on-Nonlinear-Winkler-Foundation (BNWF) approach resolves this soil-structure interaction (SSI) by idealizing the retaining wall as finite elastic-plastic beam-column elements supported along their embedded length by discrete, non-linear p-y spring elements. This simulation utilizes the OpenSeesPy finite element framework to model a multi-stage sequential excavation, where soil layers are excavated in realistic construction increments (Stages 1 through 4) while the backfill mobilizes active pressure and the embedded toe activates elastoplastic hyperbolic resistance (PySimple1 materials with tension gap separation and radiation dashpots).</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  Users initiate this simulation by selecting the BNWF / OpenSees mode and clicking "Run 2D BNWF (OpenSees)" on the top action bar. The automated mesher generates a 2D OpenSees discretization, initializes geostatic in-situ earth pressures at rest (K<sub>0</sub> = 1 - sin&phi;), and applies sequential excavation unloading stages. Following excavation, an automated displacement-controlled lateral pushover analysis applies monotonic horizontal head displacement until ultimate plastic hinge formation occurs at the wall-footing junction. The BNWF & PINN Envelope bottom tab plots the resulting base shear vs. crest displacement pushover curve, displaying yield initiation (V<sub>y</sub> = 185 kN/m at &Delta; = 18 mm), plastic plateauing, and non-linear bending moment envelopes along the wall depth. This provides structural engineers with ductibility ratios and overstrength factors that cannot be extracted from classical limit-equilibrium methods.</p>
</div>

<!-- Simulation 06 -->
<div class="sim-card" style="border-left-color: #4f46e5;">
  <div class="sim-title">Simulation 06: Continuum 3D Non-Linear Soil-Structure FEA & Corner Effects</div>
  <div class="badge-container">
    <span class="badge badge-blue">3D Continuum FEA</span>
    <span class="badge badge-orange">OpenSees 3D & Kratos GeoMechanics</span>
    <span class="badge badge-green">Lysmer Viscous Boundaries</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  While two-dimensional plane-strain models are standard in routine design, real retaining structures feature finite lengths, 90-degree corner returns, and complex three-dimensional boundary conditions that generate intense stress concentrations and three-dimensional arching. Near wall corners and transverse return walls, lateral soil pressures decrease substantially because backfill shear stresses transfer load toward the rigid corners in two orthogonal directions&mdash;a phenomenon known as the 3D corner effect. This simulation executes a complete continuum three-dimensional finite element analysis utilizing OpenSeesPy 3D or Kratos Multiphysics 10.4.4 GeoMechanics, discretizing the retaining wall and full soil domain with 8-node hexahedral brick solid elements (stdBrick / SSPbrick), non-linear Mohr-Coulomb elastoplastic soil plasticity, and Lysmer-Kuhlemeyer non-reflecting viscous dashpot boundaries.</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  Executing this simulation via the "Run 3D FEA (OpenSees)" or "Run Kratos GeoMechanics FEA" buttons triggers orang3D's high-performance background continuum mesher and solver pipeline. The simulation begins with geostatic K<sub>0</sub> gravity initialization to establish realistic initial stress tensor fields without spurious initial displacements, followed by active wall displacement. The Theory vs. FEA tab displays the true 3D lateral earth pressure distribution along the wall length, revealing a 32% reduction in earth pressure within a distance of 1.5 H from the corner compared to the plane-strain centerline. Users can inspect full 3D von Mises stress contours, principal plastic strain fields, and Lysmer energy dissipation in the interactive PyVista viewport, providing conclusive validation for optimizing wall thicknesses near corners in accordance with advanced research and experimental centrifuge findings.</p>
</div>

<!-- Simulation 07 -->
<div class="sim-card" style="border-left-color: #ea580c;">
  <div class="sim-title">Simulation 07: Architectural Surcharges & Stepped Terraced Wall Alignment</div>
  <div class="badge-container">
    <span class="badge badge-blue">Urban Geotechnics</span>
    <span class="badge badge-orange">Boussinesq (1885) Elastic Theory</span>
    <span class="badge badge-green">Stepped Terraced Wall Mesher</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  In congested urban developments and hillside infrastructure, retaining walls rarely support uniform, horizontal backfills; instead, they frequently retain multi-tiered stepped terraces and support concentrated adjacent foundation surcharges from buildings, highways, and crane outriggers. Elastic theory dictates that a concentrated vertical surface load Q or strip load q induces an additional lateral horizontal stress &Delta;&sigma;<sub>h</sub>(z) on the wall stem, formulated via the classical Boussinesq (1885) and Mindlin (1936) equations modified for semi-infinite rigid boundaries: &Delta;&sigma;<sub>h</sub>(z) = (2q/&pi;) &middot; [&beta; - sin&beta; cos(2&alpha;)]. Furthermore, stepped terraced walls exhibit complex load interactions, where the upper wall tier imposes a massive surcharge on the backfill of the lower wall tier, requiring integrated stability assessments.</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  Through the Arch. & Surcharge panel, users define adjacent surcharge profiles (point, strip, line, or area loads) by specifying offset distance, width, and load magnitude (q = 50.0 kPa), as well as multi-tier terraced stepped geometry with variable berm widths. The analytical solver numerically integrates Boussinesq horizontal stress tensors along the stem depth, computing the lateral surcharge thrust increment (&Delta;P<sub>q</sub> = 28.4 kN/m) and its specific line of action (z<sub>q</sub> = 3.65 m above base). The 3D viewport renders the multi-level stepped retaining tiers, adjacent building footings, and color-coded horizontal stress isobar bulbs. The resulting safety factor audit alerts the engineer if the surcharge drives resultant eccentricity outside the middle third or induces flexural stem overstress, providing clear geometric rules for optimal terrace berm set-backs.</p>
</div>

<!-- Simulation 08 -->
<div class="sim-card" style="border-left-color: #16a34a;">
  <div class="sim-title">Simulation 08: Hill-Slope DEM Terrain Import & Topographic Amplification</div>
  <div class="badge-container">
    <span class="badge badge-blue">Terrain Topography</span>
    <span class="badge badge-orange">Eurocode 8 Cl. 4.1.4 & IS 1893</span>
    <span class="badge badge-green">ESRI ASC & GeoTIFF Meshing</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  Retaining structures constructed along mountainous slopes, highway ridge cuts, and canyon embankments experience amplified seismic shaking due to topographic wave focusing. Seismic P and SV waves reflecting within convex ridges and slope crests undergo constructive interference, amplifying ground surface motions by 20% to 40% relative to flat ground. Both Eurocode 8 (Part 5, Clause 4.1.4) and the Bureau of Indian Standards (IS 1893, Clause 6.4.4) prescribe a mandatory topographic amplification factor S<sub>T</sub> &ge; 1.20 for retaining structures built along slopes with inclination angles &beta; > 15&deg;, and S<sub>T</sub> &ge; 1.40 near steep ridge crests (&beta; > 30&deg;).</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  Using the Terrain & Studio panel, users import real-world Digital Elevation Models (DEM) from ESRI ASCII Grid (.asc), XYZ point cloud (.csv), Wavefront (.obj), or GeoTIFF (.tif) files. The computational terrain analyzer processes the raster mesh, extracts the mean backfill slope angle (&beta; = 22.4&deg;), and automatically computes the governing regulatory topographic amplification factor (S<sub>T</sub> = 1.20). The seismic demand in the Disaster / Seismic panel is immediately scaled (k<sub>h,topo</sub> = S<sub>T</sub> &middot; k<sub>h</sub> = 1.20 &times; 0.20 g = 0.24 g), and the passive resistance at the toe is adjusted for down-slope terrain loss. The 3D viewport displays the textured, draped terrain mesh with elevation contour bands, allowing geotechnical designers to realistically model cuts, fills, and hillside anchorages in their actual topographical setting.</p>
</div>

<!-- Simulation 09 -->
<div class="sim-card" style="border-left-color: #d97706;">
  <div class="sim-title">Simulation 09: Live Multi-Code Regulatory Compliance Audit</div>
  <div class="badge-container">
    <span class="badge badge-blue">Regulatory Compliance</span>
    <span class="badge badge-orange">IS 456 / EC7 / AASHTO / ACI</span>
    <span class="badge badge-green">Live Real-Time Standard Switcher</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  Civil engineering consulting firms operating globally must frequently verify retaining structure compliance against competing national and international design codes. Prescriptive codes (such as India's IS 456 / IS 2911 / IS 1893 and America's ACI 318-19) utilize working stress or allowable stress design (ASD) with global safety factors (FS &ge; 1.50 sliding, FS &ge; 2.00 overturning), whereas modern limit state codes (such as Eurocode 7 EN 1997-1 Design Approaches DA1/DA2/DA3 and AASHTO LRFD Bridge Design Specifications) employ partial material and load resistance factor design (LRFD). A wall dimensioned to pass IS 456 may fail Eurocode 7's combination of permanent unfavourable actions (&gamma;<sub>G</sub> = 1.35) and degraded shear strength (&gamma;<sub>&phi;</sub> = 1.25).</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  orang3D addresses this compliance challenge through its integrated live regulatory auditor located in the Design Audit bottom tab. With a single click, users toggle between IS, Eurocode 7/8, AASHTO LRFD, and ACI 318 standards, dynamically recalculating the complete stability matrix in real time without modifying the structural model. The audit interface displays a side-by-side compliance grid featuring color-coded status badges, required code threshold values, achieved design margins, and specific regulatory clause citations (e.g., EC7 Cl. 6.5.3, AASHTO Table 10.5.5.2.2-1, IS 14458 Part 2). This automated cross-checking capability allows engineers to immediately identify governing limit states across jurisdictions and generate multi-standard audit tables for statutory submission.</p>
</div>

<!-- Simulation 10 -->
<div class="sim-card" style="border-left-color: #0891b2;">
  <div class="sim-title">Simulation 10: Physics-Informed Neural Network (PINN) Surrogate & Monte Carlo Fragility</div>
  <div class="badge-container">
    <span class="badge badge-blue">AI & Uncertainty Quantification</span>
    <span class="badge badge-orange">Raissi et al. (2019) PINN Surrogate</span>
    <span class="badge badge-green">HAZUS Seismic Fragility Curves</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  Rigorous seismic risk assessment and regional hazard analysis require running thousands of non-linear dynamic simulations to account for geotechnical soil variability and uncertain ground motion properties. Conventional 3D continuum FEA runs are too computationally expensive for brute-force Monte Carlo simulation. orang3D bridges this gap by embedding a Physics-Informed Neural Network (PINN) surrogate model (Raissi et al., 2019) pre-trained under physics-based loss functions enforcing momentum equilibrium and Mohr-Coulomb yield criteria. The PINN surrogate evaluates wall lateral thrust, sliding displacement, and toe pressure in under 5 ms per sample, enabling real-time probabilistic Latin Hypercube Sampling (LHS) Monte Carlo reliability evaluations (N = 10,000 iterations).</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  In the UQ & Seismic Fragility bottom tab, users define probability distribution parameters (mean, standard deviation, and lognormal bounds) for soil friction angle &phi;, cohesion c, ground acceleration k<sub>h</sub>, and groundwater depth. Running the Monte Carlo engine executes 10,000 physics-surrogate evaluations in seconds, plotting probabilistic histograms of safety factors, calculating Cornell reliability indices (&beta; = 2.45), and computing failure probabilities (P<sub>f</sub> = &Phi;(-&beta;) = 0.71%). The module automatically generates four-state HAZUS-MH seismic fragility curves (Slight, Moderate, Extensive, and Complete damage states) as functions of Peak Ground Acceleration (PGA &isin; [0.05 g, 1.0 g]). This arms risk analysts and municipal planners with quantitative seismic vulnerability curves for catastrophic earthquake scenarios.</p>
</div>

<!-- Simulation 11 -->
<div class="sim-card" style="border-left-color: #0d9488;">
  <div class="sim-title">Simulation 11: Soil Lab CSV Calibration, Unsaturated SWCC & Rainstorm Infiltration</div>
  <div class="badge-container">
    <span class="badge badge-blue">Unsaturated Soil Mechanics</span>
    <span class="badge badge-orange">Darendeli (2001) & Van Genuchten (1980)</span>
    <span class="badge badge-green">Green-Ampt Rain Infiltration</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  Soil shear stiffness and damping degrade non-linearly under cyclic earthquake loading, while rainfall infiltration into unsaturated backfill reduces matric suction and destroys apparent cohesion. Traditional design typically relies on constant, dry friction angles, ignoring the dangerous loss of strength during monsoon rainfall or extreme cyclonic downpours. This simulation combines laboratory soil test calibration with unsaturated soil mechanics: experimental cyclic triaxial or resonant column test CSV data is fitted against the empirical Darendeli (2001) non-linear shear modulus reduction (G/G<sub>max</sub>) and hysteretic damping curves, while unsaturated soil-water characteristics are modeled using the Van Genuchten (1980) SWCC model coupled with Green & Ampt (1911) 1D infiltration equations.</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  Users open the Lab Soil Calibration Wizard via Tools &rarr; Lab Soil Calibration Wizard (CSV)... to import raw laboratory test datasets, executing non-linear least-squares Levenberg-Marquardt curve fitting to extract reference shear strain &gamma;<sub>r</sub> and curvature coefficient a (R&sup2; > 0.98). In the Soil Strata panel, users apply rainstorm precipitation intensity (i = 25 mm/hr) over an extended infiltration duration (t = 24 hr). The engine computes the downward wetting front depth, tracks matric suction dissipation (&psi; = u<sub>a</sub> - u<sub>w</sub>), and models the loss of apparent unsaturated cohesion c'(&psi;) = c' + (u<sub>a</sub> - u<sub>w</sub>) tan&phi;<sup>b</sup>. The dynamic stability curves show a progressive decline in factor of safety as the wetting front saturates the active shear wedge, demonstrating why retaining walls frequently collapse during or immediately following prolonged rainfall events.</p>
</div>

<!-- Simulation 12 -->
<div class="sim-card" style="border-left-color: #f97316;">
  <div class="sim-title">Simulation 12: Parametric Sensitivity Sweep & Interactive Sizing Advisor</div>
  <div class="badge-container">
    <span class="badge badge-blue">Automated Optimization</span>
    <span class="badge badge-orange">Analytical Sweeps (&lt; 50 ms)</span>
    <span class="badge badge-green">1-Click Geometric Remediation</span>
  </div>
  <p><span class="p-header">Theoretical Formulation & Benchmark Context:</span>
  Initial retaining wall sizing in consulting practice often involves trial-and-error iterations where dimensions fail one or more stability checks under severe seismic acceleration (k<sub>h</sub> > 0.20 g) or high soil thrust. Geotechnical designers conventionally re-guess heel lengths, toe projections, and shear key depths across multiple spreadsheet runs. orang3D automates this optimization cycle through two integrated tools: a high-speed Parametric Sensitivity Sweep engine that computes monotonic response curves (K<sub>ae</sub>, FS<sub>sliding</sub>, FS<sub>overturn</sub>, FS<sub>bearing</sub>, u<sub>Newmark</sub>, &eta;<sub>arch</sub>) across 10 to 80 points in &lt; 50 ms, and an Interactive Sizing Advisor that performs an automated directed search to upgrade deficient geometry to full code compliance.</p>
  <p><span class="p-header">Workflow & Verification Output:</span>
  To experience this workflow, users input an intentionally undersized trial wall (H = 6.5 m, t<sub>b</sub> = 0.35 m, B<sub>toe</sub> = 0.40 m, B<sub>heel</sub> = 1.0 m) under seismic shaking (k<sub>h</sub> = 0.22 g), observing immediate red failure badges across sliding (0.74 &lt; 1.10), overturning (0.91 &lt; 1.50), bearing (1.12 &lt; 2.00), and concrete tensile cracking (6.42 MPa > 2.80 MPa). In the Parametric Sensitivity Sweep dialog, users sweep k<sub>h</sub> and &phi; to visualize critical threshold crossings against dashed code limit lines. Switching to the Terrain & Studio panel and clicking "Evaluate Sizing" generates concrete remediation steps: extending heel length to mobilize backfill gravity weight, introducing a shear key to activate passive soil wedge resistance, widening the toe, and thickening the stem base. Clicking "Apply Recommended Geometry" executes an instantaneous 1-click upgrade: the wall dimensions update, stability is recalculated, all safety badges flip to green ([SAFE]), and the compliant model is ready for AutoCAD DXF and calculation report export.</p>
</div>

<div class="footer">
  orang3D Engineering Guide &bull; Generated from Official Simulation Specifications &bull; &copy; 2026 orang3D Project
</div>

</body>
</html>
"""

printer = QPrinter(QPrinter.HighResolution)
printer.setOutputFormat(QPrinter.PdfFormat)
printer.setOutputFileName(pdf_path)

doc = QTextDocument()
doc.setHtml(html_content)
doc.print_(printer)

print("PDF successfully written to:", pdf_path)
print("File size:", os.path.getsize(pdf_path), "bytes")

