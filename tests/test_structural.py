"""
Unit, invariant, and design code validation tests for Structural Concrete & Rebar Demand Mechanics (Phase 4).
Covers:
- Continuous internal shear force profile V(y) and bending moment profile M(y)
- Differential equilibrium invariant: dM/dy = -V(y) and M(0) = integral(V)
- Crest boundary conditions: M(H) = 0, V(H) = 0
- Elastic flexural tensile stress profile sigma_t(y) and cracking transition
- ACI 318 / Eurocode 2 flexural reinforcement demand A_s and A_s,min
- Concrete shear capacity phi*V_c and shear reinforcement check
- Parametric sensitivity to concrete grade (f'c) and rebar grade (fy)
"""

import pytest
import numpy as np

from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
)
from orang3d.physics.structural import (
    compute_stem_internal_profiles,
    design_flexural_reinforcement,
    StemStructuralProfile,
    RebarDesignResults,
)


@pytest.fixture
def structural_setup():
    geom = RetainingWallGeometry(
        stem_height=6.0,
        stem_thickness_top=0.35,
        stem_thickness_base=0.70,
        toe_length=1.0,
        heel_length=2.5,
        footing_thickness=0.7,
        wall_length=1.0,
    )
    soil = SoilProperties(
        friction_angle=32.0,
        wall_friction_angle=20.0,
        unit_weight=18.0,
    )
    seismic = SeismicParams(
        horizontal_pga=0.20,
        vertical_pga=0.10,
        water_table_depth=4.0,
    )
    return geom, soil, seismic


def test_crest_and_base_boundary_conditions(structural_setup):
    """Bending moment and shear force must be identically 0 at crest and peak at base."""
    geom, soil, seismic = structural_setup
    profile = compute_stem_internal_profiles(geom, soil, seismic, n_points=50)

    assert isinstance(profile, StemStructuralProfile)
    assert len(profile.heights) == 50

    # Crest boundary (y = H_stem, index -1)
    assert profile.heights[-1] == pytest.approx(geom.stem_height, abs=1e-3)
    assert profile.bending_moments[-1] == pytest.approx(0.0, abs=1e-3)
    assert profile.shear_forces[-1] == pytest.approx(0.0, abs=1e-3)
    assert profile.tensile_stresses[-1] == pytest.approx(0.0, abs=1e-3)

    # Base junction boundary (y = 0, index 0)
    assert profile.heights[0] == pytest.approx(0.0, abs=1e-3)
    assert profile.bending_moments[0] == pytest.approx(profile.max_bending_moment, abs=1e-3)
    assert profile.shear_forces[0] == pytest.approx(profile.max_shear_force, abs=1e-3)
    assert profile.tensile_stresses[0] == pytest.approx(profile.max_tensile_stress, abs=1e-3)

    # Moments and shears must be non-negative and monotonic
    assert np.all(profile.bending_moments >= 0.0)
    assert np.all(profile.shear_forces >= 0.0)
    # Moment decreases from base to crest
    assert np.all(np.diff(profile.bending_moments) <= 1e-4)


def test_differential_equilibrium_invariant(structural_setup):
    """Verify that bending moment is the integral of shear force: dM/dy = -V(y)."""
    geom, soil, seismic = structural_setup
    n_pts = 100
    profile = compute_stem_internal_profiles(geom, soil, seismic, n_points=n_pts)

    y = profile.heights
    M = profile.bending_moments
    V = profile.shear_forces

    # Numerical derivative dM/dy
    dM_dy = np.gradient(M, y)
    # Invariant: dM/dy = -V
    rel_error = np.mean(np.abs(dM_dy + V)) / max(1.0, np.max(V))
    assert rel_error < 0.05, f"dM/dy != -V relative error {rel_error:.4f} exceeded 5%"

    # Trapezoidal integral of shear force: M(0) = integral_0^H V(y) dy
    _trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
    integrated_moment = _trapz(V, y)
    assert integrated_moment == pytest.approx(profile.max_bending_moment, rel=0.03)


