"""
Unit and invariant tests for orang3D Advanced Geotechnical Suite Phase 1:
Data Contracts, Validation Schemas, and Engineering Invariants.
"""

import json
import math
import pytest
from orang3d.models.advanced_wall_params import (
    CurvedShellGeometry,
    PierAndPileGeometry,
    StrutSupportSystem,
    MultiStrutPiledWallModel,
)
from orang3d.models.tower_params import TransmissionTowerParams
from orang3d.models.is_code_params import (
    IndianDesignStandards,
    SeismicZone,
    FoundationSoilType,
    SEISMIC_ZONE_FACTORS,
)


# ==============================================================================
# 1. CurvedShellGeometry Tests
# ==============================================================================

def test_shell_geometry_defaults():
    shell = CurvedShellGeometry()
    assert shell.radius == 4.0
    assert shell.subtended_angle == 60.0
    assert shell.thickness == 0.25
    assert shell.crown_to_backfill is True
    assert shell.bay_span == 4.0
    assert shell.panel_height == 6.0
    assert shell.concrete_grade == "M30"
    assert shell.concrete_unit_weight == 25.0


def test_shell_geometry_properties():
    # R = 4.0 m, 2*theta = 60 deg -> theta = 30 deg = pi/6 rad
    shell = CurvedShellGeometry(radius=4.0, subtended_angle=60.0, thickness=0.20, panel_height=5.0)
    assert shell.half_angle_rad == pytest.approx(math.pi / 6.0)
    # Arc length S = R * 2*theta_rad = 4 * (pi/3)
    assert shell.arc_length == pytest.approx(4.0 * (math.pi / 3.0))
    # Chord length C = 2 * R * sin(theta) = 2 * 4 * sin(30 deg) = 4.0 m
    assert shell.chord_length == pytest.approx(4.0)
    # Sagitta f = R * (1 - cos(30 deg)) = 4 * (1 - sqrt(3)/2)
    assert shell.crown_sagitta == pytest.approx(4.0 * (1.0 - math.cos(math.radians(30))))
    # Surface area = S * H_p
    assert shell.surface_area == pytest.approx(shell.arc_length * 5.0)
    # Concrete volume = surface_area * thickness
    assert shell.concrete_volume == pytest.approx(shell.surface_area * 0.20)
    # Total weight = volume * 25.0
    assert shell.total_weight == pytest.approx(shell.concrete_volume * 25.0)


def test_shell_geometry_bounds():
    """Phase 1.4: Rejects 2*theta >= 180 deg or t_s <= 0.05 m."""
    # Subtended angle >= 180 degrees
    with pytest.raises(ValueError, match="subtended_angle must be strictly between 0 and 180 degrees"):
        CurvedShellGeometry(subtended_angle=180.0)
    with pytest.raises(ValueError, match="subtended_angle must be strictly between 0 and 180 degrees"):
        CurvedShellGeometry(subtended_angle=200.0)
    with pytest.raises(ValueError, match="subtended_angle must be strictly between 0 and 180 degrees"):
        CurvedShellGeometry(subtended_angle=0.0)
    with pytest.raises(ValueError, match="subtended_angle must be strictly between 0 and 180 degrees"):
        CurvedShellGeometry(subtended_angle=-10.0)

    # Thickness <= 0.05 m (50 mm)
    with pytest.raises(ValueError, match="thickness must be > 0.05 m"):
        CurvedShellGeometry(thickness=0.05)
    with pytest.raises(ValueError, match="thickness must be > 0.05 m"):
        CurvedShellGeometry(thickness=0.03)
    with pytest.raises(ValueError, match="thickness must be > 0.05 m"):
        CurvedShellGeometry(thickness=-0.2)

    # Positive dimensions
    with pytest.raises(ValueError, match="radius must be positive"):
        CurvedShellGeometry(radius=0.0)
    with pytest.raises(ValueError, match="radius must be positive"):
        CurvedShellGeometry(radius=-2.0)
    with pytest.raises(ValueError, match="bay_span must be positive"):
        CurvedShellGeometry(bay_span=0.0)
    with pytest.raises(ValueError, match="panel_height must be positive"):
        CurvedShellGeometry(panel_height=-5.0)
    with pytest.raises(ValueError, match="concrete_unit_weight must be positive"):
        CurvedShellGeometry(concrete_unit_weight=0.0)

    # Bay span exceeding cylinder diameter (2*R)
    with pytest.raises(ValueError, match="bay_span.*cannot exceed cylinder diameter"):
        CurvedShellGeometry(radius=2.0, bay_span=5.0)


