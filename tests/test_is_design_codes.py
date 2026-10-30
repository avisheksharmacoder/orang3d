"""
Comprehensive verification test suite for Indian Standards (IS) Member Design Engine:
- IS 456:2000 (Plain and Reinforced Concrete)
- IS 2911 (Part 1/Sec 2: 2010) (Bored Cast-in-Situ Concrete Piles)
- IS 800:2007 (General Construction in Steel - Limit State Method)
- Unified Engineering Audit Engine & Compliance Reports
"""

import math
import pytest
import numpy as np

from orang3d.models.is_code_params import IndianDesignStandards
from orang3d.physics.is_codes import (
    # IS 456
    design_is456_flexure,
    design_is456_shear,
    check_is456_crack_width,
    calculate_is456_limiting_moment,
    calculate_is456_tau_c,
    calculate_is456_tau_c_max,
    generate_is456_bar_callout,
    # IS 2911
    calculate_is2911_axial_capacity,
    calculate_is2911_lateral_capacity,
    design_is2911_structural_pile,
    interpolate_is2911_factors,
    get_is2911_adhesion_factor,
    # IS 800
    BucklingCurve,
    calculate_is800_design_compressive_stress,
    design_is800_steel_strut,
    # Audit Engine
    run_full_retaining_wall_is_audit,
)


# ==============================================================================
# 1. IS 456: Singly & Doubly Reinforced Section Verification (SP 16 Benchmark)
# ==============================================================================

def test_is456_singly_reinforced_slab():
    """
    Validates computed steel percentage pt against IS 456 SP 16 design table values
    within 0.5% tolerance.
    SP 16 Table 3: Concrete M30, Steel Fe 500, Mu / (b * d^2) = 2.00 N/mm2 -> pt = 0.502%.
    """
    b = 1000.0   # mm
    d = 350.0    # mm
    D = 400.0    # mm
    f_ck = 30.0  # MPa (M30)
    f_y = 500.0  # MPa (Fe 500)

    # Applied moment for Mu / (b * d^2) = 2.0 N/mm2
    m_u_target = 2.0 * b * (d ** 2) / 1e6 # 245.0 kNm
    res = design_is456_flexure(
        m_u_kNm=m_u_target,
        b_mm=b,
        d_mm=d,
        D_mm=D,
        f_ck=f_ck,
        f_y=f_y,
        is_slab=True,
    )

    # SP 16 exact theoretical pt is 0.502%
    sp16_pt = 0.502
    assert abs(res.pt_percentage - sp16_pt) / sp16_pt < 0.005, (
        f"pt = {res.pt_percentage:.4f}% deviates from SP 16 {sp16_pt}%"
    )

    # Verify limiting moment: for Fe 500, Ru_lim / fck = 0.1331 -> Mu_lim = 0.1331 * 30 * 1000 * 350^2 / 1e6 = 489.14 kNm
    mu_lim_expected = 0.1331 * f_ck * b * (d ** 2) / 1e6
    assert abs(res.m_u_lim - mu_lim_expected) / mu_lim_expected < 0.01
    assert not res.is_doubly_reinforced
    assert res.status == "PASS"

    # Doubly reinforced section: Apply moment exceeding Mu_lim (e.g. 600 kNm)
    res_doubly = design_is456_flexure(
        m_u_kNm=600.0,
        b_mm=b,
        d_mm=d,
        D_mm=D,
        f_ck=f_ck,
        f_y=f_y,
        is_slab=True,
    )
    assert res_doubly.is_doubly_reinforced
    assert res_doubly.a_sc_required > 0.0
    assert res_doubly.a_st_required > res.a_st_required


# ==============================================================================
# 2. IS 456: Concrete Shear Strength tau_c & Reinforcement Checks
# ==============================================================================

