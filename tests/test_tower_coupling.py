"""
Comprehensive Test Suite for Phase 6: Uphill Transmission Tower Co-Simulation & Multi-Hazard Loads.
Validates:
1. Dead load vertical equilibrium invariant (sum R_v = W_tower).
2. Asymmetrical broken-wire torsional couples and longitudinal overturning (IS 802).
3. Coupled slope surcharge stress attenuation onto retaining wall (modified Boussinesq).
4. Fundamental flexural natural frequency f_1 (IS 802 / OpenSees modal analysis).
5. IS 875 (Part 3) height-dependent wind speed, pressure, and aerodynamic drag profiles.
6. Multi-hazard load combinations (Dead + Wind + Broken-Wire + Seismic).
7. PyVista 3D wireframe PolyData generation and geometric bounds.
8. Error handling, physical bounds enforcement, and invariant edge cases.
"""

from __future__ import annotations

import math
import pytest
import numpy as np

from orang3d.models.tower_params import TransmissionTowerParams
from orang3d.physics.wind_loads import (
    IS875WindParameters,
    TowerWindProfileResult,
    compute_k2_factor,
    compute_lattice_force_coefficient,
    calculate_transmission_tower_wind_loads,
)
from orang3d.physics.tower_coupling import (
    TowerLegReaction,
    TowerCouplingResult,
    WallSurchargeProfile,
    compute_boussinesq_point_surcharge_on_wall,
    calculate_retaining_wall_surcharge_distribution,
    estimate_tower_natural_frequency,
    build_and_solve_opensees_tower,
    simulate_transmission_tower_coupling,
    build_tower_3d_wireframe,
    _solve_analytical_tower_reactions,
    OPENSEES_AVAILABLE,
    PYVISTA_AVAILABLE,
)


# -----------------------------------------------------------------------------
# 1. Dead Load Vertical Equilibrium Invariant
# -----------------------------------------------------------------------------
def test_tower_static_dead_load():
    """
    Physical Invariant:
    Under dead gravity load, sum of vertical leg reactions across all 4 corner footings
    must exactly equal the total structural self-weight W_tower = 4 * P_leg.
    """
    tower = TransmissionTowerParams(
        base_width=6.0,
        base_length=6.0,
        total_height=35.0,
        vertical_load_per_leg=250.0,
    )
    expected_total_w = tower.total_vertical_load # 1000.0 kN

    # Test Analytical Solution
    ana_reactions, f_1, converged = _solve_analytical_tower_reactions(
        tower=tower,
        include_wind=False,
        include_broken_wire=False,
        include_seismic=False,
    )
    sum_rv_ana = sum(leg.f_vertical for leg in ana_reactions.values())
    assert pytest.approx(sum_rv_ana, abs=1e-3) == expected_total_w
    for leg in ana_reactions.values():
        assert pytest.approx(leg.f_vertical, abs=1e-3) == 250.0
        assert pytest.approx(leg.f_horizontal_x, abs=1e-3) == 0.0
        assert pytest.approx(leg.f_horizontal_y, abs=1e-3) == 0.0

    # Test OpenSees 3D Space Truss (if installed)
    if OPENSEES_AVAILABLE:
        ops_reactions, f_ops, ops_ok = build_and_solve_opensees_tower(
            tower=tower,
            include_wind=False,
            include_broken_wire=False,
            include_seismic=False,
        )
        assert ops_ok is True
        sum_rv_ops = sum(leg.f_vertical for leg in ops_reactions.values())
        assert pytest.approx(sum_rv_ops, rel=0.01) == expected_total_w


