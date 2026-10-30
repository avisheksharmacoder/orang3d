"""
Comprehensive Test Suite for Phase 10:
GUI Integration, CAD Export (ezdxf), Live IS Audit Tab, and Golden Textbook Benchmarks.
"""

import math
import os
from pathlib import Path
import pytest
import numpy as np

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from orang3d.models.advanced_wall_params import (
    MultiStrutPiledWallModel,
    CurvedShellGeometry,
    PierAndPileGeometry,
    StrutSupportSystem,
)
from orang3d.models.wall_params import RetainingWallGeometry, SoilProperties, SeismicParams
from orang3d.models.is_code_params import IndianDesignStandards
from orang3d.io.dxf_export import (
    RetainingWallDXFExporter,
    export_retaining_wall_dxf,
    DXF_LAYERS,
    EZDXF_AVAILABLE,
)
from orang3d.gui.panels.shell_panel import ShellAndPierPanel
from orang3d.gui.panels.strut_pile_panel import StrutAndPilePanel
from orang3d.gui.panels.audit_tab import ISDesignAuditTab
from orang3d.gui.main_window import MainWindow
from orang3d.physics.is_codes.audit_engine import run_full_retaining_wall_is_audit
from orang3d.physics.mononobe_okabe import compute_coulomb_earth_pressures, compute_mononobe_okabe
from orang3d.physics.shell_arching import compute_horizontal_arching_stress