def test_is456_shear_capacity():
    """
    Validates design shear strength of concrete tau_c against IS 456:2000 Table 19
    across concrete grades M25, M30, M35, M40.
    """
    # For pt = 0.50%: Table 19 gives:
    # M25 -> 0.49 MPa, M30 -> 0.50 MPa, M35 -> 0.50 MPa, M40 -> 0.51 MPa
    expected_pt05 = {
        25.0: 0.49,
        30.0: 0.50,
        35.0: 0.50,
        40.0: 0.51,
    }
    for grade, expected_val in expected_pt05.items():
        tau_c = calculate_is456_tau_c(f_ck=grade, pt_percent=0.50)
        assert abs(tau_c - expected_val) <= 0.03, (
            f"tau_c for M{grade} at pt=0.50%: got {tau_c:.3f}, expected ~{expected_val}"
        )

    # For pt = 1.00%: Table 19 gives:
    # M25 -> 0.64 MPa, M30 -> 0.66 MPa, M35 -> 0.67 MPa, M40 -> 0.68 MPa
    expected_pt10 = {
        25.0: 0.64,
        30.0: 0.66,
        35.0: 0.67,
        40.0: 0.68,
    }
    for grade, expected_val in expected_pt10.items():
        tau_c = calculate_is456_tau_c(f_ck=grade, pt_percent=1.00)
        assert abs(tau_c - expected_val) <= 0.03, (
            f"tau_c for M{grade} at pt=1.00%: got {tau_c:.3f}, expected ~{expected_val}"
        )

    # Test shear design when tau_v <= tau_c (nominal adequate)
    res_nominal = design_is456_shear(
        v_u_kN=80.0,
        b_mm=1000.0,
        d_mm=350.0,
        f_ck=30.0,
        f_y=500.0,
        a_st_provided_mm2=1757.0, # pt = 0.502% -> tau_c ~ 0.50 MPa -> Vc ~ 175 kN
        is_slab=True,
    )
    assert not res_nominal.shear_rebar_required
    assert res_nominal.tau_v < res_nominal.tau_c
    assert res_nominal.status == "PASS"

    # Test shear design when tau_v > tau_c (stirrups required)
    res_stirrups = design_is456_shear(
        v_u_kN=280.0, # tau_v = 280000 / (1000 * 350) = 0.80 MPa > 0.50 MPa
        b_mm=1000.0,
        d_mm=350.0,
        f_ck=30.0,
        f_y=500.0,
        a_st_provided_mm2=1757.0,
        is_slab=True,
    )
    assert res_stirrups.shear_rebar_required
    assert res_stirrups.a_sv_per_meter > 0.0
    assert "T10 @" in res_stirrups.stirrup_callout
    assert res_stirrups.status == "PASS"

    # Test section inadequacy when tau_v > tau_c_max = 0.62 * sqrt(30) = 3.40 MPa
    res_fail = design_is456_shear(
        v_u_kN=1500.0, # tau_v = 1500000 / (1000 * 350) = 4.28 MPa > 3.40 MPa
        b_mm=1000.0,
        d_mm=350.0,
        f_ck=30.0,
        f_y=500.0,
        a_st_provided_mm2=1757.0,
        is_slab=True,
    )
    assert res_fail.status == "FAIL"
    assert res_fail.unity_ratio > 1.0


# ==============================================================================
# 3. IS 2911: Bored Pile Axial Capacity Benchmark & Lateral Fixity
# ==============================================================================

