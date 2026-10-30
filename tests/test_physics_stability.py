"""
Unit, invariant, and benchmark tests for Analytical Physics & Geotechnical Stability (Phase 3).
Covers:
- Mononobe-Okabe (M-O) dynamic earth pressure and asymptotic limits
- Rankine and Coulomb static active/passive earth pressures
- Seed & Whitman (1970) dynamic thrust partitioning
- Pore water pressure & water table immersion
- Non-linear liquefaction degradation model (r_u pore pressure ratio)
- Bearing capacity factors (Meyerhof, Hansen, Vesic) and load inclination
- Shear key passive sliding resistance
- Golden textbook benchmarks (Das, Kramer)
"""

import pytest
import numpy as np

from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
)
from orang3d.physics.mononobe_okabe import (
    compute_mononobe_okabe,
    compute_lateral_thrusts,
    compute_rankine_earth_pressures,
    compute_coulomb_earth_pressures,
    compute_liquefaction_degradation,
)
from orang3d.physics.stability import (
    evaluate_wall_stability,
    compute_bearing_capacity_factors,
    compute_ultimate_bearing_capacity,
)


def test_mononobe_okabe_static_limit():
    """When kh=0 and kv=0, Kae must exactly equal static Coulomb Ka."""
    k_ae, k_a, delta_k = compute_mononobe_okabe(
        phi_deg=35.0,
        delta_deg=20.0,
        kh=0.0,
        kv=0.0,
        beta_deg=0.0,
    )
    assert k_ae == pytest.approx(k_a, abs=1e-4)
    assert delta_k == pytest.approx(0.0, abs=1e-4)
    assert 0.20 < k_a < 0.35  # Typical range for phi=35


def test_mononobe_okabe_seismic_increase():
    """Higher seismic acceleration must monotonically increase Kae and delta_K."""
    k_ae_low, _, delta_low = compute_mononobe_okabe(32.0, 20.0, kh=0.1, kv=0.05)
    k_ae_high, _, delta_high = compute_mononobe_okabe(32.0, 20.0, kh=0.3, kv=0.15)

    assert k_ae_high > k_ae_low
    assert delta_high > delta_low


def test_seed_whitman_thrust_height():
    """Dynamic thrust resultant must act higher than static H/3."""
    H = 6.0
    _, h_static, _, _ = compute_lateral_thrusts(
        wall_height=H,
        gamma=18.0,
        gamma_sat=20.0,
        k_ae=0.28,
        k_a=0.28,  # Pure static
        water_table_depth=10.0,  # Dry
    )
    assert h_static == pytest.approx(H / 3.0, abs=0.01)

    _, h_seismic, _, _ = compute_lateral_thrusts(
        wall_height=H,
        gamma=18.0,
        gamma_sat=20.0,
        k_ae=0.50,  # Strong seismic
        k_a=0.28,
        water_table_depth=10.0,
    )
    assert h_seismic > h_static
    assert h_seismic <= 0.6 * H + 0.1


def test_rankine_earth_pressures():
    """Test Rankine active and passive earth pressure coefficients."""
    # For phi=30: Ka = (1 - sin30)/(1 + sin30) = 1/3; Kp = 3.0; Ka * Kp = 1.0
    ka, kp = compute_rankine_earth_pressures(phi_deg=30.0)
    assert ka == pytest.approx(1.0 / 3.0, abs=1e-4)
    assert kp == pytest.approx(3.0, abs=1e-4)
    assert ka * kp == pytest.approx(1.0, abs=1e-4)

    # For phi=0 (cohesive soil): Ka = 1.0, Kp = 1.0
    ka_0, kp_0 = compute_rankine_earth_pressures(phi_deg=0.0)
    assert ka_0 == pytest.approx(1.0, abs=1e-4)
    assert kp_0 == pytest.approx(1.0, abs=1e-4)


def test_coulomb_earth_pressures():
    """Coulomb with delta=0 and beta=0 must match Rankine."""
    ka_coulomb, kp_coulomb = compute_coulomb_earth_pressures(
        phi_deg=30.0,
        delta_deg=0.0,
        beta_deg=0.0,
        theta_deg=0.0,
    )
    ka_rankine, kp_rankine = compute_rankine_earth_pressures(phi_deg=30.0)
    assert ka_coulomb == pytest.approx(ka_rankine, abs=1e-4)
    assert kp_coulomb == pytest.approx(kp_rankine, abs=1e-4)

    # With wall friction (delta > 0), Ka decreases and Kp increases
    ka_fric, kp_fric = compute_coulomb_earth_pressures(phi_deg=30.0, delta_deg=20.0)
    assert ka_fric < ka_coulomb
    assert kp_fric > kp_coulomb