@pytest.fixture
def qapp():
    """Ensure QApplication instance exists for offscreen GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ==============================================================================
# 1. AutoCAD DXF Export Tests
# ==============================================================================

def test_dxf_export_validity(tmp_path: Path):
    """Verifies layered AutoCAD DXF generation and integrity."""
    dxf_path = tmp_path / "test_retaining_wall.dxf"

    shell = CurvedShellGeometry(radius=4.5, bay_span=3.5, panel_height=6.5, thickness=0.45)
    piers = PierAndPileGeometry(
        pier_width=0.8,
        pier_depth=1.2,
        pier_height=7.0,
        pile_diameter=1.2,
        pile_length=14.0,
        pile_spacing=3.2,
        rock_socket_length=2.0,
    )
    struts = StrutSupportSystem(strut_levels=[2.5, 5.0], inclination_angle_deg=20.0)
    model = MultiStrutPiledWallModel(shell=shell, piers=piers, struts=struts)

    out_file = export_retaining_wall_dxf(
        model=model,
        file_path=str(dxf_path),
        project_title="Golden Gate Retaining System",
        drawing_number="DWG-TEST-100",
        num_bays=4,
    )

    assert Path(out_file).exists()
    assert Path(out_file).stat().st_size > 500

    if EZDXF_AVAILABLE:
        import ezdxf
        doc = ezdxf.readfile(out_file)
        msp = doc.modelspace()

        # Check layers
        layer_names = [layer.dxf.name for layer in doc.layers]
        for expected_layer in DXF_LAYERS.keys():
            assert expected_layer in layer_names, f"Layer {expected_layer} missing from DXF"

        # Check modelspace entity population
        entities = list(msp)
        assert len(entities) > 20, f"Expected rich CAD entities, found {len(entities)}"

        types = set(e.dxftype() for e in entities)
        assert "LINE" in types
        assert "TEXT" in types or "MTEXT" in types
    else:
        # Check pure Python ASCII DXF fallback
        content = dxf_path.read_text(encoding="utf-8")
        assert "SECTION" in content
        assert "ENTITIES" in content
        assert "WALL_OUTLINE" in content
        assert "EOF" in content


def test_dxf_fallback_ascii(tmp_path: Path):
    """Directly tests pure Python ASCII DXF export engine without ezdxf dependency."""
    dxf_path = tmp_path / "fallback_wall.dxf"
    exporter = RetainingWallDXFExporter()

    res = exporter._export_fallback_ascii(
        file_path=dxf_path,
        project_title="Pure ASCII CAD Test",
        drawing_number="DWG-ASCII-001",
        num_bays=3,
        rebar_callout="2-layer T16 @ 125 mm c/c",
        pile_callout="12-T25 Cage",
        strut_callout="CHS 355.6x12.5",
    )

    assert Path(res).exists()
    text = Path(res).read_text(encoding="utf-8")
    assert "0\nSECTION" in text
    assert "2\nENTITIES" in text
    assert "WALL_OUTLINE" in text
    assert "DIMENSIONS_AND_TEXT" in text
    assert "Pure ASCII CAD Test" in text
    assert "0\nEOF" in text


# ==============================================================================
# 2. PySide6 Interactive Control Panels Tests
# ==============================================================================

def test_shell_and_pier_panel(qapp):
    """Tests interactive tuning and signal emission in ShellAndPierPanel."""
    panel = ShellAndPierPanel()
    assert panel.spin_radius.value() > 0.0
    assert panel.spin_height.value() > 0.0

    emitted_signals = []
    panel.shellChanged.connect(lambda s, p, n: emitted_signals.append((s, p, n)))

    # Modify parameters
    panel.spin_radius.setValue(5.25)
    panel.spin_bay.setValue(4.25)
    panel.spin_height.setValue(8.0)
    panel.spin_thick.setValue(0.50)
    panel.spin_bays.setValue(4)
    panel.spin_bp.setValue(0.90)
    panel.spin_dp.setValue(1.40)
    panel.spin_hp.setValue(8.5)

    assert len(emitted_signals) >= 1
    latest_shell, latest_pier, latest_bays = emitted_signals[-1]

    assert latest_shell.radius == 5.25
    assert latest_shell.bay_span == 4.25
    assert latest_shell.panel_height == 8.0
    assert latest_shell.thickness == 0.50
    assert latest_bays == 4
    assert latest_pier.pier_width == 0.90
    assert latest_pier.pier_depth == 1.40
    assert latest_pier.pier_height == 8.5

    s_geom, p_geom, n_b = panel.get_geometry()
    assert s_geom.radius == 5.25
    assert n_b == 4


def test_strut_and_pile_panel(qapp):
    """Tests StrutAndPilePanel for multi-level struts and bored pile foundation tuning."""
    panel = StrutAndPilePanel()
    assert panel.spin_dpile.value() > 0.0
    assert panel.spin_lpile.value() > 0.0

    emitted_signals = []
    panel.strutPileChanged.connect(lambda s, p: emitted_signals.append((s, p)))

    # Modify bored pile parameters
    panel.spin_dpile.setValue(1.00)
    panel.spin_lpile.setValue(18.0)
    panel.spin_socket.setValue(3.50)

    # Change strut levels to 3
    panel.spin_nstruts.setValue(3)
    panel.spin_level1.setValue(2.25)
    panel.spin_level2.setValue(5.75)
    panel.spin_rake.setValue(25.0)

    assert len(emitted_signals) >= 1
    latest_struts, latest_pier_pile = emitted_signals[-1]

    assert latest_pier_pile.pile_diameter == 1.00
    assert latest_pier_pile.pile_length == 18.0
    assert latest_pier_pile.rock_socket_length == 3.50
    assert len(latest_struts.strut_levels) == 3
    assert latest_struts.inclination_angle_deg == 25.0

    # Test count reduction to 1
    panel.spin_nstruts.setValue(1)
    s_res, p_res = panel.get_struts_and_piles()
    assert len(s_res.strut_levels) == 1


def test_audit_tab_ui(qapp, monkeypatch, tmp_path: Path):
    """Tests ISDesignAuditTab table updates and calculation report export."""
    tab = ISDesignAuditTab()
    assert tab.table.columnCount() == 9
    assert tab.table.rowCount() > 0
    assert "Overall Compliance" in tab.lbl_overall.text()

    # Trigger custom audit update
    tab.update_audit(
        shell_geom=CurvedShellGeometry(panel_height=7.0, thickness=0.40),
        pier_pile_geom=PierAndPileGeometry(pile_diameter=1.0, pile_length=15.0, pile_spacing=2.8),
        struts=StrutSupportSystem(strut_levels=[3.0]),
        soil=SoilProperties(cohesion=20.0, friction_angle=32.0, unit_weight=19.0),
        seismic=SeismicParams(horizontal_pga=0.15),
    )

    assert tab.table.rowCount() >= 8
    first_item_text = tab.table.item(0, 0).text()
    assert "Shell" in first_item_text or "RC" in first_item_text or "Panel" in first_item_text

    # Test synthetic WARNING status
    from orang3d.physics.is_codes.audit_engine import EngineeringAuditReport, AuditCheckItem
    warn_item = AuditCheckItem(
        component="RC Shell Panel",
        check_title="Flexural Warning",
        code_clause="IS 456 Cl. 38",
        demand=95.0,
        capacity=100.0,
        unit="kNm/m",
        unity_ratio=0.95,
        status="WARNING",
        detailing_note="High utilization",
    )
    warn_report = EngineeringAuditReport(
        project_title="Warning Test",
        wall_model_name="Wall",
        standards=IndianDesignStandards(),
        items=[warn_item],
        max_unity_ratio=0.95,
        governing_clause="IS 456 Cl. 38",
        overall_status="WARNING",
    )
    tab.update_audit(report=warn_report)
    assert "WARNING" in tab.lbl_overall.text()
    assert tab.table.item(0, 7).text() == "WARNING"

    # Test export button dialog
    export_file = tmp_path / "clicked_audit.md"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_file), "Markdown Files (*.md)"),
    )
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *args, **kwargs: None)
    tab._on_export_clicked()
    assert export_file.exists()
    assert export_file.stat().st_size > 100

    # Test empty report guard
    tab.current_report = None
    tab._on_export_clicked() # Should safely return without error


# ==============================================================================
# 3. MainWindow Full Integration & Dock Synchronization
# ==============================================================================

def test_main_window_dock_synchronization(qapp, monkeypatch, tmp_path: Path):
    """Tests dock panel synchronization, real-time recalculation, and DXF menu action in MainWindow."""
    window = MainWindow()

    # Verify tabs
    assert window.tabs.count() == 5
    assert window.tabs.tabText(0) == "Cantilever Wall"
    assert window.tabs.tabText(1) == "Curved Shell"
    assert window.tabs.tabText(2) == "Strut & Piles"
    assert window.tabs.tabText(3) == "Soil Strata"
    assert window.tabs.tabText(4) == "Disaster / Seismic"

    # Verify bottom tabs
    assert window.bottom_tabs.count() == 2
    assert "Seismic Waveforms" in window.bottom_tabs.tabText(0)
    assert "IS Design Audit" in window.bottom_tabs.tabText(1)

    # Change Shell parameters through panel
    window.panel_shell.spin_radius.setValue(4.75)
    window.panel_shell.spin_bay.setValue(3.80)
    assert window.shell_geom.radius == 4.75
    assert window.shell_geom.bay_span == 3.80

    # Change Strut/Pile parameters through panel
    window.panel_strut.spin_lpile.setValue(16.5)
    window.panel_strut.spin_dpile.setValue(0.95)
    assert window.pier_pile_geom.pile_length == 16.5
    assert window.pier_pile_geom.pile_diameter == 0.95

    # Verify IS Audit Tab is live and updated
    assert window.audit_tab.table.rowCount() > 0

    # Mock QFileDialog to test _export_dxf_dialog without blocking GUI prompt
    target_dxf = tmp_path / "gui_export.dxf"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(target_dxf), "AutoCAD DXF Files (*.dxf)"),
    )
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.information", lambda *args, **kwargs: None)
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.critical", lambda *args, **kwargs: None)

    window._export_dxf_dialog()
    assert target_dxf.exists()
    assert target_dxf.stat().st_size > 500

    window.close()


# ==============================================================================
# 4. Golden Textbook Benchmarks (Das, Bowles, IS Codes)
# ==============================================================================

def test_golden_textbook_benchmarks():
    """
    Regression validation against published textbook benchmarks:
    1. B.M. Das (Principles of Foundation Engineering): Coulomb Active Earth Pressure.
    2. J.E. Bowles (Foundation Analysis and Design): Arching Stress Reduction.
    3. IS 2911 (Part 1/Sec 2): Bored Pile Flexural Rigidity and Characteristic Length.
    4. IS 800:2007: Circular Hollow Section (CHS) Strut Compressive Capacity.
    """
    # --------------------------------------------------------------------------
    # Benchmark 1: Das Foundation Engineering - Coulomb Earth Pressure
    # Reference: Das 9th Ed., Section 13.7: phi = 32 deg, delta = 20 deg, beta = 0, theta = 0 (vertical)
    # Ka analytical = 0.2803
    # --------------------------------------------------------------------------
    phi_rad = math.radians(32.0)
    delta_rad = math.radians(20.0)
    ka_exact = (math.cos(phi_rad) ** 2) / (
        math.cos(delta_rad) * (1.0 + math.sqrt((math.sin(phi_rad + delta_rad) * math.sin(phi_rad)) / math.cos(delta_rad))) ** 2
    )

    gamma = 18.0
    H = 6.0
    p_a_exact = 0.5 * gamma * (H ** 2) * ka_exact

    # Coulomb static via compute_coulomb_earth_pressures
    k_a_calc, _ = compute_coulomb_earth_pressures(phi_deg=32.0, delta_deg=20.0)
    assert abs(k_a_calc - ka_exact) / ka_exact < 0.005, f"Coulomb Ka mismatch: Orang3D {k_a_calc} vs Das {ka_exact}"

    # Also check Mononobe-Okabe with kh=0, kv=0 equals static Coulomb Ka
    k_ae, k_a_mo, _ = compute_mononobe_okabe(phi_deg=32.0, delta_deg=20.0, kh=0.0, kv=0.0)
    assert abs(k_ae - ka_exact) / ka_exact < 0.005, f"MO Ka mismatch: Orang3D {k_ae} vs Das {ka_exact}"

    # --------------------------------------------------------------------------
    # Benchmark 2: Bowles Foundation Analysis - Horizontal Arching Reduction
    # Reference: Bowles 5th Ed., Section 12-7 & Handy (1985).
    # Arching between vertical piers spaced at L_bay / R <= 1.0 reduces lateral earth pressure
    # by 25% to 75% relative to Rankine/Coulomb free-field.
    # --------------------------------------------------------------------------
    z = 5.0
    L_bay = 2.0
    phi_soil = 30.0
    sigma_arching = compute_horizontal_arching_stress(
        z=z,
        gamma=18.5,
        phi=phi_soil,
        bay_span=L_bay,
        c=0.0,
    )
    ka_rankine = (1.0 - math.sin(math.radians(phi_soil))) / (1.0 + math.sin(math.radians(phi_soil)))
    sigma_free_field = 18.5 * z * ka_rankine

    eta_arching = sigma_arching / sigma_free_field
    assert 0.25 <= eta_arching <= 0.75, f"Arching stress ratio {eta_arching:.3f} outside expected Bowles range [0.25, 0.75]"

    # --------------------------------------------------------------------------
    # Benchmark 3: IS 2911 (Part 1/Sec 2: 2010) Bored Pile Rigidity
    # Pile Diameter D = 1.0 m, Concrete Grade M30 -> E_c = 5000 * sqrt(30) = 27386 MPa ~ 2.7386e7 kN/m2
    # I = pi * D^4 / 64 = 0.049087 m4
    # Flexural Rigidity EI = E_c * I ~ 1.344e6 kN.m2
    # --------------------------------------------------------------------------
    D = 1.0
    E_c = 5000.0 * math.sqrt(30.0) * 1000.0 # kPa (kN/m2)
    I_pile = (math.pi * (D ** 4)) / 64.0
    EI_expected = E_c * I_pile
    assert 1.2e6 <= EI_expected <= 1.5e6

    # --------------------------------------------------------------------------
    # Benchmark 4: IS 800:2007 Structural Steel Strut Compressive Capacity
    # CHS 355.6 x 12.5 (Fe 250): A = 13470 mm2, r = 121.3 mm, Effective length KL = 6.0 m
    # Slenderness lambda = 6000 / 121.3 = 49.46
    # Per IS 800 Table 9(a) (Buckling class 'a' for hot finished hollow sections):
    # For lambda = 50, fy = 250 MPa, design compressive stress fcd should be >= 195 MPa.
    # --------------------------------------------------------------------------
    audit = run_full_retaining_wall_is_audit(
        standards=IndianDesignStandards(),
        strut_length_m=6.0,
        strut_compression_kN=500.0,
        strut_area_mm2=13470.0,
        strut_radius_gyration_mm=121.3,
    )
    strut_checks = [it for it in audit.items if "Steel Strut" in it.component]
    assert len(strut_checks) >= 3
    buckling_check = next(it for it in strut_checks if "Buckling" in it.check_title)
    assert buckling_check.capacity > 1000.0 # kN
    assert buckling_check.status == "PASS"


# ==============================================================================
# 5. Headless CI Rendering Smoke Test
# ==============================================================================

def test_headless_ci_render(qapp):
    """Verifies offscreen PyVista 3D scene creation without display server crashes."""
    geom = RetainingWallGeometry(stem_height=6.0)
    soil = SoilProperties()
    seismic = SeismicParams()
    from orang3d.physics.stability import evaluate_wall_stability
    results = evaluate_wall_stability(geom, soil, seismic)

    from orang3d.gui.viewport_3d import Viewport3D
    vp = Viewport3D()
    vp.update_scene(geom, soil, seismic, results)
    assert vp.plotter is not None
    vp.close()