def test_is2911_pile_capacity():
    """
    Validates bored cast-in-situ pile axial compression capacity (IS 2911 Appendix B)
    against golden textbook hand calculation for c-phi and purely cohesive soil.
    """
    # 1. Purely cohesive soil (clay) golden check
    # Dp = 1.0 m, Lp = 15.0 m, cu = 50 kPa, phi = 0
    # Ap = pi/4 * 1^2 = 0.7854 m2
    # Qb = 9 * cu * Ap = 9 * 50 * 0.7854 = 353.43 kN
    # alpha = 0.50 (for cu = 50 kPa per Table 2)
    # Qs = alpha * cu * (pi * Dp * Lp) = 0.50 * 50 * (pi * 1.0 * 15.0) = 1178.10 kN
    # Qu = 353.43 + 1178.10 = 1531.53 kN, Qsafe = 1531.53 / 2.5 = 612.61 kN
    res_clay = calculate_is2911_axial_capacity(
        pile_diameter_m=1.0,
        pile_length_m=15.0,
        cohesion_kPa=50.0,
        friction_angle_deg=0.0,
        unit_weight_kNm3=18.0,
        applied_axial_kN=500.0,
        is_seismic=False,
    )
    assert abs(res_clay.ultimate_end_bearing - 353.43) < 2.0
    assert abs(res_clay.ultimate_skin_friction - 1178.10) < 5.0
    assert abs(res_clay.ultimate_capacity - 1531.53) < 7.0
    assert abs(res_clay.safe_capacity - 612.61) < 5.0
    assert res_clay.unity_ratio == pytest.approx(500.0 / res_clay.safe_capacity, rel=1e-4)
    assert res_clay.status == "PASS"

    # 2. c-phi soil with friction angle phi = 30 deg
    res_cphi = calculate_is2911_axial_capacity(
        pile_diameter_m=1.0,
        pile_length_m=15.0,
        cohesion_kPa=15.0,
        friction_angle_deg=30.0,
        unit_weight_kNm3=18.5,
        applied_axial_kN=1200.0,
        is_seismic=False,
    )
    assert res_cphi.ultimate_end_bearing > 1000.0
    assert res_cphi.ultimate_skin_friction > 500.0
    assert res_cphi.safe_capacity > 800.0

    # 3. Lateral Capacity and Depth of Fixity (Appendix C)
    lat_res = calculate_is2911_lateral_capacity(
        pile_diameter_m=1.0,
        pile_length_m=15.0,
        f_ck=30.0,
        subgrade_modulus_nh_kNm3=6000.0,
        applied_lateral_kN=100.0,
        fixed_head=True,
    )
    # Stiffness factor T should be in range [1.5, 3.5] m
    assert 1.5 <= lat_res.stiffness_factor_T <= 3.5
    assert lat_res.depth_of_fixity_zf == pytest.approx(2.0 * lat_res.stiffness_factor_T, rel=1e-3)
    assert lat_res.safe_lateral_capacity > 100.0
    assert lat_res.status == "PASS"

    # 4. Structural rebar cage detailing
    struct_res = design_is2911_structural_pile(
        pile_diameter_m=1.0,
        pile_length_m=15.0,
        f_ck=30.0,
        f_y=500.0,
        applied_axial_kN=1000.0,
    )
    # Minimum longitudinal steel is 0.4%
    assert struct_res.longitudinal_ratio_percent >= 0.40
    assert struct_res.axial_structural_capacity_kN > 5000.0
    assert "bars uniformly distributed" in struct_res.rebar_cage_callout
    assert struct_res.status == "PASS"


# ==============================================================================
# 4. IS 800: Steel Strut Buckling Curve c Table 9(c) Cross-Check
# ==============================================================================

def test_is800_strut_buckling_curve():
    """
    Verifies design compressive stress f_cd against IS 800:2007 Table 9(c)
    (f_y = 250 MPa, Curve c with imperfection factor alpha_b = 0.49).
    Table 9(c) values:
        KL/r = 20  -> 224 MPa
        KL/r = 60  -> 168 MPa
        KL/r = 100 -> 107 MPa
        KL/r = 140 -> 66.2 MPa
        KL/r = 180 -> 43.6 MPa
    """
    table_9c_benchmarks = {
        20.0: 224.0,
        60.0: 168.0,
        100.0: 107.0,
        140.0: 66.2,
        180.0: 43.6,
    }

    for kl_r, expected_fcd in table_9c_benchmarks.items():
        f_cd, lam, chi = calculate_is800_design_compressive_stress(
            slenderness_kl_r=kl_r,
            f_y=250.0,
            buckling_curve="c",
        )
        assert abs(f_cd - expected_fcd) / expected_fcd <= 0.015, (
            f"f_cd at KL/r={kl_r}: got {f_cd:.2f} MPa, expected {expected_fcd} MPa per Table 9(c)"
        )

    # Verify hierarchy of buckling curves: Curve a > Curve b > Curve c > Curve d
    f_cd_a, _, _ = calculate_is800_design_compressive_stress(80.0, 250.0, buckling_curve="a")
    f_cd_b, _, _ = calculate_is800_design_compressive_stress(80.0, 250.0, buckling_curve="b")
    f_cd_c, _, _ = calculate_is800_design_compressive_stress(80.0, 250.0, buckling_curve="c")
    f_cd_d, _, _ = calculate_is800_design_compressive_stress(80.0, 250.0, buckling_curve="d")
    assert f_cd_a > f_cd_b > f_cd_c > f_cd_d

    # Full strut member design
    strut_report = design_is800_steel_strut(
        applied_compression_kN=400.0,
        effective_length_m=6.0,
        section_area_mm2=10000.0,
        radius_of_gyration_mm=90.0,
        f_y=250.0,
        applied_tension_reversal_kN=50.0,
        is_seismic=True,
    )
    assert strut_report.compression_result.slenderness_ratio == pytest.approx(6000.0 / 90.0, rel=1e-3)
    assert strut_report.compression_result.slenderness_status == "PASS"
    assert strut_report.overall_status == "PASS"
    assert strut_report.connection_result.num_bolts_required >= 4


