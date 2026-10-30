"""
Unit tests for orang3D parameter models, data contracts, and bounds enforcement (Phase 1).
"""

import pytest
from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
    validate_seismic_with_soil,
)


def test_retaining_wall_geometry_defaults():
    geom = RetainingWallGeometry()
    assert geom.stem_height == 6.0
    assert geom.footing_thickness == 0.7
    assert geom.total_height == pytest.approx(6.7)
    assert geom.toe_length == 1.0
    assert geom.stem_thickness_base == 0.65
    assert geom.heel_length == 2.5
    assert geom.base_width == pytest.approx(4.15)


def test_retaining_wall_geometry_custom():
    geom = RetainingWallGeometry(
        stem_height=8.0,
        footing_thickness=1.0,
        toe_length=1.5,
        stem_thickness_base=0.8,
        heel_length=3.0,
    )
    assert geom.total_height == pytest.approx(9.0)
    assert geom.base_width == pytest.approx(5.3)


def test_retaining_wall_geometry_invalid_stem_thickness():
    # Stem top cannot be thicker than stem base
    with pytest.raises(ValueError, match="stem_thickness_top.*cannot exceed stem_thickness_base"):
        RetainingWallGeometry(stem_thickness_top=0.8, stem_thickness_base=0.5)


def test_retaining_wall_geometry_non_positive_dimensions():
    # Non-positive stem height
    with pytest.raises(ValueError, match="stem_height must be positive"):
        RetainingWallGeometry(stem_height=0.0)
    with pytest.raises(ValueError, match="stem_height must be positive"):
        RetainingWallGeometry(stem_height=-2.0)

    # Non-positive stem thickness top
    with pytest.raises(ValueError, match="stem_thickness_top must be positive"):
        RetainingWallGeometry(stem_thickness_top=0.0)
    with pytest.raises(ValueError, match="stem_thickness_top must be positive"):
        RetainingWallGeometry(stem_thickness_top=-0.2)

    # Non-positive footing thickness
    with pytest.raises(ValueError, match="footing_thickness must be positive"):
        RetainingWallGeometry(footing_thickness=0.0)

    # Non-positive stem base thickness
    with pytest.raises(ValueError, match="stem_thickness_base must be positive"):
        RetainingWallGeometry(stem_thickness_base=-0.1)

    # Negative toe or heel length
    with pytest.raises(ValueError, match="toe_length cannot be negative"):
        RetainingWallGeometry(toe_length=-0.5)
    with pytest.raises(ValueError, match="heel_length cannot be negative"):
        RetainingWallGeometry(heel_length=-1.0)

    # Non-positive wall length
    with pytest.raises(ValueError, match="wall_length must be positive"):
        RetainingWallGeometry(wall_length=0.0)

    # Non-positive concrete unit weight
    with pytest.raises(ValueError, match="concrete_unit_weight must be positive"):
        RetainingWallGeometry(concrete_unit_weight=-24.0)


def test_retaining_wall_geometry_invalid_shear_key():
    with pytest.raises(ValueError, match="shear_key_depth cannot be negative"):
        RetainingWallGeometry(shear_key_depth=-0.2)
    with pytest.raises(ValueError, match="shear_key_width cannot be negative"):
        RetainingWallGeometry(shear_key_width=-0.5)
    with pytest.raises(ValueError, match=r"shear_key_width.*cannot exceed base_width"):
        RetainingWallGeometry(shear_key_width=10.0, toe_length=1.0, stem_thickness_base=0.5, heel_length=1.0)


def test_soil_properties_defaults():
    soil = SoilProperties()
    assert soil.friction_angle == 32.0
    assert soil.cohesion == 0.0
    assert soil.unit_weight == 18.0
    assert soil.saturated_unit_weight == 20.0
    assert soil.wall_friction_angle == 20.0
    assert soil.foundation_friction_angle == 30.0
    assert soil.allowable_bearing_capacity == 350.0


def test_soil_properties_invalid_friction_angle():
    with pytest.raises(ValueError, match="friction_angle must be between 0 and 55"):
        SoilProperties(friction_angle=0.0)
    with pytest.raises(ValueError, match="friction_angle must be between 0 and 55"):
        SoilProperties(friction_angle=-5.0)
    with pytest.raises(ValueError, match="friction_angle must be between 0 and 55"):
        SoilProperties(friction_angle=60.0)


def test_soil_properties_invalid_cohesion():
    with pytest.raises(ValueError, match="cohesion cannot be negative"):
        SoilProperties(cohesion=-10.0)


def test_soil_properties_invalid_unit_weights():
    with pytest.raises(ValueError, match="unit_weight must be positive"):
        SoilProperties(unit_weight=0.0)
    with pytest.raises(ValueError, match="saturated_unit_weight must be positive"):
        SoilProperties(saturated_unit_weight=-5.0)
    with pytest.raises(ValueError, match=r"saturated_unit_weight.*must be >= unit_weight"):
        SoilProperties(unit_weight=20.0, saturated_unit_weight=18.0)


def test_soil_properties_invalid_wall_friction():
    with pytest.raises(ValueError, match="wall_friction_angle cannot be negative"):
        SoilProperties(wall_friction_angle=-1.0)
    with pytest.raises(ValueError, match=r"wall_friction_angle.*cannot exceed.*friction_angle"):
        SoilProperties(friction_angle=30.0, wall_friction_angle=35.0)


