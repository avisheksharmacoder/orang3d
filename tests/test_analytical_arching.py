"""
Unit, invariant, and performance tests for Phase 3:
Level L0 Analytical Engine (Arching, Piles, Multi-Struts & IS 1893).
"""

import time
import math
import pytest
import numpy as np

from orang3d.models.advanced_wall_params import (
    CurvedShellGeometry,
    PierAndPileGeometry,
    StrutSupportSystem,
    MultiStrutPiledWallModel,
)
from orang3d.models.is_code_params import IndianDesignStandards, SeismicZone
from orang3d.models.wall_params import SoilProperties
from orang3d.physics.shell_arching import (
    compute_horizontal_arching_stress,
    compute_shell_arching_partition,
)
from orang3d.physics.is_1893_engine import (
    calculate_is1893_seismic_coefficients,
    compute_mononobe_okabe_kae,
    calculate_is1893_dynamic_earth_pressure,
)
from orang3d.physics.strut_statics import (
    compute_apparent_earth_pressure,
    compute_multi_strut_apportionment,
)
from orang3d.physics.pile_statics import (
    compute_broms_lateral_capacity,
    calculate_minimum_pile_embedment,
)


# ==============================================================================
# 1. Horizontal Soil Arching: Planar Limit & Equilibrium Conservation
# ==============================================================================

def test_arching_planar_limit():
    """
    Phase 3.4: As shell radius R -> infinity and L_bay -> infinity,
    arching stress must asymptotically converge to classical Rankine active pressure.
    """
    gamma = 18.0
    phi = 30.0
    # Rankine Ka = tan^2(45 - 30/2) = tan^2(30) = 1/3 = 0.333333
    ka = math.tan(math.radians(30.0)) ** 2

    depths = np.array([1.0, 3.0, 5.0, 8.0], dtype=np.float64)
    expected_rankine = ka * gamma * depths # [6.0, 18.0, 30.0, 48.0]

    # Very large bay span L_bay -> inf (e.g. 100,000 m)
    large_bay = 100000.0
    computed_stress = compute_horizontal_arching_stress(
        z=depths,
        gamma=gamma,
        phi=phi,
        bay_span=large_bay,
        c=0.0,
        k_coeff=ka,
    )

    # Relative difference must be < 0.01%
    assert np.allclose(computed_stress, expected_rankine, rtol=1e-4)


def test_equilibrium_conservation():
    """
    Phase 3.4: Total earth thrust must equal sum of pier reactions plus shell face thrust (sum F_x = 0).
    """
    geom = CurvedShellGeometry(radius=4.5, bay_span=4.0, panel_height=6.0)
    soil = SoilProperties(unit_weight=18.0, friction_angle=32.0, cohesion=5.0)

    res = compute_shell_arching_partition(geom, soil)

    # 1. Exact equilibrium conservation: P_free = P_shell + P_pier
    assert math.isclose(
        res.total_free_field_thrust,
        res.total_shell_thrust + res.total_pier_thrust,
        rel_tol=1e-6,
    )

    # 2. Arching relief: shell thrust must be strictly less than free field
    assert res.total_shell_thrust < res.total_free_field_thrust
    assert res.total_pier_thrust > 0.0

    # 3. Arching partition factor in (0, 1)
    assert 0.0 < res.arching_ratio < 1.0

    # 4. Hoop thrust and bending moment positive
    assert res.max_hoop_thrust > 0.0
    assert res.max_shell_bending_moment > 0.0


def test_cohesion_effect_on_arching():
    """Verifies that increasing cohesion reduces lateral arching pressure."""
    geom = CurvedShellGeometry(radius=4.5, bay_span=4.0, panel_height=6.0)
    soil_cohesionless = SoilProperties(unit_weight=18.0, friction_angle=30.0, cohesion=0.0)
    soil_cohesive = SoilProperties(unit_weight=18.0, friction_angle=30.0, cohesion=15.0)

    res_dry = compute_shell_arching_partition(geom, soil_cohesionless)
    res_coh = compute_shell_arching_partition(geom, soil_cohesive)

    # Cohesive soil develops tension cracks and lower thrust
    assert res_coh.total_free_field_thrust < res_dry.total_free_field_thrust
    assert res_coh.total_shell_thrust < res_dry.total_shell_thrust