# ==============================================================================
# 5. Unity Ratio Thresholds & Failure Triggering
# ==============================================================================

def test_unity_ratio_thresholds():
    """
    Ensures all engineering checks flag UR > 1.0 as FAIL with exact clause reference.
    """
    standards = IndianDesignStandards(
        seismic_zone="Zone V",
        concrete_grade="M30",
        steel_grade="Fe500",
    )

    # 1. Normal safe case -> PASS
    report_safe = run_full_retaining_wall_is_audit(
        standards=standards,
        panel_height_m=6.0,
        panel_thickness_m=0.45,
        max_panel_moment_kNm_m=110.0,
        max_panel_shear_kN_m=80.0,
        pile_axial_load_kN=600.0,
        strut_compression_kN=350.0,
    )
    assert report_safe.overall_status == "PASS"
    assert report_safe.max_unity_ratio < 0.90
    for item in report_safe.items:
        assert item.status == "PASS"
        assert item.unity_ratio <= 1.0

    # 2. Excessive Moment -> Trigger RC Panel Flexure Failure (UR > 1.0)
    report_fail_moment = run_full_retaining_wall_is_audit(
        standards=standards,
        panel_thickness_m=0.25, # Thin panel
        max_panel_moment_kNm_m=1200.0, # Massive moment
    )
    assert report_fail_moment.overall_status == "FAIL"
    panel_flex_item = next(it for it in report_fail_moment.items if it.check_title == "Flexural Moment Resistance")
    assert panel_flex_item.status == "FAIL"
    assert panel_flex_item.unity_ratio > 1.0
    assert "IS 456" in panel_flex_item.code_clause

    # 3. Excessive Pile Axial Load -> Trigger IS 2911 Axial Capacity Failure
    report_fail_pile = run_full_retaining_wall_is_audit(
        standards=standards,
        pile_diameter_m=0.60,
        pile_length_m=6.0,
        pile_axial_load_kN=4000.0, # Far exceeds safe capacity
    )
    assert report_fail_pile.overall_status == "FAIL"
    pile_item = next(it for it in report_fail_pile.items if it.check_title == "Axial Geotechnical Compression")
    assert pile_item.status == "FAIL"
    assert pile_item.unity_ratio > 1.0
    assert "IS 2911" in pile_item.code_clause

    # 4. Excessive Strut Slenderness -> Trigger IS 800 Table 3 Failure
    report_fail_strut = run_full_retaining_wall_is_audit(
        standards=standards,
        strut_length_m=20.0, # Long slender strut
        strut_radius_gyration_mm=50.0, # KL/r = 20000 / 50 = 400 > 250
        is_seismic=True,
    )
    assert report_fail_strut.overall_status == "FAIL"
    slenderness_item = next(it for it in report_fail_strut.items if "Slenderness" in it.check_title)
    assert slenderness_item.status == "FAIL"
    assert "IS 800" in slenderness_item.code_clause


# ==============================================================================
# 6. Crack Width & Detailing Checks
# ==============================================================================

def test_is456_crack_width_and_bar_callouts():
    """
    Tests IS 456 Annex F crack width evaluation and detailing callout generator.
    """
    callout, ast_prov = generate_is456_bar_callout(
        a_st_req_mm2=1500.0,
        b_mm=1000.0,
        max_spacing_mm=300.0,
        preferred_dia_mm=16,
        two_layers=True,
    )
    assert "2-layer T16 @" in callout
    assert ast_prov >= 1500.0 * 0.999

    # Crack width check
    cw_res = check_is456_crack_width(
        m_service_kNm=100.0,
        b_mm=1000.0,
        d_mm=350.0,
        D_mm=400.0,
        a_st_provided_mm2=ast_prov,
        bar_dia_mm=16.0,
        bar_spacing_mm=125.0,
        cover_mm=50.0,
        aggressive_environment=True,
    )
    assert cw_res.allowable_crack_width == 0.20
    assert cw_res.calculated_crack_width > 0.0
    assert cw_res.calculated_crack_width <= 0.20
    assert cw_res.status == "PASS"


# ==============================================================================
# 7. Comprehensive Branch Coverage & Edge Cases (Phase 8)
# ==============================================================================