# ==============================================================================
# 2. PierAndPileGeometry Tests
# ==============================================================================

def test_pile_geometry_defaults():
    pp = PierAndPileGeometry()
    assert pp.pier_width == 0.8
    assert pp.pier_depth == 1.0
    assert pp.pier_height == 6.5
    assert pp.pile_diameter == 0.8
    assert pp.pile_length == 10.0
    assert pp.num_piles_per_pier == 2
    assert pp.pile_spacing == 2.5
    assert pp.pile_cap_width == 1.2
    assert pp.pile_cap_length == 3.5
    assert pp.pile_cap_depth == 1.0
    assert pp.concrete_unit_weight == 25.0


def test_pile_geometry_properties():
    pp = PierAndPileGeometry(
        pier_width=1.0,
        pier_depth=1.0,
        pier_height=6.0,
        pile_diameter=1.0,
        pile_length=12.0,
        num_piles_per_pier=2,
        pile_spacing=3.0,
        pile_cap_width=1.5,
        pile_cap_length=4.0,
        pile_cap_depth=1.0,
        concrete_unit_weight=24.0,
    )
    # Area = pi * (1.0/2)^2 = pi * 0.25
    assert pp.pile_cross_sectional_area == pytest.approx(math.pi * 0.25)
    # Perimeter = pi * 1.0
    assert pp.pile_perimeter == pytest.approx(math.pi)
    # Total pile length = 2 * 12.0 = 24.0
    assert pp.total_pile_length == pytest.approx(24.0)
    # Pier volume = 1.0 * 1.0 * 6.0 = 6.0 m^3
    assert pp.pier_volume == pytest.approx(6.0)
    # Cap volume = 1.5 * 4.0 * 1.0 = 6.0 m^3
    assert pp.pile_cap_volume == pytest.approx(6.0)
    # Total piles volume = 2 * (pi * 0.25) * 12.0 = 6.0 * pi m^3
    assert pp.total_piles_volume == pytest.approx(6.0 * math.pi)
    # Substructure weight
    expected_vol = 6.0 + 6.0 + 6.0 * math.pi
    assert pp.total_substructure_volume == pytest.approx(expected_vol)
    assert pp.total_substructure_weight == pytest.approx(expected_vol * 24.0)


