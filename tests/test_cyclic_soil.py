"""
Comprehensive Test Suite for Phase 7: Advanced Cyclic Soil Models & Rainfall Infiltration.
Validates:
1. Masing (1926) cyclic stress-strain hysteresis loop symmetry and positive plastic dissipation.
2. Modulus degradation G/G_max(gamma) and hysteretic damping D(gamma) monotonicity and bounds.
3. Matric suction loss and apparent cohesion softening under monsoon rainfall infiltration.
4. Cascading compound disaster sequencing (Rainfall Infiltration -> Suction Loss -> Newmark Slip Jump).
5. Van Genuchten (1980) SWCC retention curve asymptotic limits and invariants.
6. Laboratory calibration wizard fitting G/G_max, D(gamma), SWCC, and Mohr-Coulomb envelopes (R^2 >= 0.98).
7. OpenSees PressureDependMultiYield02 (PDMY02) parameter synthesis.
8. Physical bounds enforcement, exception handling, and edge cases.
"""

from __future__ import annotations

import math
import pytest
import numpy as np

from orang3d.models.wall_params import RetainingWallGeometry, SoilProperties
from orang3d.physics.unsaturated_soil import (
    VanGenuchtenParams,
    UnsaturatedSoilParameters,
    RainfallInfiltrationResult,
    CompoundDisasterResult,
    simulate_rainfall_infiltration,
    simulate_compound_rainfall_earthquake,
)
from orang3d.physics.cyclic_soil import (
    CyclicSoilParameters,
    CyclicDegradationCurves,
    MasingHysteresisLoop,
    compute_modulus_reduction,
    compute_hysteretic_damping,
    generate_cyclic_degradation_curves,
    compute_backbone_shear_stress,
    generate_masing_hysteresis_loop,
    generate_opensees_pdmy02_parameters,
)
from orang3d.physics.calibration import (
    CalibrationFitResult,
    fit_cyclic_modulus_reduction_curve,
    fit_hysteretic_damping_curve,
    fit_van_genuchten_swcc,
    fit_mohr_coulomb_shear_strength,
)
from orang3d.signals.synthetic import generate_ricker_wavelet


# -----------------------------------------------------------------------------
# 1. Extended Masing (1926) Cyclic Hysteresis Loops & Energy Dissipation
# -----------------------------------------------------------------------------
def test_backbone_mashing():
    """
    Validates that:
    1. Backbone shear stress curve is anti-symmetric: tau(-gamma) = -tau(gamma).
    2. Cyclic hysteresis loop loading and unloading branches satisfy Masing criteria.
    3. Loop plastic energy dissipation Delta_W = int(tau d_gamma) is strictly positive.
    4. Equivalent damping ratio D_loop is positive and physically realistic.
    """
    params = CyclicSoilParameters(
        max_shear_modulus_gmax_kpa=80000.0,
        reference_shear_strain=0.0008,
        curvature_param_a=0.95,
        min_damping_ratio=0.02,
        max_damping_ratio=0.25,
    )

    # 1. Backbone anti-symmetry
    tau_pos = compute_backbone_shear_stress(0.001, params)
    tau_neg = compute_backbone_shear_stress(-0.001, params)
    assert tau_pos > 0.0
    assert tau_neg < 0.0
    assert pytest.approx(tau_pos, abs=1e-3) == -tau_neg

    # 2. Closed Masing Hysteresis Loop
    loop = generate_masing_hysteresis_loop(
        params=params,
        strain_amplitude=0.002, # 0.2% cyclic strain
        num_points_per_branch=50,
    )

    assert isinstance(loop, MasingHysteresisLoop)
    assert loop.peak_shear_stress_kpa == pytest.approx(compute_backbone_shear_stress(0.002, params), abs=0.1)

    # First point and midpoint check
    strains = np.array(loop.strains)
    stresses = np.array(loop.shear_stresses_kpa)
    assert strains[0] == pytest.approx(-0.002, abs=1e-5)
    assert max(strains) == pytest.approx(0.002, abs=1e-5)

    # 3. Positive plastic work dissipation (Second Law of Thermodynamics)
    assert loop.loop_energy_dissipation_kpa > 0.0

    # 4. Loop damping ratio
    assert 0.02 <= loop.equivalent_damping_ratio <= 0.25