# -----------------------------------------------------------------------------
# 2. Broken-Wire Torsion & Asymmetry (IS 802)
# -----------------------------------------------------------------------------
def test_broken_wire_torsion():
    """
    Validates that an unbalanced broken conductor pull (T_bw) at one cross-arm tip
    produces asymmetrical vertical reaction couples and horizontal yaw torsion.
    """
    tower = TransmissionTowerParams(
        base_width=6.0,
        base_length=6.0,
        total_height=35.0,
        vertical_load_per_leg=250.0,
        broken_wire_tension=80.0,
    )

    # Solve with Broken Wire only (no wind, no seismic)
    reactions, f_1, ok = _solve_analytical_tower_reactions(
        tower=tower,
        include_wind=False,
        include_broken_wire=True,
        include_seismic=False,
    )

    # 1. Total vertical load must still be conserved (equilibrium)
    sum_rv = sum(leg.f_vertical for leg in reactions.values())
    assert pytest.approx(sum_rv, abs=1e-2) == 1000.0

    # 2. Right legs (in direction of broken wire) experience increased vertical load
    # while left legs experience reduced vertical load (or uplift)
    r1 = reactions["leg_1_uphill_left"].f_vertical
    r2 = reactions["leg_2_uphill_right"].f_vertical
    r3 = reactions["leg_3_downhill_right"].f_vertical
    r4 = reactions["leg_4_downhill_left"].f_vertical

    assert r2 > r1, f"Uphill right ({r2}) should be greater than uphill left ({r1})"
    assert r3 > r4, f"Downhill right ({r3}) should be greater than downhill left ({r4})"

    # 3. Asymmetric longitudinal reactions
    delta_couple_rear = r2 - r1
    delta_couple_front = r3 - r4
    assert delta_couple_rear > 0
    assert delta_couple_front > 0
    assert pytest.approx(delta_couple_rear, rel=1e-4) == delta_couple_front

    # 4. Horizontal transverse shear present to resist broken wire pull
    sum_rhy = sum(leg.f_horizontal_y for leg in reactions.values())
    assert abs(sum_rhy) > 0.0


# -----------------------------------------------------------------------------
# 3. Coupled Slope Surcharge Attenuation (Modified Boussinesq)
# -----------------------------------------------------------------------------
def test_coupled_slope_surcharge():
    """
    Validates modified Boussinesq lateral earth pressure transfer from uphill tower footings:
    1. Attenuation with distance: A tower farther from crest produces lower lateral thrust.
    2. Attenuation with depth: Surcharge pressure vanishes at surface and deep underground.
    3. Monotonic positive lateral thrust on retaining wall backface.
    """
    tower_near = TransmissionTowerParams(
        crest_offset=4.0, # 4m from crest
        vertical_load_per_leg=300.0,
    )
    tower_far = TransmissionTowerParams(
        crest_offset=12.0, # 12m from crest
        vertical_load_per_leg=300.0,
    )

    wall_h = 8.0

    # Solve reactions
    rx_near, _, _ = _solve_analytical_tower_reactions(tower_near, include_wind=False, include_broken_wire=False)
    rx_far, _, _ = _solve_analytical_tower_reactions(tower_far, include_wind=False, include_broken_wire=False)

    prof_near = calculate_retaining_wall_surcharge_distribution(rx_near, wall_height=wall_h)
    prof_far = calculate_retaining_wall_surcharge_distribution(rx_far, wall_height=wall_h)

    # 1. Farther tower must produce strictly smaller total surcharge thrust
    assert prof_far.total_thrust_kn_per_m < prof_near.total_thrust_kn_per_m
    assert prof_near.total_thrust_kn_per_m > 0.0
    assert prof_far.total_thrust_kn_per_m > 0.0

    # 2. Resultant elevation must be within wall stem (0 < h_res < H)
    assert 0.0 < prof_near.resultant_elevation_m < wall_h
    assert 0.0 < prof_far.resultant_elevation_m < wall_h

    # 3. Point Boussinesq formula test: deep point attenuates towards zero
    p_shallow = compute_boussinesq_point_surcharge_on_wall(300.0, x_offset=5.0, y_offset=0.0, z_depth=3.0, wall_height=8.0)
    p_very_deep = compute_boussinesq_point_surcharge_on_wall(300.0, x_offset=5.0, y_offset=0.0, z_depth=50.0, wall_height=8.0)
    assert p_shallow > 0.0
    assert p_very_deep < p_shallow * 0.05