def test_pile_geometry_invariants():
    """Phase 1.4: Rejects L_pile <= 0 or s_p < 2.5 * D_p."""
    # Pile length <= 0
    with pytest.raises(ValueError, match="pile_length must be positive"):
        PierAndPileGeometry(pile_length=0.0)
    with pytest.raises(ValueError, match="pile_length must be positive"):
        PierAndPileGeometry(pile_length=-5.0)

    # Pile spacing < 2.5 * D_p for group piles
    # With D_p = 0.8, min spacing is 2.5 * 0.8 = 2.0 m
    with pytest.raises(ValueError, match="pile_spacing.*must be >= 2.5 \\* pile_diameter"):
        PierAndPileGeometry(pile_diameter=0.8, num_piles_per_pier=2, pile_spacing=1.8)

    # Single pile allows spacing 0.0 or positive
    single_pile = PierAndPileGeometry(num_piles_per_pier=1, pile_spacing=0.0)
    assert single_pile.num_piles_per_pier == 1
    assert single_pile.pile_spacing == 0.0

    with pytest.raises(ValueError, match="pile_spacing cannot be negative"):
        PierAndPileGeometry(num_piles_per_pier=1, pile_spacing=-1.0)

    # Number of piles >= 1
    with pytest.raises(ValueError, match="num_piles_per_pier must be >= 1"):
        PierAndPileGeometry(num_piles_per_pier=0)

    # Dimensions > 0
    with pytest.raises(ValueError, match="pier_width must be positive"):
        PierAndPileGeometry(pier_width=0.0)
    with pytest.raises(ValueError, match="pier_depth must be positive"):
        PierAndPileGeometry(pier_depth=-0.5)
    with pytest.raises(ValueError, match="pier_height must be positive"):
        PierAndPileGeometry(pier_height=0.0)
    with pytest.raises(ValueError, match="pile_diameter must be positive"):
        PierAndPileGeometry(pile_diameter=-0.8)
    with pytest.raises(ValueError, match="pile_cap_width must be positive"):
        PierAndPileGeometry(pile_cap_width=0.0)
    with pytest.raises(ValueError, match="pile_cap_length must be positive"):
        PierAndPileGeometry(pile_cap_length=-1.0)
    with pytest.raises(ValueError, match="pile_cap_depth must be positive"):
        PierAndPileGeometry(pile_cap_depth=0.0)
    with pytest.raises(ValueError, match="concrete_unit_weight must be positive"):
        PierAndPileGeometry(concrete_unit_weight=-25.0)


# ==============================================================================
# 3. StrutSupportSystem Tests
# ==============================================================================

def test_strut_support_defaults():
    struts = StrutSupportSystem()
    assert struts.strut_levels == [2.5, 5.0]
    assert struts.inclination_angle == 25.0
    assert struts.cross_section_area == 0.015
    assert struts.moment_of_inertia == 1.5e-4
    assert struts.elastic_modulus == 2.0e8
    assert struts.yield_strength == 250.0
    assert struts.pre_stress_load == 50.0
    assert struts.allowable_slenderness == 180.0
    assert struts.unbraced_length == 8.0
    assert struts.num_struts == 2


def test_strut_support_properties():
    struts = StrutSupportSystem(
        cross_section_area=0.01,
        moment_of_inertia=1.0e-4,
        elastic_modulus=2.0e8,
        yield_strength=350.0,
        unbraced_length=5.0,
    )
    # r = sqrt(I / A) = sqrt(1e-4 / 1e-2) = sqrt(0.01) = 0.1 m
    assert struts.radius_of_gyration == pytest.approx(0.1)
    # lambda = L / r = 5.0 / 0.1 = 50.0
    assert struts.slenderness_ratio == pytest.approx(50.0)
    # Euler buckling P_cr = pi^2 * E * I / L^2 = pi^2 * 2e8 * 1e-4 / 25 = pi^2 * 800 kN
    expected_pcr = (math.pi ** 2 * 2.0e8 * 1.0e-4) / (5.0 ** 2)
    assert struts.euler_buckling_load == pytest.approx(expected_pcr)
    # Yield capacity P_y = A * (f_y * 1000) = 0.01 * 350,000 = 3500 kN
    assert struts.yield_capacity == pytest.approx(3500.0)