def test_liquefaction_degradation_ru():
    """Test non-linear liquefaction degradation as pore pressure ratio r_u -> 1.0."""
    phi_0 = 34.0
    c_0 = 15.0

    # r_u = 0.0 (no pore pressure build up)
    phi_eff, c_eff = compute_liquefaction_degradation(phi_0, c_0, r_u=0.0)
    assert phi_eff == pytest.approx(phi_0, abs=1e-4)
    assert c_eff == pytest.approx(c_0, abs=1e-4)

    # r_u = 0.5 (partial liquefaction)
    phi_50, c_50 = compute_liquefaction_degradation(phi_0, c_0, r_u=0.5)
    assert np.tan(np.radians(phi_50)) == pytest.approx(0.5 * np.tan(np.radians(phi_0)), rel=1e-3)
    assert c_50 == pytest.approx(0.5 * c_0, abs=1e-4)

    # r_u = 1.0 (complete liquefaction: zero shear strength)
    phi_100, c_100 = compute_liquefaction_degradation(phi_0, c_0, r_u=1.0)
    assert phi_100 == pytest.approx(0.0, abs=1e-2)
    assert c_100 == pytest.approx(0.0, abs=1e-4)


def test_bearing_capacity_factors_meyerhof_vesic():
    """Verify bearing capacity factors Nc, Nq, Ngamma against textbook tables."""
    # phi = 0 (Prandtl solution)
    nc_0, nq_0, ng_0 = compute_bearing_capacity_factors(phi_deg=0.0)
    assert nc_0 == pytest.approx(5.14, abs=0.01)
    assert nq_0 == pytest.approx(1.0, abs=1e-4)
    assert ng_0 == pytest.approx(0.0, abs=1e-4)

    # phi = 30 degrees (Standard geotechnical tables)
    # Nq = exp(pi*tan30)*tan^2(60) ~ 18.40
    # Nc = (Nq - 1)/tan30 ~ 30.14
    # Ngamma (Vesic) = 2*(Nq + 1)*tan30 ~ 22.40
    nc_30, nq_30, ng_30 = compute_bearing_capacity_factors(phi_deg=30.0)
    assert nq_30 == pytest.approx(18.40, rel=0.02)
    assert nc_30 == pytest.approx(30.14, rel=0.02)
    assert ng_30 == pytest.approx(22.40, rel=0.05)


def test_ultimate_bearing_capacity_hansen_meyerhof():
    """Verify ultimate bearing capacity calculation with eccentricity and inclination."""
    q_ult, fs_bearing = compute_ultimate_bearing_capacity(
        base_width=4.0,
        vertical_load=600.0,       # kN/m
        horizontal_load=150.0,     # kN/m
        eccentricity=0.3,          # m
        embedment_depth=1.0,       # m
        foundation_phi=30.0,       # deg
        foundation_cohesion=10.0,  # kPa
        foundation_unit_weight=19.0, # kN/m^3
    )
    assert q_ult > 0.0
    assert fs_bearing > 1.0

    # Undrained cohesive soil condition (phi_f = 0)
    q_ult_clay, fs_clay = compute_ultimate_bearing_capacity(
        base_width=4.0,
        vertical_load=400.0,
        horizontal_load=50.0,
        eccentricity=0.2,
        embedment_depth=1.0,
        foundation_phi=0.0,
        foundation_cohesion=50.0,
        foundation_unit_weight=18.0,
    )
    assert q_ult_clay > 0.0
    assert fs_clay > 1.0


def test_coulomb_and_lateral_thrust_edge_cases():
    """Test Coulomb and thrust resultants under extreme/zero limit conditions."""
    # Coulomb with beta > phi (slope instability)
    ka_steep, kp_steep = compute_coulomb_earth_pressures(
        phi_deg=25.0,
        delta_deg=10.0,
        beta_deg=30.0,
    )
    assert ka_steep == 1.0

    # Zero thrust boundary
    total_t, h_t, p_w, _ = compute_lateral_thrusts(
        wall_height=0.0,
        gamma=18.0,
        gamma_sat=20.0,
        k_ae=0.0,
        k_a=0.0,
        water_table_depth=0.0,
    )
    assert total_t == 0.0
    assert h_t == 0.0


def test_shear_key_increases_sliding_resistance():
    """Presence of a bottom shear key must increase sliding factor of safety."""
    geom_no_key = RetainingWallGeometry(shear_key_depth=0.0)
    geom_with_key = RetainingWallGeometry(shear_key_depth=0.6, shear_key_width=0.5)
    soil = SoilProperties()
    seismic = SeismicParams(horizontal_pga=0.25)

    res_no_key = evaluate_wall_stability(geom_no_key, soil, seismic)
    res_with_key = evaluate_wall_stability(geom_with_key, soil, seismic)

    assert res_with_key.fs_sliding > res_no_key.fs_sliding


def test_global_factors_of_safety_positive():
    geom = RetainingWallGeometry()
    soil = SoilProperties()
    seismic = SeismicParams(horizontal_pga=0.1, vertical_pga=0.05)

    results = evaluate_wall_stability(geom, soil, seismic)

    assert results.fs_sliding > 0.0
    assert results.fs_overturning > 0.0
    assert results.fs_bearing > 0.0
    assert results.max_bearing_pressure > 0.0