def test_is_codes_edge_cases_and_branch_coverage():
    """
    Exercises all input validations, edge cases, and report serializations.
    """
    # 1. Invalid section dimensions
    with pytest.raises(ValueError, match="Section dimensions must be positive"):
        design_is456_flexure(100.0, -100.0, 300.0, 350.0, 30.0, 500.0)

    with pytest.raises(ValueError, match="f_ck must be >= 15 MPa"):
        design_is456_flexure(100.0, 1000.0, 300.0, 350.0, 10.0, 500.0)

    with pytest.raises(ValueError, match="f_y must be >= 250 MPa"):
        design_is456_flexure(100.0, 1000.0, 300.0, 350.0, 30.0, 200.0)

    with pytest.raises(ValueError, match="Dimensions must be positive"):
        design_is456_shear(50.0, -100.0, 300.0, 30.0, 500.0, 1000.0)

    with pytest.raises(ValueError, match="Pile dimensions must be positive"):
        calculate_is2911_axial_capacity(-1.0, 15.0, 20.0, 30.0, 18.0)

    with pytest.raises(ValueError, match="Slenderness ratio must be positive"):
        calculate_is800_design_compressive_stress(-5.0, 250.0)

    with pytest.raises(ValueError, match="Yield stress must be positive"):
        calculate_is800_design_compressive_stress(50.0, -250.0)

    # 2. IS 456 mild steel Fe 250 and beam (non-slab) flexure
    res_mild = design_is456_flexure(
        m_u_kNm=50.0,
        b_mm=300.0,
        d_mm=450.0,
        D_mm=500.0,
        f_ck=25.0,
        f_y=250.0,
        is_slab=False,
    )
    assert res_mild.status == "PASS"

    # 3. Slab thickness interpolation in shear
    res_shear_slab = design_is456_shear(
        v_u_kN=40.0,
        b_mm=1000.0,
        d_mm=170.0,
        f_ck=30.0,
        f_y=500.0,
        a_st_provided_mm2=800.0,
        is_slab=True,
        D_mm=200.0, # Intermediate slab thickness 150 < D < 300
    )
    assert res_shear_slab.status == "PASS"

    # 4. Free-head pile lateral capacity & high shear
    lat_free = calculate_is2911_lateral_capacity(
        pile_diameter_m=0.8,
        pile_length_m=10.0,
        f_ck=25.0,
        applied_lateral_kN=500.0,
        fixed_head=False,
    )
    assert lat_free.depth_of_fixity_zf > 0.0

    # 5. Adhesion factor interpolation
    assert get_is2911_adhesion_factor(10.0) == 0.70
    assert get_is2911_adhesion_factor(200.0) == 0.30
    assert 0.35 <= get_is2911_adhesion_factor(80.0) <= 0.40

    # 6. Bearing capacity factors interpolation
    nc, nq, ngamma = interpolate_is2911_factors(28.0)
    assert nq == 12.5
    assert ngamma == 10.0

    # 7. Audit report Markdown and Dictionary generation
    standards = IndianDesignStandards()
    report = run_full_retaining_wall_is_audit(standards=standards)
    md_sheet = report.generate_markdown_audit_sheet()
    assert "# Structural & Geotechnical Audit Report" in md_sheet
    assert "| RC Shell Panel |" in md_sheet
    assert "| Bored Pile |" in md_sheet
    assert "| Steel Strut |" in md_sheet

    d = report.to_dict()
    assert "items" in d
    assert len(d["items"]) >= 10
    assert "governing_clause" in d

    # 8. Markdown report branch coverage for WARNING and FAIL statuses
    report_warning = run_full_retaining_wall_is_audit(
        standards=standards,
        panel_thickness_m=0.35,
        max_panel_moment_kNm_m=280.0, # Causes flexure UR ~ 0.93 -> WARNING
    )
    md_warning = report_warning.generate_markdown_audit_sheet()
    assert "WARNING" in md_warning or "FAILED" in md_warning

    report_fail = run_full_retaining_wall_is_audit(
        standards=standards,
        panel_thickness_m=0.20,
        max_panel_moment_kNm_m=2000.0,
    )
    md_fail = report_fail.generate_markdown_audit_sheet()
    assert "FAILED" in md_fail