def test_strut_spacing_bounds():
    """Phase 1.4: Validates that strut levels fit within total pier height H_pier."""
    struts = StrutSupportSystem(strut_levels=[2.0, 4.5])
    # Fits within pier_height = 5.0 m
    assert struts.validate_with_pier(5.0) is True

    # Violates pier_height (strut level >= pier height)
    with pytest.raises(ValueError, match=r"strut level \(4.5 m\) must be strictly less than total pier_height \(4.0 m\)"):
        struts.validate_with_pier(4.0)

    # Strut levels must be strictly increasing
    with pytest.raises(ValueError, match="strut_levels must be strictly increasing"):
        StrutSupportSystem(strut_levels=[4.0, 2.0])

    # Cannot have duplicate depths
    with pytest.raises(ValueError, match="strut_levels cannot contain duplicate depths"):
        StrutSupportSystem(strut_levels=[2.0, 2.0])

    # Cannot be empty
    with pytest.raises(ValueError, match="strut_levels cannot be empty"):
        StrutSupportSystem(strut_levels=[])

    # Negative depth
    with pytest.raises(ValueError, match=r"strut level at index 0 cannot be negative"):
        StrutSupportSystem(strut_levels=[-1.0, 3.0])

    # Inclination angle bounds
    with pytest.raises(ValueError, match="inclination_angle must be between 0 and 60 degrees"):
        StrutSupportSystem(inclination_angle=-5.0)
    with pytest.raises(ValueError, match="inclination_angle must be between 0 and 60 degrees"):
        StrutSupportSystem(inclination_angle=70.0)

    # Positive properties
    with pytest.raises(ValueError, match="cross_section_area must be positive"):
        StrutSupportSystem(cross_section_area=0.0)
    with pytest.raises(ValueError, match="moment_of_inertia must be positive"):
        StrutSupportSystem(moment_of_inertia=-1.0e-4)
    with pytest.raises(ValueError, match="elastic_modulus must be positive"):
        StrutSupportSystem(elastic_modulus=0.0)
    with pytest.raises(ValueError, match="yield_strength must be positive"):
        StrutSupportSystem(yield_strength=-250.0)
    with pytest.raises(ValueError, match="pre_stress_load cannot be negative"):
        StrutSupportSystem(pre_stress_load=-10.0)
    with pytest.raises(ValueError, match="allowable_slenderness must be positive"):
        StrutSupportSystem(allowable_slenderness=0.0)
    with pytest.raises(ValueError, match="unbraced_length must be positive"):
        StrutSupportSystem(unbraced_length=-8.0)


# ==============================================================================
# 4. MultiStrutPiledWallModel Composite Tests
# ==============================================================================

def test_composite_system_model_defaults():
    model = MultiStrutPiledWallModel()
    assert model.shell.panel_height == 6.0
    assert model.pier_pile.pier_height == 6.5
    assert model.struts.strut_levels == [2.5, 5.0]


def test_composite_system_model_cross_validation():
    # Strut level exceeds pier height
    with pytest.raises(ValueError, match="must be strictly less than total pier_height"):
        MultiStrutPiledWallModel(
            pier_pile=PierAndPileGeometry(pier_height=4.0),
            struts=StrutSupportSystem(strut_levels=[2.0, 4.5]),
        )

    # Pier height smaller than shell panel height
    with pytest.raises(ValueError, match="cannot be smaller than shell panel_height"):
        MultiStrutPiledWallModel(
            shell=CurvedShellGeometry(panel_height=8.0),
            pier_pile=PierAndPileGeometry(pier_height=6.0),
            struts=StrutSupportSystem(strut_levels=[2.0, 4.0]),
        )


# ==============================================================================
# 5. TransmissionTowerParams Tests
# ==============================================================================

def test_tower_params_defaults():
    tower = TransmissionTowerParams()
    assert tower.base_width == 6.0
    assert tower.base_length == 6.0
    assert tower.total_height == 35.0
    assert tower.crest_offset == 8.0
    assert tower.vertical_load_per_leg == 250.0
    assert tower.wind_shear_per_leg == 45.0
    assert tower.broken_wire_tension == 80.0
    assert tower.seismic_mass_ratio == 0.15