# ==============================================================================
# 2. IS 1893 Seismic Coefficients & Dynamic Earth Pressures
# ==============================================================================

def test_is1893_seismic_coefficients():
    """
    Phase 3.4: Verifies A_h calculation against IS 1893 (Pt 3) Table 1
    for Zone V (Z=0.36, I=1.5, R=3.0).
    """
    # Zone V (Z=0.36), I=1.5, R=3.0, Type II Medium Soil, T=0.3 s (Sa/g = 2.50)
    standards_v = IndianDesignStandards(
        seismic_zone="Zone V",
        importance_factor=1.5,
        response_reduction_factor=3.0,
        soil_type="Type II",
        damping_ratio=0.05,
    )
    a_h, a_v = calculate_is1893_seismic_coefficients(standards_v, time_period=0.3)

    # A_h = (Z / 2) * (I / R) * (Sa / g) = (0.36 / 2) * (1.5 / 3.0) * 2.50 = 0.18 * 0.5 * 2.50 = 0.225
    assert a_h == pytest.approx(0.225)
    # A_v = 2/3 * A_h = 2/3 * 0.225 = 0.150
    assert a_v == pytest.approx(0.150)

    # Zone IV (Z=0.24)
    standards_iv = IndianDesignStandards(
        seismic_zone="Zone IV",
        importance_factor=1.5,
        response_reduction_factor=3.0,
        soil_type="Type II",
        damping_ratio=0.05,
    )
    a_h_iv, a_v_iv = calculate_is1893_seismic_coefficients(standards_iv, time_period=0.3)
    assert a_h_iv == pytest.approx(0.150)
    assert a_v_iv == pytest.approx(0.100)


def test_is1893_dynamic_earth_pressure_demand():
    geom = CurvedShellGeometry(radius=4.5, bay_span=4.0, panel_height=6.0)
    soil = SoilProperties(unit_weight=18.0, friction_angle=32.0, cohesion=8.0, wall_friction_angle=20.0)
    standards = IndianDesignStandards(seismic_zone="Zone V")

    demand = calculate_is1893_dynamic_earth_pressure(geom, soil, standards, time_period=0.3)

    # Mononobe-Okabe Kae must exceed static Ka
    assert demand.k_ae > demand.k_a_static
    assert demand.delta_k_ae > 0.0

    # Total dynamic thrust exceeds static thrust
    assert demand.total_dynamic_thrust > demand.static_thrust
    assert demand.dynamic_thrust_increment > 0.0

    # Tension crack depth in cohesive soil z_c = 2c / (gamma * sqrt(Ka))
    assert demand.tension_crack_depth > 0.0

    # Centroid height rises upwards from effective base towards 0.5 - 0.6 H
    eff_h = geom.panel_height - demand.tension_crack_depth
    assert demand.thrust_centroid_height > (eff_h / 3.0)

    # Dry cohesionless case: centroid height strictly exceeds H / 3.0
    soil_dry = SoilProperties(unit_weight=18.0, friction_angle=32.0, cohesion=0.0)
    demand_dry = calculate_is1893_dynamic_earth_pressure(geom, soil_dry, standards, time_period=0.3)
    assert demand_dry.thrust_centroid_height > (geom.panel_height / 3.0)


# ==============================================================================
# 3. Multi-Strut Statics & Apparent Earth Pressure Envelopes
# ==============================================================================