# -----------------------------------------------------------------------------
# 4. Fundamental Flexural Natural Frequency (IS 802 / OpenSees)
# -----------------------------------------------------------------------------
def test_eigen_frequencies_tower():
    """
    Validates that the natural frequency of the 35m lattice transmission tower
    lies within the textbook / IS 802 expected range for cantilever towers (1.5 - 3.5 Hz).
    """
    tower = TransmissionTowerParams(
        base_width=6.0,
        base_length=6.0,
        total_height=35.0,
        vertical_load_per_leg=250.0,
    )

    f_analytical = estimate_tower_natural_frequency(tower)
    assert 1.5 <= f_analytical <= 3.5, f"Expected 1.5-3.5 Hz, got {f_analytical}"

    if OPENSEES_AVAILABLE:
        _, f_ops, ok = build_and_solve_opensees_tower(tower, include_wind=False, include_broken_wire=False)
        assert ok is True
        assert 1.2 <= f_ops <= 3.5, f"OpenSees frequency out of expected range: {f_ops}"

    # Frequency sensitivity: A taller tower of the same base width must have a lower natural frequency
    tower_tall = TransmissionTowerParams(
        base_width=6.0,
        base_length=6.0,
        total_height=50.0,
        vertical_load_per_leg=250.0,
    )
    f_tall = estimate_tower_natural_frequency(tower_tall)
    assert f_tall < f_analytical


# -----------------------------------------------------------------------------
# 5. IS 875 (Part 3) Wind Velocity & Pressure Profiles
# -----------------------------------------------------------------------------
def test_is875_wind_load_profile():
    """
    Validates IS 875 (Part 3): 2015 wind speed, pressure, and lattice drag formulation:
    - k2 factor increases with height
    - Design velocity V_z increases with height
    - Force coefficient C_f is within code bounds
    - Conductor drag and overturning moment are non-negative
    """
    wind_params = IS875WindParameters(
        basic_wind_speed=47.0,
        terrain_category=2,
        risk_coefficient_k1=1.06,
        topography_factor_k3=1.15,
        solidity_ratio=0.20,
    )

    # 1. k2 factor validation
    k2_10 = compute_k2_factor(10.0, terrain_category=2)
    k2_35 = compute_k2_factor(35.0, terrain_category=2)
    assert k2_10 == pytest.approx(1.00, abs=0.02)
    assert k2_35 > k2_10

    # 2. Lattice force coefficient
    cf_01 = compute_lattice_force_coefficient(0.10)
    cf_02 = compute_lattice_force_coefficient(0.20)
    cf_04 = compute_lattice_force_coefficient(0.40)
    assert cf_01 > cf_02 > cf_04
    assert 2.0 <= cf_04 <= 3.6

    # 3. Tower wind load calculation
    res = calculate_transmission_tower_wind_loads(
        tower_height=35.0,
        base_width=6.0,
        top_width=1.5,
        wind_params=wind_params,
        num_panels=5,
    )

    assert isinstance(res, TowerWindProfileResult)
    assert len(res.heights) == 5
    assert res.total_tower_body_shear > 0.0
    assert res.conductor_drag_shear > 0.0
    assert res.total_base_wind_shear > res.total_tower_body_shear
    assert res.base_overturning_moment > 0.0
    assert 0.0 < res.effective_wind_thrust_height < 35.0


# -----------------------------------------------------------------------------
# 6. Multi-Hazard Load Combinations & Overturning
# -----------------------------------------------------------------------------
def test_multi_hazard_load_combinations():
    """
    Validates combined multi-hazard co-simulation:
    - Dead + Wind causes front leg compression and rear leg relief.
    - Adding broken wire increases torsion and longitudinal moments.
    - Adding seismic inertia increases downhill base shear.
    """
    tower = TransmissionTowerParams(
        base_width=6.0,
        base_length=6.0,
        total_height=35.0,
        vertical_load_per_leg=250.0,
        wind_shear_per_leg=45.0,
        broken_wire_tension=80.0,
    )

    # Case A: Dead + Wind only
    res_wind = simulate_transmission_tower_coupling(
        tower=tower,
        wall_height=8.0,
        include_wind=True,
        include_broken_wire=False,
        include_seismic=False,
    )
    assert res_wind.total_downhill_shear > 0.0
    # Front legs (3, 4) should carry more vertical load than rear legs (1, 2)
    rv_front = res_wind.leg_reactions["leg_3_downhill_right"].f_vertical
    rv_rear = res_wind.leg_reactions["leg_1_uphill_left"].f_vertical
    assert rv_front > rv_rear

    # Case B: Dead + Wind + Broken-Wire
    res_bw = simulate_transmission_tower_coupling(
        tower=tower,
        wall_height=8.0,
        include_wind=True,
        include_broken_wire=True,
        include_seismic=False,
    )
    # Torsional yaw moment about vertical axis must be non-zero
    assert abs(res_bw.base_torsional_moment_z) > 0.0
    assert abs(res_bw.base_overturning_moment_y) > 0.0

    # Case C: Full Multi-Hazard (Dead + Wind + Broken-Wire + Seismic)
    res_full = simulate_transmission_tower_coupling(
        tower=tower,
        wall_height=8.0,
        include_wind=True,
        include_broken_wire=True,
        include_seismic=True,
        seismic_pga_g=0.36,
    )
    assert res_full.total_downhill_shear > res_bw.total_downhill_shear
    assert res_full.retaining_wall_surcharge_thrust > 0.0