def test_tower_params_load_computations():
    tower = TransmissionTowerParams(
        base_width=6.0,
        base_length=6.0,
        total_height=30.0,
        vertical_load_per_leg=200.0,
        wind_shear_per_leg=40.0,
        broken_wire_tension=60.0,
    )
    # Total vertical load = 4 * 200 = 800 kN
    assert tower.total_vertical_load == pytest.approx(800.0)
    # Total wind shear = 4 * 40 = 160 kN
    assert tower.total_wind_shear == pytest.approx(160.0)
    # Overturning moment wind = 160 * (30 / 2) = 2400 kNm
    assert tower.wind_overturning_moment == pytest.approx(2400.0)
    # Broken wire torsional moment = 60 * (6.0 / 2) = 180 kNm
    assert tower.broken_wire_torsional_moment == pytest.approx(180.0)
    # Broken wire overturning moment = 60 * (0.85 * 30) = 1530 kNm
    assert tower.broken_wire_overturning_moment == pytest.approx(1530.0)

    # Test leg vertical reactions:
    # delta_p_wind = 2400 / (2 * 6) = 200 kN
    # delta_p_bw = 1530 / (2 * 6) = 127.5 kN
    reactions = tower.compute_leg_vertical_reactions(include_wind=True, include_broken_wire=True)
    assert reactions["leg_1_uphill_left"] == pytest.approx(200.0 - 200.0 - 127.5) # -127.5 (uplift)
    assert reactions["leg_2_uphill_right"] == pytest.approx(200.0 - 200.0 + 127.5) # +127.5
    assert reactions["leg_3_downhill_right"] == pytest.approx(200.0 + 200.0 + 127.5) # +527.5 (heavy compression)
    assert reactions["leg_4_downhill_left"] == pytest.approx(200.0 + 200.0 - 127.5) # +272.5

    # Sum of vertical reactions must strictly conserve total dead load (sum of delta_P is zero)
    total_reaction = sum(reactions.values())
    assert total_reaction == pytest.approx(tower.total_vertical_load)


def test_tower_params_bounds():
    with pytest.raises(ValueError, match="base_width must be positive"):
        TransmissionTowerParams(base_width=0.0)
    with pytest.raises(ValueError, match="base_length must be positive"):
        TransmissionTowerParams(base_length=-6.0)
    with pytest.raises(ValueError, match="total_height must be positive"):
        TransmissionTowerParams(total_height=0.0)
    with pytest.raises(ValueError, match="crest_offset cannot be negative"):
        TransmissionTowerParams(crest_offset=-2.0)
    with pytest.raises(ValueError, match="vertical_load_per_leg must be positive"):
        TransmissionTowerParams(vertical_load_per_leg=0.0)
    with pytest.raises(ValueError, match="wind_shear_per_leg cannot be negative"):
        TransmissionTowerParams(wind_shear_per_leg=-10.0)
    with pytest.raises(ValueError, match="broken_wire_tension cannot be negative"):
        TransmissionTowerParams(broken_wire_tension=-5.0)
    with pytest.raises(ValueError, match="seismic_mass_ratio must be between 0.0 and 1.0"):
        TransmissionTowerParams(seismic_mass_ratio=1.5)


# ==============================================================================
# 6. IndianDesignStandards Tests
# ==============================================================================

def test_is_code_zoning_matrix():
    """Phase 1.4: Validates Zone V (Z=0.36), Zone IV (Z=0.24), Zone III (Z=0.16), and Zone II (Z=0.10)."""
    assert IndianDesignStandards(seismic_zone="Zone V").zone_factor == pytest.approx(0.36)
    assert IndianDesignStandards(seismic_zone="Zone IV").zone_factor == pytest.approx(0.24)
    assert IndianDesignStandards(seismic_zone="Zone III").zone_factor == pytest.approx(0.16)
    assert IndianDesignStandards(seismic_zone="Zone II").zone_factor == pytest.approx(0.10)

    # Enum forms
    assert IndianDesignStandards(seismic_zone=SeismicZone.ZONE_V.value).zone_factor == pytest.approx(0.36)
    assert IndianDesignStandards(seismic_zone=SeismicZone.ZONE_IV.value).zone_factor == pytest.approx(0.24)

    # Invalid zone
    with pytest.raises(ValueError, match="Invalid seismic_zone"):
        IndianDesignStandards(seismic_zone="Zone VI")