def test_multi_strut_apportionment():
    struts = StrutSupportSystem(
        strut_levels=[2.0, 4.5],
        inclination_angle=25.0,
        pre_stress_load=50.0,
    )
    pier_height = 6.5
    total_thrust = 120.0 # kN/m
    bay_span = 4.0 # m

    sys_result = compute_multi_strut_apportionment(
        struts=struts,
        pier_height=pier_height,
        total_thrust=total_thrust,
        bay_span=bay_span,
    )

    # 2 struts
    assert len(sys_result.strut_reactions) == 2
    r0 = sys_result.strut_reactions[0]
    r1 = sys_result.strut_reactions[1]

    # Pre-stress included: P_strut = F_h / cos(alpha) + P_0
    cos_alpha = math.cos(math.radians(25.0))
    assert r0.axial_force > r0.horizontal_force / cos_alpha
    assert r0.vertical_reaction > 0.0

    # Buckling status
    assert r0.status in ("PASS", "FAIL")
    assert r1.status in ("PASS", "FAIL")

    # Apparent earth pressure profile matches integral
    assert len(sys_result.depths) == 50
    assert len(sys_result.apparent_earth_pressure) == 50
    integrate_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
    int_aep = float(integrate_trapz(sys_result.apparent_earth_pressure, sys_result.depths))
    assert int_aep == pytest.approx(total_thrust, rel=1e-3)


# ==============================================================================
# 4. Bored Pile Lateral Capacity & Broms' Equilibrium
# ==============================================================================

def test_pile_embedment_equilibrium():
    """
    Phase 3.4: Ensures computed pile depth provides FS_lateral >= 1.5
    against Broms' ultimate lateral soil capacity.
    """
    pier_pile = PierAndPileGeometry(
        pile_diameter=0.8,
        pile_length=10.0,
        num_piles_per_pier=2,
        pile_spacing=2.5,
    )
    soil = SoilProperties(
        foundation_unit_weight=19.0,
        foundation_friction_angle=30.0,
        foundation_cohesion=15.0,
    )

    applied_shear_per_pier = 200.0 # kN per pier (100 kN per pile)

    # 1. Lateral capacity calculation
    res = compute_broms_lateral_capacity(pier_pile, soil, applied_shear_per_pier)

    assert res.applied_lateral_load_per_pile == pytest.approx(100.0)
    assert res.ultimate_lateral_capacity > res.applied_lateral_load_per_pile
    assert res.factor_of_safety_lateral >= 1.5
    assert res.status == "PASS"
    assert res.depth_of_fixity > 0.0
    assert res.max_pile_bending_moment > 0.0

    # 2. Minimum pile embedment solver for target FS = 1.5
    l_min = calculate_minimum_pile_embedment(
        pier_pile=pier_pile,
        soil=soil,
        applied_shear_per_pier=applied_shear_per_pier,
        target_fs=1.5,
    )

    # Test embedment with calculated l_min
    pier_pile_opt = PierAndPileGeometry(
        pile_diameter=0.8,
        pile_length=l_min,
        num_piles_per_pier=2,
        pile_spacing=2.5,
    )
    res_opt = compute_broms_lateral_capacity(pier_pile_opt, soil, applied_shear_per_pier)
    # Must achieve FS >= 1.5 within 2% tolerance
    assert res_opt.factor_of_safety_lateral >= 1.48


# ==============================================================================
# 5. Analytical Engine Latency Benchmark (< 1.5 ms)
# ==============================================================================