# -----------------------------------------------------------------------------
# 7. PyVista 3D Wireframe Generation
# -----------------------------------------------------------------------------
@pytest.mark.skipif(not PYVISTA_AVAILABLE, reason="PyVista not installed")
def test_pyvista_3d_wireframe():
    """
    Validates generation of PyVista PolyData wireframe for interactive 3D rendering.
    """
    tower = TransmissionTowerParams(
        base_width=6.0,
        base_length=6.0,
        total_height=35.0,
        crest_offset=8.0,
    )

    poly = build_tower_3d_wireframe(
        tower=tower,
        base_elevation=10.0,
        slope_angle_deg=20.0,
    )

    assert poly is not None
    assert poly.n_points > 15
    assert poly.n_cells > 20
    assert "MemberType" in poly.cell_data
    assert "Elevation" in poly.point_data

    # Bounds check: X should center around crest_offset (8.0m)
    bounds = poly.bounds
    x_min, x_max, y_min, y_max, z_min, z_max = bounds
    assert x_min < 8.0 < x_max
    assert z_max >= 10.0 + 35.0 - 1.0 # Reaches top of tower elevation


# -----------------------------------------------------------------------------
# 8. Error Handling & Invariant Edge Cases
# -----------------------------------------------------------------------------
def test_tower_coupling_edge_cases():
    """
    Tests input bounds validation and edge cases.
    """
    # Negative dimensions
    with pytest.raises(ValueError):
        TransmissionTowerParams(base_width=-5.0)
    with pytest.raises(ValueError):
        TransmissionTowerParams(total_height=0.0)
    with pytest.raises(ValueError):
        TransmissionTowerParams(crest_offset=-2.0)
    with pytest.raises(ValueError):
        TransmissionTowerParams(seismic_mass_ratio=1.5)

    # Wind parameter invalid values
    with pytest.raises(ValueError):
        IS875WindParameters(basic_wind_speed=-40.0)
    with pytest.raises(ValueError):
        IS875WindParameters(terrain_category=5)
    with pytest.raises(ValueError):
        IS875WindParameters(topography_factor_k3=0.8)

    # Zero surcharge depth / offset returns 0
    s_zero = compute_boussinesq_point_surcharge_on_wall(
        point_load_kn=0.0,
        x_offset=5.0,
        y_offset=0.0,
        z_depth=2.0,
        wall_height=8.0,
    )
    assert s_zero == 0.0

    # Negative wall height in surcharge profile raises ValueError
    with pytest.raises(ValueError):
        calculate_retaining_wall_surcharge_distribution({}, wall_height=-8.0)
    with pytest.raises(ValueError):
        calculate_retaining_wall_surcharge_distribution({}, wall_height=8.0, num_eval_points=2)