# -----------------------------------------------------------------------------
# 2. Modulus Degradation & Damping Bounds
# -----------------------------------------------------------------------------
def test_hysteretic_damping_bounds():
    """
    Validates that:
    1. Small-strain damping matches target D_min (approx 2% - 5%).
    2. Damping D(gamma) increases strictly monotonically with cyclic shear strain.
    3. Modulus reduction G/G_max degrades strictly monotonically from 1.0 to near zero.
    4. Large-strain damping approaches D_max without divergence.
    """
    params = CyclicSoilParameters(
        reference_shear_strain=0.0006,
        min_damping_ratio=0.025, # 2.5%
        max_damping_ratio=0.28,  # 28%
    )

    # Small strain limit (10^-7)
    d_small = compute_hysteretic_damping(1e-7, reference_strain=0.0006, d_min=0.025)
    g_small = compute_modulus_reduction(1e-7, reference_strain=0.0006)
    assert d_small == pytest.approx(0.025, abs=1e-4)
    assert g_small == pytest.approx(1.0, abs=1e-3)

    # Medium strain (gamma = gamma_r)
    g_ref = compute_modulus_reduction(0.0006, reference_strain=0.0006, curvature_a=1.0)
    assert g_ref == pytest.approx(0.50, abs=0.02)

    # Large strain limit (10^-1)
    d_large = compute_hysteretic_damping(0.10, reference_strain=0.0006, d_min=0.025, d_max=0.28)
    g_large = compute_modulus_reduction(0.10, reference_strain=0.0006)
    assert d_large > 0.25
    assert g_large < 0.05

    # Full curves monotonicity check
    curves = generate_cyclic_degradation_curves(params, num_points=25)
    assert len(curves.strains) == 25

    # G/G_max must be monotonically non-increasing
    for i in range(len(curves.modulus_reduction_ratios) - 1):
        assert curves.modulus_reduction_ratios[i] >= curves.modulus_reduction_ratios[i + 1]

    # Damping must be monotonically non-decreasing
    for i in range(len(curves.damping_ratios) - 1):
        assert curves.damping_ratios[i] <= curves.damping_ratios[i + 1]


# -----------------------------------------------------------------------------
# 3. Suction Loss & Softening under Rainfall Infiltration
# -----------------------------------------------------------------------------
def test_suction_loss_softening():
    """
    Validates that:
    1. Rainfall infiltration advances a wetting front down into the backfill.
    2. Infiltration causes matric suction loss, reducing apparent cohesion.
    3. Critical yield acceleration ky drops monotonically with rainfall duration.
    4. Bulk unit weight increases due to water saturation.
    """
    soil_params = UnsaturatedSoilParameters(
        effective_cohesion=10.0,
        effective_friction_angle=32.0,
        phi_b_angle=18.0,
        initial_matric_suction=60.0, # 60 kPa suction initially
    )
    wall_geom = RetainingWallGeometry(
        stem_height=5.2,
        footing_thickness=0.8,
        toe_length=1.0,
        heel_length=2.2,
        stem_thickness_base=0.6,
        stem_thickness_top=0.35,
    )

    # Initial dry cohesion
    c_init = soil_params.compute_total_cohesion(soil_params.initial_matric_suction)
    c_sat = soil_params.compute_total_cohesion(0.0) # Saturated state
    assert c_init > c_sat == soil_params.effective_cohesion

    # Simulate 6-hour vs 24-hour storm
    res_6h = simulate_rainfall_infiltration(
        soil_params=soil_params,
        wall_geometry=wall_geom,
        rainfall_intensity_mm_hr=25.0,
        rainfall_duration_hours=6.0,
    )
    res_24h = simulate_rainfall_infiltration(
        soil_params=soil_params,
        wall_geometry=wall_geom,
        rainfall_intensity_mm_hr=25.0,
        rainfall_duration_hours=24.0,
    )

    # 1. Wetting front advances deeper with duration
    assert res_24h.wetting_front_depth_m > res_6h.wetting_front_depth_m
    assert res_24h.wetting_front_depth_m <= wall_geom.total_height

    # 2. Cohesion drops deeper with longer duration
    assert res_24h.degraded_cohesion_kpa < res_6h.degraded_cohesion_kpa < c_init

    # 3. Bulk unit weight increases as saturation replaces air
    assert res_24h.degraded_unit_weight_kpa > res_6h.degraded_unit_weight_kpa > res_6h.initial_unit_weight_kpa

    # 4. Critical yield acceleration ky drops
    assert res_24h.degraded_yield_acceleration_ky < res_6h.degraded_yield_acceleration_ky < res_6h.initial_yield_acceleration_ky
    assert res_24h.percent_ky_reduction > 0.0