def test_is_code_spectral_acceleration():
    # Type I (Rock)
    std_rock = IndianDesignStandards(soil_type="Type I", damping_ratio=0.05)
    assert std_rock.spectral_acceleration_ratio(0.05) == pytest.approx(1.0 + 15.0 * 0.05)
    assert std_rock.spectral_acceleration_ratio(0.20) == pytest.approx(2.50)
    assert std_rock.spectral_acceleration_ratio(1.00) == pytest.approx(1.00)

    # Type II (Medium)
    std_med = IndianDesignStandards(soil_type="Type II", damping_ratio=0.05)
    assert std_med.spectral_acceleration_ratio(0.05) == pytest.approx(1.0 + 15.0 * 0.05)
    assert std_med.spectral_acceleration_ratio(0.30) == pytest.approx(2.50)
    assert std_med.spectral_acceleration_ratio(1.00) == pytest.approx(1.36)

    # Type III (Soft)
    std_soft = IndianDesignStandards(soil_type="Type III", damping_ratio=0.05)
    assert std_soft.spectral_acceleration_ratio(0.05) == pytest.approx(1.0 + 15.0 * 0.05)
    assert std_soft.spectral_acceleration_ratio(0.50) == pytest.approx(2.50)
    assert std_soft.spectral_acceleration_ratio(1.00) == pytest.approx(1.67)

    # Damping correction: 2% damping -> factor > 1.0, 10% damping -> factor < 1.0
    std_low_damp = IndianDesignStandards(damping_ratio=0.02)
    assert std_low_damp.damping_multiplying_factor() > 1.0
    std_high_damp = IndianDesignStandards(damping_ratio=0.10)
    assert std_high_damp.damping_multiplying_factor() < 1.0

    # Negative time period
    with pytest.raises(ValueError, match="time_period must be non-negative"):
        std_rock.spectral_acceleration_ratio(-0.5)


def test_is_code_seismic_coefficients():
    # Zone V (Z=0.36), I=1.5, R=3.0, Medium Soil, T=0.3 s (Sa/g = 2.50)
    std = IndianDesignStandards(
        seismic_zone="Zone V",
        importance_factor=1.5,
        response_reduction_factor=3.0,
        soil_type="Type II",
        damping_ratio=0.05,
    )
    # A_h = (0.36 / 2) * (1.5 / 3.0) * 2.50 = 0.18 * 0.5 * 2.50 = 0.225
    expected_ah = (0.36 / 2.0) * (1.5 / 3.0) * 2.50
    assert std.compute_horizontal_seismic_coefficient(0.3) == pytest.approx(expected_ah)
    # A_v = 2/3 * A_h = 2/3 * 0.225 = 0.150
    assert std.compute_vertical_seismic_coefficient(0.3) == pytest.approx((2.0 / 3.0) * expected_ah)