def test_wind_loads_comprehensive_coverage():
    """
    Exhaustive branch coverage for IS 875 wind formulation.
    """
    # Terrain categories 1, 3, 4
    k2_cat1 = compute_k2_factor(25.0, terrain_category=1)
    k2_cat3 = compute_k2_factor(25.0, terrain_category=3)
    k2_cat4_low = compute_k2_factor(15.0, terrain_category=4)
    k2_cat4_high = compute_k2_factor(35.0, terrain_category=4)

    assert k2_cat1 > 1.05
    assert k2_cat3 > 0.91
    assert k2_cat4_low == 0.80
    assert k2_cat4_high > 0.80

    # Force coefficient for high solidity ratio > 0.40
    cf_dense = compute_lattice_force_coefficient(0.55)
    assert 2.0 <= cf_dense <= 2.1

    # IS875WindParameters validations
    with pytest.raises(ValueError):
        IS875WindParameters(risk_coefficient_k1=-1.0)
    with pytest.raises(ValueError):
        IS875WindParameters(solidity_ratio=0.01)
    with pytest.raises(ValueError):
        IS875WindParameters(solidity_ratio=0.75)
    with pytest.raises(ValueError):
        IS875WindParameters(wind_span=-50.0)
    with pytest.raises(ValueError):
        IS875WindParameters(conductor_diameter=0.0)

    # calculate_transmission_tower_wind_loads validations
    with pytest.raises(ValueError):
        calculate_transmission_tower_wind_loads(tower_height=-20.0, base_width=6.0, top_width=2.0)
    with pytest.raises(ValueError):
        calculate_transmission_tower_wind_loads(tower_height=30.0, base_width=-6.0, top_width=2.0)
    with pytest.raises(ValueError):
        calculate_transmission_tower_wind_loads(tower_height=30.0, base_width=6.0, top_width=-2.0)
    with pytest.raises(ValueError):
        calculate_transmission_tower_wind_loads(tower_height=30.0, base_width=6.0, top_width=8.0) # top > base
    with pytest.raises(ValueError):
        calculate_transmission_tower_wind_loads(tower_height=30.0, base_width=6.0, top_width=2.0, num_panels=1)


def test_tower_coupling_branch_coverage(monkeypatch):
    """
    Exhaustive branch coverage for tower coupling, fallbacks, and properties.
    """
    # 1. f_horizontal_resultant property
    leg = TowerLegReaction(
        leg_id="test_leg",
        x=5.0,
        y=3.0,
        z=0.0,
        f_vertical=200.0,
        f_horizontal_x=30.0,
        f_horizontal_y=40.0,
    )
    assert leg.f_horizontal_resultant == pytest.approx(50.0, abs=1e-3)

    # 2. Point Boussinesq zero returns
    assert compute_boussinesq_point_surcharge_on_wall(-100.0, 5.0, 0.0, 2.0, 8.0) == 0.0
    assert compute_boussinesq_point_surcharge_on_wall(100.0, 5.0, 0.0, -2.0, 8.0) == 0.0
    assert compute_boussinesq_point_surcharge_on_wall(100.0, -5.0, 0.0, 2.0, 8.0) == 0.0
    assert compute_boussinesq_point_surcharge_on_wall(100.0, 0.001, 0.0, 0.001, 8.0) == 0.0

    # 3. Surcharge distribution with zero load
    zero_rx = {
        "leg_1": TowerLegReaction("leg_1", 5.0, -3.0, 0.0, 0.0, 0.0, 0.0),
        "leg_2": TowerLegReaction("leg_2", 5.0, 3.0, 0.0, 0.0, 0.0, 0.0),
    }
    zero_prof = calculate_retaining_wall_surcharge_distribution(zero_rx, wall_height=9.0)
    assert zero_prof.total_thrust_kn_per_m == 0.0
    assert zero_prof.resultant_elevation_m == pytest.approx(3.0, abs=1e-2)

    # 4. Natural frequency fallback with zero stiffness
    tower = TransmissionTowerParams(base_width=6.0, total_height=35.0)
    f_zero = estimate_tower_natural_frequency(tower, steel_modulus_kpa=0.0)
    assert f_zero == 2.20

    # 5. Analytical reactions with & without wind profile & with seismic
    wp = calculate_transmission_tower_wind_loads(35.0, 6.0, 1.5)
    rx_ana_wp, _, _ = _solve_analytical_tower_reactions(
        tower=tower,
        wind_profile=wp,
        include_wind=True,
    )
    assert len(rx_ana_wp) == 4

    rx_ana, _, _ = _solve_analytical_tower_reactions(
        tower=tower,
        wind_profile=None,
        include_wind=True,
        include_broken_wire=False,
        include_seismic=True,
        seismic_pga_g=0.36,
    )
    assert len(rx_ana) == 4

    # 6. Fallback when OpenSees is not available
    import orang3d.physics.tower_coupling as tc
    monkeypatch.setattr(tc, "OPENSEES_AVAILABLE", False)
    rx_no_ops, f_no_ops, ok_no_ops = tc.build_and_solve_opensees_tower(tower)
    assert ok_no_ops is True
    assert len(rx_no_ops) == 4

    # 7. Fallback when PyVista is not available
    monkeypatch.setattr(tc, "PYVISTA_AVAILABLE", False)
    assert tc.build_tower_3d_wireframe(tower) is None