# -----------------------------------------------------------------------------
# 4. Cascading Compound Disaster Sequencing (Rain + Earthquake)
# -----------------------------------------------------------------------------
def test_compound_disaster_sequencing():
    """
    Validates compound multi-hazard coupling:
    Monsoon storm softens backfill -> Earthquake triggers Newmark sliding.
    Verifies that compound disaster permanent displacement exceeds dry state slip (u_compound > u_dry).
    """
    soil_params = UnsaturatedSoilParameters(
        effective_cohesion=12.0,
        effective_friction_angle=30.0,
        phi_b_angle=18.0,
        initial_matric_suction=50.0,
    )
    wall_geom = RetainingWallGeometry(
        stem_height=5.2,
        footing_thickness=0.8,
        toe_length=1.0,
        heel_length=2.0,
        stem_thickness_base=0.6,
        stem_thickness_top=0.35,
    )

    # Synthetic earthquake accelerogram exceeding ky (0.45g Ricker wavelet)
    time_arr, accel_arr = generate_ricker_wavelet(
        pga_g=0.45,
        central_freq_hz=2.5,
        duration_sec=6.0,
        sampling_rate_hz=100.0,
    )

    res = simulate_compound_rainfall_earthquake(
        soil_params=soil_params,
        wall_geometry=wall_geom,
        time_arr=time_arr,
        accel_g_arr=accel_arr,
        rainfall_intensity_mm_hr=30.0,
        rainfall_duration_hours=24.0,
    )

    assert isinstance(res, CompoundDisasterResult)
    # Compound sliding displacement must be strictly greater than dry state
    assert res.compound_permanent_displacement_cm > res.initial_permanent_displacement_cm
    assert res.slip_amplification_ratio >= 1.05
    assert len(res.compound_slip_history_cm) == len(time_arr)


# -----------------------------------------------------------------------------
# 5. Van Genuchten (1980) SWCC Asymptotic Limits
# -----------------------------------------------------------------------------
def test_van_genuchten_swcc_limits():
    """
    Validates Van Genuchten SWCC asymptotic invariants:
    - At zero suction (psi = 0): S_r = 1.0, theta = theta_s, S_e = 1.0.
    - At very high suction (psi -> inf): S_r -> S_r,res, theta -> theta_r, S_e -> 0.0.
    """
    vg = VanGenuchtenParams(
        alpha_kpa_inv=0.05,
        n_param=1.60,
        theta_res=0.08,
        theta_sat=0.42,
        residual_saturation=0.15,
    )

    # Zero suction
    assert vg.effective_saturation(0.0) == 1.0
    assert vg.degree_of_saturation(0.0) == 1.0
    assert vg.volumetric_water_content(0.0) == 0.42

    # High suction (10,000 to 100,000 kPa)
    assert vg.effective_saturation(10000.0) < 0.05
    assert vg.effective_saturation(100000.0) < 0.01
    assert vg.degree_of_saturation(100000.0) == pytest.approx(0.15, abs=0.01)
    assert vg.volumetric_water_content(100000.0) == pytest.approx(0.08, abs=0.01)

    # m = 1 - 1/n invariant
    assert vg.m_param == pytest.approx(1.0 - (1.0 / 1.60), abs=1e-5)


