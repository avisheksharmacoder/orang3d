"""
Tests for Phase 6: Multi-Code International Design Audits (IS / Eurocode 7&8 /
AASHTO LRFD / ACI 318-19) and Full SI/Imperial Unit Parity.
"""

from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from orang3d.config import RegionalStandard
from orang3d.gui.main_window import MainWindow
from orang3d.gui.panels.audit_tab import DesignAuditTab, ISDesignAuditTab
from orang3d.io.report_generator import generate_engineering_pdf_report
from orang3d.models.wall_params import RetainingWallGeometry, SeismicParams, SoilProperties
from orang3d.physics.code_auditor import DesignCodeAuditor, MultiCodeAuditReport
from orang3d.physics.stability import evaluate_wall_stability
from orang3d.signals.synthetic import generate_ricker_wavelet, compute_newmark_sliding_displacement
from orang3d.units import (
    M_TO_FT,
    UnitSystem,
    cm_to_in,
    convert_geometry_units,
    convert_seismic_units,
    convert_soil_units,
    in_to_cm,
    in_to_mm,
    kip_ft_per_ft_to_kn_m_per_m,
    kip_per_ft_to_kn_per_m,
    kn_m_per_m_to_kip_ft_per_ft,
    kn_per_m_to_kip_per_ft,
    ksi_to_mpa,
    mm_to_in,
    mpa_to_ksi,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_design_code_auditor_covers_all_four_standards():
    geom = RetainingWallGeometry()
    soil = SoilProperties()
    seismic = SeismicParams(horizontal_pga=0.20, vertical_pga=0.05, water_table_depth=10.0)

    # 1. Indian Standards
    rep_is = DesignCodeAuditor.run_audit(RegionalStandard.IS_14458, geom=geom, soil=soil, seismic=seismic)
    assert isinstance(rep_is, MultiCodeAuditReport)
    is_clauses = " | ".join(it.code_clause for it in rep_is.items)
    assert "IS 456" in is_clauses
    assert "IS 2911" in is_clauses
    assert "IS 800" in is_clauses
    assert "IS 14458" in is_clauses

    # 2. Eurocode 7 & 8
    rep_ec = DesignCodeAuditor.run_audit(
        RegionalStandard.EUROCODE_7, geom=geom, soil=soil, seismic=seismic,
        soil_factor_S=1.15, topography_factor_ST=1.0, ec8_r_factor=1.5,
    )
    ec_clauses = " | ".join(it.code_clause for it in rep_ec.items)
    assert "EN 1997-1" in ec_clauses
    assert "DA1-C1" in ec_clauses
    assert "DA1-C2" in ec_clauses
    assert "EN 1998-5" in ec_clauses
    assert "EN 1992-1-1" in ec_clauses

    # Topographic amplification ST=1.4 must increase EC8 seismic UR
    rep_ec_hill = DesignCodeAuditor.run_audit(
        RegionalStandard.EUROCODE_7, geom=geom, soil=soil, seismic=seismic,
        soil_factor_S=1.15, topography_factor_ST=1.4, ec8_r_factor=1.5,
    )
    ec8_base = [it for it in rep_ec.items if "EN 1998-5" in it.code_clause][0]
    ec8_hill = [it for it in rep_ec_hill.items if "EN 1998-5" in it.code_clause][0]
    assert ec8_hill.unity_ratio > ec8_base.unity_ratio

    # 3. AASHTO LRFD
    rep_aashto = DesignCodeAuditor.run_audit(RegionalStandard.AASHTO_LRFD, geom=geom, soil=soil, seismic=seismic)
    aa_clauses = " | ".join(it.code_clause for it in rep_aashto.items)
    assert "AASHTO LRFD" in aa_clauses
    assert "11.6.3.3" in aa_clauses  # Eccentricity limit
    ecc_soil = [it for it in rep_aashto.items if "11.6.3.3" in it.code_clause][0]
    assert ecc_soil.capacity == pytest.approx(geom.base_width / 3.0, rel=1e-6)

    # Rock foundation relaxes AASHTO eccentricity limit to 0.45B
    rock_soil = SoilProperties(
        friction_angle=35.0, foundation_friction_angle=40.0, foundation_cohesion=80.0
    )
    rep_aashto_rock = DesignCodeAuditor.run_audit(
        RegionalStandard.AASHTO_LRFD, geom=geom, soil=rock_soil, seismic=seismic
    )
    ecc_rock = [it for it in rep_aashto_rock.items if "11.6.3.3" in it.code_clause][0]
    assert ecc_rock.capacity == pytest.approx(0.45 * geom.base_width, rel=1e-6)

    # 4. ACI 318-19
    rep_aci = DesignCodeAuditor.run_audit(RegionalStandard.ACI_318, geom=geom, soil=soil, seismic=seismic)
    aci_clauses = " | ".join(it.code_clause for it in rep_aci.items)
    assert "ACI 318-19 Sec. 22.2" in aci_clauses
    assert "ACI 318-19 Sec. 22.5.5.1" in aci_clauses
    assert "ACI 318-19 Sec. 11.6" in aci_clauses
    assert "ACI 318-19 Sec. 25.4.2.3" in aci_clauses


def test_si_imperial_round_trip_invariance_below_1e_6():
    geom_si = RetainingWallGeometry(stem_height=6.2, heel_length=2.7, toe_length=1.1, footing_thickness=0.75)
    soil_si = SoilProperties(unit_weight=19.2, saturated_unit_weight=21.1, friction_angle=33.5, foundation_cohesion=15.0)
    seismic_si = SeismicParams(horizontal_pga=0.22, vertical_pga=0.08, water_table_depth=4.5)

    # Direct scalar conversions round-trip cleanly
    assert in_to_mm(mm_to_in(16.0)) == pytest.approx(16.0, rel=1e-12)
    assert in_to_cm(cm_to_in(3.45)) == pytest.approx(3.45, rel=1e-12)
    assert ksi_to_mpa(mpa_to_ksi(28.0)) == pytest.approx(28.0, rel=1e-12)
    assert kip_per_ft_to_kn_per_m(kn_per_m_to_kip_per_ft(145.0)) == pytest.approx(145.0, rel=1e-12)
    assert kip_ft_per_ft_to_kn_m_per_m(kn_m_per_m_to_kip_ft_per_ft(220.0)) == pytest.approx(220.0, rel=1e-12)

    # Full dataclass round-trip: SI -> Imperial -> SI
    geom_imp = convert_geometry_units(geom_si, UnitSystem.SI, UnitSystem.IMPERIAL)
    geom_rt = convert_geometry_units(geom_imp, UnitSystem.IMPERIAL, UnitSystem.SI)
    soil_imp = convert_soil_units(soil_si, UnitSystem.SI, UnitSystem.IMPERIAL)
    soil_rt = convert_soil_units(soil_imp, UnitSystem.IMPERIAL, UnitSystem.SI)
    seis_imp = convert_seismic_units(seismic_si, UnitSystem.SI, UnitSystem.IMPERIAL)
    seis_rt = convert_seismic_units(seis_imp, UnitSystem.IMPERIAL, UnitSystem.SI)

    assert abs(geom_rt.stem_height - geom_si.stem_height) < 1e-6
    assert abs(geom_rt.base_width - geom_si.base_width) < 1e-6
    assert abs(soil_rt.unit_weight - soil_si.unit_weight) < 1e-6
    assert abs(soil_rt.foundation_cohesion - soil_si.foundation_cohesion) < 1e-6
    assert abs(seis_rt.water_table_depth - seismic_si.water_table_depth) < 1e-6

    # Physics capacity/demand ratios must match identically across SI <-> Imperial round-trip
    res_orig = evaluate_wall_stability(geom_si, soil_si, seismic_si)
    res_rt = evaluate_wall_stability(geom_rt, soil_rt, seis_rt)
    assert abs(res_orig.fs_sliding - res_rt.fs_sliding) < 1e-6
    assert abs(res_orig.fs_overturning - res_rt.fs_overturning) < 1e-6
    assert abs(res_orig.fs_bearing - res_rt.fs_bearing) < 1e-6

    for std in (
        RegionalStandard.IS_14458,
        RegionalStandard.EUROCODE_7,
        RegionalStandard.AASHTO_LRFD,
        RegionalStandard.ACI_318,
    ):
        rep_a = DesignCodeAuditor.run_audit(std, geom=geom_si, soil=soil_si, seismic=seismic_si)
        rep_b = DesignCodeAuditor.run_audit(std, geom=geom_rt, soil=soil_rt, seismic=seis_rt)
        assert abs(rep_a.max_unity_ratio - rep_b.max_unity_ratio) < 1e-6
        for it_a, it_b, it_imp in zip(
            rep_a.items, rep_b.items, rep_a.items_in_units(UnitSystem.IMPERIAL)
        ):
            assert abs(it_a.unity_ratio - it_b.unity_ratio) < 1e-6
            assert abs(it_a.unity_ratio - it_imp.unity_ratio) < 1e-12


def test_design_audit_tab_selector_and_unit_formatting(qapp):
    assert ISDesignAuditTab is DesignAuditTab
    tab = DesignAuditTab()
    try:
        assert tab.combo_standard.count() == 4
        tab.set_standard(RegionalStandard.EUROCODE_7)
        assert tab.table.rowCount() >= 6
        clauses_ec = [tab.table.item(r, 2).text() for r in range(tab.table.rowCount())]
        assert any("EN 1997-1" in c for c in clauses_ec)

        ur_si = [float(tab.table.item(r, 6).text()) for r in range(tab.table.rowCount())]
        tab.set_unit_system(UnitSystem.IMPERIAL)
        ur_imp = [float(tab.table.item(r, 6).text()) for r in range(tab.table.rowCount())]
        units_imp = [tab.table.item(r, 5).text() for r in range(tab.table.rowCount())]
        assert any(u in ("kip/ft", "ksf", "kip-ft/ft", "ksi") for u in units_imp)
        assert ur_imp == pytest.approx(ur_si, abs=1e-3)

        idx_aashto = tab.combo_standard.findData(RegionalStandard.AASHTO_LRFD)
        assert idx_aashto >= 0
        tab.combo_standard.setCurrentIndex(idx_aashto)
        assert tab.current_standard == RegionalStandard.AASHTO_LRFD

        tab.set_standard(RegionalStandard.ACI_318)
        clauses_aci = [tab.table.item(r, 2).text() for r in range(tab.table.rowCount())]
        assert any("ACI 318-19" in c for c in clauses_aci)
    finally:
        tab.close()
        tab.deleteLater()
        qapp.processEvents()


def test_main_window_unit_toggle_zero_solver_drift_and_imperial_pdf(qapp, tmp_path):
    window = MainWindow()
    try:
        assert window.combo_units.count() == 2
        orig_h = window.geom.stem_height
        orig_fs_slide = window.results.fs_sliding
        orig_thrust = window.results.total_thrust

        # Toggle SI -> Imperial
        idx_imp = window.combo_units.findData(UnitSystem.IMPERIAL)
        assert idx_imp >= 0
        window.combo_units.setCurrentIndex(idx_imp)
        assert window.unit_system == UnitSystem.IMPERIAL
        assert window.panel_geom.spin_height.value() == pytest.approx(orig_h * M_TO_FT, rel=1e-2)
        assert "kip/ft" in window.charts_2d.lbl_thrust.text()
        assert "ft" in window.panel_geom.group.title()

        # Canonical solver state remains untouched (zero drift!)
        assert window.geom.stem_height == pytest.approx(orig_h, abs=1e-12)
        assert window.results.fs_sliding == pytest.approx(orig_fs_slide, abs=1e-12)
        assert window.results.total_thrust == pytest.approx(orig_thrust, abs=1e-12)

        # Toggle back Imperial -> SI
        idx_si = window.combo_units.findData(UnitSystem.SI)
        window.combo_units.setCurrentIndex(idx_si)
        assert window.unit_system == UnitSystem.SI
        assert window.panel_geom.spin_height.value() == pytest.approx(orig_h, abs=1e-9)
        assert "kN/m" in window.charts_2d.lbl_thrust.text()

        # Editing a spinbox in Imperial converts accurately into canonical SI
        window.set_unit_system(UnitSystem.IMPERIAL)
        window.panel_geom.spin_height.setValue(20.0)  # 20.0 ft = 6.096 m
        assert window.geom.stem_height == pytest.approx(20.0 / M_TO_FT, rel=1e-4)

        # Generate Imperial PDF report cleanly
        t_arr, a_arr = generate_ricker_wavelet(pga_g=0.25, duration_sec=4.0, sampling_rate_hz=40.0)
        slip_arr, _ = compute_newmark_sliding_displacement(t_arr, a_arr, 0.15)
        pdf_path = str(tmp_path / "imperial_audit_report.pdf")
        out_pdf = generate_engineering_pdf_report(
            filepath=pdf_path,
            geom=window.geom,
            soil=window.soil,
            seismic=window.seismic,
            results=window.results,
            regional_standard=RegionalStandard.AASHTO_LRFD,
            time_arr=t_arr,
            slip_arr=slip_arr,
            unit_system=UnitSystem.IMPERIAL,
        )
        assert os.path.exists(out_pdf)
        assert os.path.getsize(out_pdf) > 20_000
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()