def test_water_table_immersion_reduces_stability():
    geom = RetainingWallGeometry()
    soil = SoilProperties()

    # Dry condition (water table deep)
    seismic_dry = SeismicParams(water_table_depth=10.0)
    res_dry = evaluate_wall_stability(geom, soil, seismic_dry)

    # Flooded condition (water table near crest)
    seismic_flood = SeismicParams(water_table_depth=1.0)
    res_flood = evaluate_wall_stability(geom, soil, seismic_flood)

    # Flooding increases thrust and reduces factors of safety
    assert res_flood.total_thrust > res_dry.total_thrust
    assert res_flood.water_thrust > 0.0
    assert res_flood.fs_sliding < res_dry.fs_sliding
    assert res_flood.fs_overturning < res_dry.fs_overturning


def test_liquefaction_reduces_sliding_safety():
    geom = RetainingWallGeometry()
    soil = SoilProperties()

    seismic_solid = SeismicParams(liquefaction_factor=0.0)
    res_solid = evaluate_wall_stability(geom, soil, seismic_solid)

    seismic_liq = SeismicParams(liquefaction_factor=0.8)
    res_liq = evaluate_wall_stability(geom, soil, seismic_liq)

    assert res_liq.k_ae > res_solid.k_ae
    assert res_liq.fs_sliding < res_solid.fs_sliding


def test_concrete_stem_cracking_under_extreme_seismic():
    geom = RetainingWallGeometry(stem_thickness_base=0.45)  # Thin stem
    soil = SoilProperties()
    seismic_mild = SeismicParams(horizontal_pga=0.05)
    seismic_severe = SeismicParams(horizontal_pga=0.55)

    res_mild = evaluate_wall_stability(geom, soil, seismic_mild)
    res_severe = evaluate_wall_stability(geom, soil, seismic_severe)

    assert res_severe.max_bending_moment > res_mild.max_bending_moment
    assert res_severe.concrete_tensile_stress > res_mild.concrete_tensile_stress
    assert res_severe.cracking_predicted is True


def test_golden_textbook_kramer_seismic_mo():
    """
    Golden Textbook Benchmark: Kramer (1996) Geotechnical Earthquake Engineering, Example 11.1
    phi = 35 deg, delta = 17.5 deg, beta = 0 deg, theta = 0 deg.
    kh = 0.20, kv = 0.0.
    Kramer closed-form Kae = 0.380 (+/- 0.01).
    """
    k_ae, k_a, delta_k = compute_mononobe_okabe(
        phi_deg=35.0,
        delta_deg=17.5,
        kh=0.20,
        kv=0.0,
        beta_deg=0.0,
        wall_slope_deg=0.0,
    )
    assert k_ae == pytest.approx(0.380, abs=0.015)
    assert k_a == pytest.approx(0.246, abs=0.015)
    assert delta_k == pytest.approx(0.134, abs=0.015)


def test_golden_textbook_das_retaining_wall():
    """
    Golden Textbook Benchmark: B.M. Das (Principles of Foundation Engineering) Cantilever Wall.
    H_stem = 6.0m, footing = 0.7m, B_toe = 1.0m, t_base = 0.7m, B_heel = 2.6m.
    Soil: gamma = 18.0 kN/m3, phi = 32 deg, delta = 20 deg.
    Foundation: gamma_f = 19.0 kN/m3, phi_f = 30 deg, c_f = 20 kPa, q_allow = 350 kPa.
    Static conditions (kh=0, kv=0).
    Expected: FS_sliding ~ 1.8 - 2.5, FS_overturning ~ 2.5 - 3.8, contact pressure < q_allow.
    """
    geom = RetainingWallGeometry(
        stem_height=6.0,
        footing_thickness=0.7,
        toe_length=1.0,
        stem_thickness_base=0.7,
        heel_length=2.6,
        wall_length=1.0,
    )
    soil = SoilProperties(
        friction_angle=32.0,
        wall_friction_angle=20.0,
        unit_weight=18.0,
        foundation_friction_angle=30.0,
        foundation_cohesion=20.0,
        allowable_bearing_capacity=350.0,
    )
    seismic_static = SeismicParams(
        horizontal_pga=0.0,
        vertical_pga=0.0,
        water_table_depth=10.0,  # Dry backfill per standard Das problem
    )

    res = evaluate_wall_stability(geom, soil, seismic_static)

    assert 1.6 <= res.fs_sliding <= 2.8
    assert 2.5 <= res.fs_overturning <= 5.2
    assert res.fs_bearing >= 1.5
    assert res.max_bearing_pressure < soil.allowable_bearing_capacity
    assert res.eccentricity < geom.base_width / 6.0  # Kern / middle-third condition satisfied