def test_is456_additional_branches():
    """
    Tests get_xu_max_ratio, calculate_is456_tau_c_max, beam shear stirrups,
    single-layer bar callout, and to_dict methods.
    """
    from orang3d.physics.is_codes.is_456 import get_xu_max_ratio

    # get_xu_max_ratio across grades
    assert get_xu_max_ratio(250.0) == 0.53
    assert get_xu_max_ratio(300.0) < 0.53 # interpolated
    assert get_xu_max_ratio(415.0) == 0.48
    assert get_xu_max_ratio(450.0) < 0.48 # interpolated
    assert get_xu_max_ratio(500.0) == 0.46
    assert get_xu_max_ratio(525.0) < 0.46 # interpolated
    assert get_xu_max_ratio(550.0) == 0.44
    assert get_xu_max_ratio(600.0) == 0.44

    # calculate_is456_tau_c_max
    for fck, val in [(20.0, 2.8), (25.0, 3.1), (30.0, 3.5), (35.0, 3.7), (40.0, 4.0)]:
        assert calculate_is456_tau_c_max(fck) == val
    assert calculate_is456_tau_c_max(50.0) == pytest.approx(0.62 * math.sqrt(50.0), rel=1e-3)

    # Single-layer callout & zero Ast required
    callout_single, prov_single = generate_is456_bar_callout(
        a_st_req_mm2=0.0,
        b_mm=1000.0,
        max_spacing_mm=300.0,
        preferred_dia_mm=12,
        two_layers=False,
    )
    assert "T12 @" in callout_single
    assert "2-layer" not in callout_single

    # Beam / pier nominal shear stirrups (is_slab=False)
    beam_shear = design_is456_shear(
        v_u_kN=30.0,
        b_mm=400.0,
        d_mm=500.0,
        f_ck=30.0,
        f_y=500.0,
        a_st_provided_mm2=2000.0,
        is_slab=False,
    )
    assert not beam_shear.shear_rebar_required
    assert "Nominal 2-legged" in beam_shear.stirrup_callout
    d_shear = beam_shear.to_dict()
    assert d_shear["v_u_applied_kN"] == 30.0

    # Crack width to_dict
    cw = check_is456_crack_width(
        m_service_kNm=50.0,
        b_mm=1000.0,
        d_mm=350.0,
        D_mm=400.0,
        a_st_provided_mm2=1500.0,
        bar_dia_mm=16.0,
        bar_spacing_mm=125.0,
        aggressive_environment=False,
    )
    d_cw = cw.to_dict()
    assert d_cw["allowable_crack_width_mm"] == 0.30

    # Flexure warning branch (0.90 <= UR <= 1.0)
    res_warn = design_is456_flexure(
        m_u_kNm=460.0, # Close to Mu_lim (489.1 kNm), UR ~ 0.94
        b_mm=1000.0,
        d_mm=350.0,
        D_mm=400.0,
        f_ck=30.0,
        f_y=500.0,
        is_slab=True,
    )
    assert res_warn.status == "WARNING"


def test_is800_and_is2911_additional_branches():
    """
    Tests IS 800 and IS 2911 to_dict methods, zero load connection,
    and structural pile dict serialization.
    """
    from orang3d.physics.is_codes.is_800 import design_is800_steel_strut
    from orang3d.physics.is_codes.is_2911 import (
        calculate_is2911_axial_capacity,
        calculate_is2911_lateral_capacity,
        design_is2911_structural_pile,
    )

    # Strut with zero load connection
    strut = design_is800_steel_strut(
        applied_compression_kN=0.0,
        effective_length_m=5.0,
        section_area_mm2=8000.0,
        radius_of_gyration_mm=80.0,
        applied_tension_reversal_kN=0.0,
    )
    d_strut = strut.to_dict()
    assert d_strut["effective_length_m"] == 5.0
    assert "compression" in d_strut
    assert "tension" in d_strut
    assert "connection" in d_strut

    # IS 2911 dataclass to_dict
    axial = calculate_is2911_axial_capacity(
        pile_diameter_m=1.0,
        pile_length_m=12.0,
        cohesion_kPa=20.0,
        friction_angle_deg=30.0,
        unit_weight_kNm3=18.0,
    )
    d_axial = axial.to_dict()
    assert "safe_capacity_kN" in d_axial

    lat = calculate_is2911_lateral_capacity(
        pile_diameter_m=1.0,
        pile_length_m=12.0,
        f_ck=30.0,
    )
    d_lat = lat.to_dict()
    assert "depth_of_fixity_zf_m" in d_lat

    pile_struct = design_is2911_structural_pile(
        pile_diameter_m=1.0,
        pile_length_m=12.0,
        f_ck=30.0,
        f_y=500.0,
        applied_axial_kN=500.0,
    )
    d_struct = pile_struct.to_dict()
    assert "rebar_cage_callout" in d_struct