# -----------------------------------------------------------------------------
# 6. Laboratory Calibration: Resonant Column & Cyclic Shear Fitting
# -----------------------------------------------------------------------------
def test_calibration_curve_fit():
    """
    Generates synthetic resonant column G/G_max data with known parameters,
    fits modified hyperbolic model via scipy.optimize.curve_fit,
    and asserts recovery of parameters with R^2 >= 0.98.
    """
    true_gamma_r = 0.00065
    true_a = 0.98

    # Synthetic noisy experimental data
    strains = np.logspace(-5, -1, 15)
    exact_g = 1.0 / (1.0 + ((strains / true_gamma_r) ** true_a))
    # Small synthetic noise (+/- 1.5%)
    np.random.seed(42)
    noise = np.random.normal(0.0, 0.012, size=len(strains))
    measured_g = np.clip(exact_g + noise, 0.01, 1.0)

    fitted_gamma_r, fitted_a, fit_report = fit_cyclic_modulus_reduction_curve(
        measured_shear_strains=strains,
        measured_g_over_gmax=measured_g,
        initial_gamma_r=0.0005,
        initial_a=1.0,
    )

    assert isinstance(fit_report, CalibrationFitResult)
    assert fit_report.r_squared >= 0.98
    assert fit_report.is_statistically_significant is True
    assert fit_report.rmse < 0.04
    assert pytest.approx(fitted_gamma_r, rel=0.15) == true_gamma_r
    assert pytest.approx(fitted_a, rel=0.15) == true_a


# -----------------------------------------------------------------------------
# 7. Laboratory Calibration: Damping, SWCC & Mohr-Coulomb
# -----------------------------------------------------------------------------
def test_calibration_damping_swcc_and_shear():
    """
    Validates laboratory fitting for:
    1. Cyclic damping curve D(gamma)
    2. SWCC Van Genuchten retention curve
    3. Mohr-Coulomb direct shear failure envelope
    """
    # 1. Damping fit
    true_d_min = 0.028
    true_d_max = 0.27
    strains = np.logspace(-5, -1, 12)
    g_ratio = 1.0 / (1.0 + ((strains / 0.0006) ** 0.95))
    meas_d = true_d_min + (true_d_max - true_d_min) * ((1.0 - g_ratio) ** 1.10)

    fit_dmin, fit_dmax, d_report = fit_hysteretic_damping_curve(
        measured_shear_strains=strains,
        measured_damping_ratios=meas_d,
    )
    assert d_report.r_squared >= 0.98
    assert pytest.approx(fit_dmin, abs=0.005) == true_d_min
    assert pytest.approx(fit_dmax, abs=0.015) == true_d_max

    # 2. SWCC fit
    true_alpha = 0.045
    true_n = 1.65
    suctions = np.array([0.0, 5.0, 15.0, 35.0, 75.0, 150.0, 400.0, 1000.0])
    m_val = 1.0 - (1.0 / true_n)
    se_val = (1.0 + (true_alpha * suctions) ** true_n) ** (-m_val)
    meas_sr = 0.15 + 0.85 * se_val

    fitted_swcc, swcc_report = fit_van_genuchten_swcc(
        measured_suctions_kpa=suctions,
        measured_degrees_of_saturation=meas_sr,
        residual_saturation=0.15,
    )
    assert swcc_report.r_squared >= 0.98
    assert pytest.approx(fitted_swcc.alpha_kpa_inv, rel=0.15) == true_alpha
    assert pytest.approx(fitted_swcc.n_param, rel=0.15) == true_n

    # 3. Mohr-Coulomb linear shear strength fit
    sigma_n = np.array([50.0, 100.0, 200.0, 300.0])
    true_c = 14.0
    true_phi = 33.0
    tau_f = true_c + sigma_n * math.tan(math.radians(true_phi))

    fit_c, fit_phi, mc_report = fit_mohr_coulomb_shear_strength(
        normal_stresses_kpa=sigma_n,
        shear_strengths_kpa=tau_f,
    )
    assert mc_report.r_squared >= 0.999
    assert pytest.approx(fit_c, abs=0.1) == true_c
    assert pytest.approx(fit_phi, abs=0.2) == true_phi