def test_soil_properties_invalid_foundation_params():
    with pytest.raises(ValueError, match="foundation_friction_angle must be between 0 and 55"):
        SoilProperties(foundation_friction_angle=0.0)
    with pytest.raises(ValueError, match="foundation_cohesion cannot be negative"):
        SoilProperties(foundation_cohesion=-5.0)
    with pytest.raises(ValueError, match="foundation_unit_weight must be positive"):
        SoilProperties(foundation_unit_weight=0.0)
    with pytest.raises(ValueError, match="allowable_bearing_capacity must be positive"):
        SoilProperties(allowable_bearing_capacity=-50.0)


def test_seismic_params_defaults():
    seismic = SeismicParams()
    assert seismic.horizontal_pga == 0.25
    assert seismic.vertical_pga == 0.125
    assert seismic.backfill_slope == 0.0
    assert seismic.water_table_depth == 4.0
    assert seismic.liquefaction_factor == 0.0


def test_seismic_params_invalid_pga():
    with pytest.raises(ValueError, match="horizontal_pga must be between 0.0 and 1.5"):
        SeismicParams(horizontal_pga=-0.1)
    with pytest.raises(ValueError, match="horizontal_pga must be between 0.0 and 1.5"):
        SeismicParams(horizontal_pga=2.0)
    with pytest.raises(ValueError, match="vertical_pga must be between 0.0 and 1.5"):
        SeismicParams(vertical_pga=-0.05)
    with pytest.raises(ValueError, match="vertical_pga must be between 0.0 and 1.5"):
        SeismicParams(vertical_pga=1.8)


def test_seismic_params_invalid_slope_and_water():
    with pytest.raises(ValueError, match="backfill_slope must be between 0 and 50"):
        SeismicParams(backfill_slope=-1.0)
    with pytest.raises(ValueError, match="backfill_slope must be between 0 and 50"):
        SeismicParams(backfill_slope=55.0)
    with pytest.raises(ValueError, match="water_table_depth cannot be negative"):
        SeismicParams(water_table_depth=-1.0)
    with pytest.raises(ValueError, match="liquefaction_factor must be between 0.0 and 1.0"):
        SeismicParams(liquefaction_factor=-0.1)
    with pytest.raises(ValueError, match="liquefaction_factor must be between 0.0 and 1.0"):
        SeismicParams(liquefaction_factor=1.5)
    with pytest.raises(ValueError, match="pore_pressure_ratio_ru must be between 0.0 and 1.0"):
        SeismicParams(pore_pressure_ratio_ru=-0.1)
    with pytest.raises(ValueError, match="pore_pressure_ratio_ru must be between 0.0 and 1.0"):
        SeismicParams(pore_pressure_ratio_ru=1.5)


def test_soil_properties_elastic_params_validation():
    with pytest.raises(ValueError, match="elastic_modulus must be positive"):
        SoilProperties(elastic_modulus=0.0)
    with pytest.raises(ValueError, match="poissons_ratio must be between 0.0 and 0.5"):
        SoilProperties(poissons_ratio=-0.1)
    with pytest.raises(ValueError, match="poissons_ratio must be between 0.0 and 0.5"):
        SoilProperties(poissons_ratio=0.5)


def test_validate_seismic_with_soil_compatibility():
    soil = SoilProperties(friction_angle=30.0)
    valid_seismic = SeismicParams(backfill_slope=20.0)
    assert validate_seismic_with_soil(valid_seismic, soil) is True

    # Backfill slope equal to or greater than friction angle is unphysical
    invalid_seismic = SeismicParams(backfill_slope=32.0)
    with pytest.raises(ValueError, match="backfill_slope.*cannot exceed soil friction_angle"):
        validate_seismic_with_soil(invalid_seismic, soil)


def test_analysis_results_dataclass():
    results = AnalysisResults(
        k_ae=0.45,
        k_a_static=0.28,
        delta_k_ae=0.17,
        total_thrust=180.5,
        thrust_height=2.4,
        water_thrust=25.0,
        fs_sliding=1.45,
        fs_overturning=2.1,
        fs_bearing=2.5,
        max_bearing_pressure=210.0,
        min_bearing_pressure=45.0,
        eccentricity=0.35,
        max_bending_moment=380.0,
        max_shear_force=160.0,
        concrete_tensile_stress=2.4,
        cracking_predicted=False,
    )
    assert results.fs_sliding == 1.45
    assert results.fs_overturning == 2.1
    assert results.cracking_predicted is False


def test_analysis_results_validation():
    with pytest.raises(ValueError, match="fs_sliding cannot be negative"):
        AnalysisResults(fs_sliding=-1.0)
    with pytest.raises(ValueError, match="fs_overturning cannot be negative"):
        AnalysisResults(fs_overturning=-0.5)
    with pytest.raises(ValueError, match="fs_bearing cannot be negative"):
        AnalysisResults(fs_bearing=-2.0)
    with pytest.raises(ValueError, match="total_thrust cannot be negative"):
        AnalysisResults(total_thrust=-10.0)