def test_analytical_latency():
    """
    Phase 3.4: Entire analytical chain executes in < 1.5 ms.
    Chains:
    - compute_shell_arching_partition
    - calculate_is1893_dynamic_earth_pressure
    - compute_multi_strut_apportionment
    - compute_broms_lateral_capacity
    - calculate_minimum_pile_embedment
    """
    shell = CurvedShellGeometry()
    pier_pile = PierAndPileGeometry()
    struts = StrutSupportSystem()
    standards = IndianDesignStandards()
    soil = SoilProperties(foundation_cohesion=20.0)

    # Warmup
    _ = compute_shell_arching_partition(shell, soil)
    _ = calculate_is1893_dynamic_earth_pressure(shell, soil, standards)
    _ = compute_multi_strut_apportionment(struts, pier_pile.pier_height, 150.0, shell.bay_span)
    _ = compute_broms_lateral_capacity(pier_pile, soil, 250.0)
    _ = calculate_minimum_pile_embedment(pier_pile, soil, 250.0)

    # Benchmark over 50 iterations
    iterations = 50
    start_time = time.perf_counter()

    for _ in range(iterations):
        res_arch = compute_shell_arching_partition(shell, soil)
        demand = calculate_is1893_dynamic_earth_pressure(shell, soil, standards, time_period=0.35)
        res_strut = compute_multi_strut_apportionment(
            struts=struts,
            pier_height=pier_pile.pier_height,
            total_thrust=demand.total_dynamic_thrust,
            bay_span=shell.bay_span,
        )
        res_pile = compute_broms_lateral_capacity(
            pier_pile=pier_pile,
            soil=soil,
            applied_shear_per_pier=res_strut.residual_base_shear,
        )
        _ = calculate_minimum_pile_embedment(
            pier_pile=pier_pile,
            soil=soil,
            applied_shear_per_pier=res_strut.residual_base_shear,
            target_fs=1.5,
        )

    total_time = time.perf_counter() - start_time
    avg_latency_ms = (total_time / iterations) * 1000.0

    print(f"\n[BENCHMARK] Full Level L0 analytical chain latency: {avg_latency_ms:.4f} ms (Threshold: < 1.5 ms)")
    assert avg_latency_ms < 1.5, f"Analytical latency {avg_latency_ms:.4f} ms exceeded 1.5 ms threshold"


# ==============================================================================
# 6. Edge Cases & Boundary Handling
# ==============================================================================

def test_edge_cases():
    # Negative bay span in arching
    with pytest.raises(ValueError, match="bay_span must be positive"):
        compute_horizontal_arching_stress(z=2.0, gamma=18.0, phi=30.0, bay_span=-4.0)

    # Invalid friction angle
    with pytest.raises(ValueError, match="phi must be between 0 and 90 degrees"):
        compute_horizontal_arching_stress(z=2.0, gamma=18.0, phi=0.0, bay_span=4.0)
    with pytest.raises(ValueError, match="phi must be between 0 and 90 degrees"):
        compute_horizontal_arching_stress(z=2.0, gamma=18.0, phi=95.0, bay_span=4.0)

    # Non-positive height in apparent pressure
    with pytest.raises(ValueError, match="height must be positive"):
        compute_apparent_earth_pressure(height=0.0, total_thrust=100.0)

    # Negative shear in pile capacity
    with pytest.raises(ValueError, match="applied_shear_per_pier cannot be negative"):
        compute_broms_lateral_capacity(PierAndPileGeometry(), SoilProperties(), -10.0)

    # Zero applied shear in minimum embedment returns practical minimum
    min_emb = calculate_minimum_pile_embedment(PierAndPileGeometry(), SoilProperties(), 0.0)
    assert min_emb >= 2.0


def test_pile_intermediate_classification():
    """Verifies IS 2911 intermediate pile classification when 2T < Lp < 4T."""
    # Default pier_pile has E=30 GPa, D=0.8 m.
    # T = (Ep * Ip / nh)^0.2 ~ (30e6 * 0.0201 / 12000)^0.2 ~ (50.26)^0.2 ~ 2.189 m
    # 2T ~ 4.38 m, 4T ~ 8.76 m.
    # So Lp = 6.0 m is classified as Intermediate.
    geom = PierAndPileGeometry(pile_length=6.0, pile_diameter=0.8)
    soil = SoilProperties()
    res = compute_broms_lateral_capacity(geom, soil, applied_shear_per_pier=50.0)
    assert res.pile_classification == "Intermediate"
    assert 2.0 * res.stiffness_factor_t < geom.pile_length < 4.0 * res.stiffness_factor_t