def test_is_code_material_validation():
    std = IndianDesignStandards(concrete_grade="M35", steel_grade="Fe500D")
    assert std.f_ck == 35.0
    assert std.f_y == 500.0

    # Test all valid steel grades
    assert IndianDesignStandards(steel_grade="Fe415").f_y == 415.0
    assert IndianDesignStandards(steel_grade="Fe500").f_y == 500.0
    assert IndianDesignStandards(steel_grade="Fe550").f_y == 550.0

    # Concrete grade < M25
    with pytest.raises(ValueError, match="concrete_grade must be at least M25"):
        IndianDesignStandards(concrete_grade="M20")
    with pytest.raises(ValueError, match="concrete_grade must be at least M25"):
        IndianDesignStandards(concrete_grade="C30")
    with pytest.raises(ValueError, match="Cannot parse characteristic strength"):
        IndianDesignStandards(concrete_grade="Mxyz")

    # Invalid soil type
    with pytest.raises(ValueError, match="Invalid soil_type"):
        IndianDesignStandards(soil_type="Type IV")

    # Invalid steel grade
    with pytest.raises(ValueError, match="steel_grade must be one of"):
        IndianDesignStandards(steel_grade="Fe250")

    # Custom object bypassing __post_init__ to test fallback in f_y
    fake_obj = object.__new__(IndianDesignStandards)
    fake_obj.steel_grade = "Fe600"
    assert fake_obj.f_y == 600.0
    fake_obj.steel_grade = "InvalidSteel"
    with pytest.raises(ValueError, match="Cannot parse yield strength"):
        _ = fake_obj.f_y

    # Invalid factors
    with pytest.raises(ValueError, match="importance_factor must be >= 1.0"):
        IndianDesignStandards(importance_factor=0.8)
    with pytest.raises(ValueError, match="response_reduction_factor must be >= 1.0"):
        IndianDesignStandards(response_reduction_factor=0.5)
    with pytest.raises(ValueError, match="damping_ratio must be between 0.0 and 0.20"):
        IndianDesignStandards(damping_ratio=0.0)
    with pytest.raises(ValueError, match="damping_ratio must be between 0.0 and 0.20"):
        IndianDesignStandards(damping_ratio=0.30)
    with pytest.raises(ValueError, match="partial_safety_factor_concrete must be > 1.0"):
        IndianDesignStandards(partial_safety_factor_concrete=1.0)
    with pytest.raises(ValueError, match="partial_safety_factor_steel must be > 1.0"):
        IndianDesignStandards(partial_safety_factor_steel=0.9)


# ==============================================================================
# 7. Dataclass Serialization Tests
# ==============================================================================

def test_dataclass_serialization():
    """Phase 1.4: Ensures all dataclasses serialize to JSON without loss of precision."""
    # 1. CurvedShellGeometry
    shell = CurvedShellGeometry(radius=5.5, subtended_angle=75.0, thickness=0.30, bay_span=4.5)
    shell_dict = shell.to_dict()
    assert json.loads(json.dumps(shell_dict)) == shell_dict
    assert CurvedShellGeometry.from_dict(shell_dict) == shell

    # 2. PierAndPileGeometry
    pier = PierAndPileGeometry(pier_width=1.0, pile_diameter=0.9, pile_spacing=2.6, num_piles_per_pier=3)
    pier_dict = pier.to_dict()
    assert json.loads(json.dumps(pier_dict)) == pier_dict
    assert PierAndPileGeometry.from_dict(pier_dict) == pier

    # 3. StrutSupportSystem
    struts = StrutSupportSystem(strut_levels=[3.0, 6.0], inclination_angle=30.0, pre_stress_load=75.0)
    struts_dict = struts.to_dict()
    assert json.loads(json.dumps(struts_dict)) == struts_dict
    assert StrutSupportSystem.from_dict(struts_dict) == struts

    # 4. TransmissionTowerParams
    tower = TransmissionTowerParams(base_width=8.0, total_height=40.0, wind_shear_per_leg=50.0)
    tower_dict = tower.to_dict()
    assert json.loads(json.dumps(tower_dict)) == tower_dict
    assert TransmissionTowerParams.from_dict(tower_dict) == tower

    # 5. IndianDesignStandards
    standards = IndianDesignStandards(seismic_zone="Zone IV", importance_factor=1.2, concrete_grade="M35")
    standards_dict = standards.to_dict()
    assert json.loads(json.dumps(standards_dict)) == standards_dict
    assert IndianDesignStandards.from_dict(standards_dict) == standards

    # 6. MultiStrutPiledWallModel composite
    model = MultiStrutPiledWallModel(shell=shell, pier_pile=pier, struts=struts)
    model_dict = model.to_dict()
    assert json.loads(json.dumps(model_dict)) == model_dict
    model_restored = MultiStrutPiledWallModel.from_dict(model_dict)
    assert model_restored.shell == shell
    assert model_restored.pier_pile == pier
    assert model_restored.struts == struts