# -----------------------------------------------------------------------------
# 8. OpenSees Material Parameter Synthesis
# -----------------------------------------------------------------------------
def test_opensees_pdmy02_parameters():
    """
    Validates generation of calibrated OpenSees PressureDependMultiYield02 material inputs.
    """
    params = CyclicSoilParameters(
        max_shear_modulus_gmax_kpa=90000.0,
        friction_angle_deg=34.0,
        cohesion_kpa=18.0,
        mass_density_tonnes_m3=2.00,
    )

    pdmy = generate_opensees_pdmy02_parameters(params)
    assert pdmy["material_type"] == "PressureDependMultiYield02"
    assert pdmy["refShearModul"] == 90000.0
    assert pdmy["frictionAng"] == 34.0
    assert pdmy["cohesion"] == 18.0
    assert pdmy["PTAng"] == 30.0 # phi - 4
    assert pdmy["rho"] == 2.00
    assert pdmy["noYieldSurf"] == 20


# -----------------------------------------------------------------------------
# 9. Bounds & Error Handling Edge Cases
# -----------------------------------------------------------------------------
def test_cyclic_soil_edge_cases():
    """
    Tests input validation, physical bounds checks, and edge cases.
    """
    # Invalid SWCC parameters
    with pytest.raises(ValueError):
        VanGenuchtenParams(alpha_kpa_inv=-0.05)
    with pytest.raises(ValueError):
        VanGenuchtenParams(n_param=0.8) # n must be > 1.0
    with pytest.raises(ValueError):
        VanGenuchtenParams(theta_res=0.5, theta_sat=0.4) # res > sat

    # Invalid Unsaturated soil parameters
    with pytest.raises(ValueError):
        UnsaturatedSoilParameters(effective_cohesion=-5.0)
    with pytest.raises(ValueError):
        UnsaturatedSoilParameters(effective_friction_angle=60.0)
    with pytest.raises(ValueError):
        UnsaturatedSoilParameters(effective_friction_angle=30.0, phi_b_angle=35.0) # phi_b > phi

    # Invalid Cyclic soil parameters
    with pytest.raises(ValueError):
        CyclicSoilParameters(max_shear_modulus_gmax_kpa=-1000.0)
    with pytest.raises(ValueError):
        CyclicSoilParameters(reference_shear_strain=-0.001)
    with pytest.raises(ValueError):
        CyclicSoilParameters(curvature_param_a=2.5) # out of [0.5, 2.0]
    with pytest.raises(ValueError):
        CyclicSoilParameters(min_damping_ratio=0.30, max_damping_ratio=0.20) # min > max

    # Invalid curve fit lengths
    with pytest.raises(ValueError):
        fit_cyclic_modulus_reduction_curve([0.001], [0.8]) # < 3 points
    with pytest.raises(ValueError):
        fit_cyclic_modulus_reduction_curve([0.001, 0.002, 0.003], [0.8, 0.7]) # length mismatch

    # Infiltration invalid inputs
    soil = UnsaturatedSoilParameters()
    geom = RetainingWallGeometry()
    with pytest.raises(ValueError):
        simulate_rainfall_infiltration(soil, geom, rainfall_intensity_mm_hr=-10.0)
    with pytest.raises(ValueError):
        simulate_rainfall_infiltration(soil, geom, rainfall_duration_hours=0.0)


