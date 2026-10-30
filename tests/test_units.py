"""
Unit tests for Unit Conversion & Invariants (Phase 1).
"""

import pytest
from orang3d.units import (
    UnitSystem,
    m_to_ft,
    ft_to_m,
    kn_to_kips,
    kips_to_kn,
    kn_m3_to_pcf,
    pcf_to_kn_m3,
    kpa_to_psf,
    psf_to_kpa,
    kpa_to_ksf,
    ksf_to_kpa,
    kn_m_to_kip_ft,
    kip_ft_to_kn_m,
    convert_geometry_units,
    convert_soil_units,
)
from orang3d.models.wall_params import RetainingWallGeometry, SoilProperties


def test_distance_roundtrip_invariants():
    test_distances = [0.1, 1.0, 5.5, 12.345, 100.0]
    for d in test_distances:
        ft = m_to_ft(d)
        m_back = ft_to_m(ft)
        assert abs(m_back - d) < 1e-7, f"Drift {abs(m_back - d)} exceeded 1e-7 for distance {d}"


def test_force_roundtrip_invariants():
    test_forces = [1.0, 50.0, 250.75, 1000.0]
    for f in test_forces:
        kips = kn_to_kips(f)
        kn_back = kips_to_kn(kips)
        assert abs(kn_back - f) < 1e-7, f"Drift {abs(kn_back - f)} exceeded 1e-7 for force {f}"


def test_unit_weight_roundtrip_invariants():
    test_unit_weights = [15.0, 18.0, 19.5, 24.0]
    for gamma in test_unit_weights:
        pcf = kn_m3_to_pcf(gamma)
        gamma_back = pcf_to_kn_m3(pcf)
        assert abs(gamma_back - gamma) < 1e-7, f"Drift {abs(gamma_back - gamma)} exceeded 1e-7 for gamma {gamma}"


def test_pressure_roundtrip_invariants():
    test_pressures = [10.0, 101.325, 250.0, 500.0]
    for p in test_pressures:
        psf = kpa_to_psf(p)
        p_back = psf_to_kpa(psf)
        assert abs(p_back - p) < 1e-7, f"Drift {abs(p_back - p)} exceeded 1e-7 for pressure {p}"

        ksf = kpa_to_ksf(p)
        p_back_ksf = ksf_to_kpa(ksf)
        assert abs(p_back_ksf - p) < 1e-7, f"Drift {abs(p_back_ksf - p)} exceeded 1e-7 for pressure {p}"


def test_moment_roundtrip_invariants():
    test_moments = [5.0, 150.0, 450.25, 2000.0]
    for m in test_moments:
        kip_ft = kn_m_to_kip_ft(m)
        m_back = kip_ft_to_kn_m(kip_ft)
        assert abs(m_back - m) < 1e-7, f"Drift {abs(m_back - m)} exceeded 1e-7 for moment {m}"


def test_standard_known_conversions():
    # 1 meter is approx 3.28084 feet
    assert m_to_ft(1.0) == pytest.approx(3.28084, rel=1e-4)
    # 1 kN is approx 0.224809 kips
    assert kn_to_kips(1.0) == pytest.approx(0.224809, rel=1e-4)
    # 18 kN/m^3 is approx 114.59 pcf
    assert kn_m3_to_pcf(18.0) == pytest.approx(114.59, rel=1e-3)
    # 100 kPa is approx 2.08854 ksf
    assert kpa_to_ksf(100.0) == pytest.approx(2.08854, rel=1e-4)


def test_model_geometry_unit_conversions():
    si_geom = RetainingWallGeometry(
        stem_height=6.0,
        stem_thickness_top=0.35,
        stem_thickness_base=0.65,
        toe_length=1.0,
        heel_length=2.5,
        footing_thickness=0.7,
        shear_key_depth=0.4,
        shear_key_width=0.5,
        wall_length=5.0,
        concrete_unit_weight=24.0,
    )
    # Identity conversion
    same_geom = convert_geometry_units(si_geom, from_system=UnitSystem.SI, to_system=UnitSystem.SI)
    assert same_geom.stem_height == si_geom.stem_height

    imp_geom = convert_geometry_units(si_geom, from_system=UnitSystem.SI, to_system=UnitSystem.IMPERIAL)
    assert imp_geom.stem_height == pytest.approx(m_to_ft(6.0), rel=1e-6)
    assert imp_geom.concrete_unit_weight == pytest.approx(kn_m3_to_pcf(24.0), rel=1e-6)

    # Convert back to SI
    si_restored = convert_geometry_units(imp_geom, from_system=UnitSystem.IMPERIAL, to_system=UnitSystem.SI)
    assert si_restored.stem_height == pytest.approx(si_geom.stem_height, abs=1e-6)
    assert si_restored.concrete_unit_weight == pytest.approx(si_geom.concrete_unit_weight, abs=1e-6)
    assert si_restored.total_height == pytest.approx(si_geom.total_height, abs=1e-6)


def test_model_soil_unit_conversions():
    si_soil = SoilProperties(
        friction_angle=32.0,
        cohesion=10.0,
        unit_weight=18.0,
        saturated_unit_weight=20.0,
        wall_friction_angle=20.0,
        foundation_friction_angle=30.0,
        foundation_cohesion=25.0,
        foundation_unit_weight=19.0,
        allowable_bearing_capacity=350.0,
    )
    # Identity conversion
    same_soil = convert_soil_units(si_soil, from_system=UnitSystem.SI, to_system=UnitSystem.SI)
    assert same_soil.unit_weight == si_soil.unit_weight

    imp_soil = convert_soil_units(si_soil, from_system=UnitSystem.SI, to_system=UnitSystem.IMPERIAL)
    # Angles should remain unchanged in degrees
    assert imp_soil.friction_angle == 32.0
    assert imp_soil.cohesion == pytest.approx(kpa_to_psf(10.0), rel=1e-6)
    assert imp_soil.unit_weight == pytest.approx(kn_m3_to_pcf(18.0), rel=1e-6)

    # Convert back to SI
    si_restored = convert_soil_units(imp_soil, from_system=UnitSystem.IMPERIAL, to_system=UnitSystem.SI)
    assert si_restored.cohesion == pytest.approx(si_soil.cohesion, abs=1e-6)
    assert si_restored.unit_weight == pytest.approx(si_soil.unit_weight, abs=1e-6)
    assert si_restored.allowable_bearing_capacity == pytest.approx(si_soil.allowable_bearing_capacity, abs=1e-6)