def test_stem_thickness_and_stress_profile(structural_setup):
    """Verify stem linear taper and elastic tensile stress calculation."""
    geom, soil, seismic = structural_setup
    profile = compute_stem_internal_profiles(geom, soil, seismic, n_points=25)

    # Stem thickness tapers from t_base at y=0 to t_top at y=H
    assert profile.thicknesses[0] == pytest.approx(geom.stem_thickness_base, abs=1e-3)
    assert profile.thicknesses[-1] == pytest.approx(geom.stem_thickness_top, abs=1e-3)

    # Section modulus Z = (1.0 * t^2) / 6
    expected_z_base = (1.0 * (geom.stem_thickness_base ** 2)) / 6.0
    expected_sigma_base = (profile.max_bending_moment / expected_z_base) / 1000.0  # MPa
    assert profile.max_tensile_stress == pytest.approx(expected_sigma_base, rel=1e-3)


def test_concrete_cracking_transition(structural_setup):
    """Cracking flag toggles precisely as max tensile stress exceeds modulus of rupture."""
    geom, soil, _ = structural_setup

    # Mild seismic load -> stress below cracking threshold
    seismic_mild = SeismicParams(horizontal_pga=0.02, water_table_depth=10.0)
    profile_mild = compute_stem_internal_profiles(geom, soil, seismic_mild)
    assert profile_mild.max_tensile_stress < profile_mild.modulus_of_rupture
    assert profile_mild.cracking_predicted is False

    # Extreme seismic load -> stress exceeds cracking modulus
    seismic_severe = SeismicParams(horizontal_pga=0.50, water_table_depth=10.0)
    profile_severe = compute_stem_internal_profiles(geom, soil, seismic_severe)
    assert profile_severe.max_tensile_stress > profile_severe.modulus_of_rupture
    assert profile_severe.cracking_predicted is True


def test_rebar_design_flexure_and_minimums():
    """Verify flexural reinforcement demand A_s and A_s,min compliance with ACI 318."""
    # Stem base thickness = 0.70m, cover = 0.05m -> d ~ 0.64m
    rebar = design_flexural_reinforcement(
        bending_moment_kNm=300.0,
        shear_force_kN=150.0,
        stem_thickness_base=0.70,
        concrete_strength_mpa=28.0,
        steel_yield_mpa=420.0,
        clear_cover_m=0.05,
    )

    assert isinstance(rebar, RebarDesignResults)
    assert rebar.required_steel_area > 0.0
    # Must meet or exceed minimum steel area
    assert rebar.required_steel_area >= rebar.minimum_steel_area
    assert rebar.reinforcement_ratio > 0.0018  # Minimum shrinkage/temperature ratio
    assert rebar.concrete_shear_capacity > 0.0
    assert len(rebar.recommended_bar_callout) > 0


def test_shear_capacity_reinforcement_trigger():
    """Shear reinforcement is triggered when V_u exceeds phi * V_c."""
    thickness = 0.60
    # Low shear: within concrete capacity
    rebar_safe_shear = design_flexural_reinforcement(
        bending_moment_kNm=200.0,
        shear_force_kN=100.0,
        stem_thickness_base=thickness,
    )
    assert rebar_safe_shear.shear_reinforcement_required is False

    # Extreme shear: exceeds concrete capacity
    rebar_high_shear = design_flexural_reinforcement(
        bending_moment_kNm=400.0,
        shear_force_kN=600.0,
        stem_thickness_base=thickness,
    )
    assert rebar_high_shear.shear_reinforcement_required is True


def test_material_grade_sensitivity():
    """Higher rebar yield strength (fy) and concrete grade (f'c) reduce steel area."""
    m_u = 350.0
    v_u = 180.0
    t_base = 0.75

    rebar_grade_420 = design_flexural_reinforcement(
        m_u, v_u, t_base, concrete_strength_mpa=28.0, steel_yield_mpa=420.0
    )
    rebar_grade_500 = design_flexural_reinforcement(
        m_u, v_u, t_base, concrete_strength_mpa=35.0, steel_yield_mpa=500.0
    )

    # Steel demand should be lower with higher yield strength
    assert rebar_grade_500.required_steel_area < rebar_grade_420.required_steel_area
    # Shear capacity of 35 MPa concrete must exceed 28 MPa concrete
    assert rebar_grade_500.concrete_shear_capacity > rebar_grade_420.concrete_shear_capacity

    # Extreme over-reinforced moment check
    rebar_extreme = design_flexural_reinforcement(
        bending_moment_kNm=50000.0,
        shear_force_kN=500.0,
        stem_thickness_base=0.50,
    )
    assert rebar_extreme.required_steel_area > 0.0