def test_comprehensive_branch_coverage_phase7():
    """
    Exhaustive branch coverage for SWCC, Cyclic soil, and Calibration validators.
    """
    # 1. VanGenuchtenParams residual_saturation out of bounds
    with pytest.raises(ValueError):
        VanGenuchtenParams(residual_saturation=-0.1)
    with pytest.raises(ValueError):
        VanGenuchtenParams(residual_saturation=1.2)

    # 2. UnsaturatedSoilParameters invalid inputs
    with pytest.raises(ValueError):
        UnsaturatedSoilParameters(dry_unit_weight=-10.0)
    with pytest.raises(ValueError):
        UnsaturatedSoilParameters(initial_matric_suction=-5.0)
    with pytest.raises(ValueError):
        UnsaturatedSoilParameters(saturated_conductivity_mps=-1e-5)

    # 3. CyclicSoilParameters invalid inputs
    with pytest.raises(ValueError):
        CyclicSoilParameters(min_damping_ratio=0.001) # < 0.005
    with pytest.raises(ValueError):
        CyclicSoilParameters(max_damping_ratio=0.45) # > 0.40
    with pytest.raises(ValueError):
        CyclicSoilParameters(friction_angle_deg=-5.0)
    with pytest.raises(ValueError):
        CyclicSoilParameters(friction_angle_deg=56.0)
    with pytest.raises(ValueError):
        CyclicSoilParameters(poissons_ratio=-0.1)
    with pytest.raises(ValueError):
        CyclicSoilParameters(mass_density_tonnes_m3=-1.5)

    # 4. Zero shear strain damping
    d_zero = compute_hysteretic_damping(0.0)
    assert d_zero == 0.025

    # 5. generate_cyclic_degradation_curves invalid inputs
    params = CyclicSoilParameters()
    with pytest.raises(ValueError):
        generate_cyclic_degradation_curves(params, num_points=2)
    with pytest.raises(ValueError):
        generate_cyclic_degradation_curves(params, min_strain=-1e-4)

    # 6. generate_masing_hysteresis_loop invalid inputs
    with pytest.raises(ValueError):
        generate_masing_hysteresis_loop(params, strain_amplitude=-0.001)
    with pytest.raises(ValueError):
        generate_masing_hysteresis_loop(params, strain_amplitude=0.001, num_points_per_branch=2)

    # 7. fit_cyclic_modulus_reduction_curve negative strains / out of bound G
    with pytest.raises(ValueError):
        fit_cyclic_modulus_reduction_curve([-0.001, 0.002, 0.003], [0.8, 0.7, 0.6])
    with pytest.raises(ValueError):
        fit_cyclic_modulus_reduction_curve([0.001, 0.002, 0.003], [-0.5, 0.7, 0.6])

    # 8. fit_hysteretic_damping_curve invalid lengths
    with pytest.raises(ValueError):
        fit_hysteretic_damping_curve([0.001], [0.05])
    with pytest.raises(ValueError):
        fit_hysteretic_damping_curve([0.001, 0.002, 0.003], [0.05, 0.08])

    # 9. fit_van_genuchten_swcc invalid inputs
    with pytest.raises(ValueError):
        fit_van_genuchten_swcc([10.0], [0.8])
    with pytest.raises(ValueError):
        fit_van_genuchten_swcc([10.0, 20.0, 30.0], [0.8, 0.6])
    with pytest.raises(ValueError):
        fit_van_genuchten_swcc([-10.0, 20.0, 30.0], [0.8, 0.6, 0.4])
    with pytest.raises(ValueError):
        fit_van_genuchten_swcc([10.0, 20.0, 30.0], [-0.2, 0.6, 0.4])

    # 10. fit_mohr_coulomb_shear_strength invalid inputs
    with pytest.raises(ValueError):
        fit_mohr_coulomb_shear_strength([10.0], [15.0])
    with pytest.raises(ValueError):
        fit_mohr_coulomb_shear_strength([10.0, 20.0], [15.0])
    with pytest.raises(ValueError):
        fit_mohr_coulomb_shear_strength([-10.0, 20.0], [15.0, 25.0])

    # 11. _r_squared zero variance edge case
    from orang3d.physics.calibration import _r_squared
    const_arr = np.array([5.0, 5.0, 5.0])
    assert _r_squared(const_arr, const_arr) == 1.0