def test_strut_single_and_triple_tiers():
    """Verifies tributary area statics for 1-tier, 3-tier, and zero-thrust cases."""
    # 1-tier
    struts_1 = StrutSupportSystem(strut_levels=[3.0])
    res_1 = compute_multi_strut_apportionment(struts_1, pier_height=8.0, total_thrust=150.0, bay_span=4.0)
    assert len(res_1.strut_reactions) == 1
    assert res_1.strut_reactions[0].horizontal_force > 0.0

    # 3-tier
    struts_3 = StrutSupportSystem(strut_levels=[1.5, 4.0, 6.5])
    res_3 = compute_multi_strut_apportionment(struts_3, pier_height=8.0, total_thrust=200.0, bay_span=4.0)
    assert len(res_3.strut_reactions) == 3
    # Equilibrium: sum(horizontal_force) + residual = total_thrust * bay_span
    total_h = sum(r.horizontal_force for r in res_3.strut_reactions) + res_3.residual_base_shear
    assert math.isclose(total_h, 200.0 * 4.0, rel_tol=1e-5)

    # Zero thrust
    d, p = compute_apparent_earth_pressure(height=6.0, total_thrust=0.0)
    assert np.allclose(p, 0.0)

    # Very small height triggering zero area branch
    d_small, p_small = compute_apparent_earth_pressure(height=1e-8, total_thrust=10.0)
    assert np.allclose(p_small, 0.0)


def test_shell_arching_scalar_and_high_cohesion():
    """Verifies scalar inputs, default k_coeff, and zero free-field thrust under high cohesion."""
    # Scalar input with default k_coeff=None
    stress_scalar = compute_horizontal_arching_stress(z=2.5, gamma=18.0, phi=32.0, bay_span=4.0, k_coeff=None)
    assert isinstance(stress_scalar, float)
    assert stress_scalar > 0.0

    # Small exponent scalar asymptotic branch
    stress_small_scalar = compute_horizontal_arching_stress(z=1e-8, gamma=18.0, phi=32.0, bay_span=10000.0)
    assert isinstance(stress_small_scalar, float)
    assert stress_small_scalar >= 0.0

    # High cohesion causing P_free <= 1e-6 (tension crack deeper than panel height)
    geom = CurvedShellGeometry(panel_height=1.0, bay_span=4.0)
    soil = SoilProperties(unit_weight=18.0, friction_angle=30.0, cohesion=250.0)
    res = compute_shell_arching_partition(geom, soil)
    assert res.total_free_field_thrust == 0.0
    assert res.total_shell_thrust == 0.0
    assert res.arching_ratio == 0.0


def test_is1893_extreme_angles_and_zero_demand():
    """Verifies IS 1893 Mononobe-Okabe extreme angle bounds and zero demand centroid."""
    # Extreme seismic angle where phi - theta - beta < 0 -> upper bound 1.5
    kae_bound = compute_mononobe_okabe_kae(phi=20.0, delta=10.0, theta=25.0, beta=0.0)
    assert kae_bound == 1.5

    # Denominator base <= 0: delta + alpha + theta >= 90
    kae_den_base = compute_mononobe_okabe_kae(phi=46.0, delta=45.0, theta=0.5, alpha=45.0, beta=0.0)
    assert kae_den_base == 1.5

    # Negative radical denominator: beta - alpha > 90 with phi - theta - beta >= 0
    kae_rad_neg = compute_mononobe_okabe_kae(phi=35.0, delta=10.0, theta=5.0, alpha=-85.0, beta=10.0)
    assert kae_rad_neg > 0.0

    # Zero dynamic demand when soil unit weight is negligible
    geom = CurvedShellGeometry(panel_height=5.0)
    soil = SoilProperties(unit_weight=1e-8, friction_angle=30.0, cohesion=0.0)
    standards = IndianDesignStandards(seismic_zone=SeismicZone.ZONE_II.value)
    demand = calculate_is1893_dynamic_earth_pressure(geom, soil, standards)
    assert math.isclose(demand.static_thrust, 0.0, abs_tol=1e-6)
    assert math.isclose(demand.total_dynamic_thrust, 0.0, abs_tol=1e-6)
    assert math.isclose(demand.thrust_centroid_height, 5.0 / 3.0, rel_tol=1e-6)

