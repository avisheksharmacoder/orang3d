"""
Phase 9 Tests: Reproducible Research Exports (.py OpenSees deck, Kratos .mdpa/JSON,
HDF5 + JSON archive), 3D CAD / BIM Interoperability (3D DXF, .glb, IFC 4),
and .o3d v2.0 Session Schema Round-Trip & v1 Backward Compatibility.
"""

from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from pathlib import Path
import subprocess
import sys

import ezdxf
import h5py
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from orang3d.config import RegionalStandard, ThemeMode
from orang3d.gui.main_window import MainWindow
from orang3d.io import (
    CURRENT_SCHEMA_VERSION,
    DXF_3D_LAYERS,
    DXF_LAYERS,
    RetainingWallDXFExporter,
    export_grid_to_3d_dxf,
    export_kratos_deck,
    export_opensees_bnwf_deck,
    export_research_archive,
    export_retaining_wall_dxf,
    export_wall_to_glb,
    export_wall_to_ifc,
    load_project_session,
    read_glb_summary,
    save_project_session,
)
from orang3d.mesher.hex_mesher import build_3d_wall_mesh
from orang3d.models.advanced_wall_params import (
    CurvedShellGeometry,
    MultiStrutPiledWallModel,
    PierAndPileGeometry,
    StrutSupportSystem,
    WallSystemMode,
)
from orang3d.models.architectural_wall_params import ArchWallMorphology, ArchitecturalWallSpec
from orang3d.models.wall_params import (
    AnalysisResults,
    RetainingWallGeometry,
    SeismicParams,
    SoilProperties,
)
from orang3d.physics.bnwf_solver import OPENSEES_AVAILABLE, OpenSeesBNWFSolver
from orang3d.physics.solver_registry import SolverTier, build_provenance
from orang3d.physics.surcharge import AdjacentSurchargeParams, SurchargeLoadType
from orang3d.units import UnitSystem


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy not installed")
def test_opensees_deck_subprocess_matches_in_app_solver(tmp_path: Path):
    """
    Executes the exported standalone OpenSeesPy .py deck in an isolated subprocess
    and asserts crest displacement history matches the in-app solver to < 1e-6.
    """
    model = MultiStrutPiledWallModel(
        shell=CurvedShellGeometry(radius=4.5, bay_span=3.5, panel_height=6.0, thickness=0.4),
        piers=PierAndPileGeometry(
            pier_width=0.8,
            pier_depth=1.2,
            pier_height=6.5,
            pile_diameter=1.0,
            pile_length=12.0,
            pile_spacing=3.0,
            rock_socket_length=1.5,
            num_piles_per_pier=2,
        ),
        struts=StrutSupportSystem(strut_levels=[2.0, 4.5], inclination_angle_deg=20.0),
    )
    soil = SoilProperties(unit_weight=19.0, friction_angle=34.0, cohesion=2.0)

    dt = 0.02
    t_arr = np.arange(0.0, 0.40 + 1e-9, dt)
    accel_arr = 0.18 * np.sin(2.0 * np.pi * 2.5 * t_arr)

    # 1. Run in-app OpenSeesBNWFSolver
    solver = OpenSeesBNWFSolver(model=model, soil=soil, slope_angle=12.0)
    solver.initialize()
    assert solver.run_staged_construction() is True
    in_app_res = solver.run_dynamic_analysis(t_arr, accel_arr, damping_ratio=0.05)
    assert in_app_res.dynamic_converged is True

    # 2. Export standalone Python deck and execute via subprocess
    deck_path = tmp_path / "standalone_bnwf.py"
    out_json = tmp_path / "subprocess_out.json"
    export_opensees_bnwf_deck(
        deck_path,
        model=model,
        soil=soil,
        time_arr=t_arr,
        accel_arr=accel_arr,
        slope_angle=12.0,
        damping_ratio=0.05,
    )
    assert deck_path.exists()
    script_text = deck_path.read_text(encoding="utf-8")
    assert "orang3d" not in script_text.lower() or "generated automatically by orang3d" in script_text.lower()
    assert "UniformExcitation" in script_text

    proc = subprocess.run(
        [sys.executable, str(deck_path), "--output-json", str(out_json)],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert "ORANG3D_RESULTS_JSON:" in proc.stdout
    sub_data = json.loads(out_json.read_text(encoding="utf-8"))
    assert sub_data["dynamic_converged"] is True
    assert sub_data["total_steps"] == in_app_res.total_steps

    sub_crest = np.asarray(sub_data["crest_displacement"], dtype=np.float64)
    max_diff = float(np.max(np.abs(sub_crest - in_app_res.crest_displacement)))
    assert max_diff < 1e-6


def test_kratos_deck_and_research_archive_exports(tmp_path: Path):
    """Validates Kratos .mdpa + ProjectParameters.json deck and HDF5 + metadata.json archive."""
    geom = RetainingWallGeometry(stem_height=5.5, heel_length=2.8, toe_length=1.1, wall_length=6.0)
    soil = SoilProperties(unit_weight=19.2, friction_angle=33.0, elastic_modulus=42000.0)
    seismic = SeismicParams(horizontal_pga=0.28, water_table_depth=3.0)
    results = AnalysisResults(total_thrust=140.0, fs_sliding=1.42, fs_overturning=2.15, fs_bearing=2.80)

    t = np.linspace(0.0, 2.0, 41)
    a = 0.25 * np.sin(2.0 * np.pi * 1.5 * t)
    disp = 0.015 * np.sin(2.0 * np.pi * 1.5 * t)
    pore = 25.0 + 5.0 * t
    stress_hist = np.ones((len(t), 3), dtype=np.float64) * (-45.0)
    strain_hist = np.ones((len(t), 3), dtype=np.float64) * (-1.1e-4)

    # 1. Kratos Deck Export
    kratos_dir = tmp_path / "kratos_deck"
    k_files = export_kratos_deck(kratos_dir, geom=geom, soil=soil, seismic=seismic, time_arr=t, accel_arr=a)
    mdpa_text = Path(k_files["mdpa"]).read_text(encoding="utf-8")
    assert "UPwSmallStrainElement2D4N" in mdpa_text
    assert "UPwLysmerAbsorbingCondition2D2N" in mdpa_text
    assert "Begin SubModelPart WallPart" in mdpa_text
    assert "Begin SubModelPart LysmerBoundaryPart" in mdpa_text

    params = json.loads(Path(k_files["parameters"]).read_text(encoding="utf-8"))
    assert params["solver_settings"]["scheme_type"] == "Newmark"
    assert params["solver_settings"]["linear_solver_settings"]["solver_type"] == "skyline_lu_factorization"
    assert Path(k_files["ground_motion"]).exists()

    # 2. Research HDF5 + Metadata JSON Archive Export
    prov = build_provenance(
        SolverTier.L2_KRATOS_FEA,
        element_types=["UPwSmallStrainElement2D4N", "UPwLysmerAbsorbingCondition2D2N"],
        constitutive_model="Elastic-Plastic Effective Stress U-Pw",
        damping_model="Lysmer + Rayleigh",
        runtime_ms=125.4,
        random_seed=1337,
    )
    arch_dir = tmp_path / "research_archive"
    a_files = export_research_archive(
        arch_dir,
        geom=geom,
        soil=soil,
        seismic=seismic,
        results=results,
        provenance=prov,
        time_arr=t,
        accel_arr=a,
        slip_arr=disp,
        pore_arr=pore,
        stress_history=stress_hist,
        strain_history=strain_hist,
        random_seed=1337,
    )
    with h5py.File(a_files["hdf5"], "r") as hf:
        assert hf.attrs["random_seed"] == 1337
        assert hf["stress_tensor_kpa"].shape == (len(t), 3)
        assert hf["strain_tensor"].shape == (len(t), 3)
        np.testing.assert_allclose(hf["time_s"][:], t)

    meta = json.loads(Path(a_files["metadata"]).read_text(encoding="utf-8"))
    assert meta["random_seed"] == 1337
    assert meta["provenance"]["tier"] == SolverTier.L2_KRATOS_FEA.value
    assert "stress_tensor_kpa" in meta["datasets"]


def test_3d_dxf_glb_and_ifc4_bim_exports(tmp_path: Path):
    """Validates 3D DXF (3DFACE/POLYLINE), binary glTF 2.0 (.glb), and IFC 4 (.ifc)."""
    geom = RetainingWallGeometry(stem_height=6.0, wall_length=5.0)
    results = AnalysisResults(fs_sliding=1.55, fs_overturning=2.30, fs_bearing=2.90, max_bending_moment=195.0)
    ms_model = MultiStrutPiledWallModel(
        shell=CurvedShellGeometry(radius=4.5, bay_span=3.5, panel_height=6.0, thickness=0.45),
        piers=PierAndPileGeometry(pier_width=0.8, pier_depth=1.2, pier_height=6.5, pile_diameter=1.0, pile_length=12.0),
        struts=StrutSupportSystem(strut_levels=[2.2, 4.8], inclination_angle_deg=20.0),
    )

    # 1. 3D DXF assembly export via ezdxf
    dxf3d_path = tmp_path / "wall_3d.dxf"
    export_retaining_wall_dxf(ms_model, str(dxf3d_path), num_bays=3, include_3d=True)
    doc = ezdxf.readfile(str(dxf3d_path))
    layer_names = {layer.dxf.name for layer in doc.layers}
    for lyr in (*DXF_LAYERS.keys(), *DXF_3D_LAYERS.keys()):
        assert lyr in layer_names
    dxftypes = {e.dxftype() for e in doc.modelspace()}
    assert "3DFACE" in dxftypes
    assert "POLYLINE" in dxftypes

    # Also validate generic PyVista grid 3D DXF export and ASCII 3D fallback
    cant_grid = build_3d_wall_mesh(geom, results)
    cant_dxf_path = tmp_path / "cantilever_3d.dxf"
    export_grid_to_3d_dxf(cant_grid, cant_dxf_path)
    doc_c = ezdxf.readfile(str(cant_dxf_path))
    assert any(e.dxftype() == "3DFACE" for e in doc_c.modelspace())

    ascii3d_path = tmp_path / "ascii_3d.dxf"
    RetainingWallDXFExporter(ms_model)._export_ascii_dxf(
        ascii3d_path,
        project_title="ASCII 3D CAD",
        drawing_number="DWG-3D",
        num_bays=2,
        rebar_callout="T16",
        pile_callout="T25",
        strut_callout="CHS",
        include_3d=True,
    )
    assert "3DFACE" in ascii3d_path.read_text(encoding="utf-8")

    # 2. Binary glTF 2.0 (.glb) export
    glb_path = tmp_path / "retaining_wall.glb"
    export_wall_to_glb(glb_path, geom, results)
    glb_info = read_glb_summary(glb_path)
    assert glb_info["magic"] == "glTF"
    assert glb_info["version"] == 2
    assert len(glb_info["manifest"]["meshes"]) == 1
    assert glb_info["manifest"]["buffers"][0]["byteLength"] > 100

    # 3. IFC 4 (.ifc) BIM export
    ifc_path = tmp_path / "retaining_wall.ifc"
    export_wall_to_ifc(
        ifc_path,
        geom,
        results,
        multi_strut_model=ms_model,
        num_bays=2,
        standard_name="EUROCODE_7",
    )
    ifc_text = ifc_path.read_text(encoding="utf-8")
    assert "ISO-10303-21;" in ifc_text
    assert "FILE_SCHEMA(('IFC4'));" in ifc_text
    assert "IFCWALL" in ifc_text
    assert "RETAININGWALL" in ifc_text
    assert "IFCPILE" in ifc_text
    assert "IFCMEMBER" in ifc_text
    assert "Pset_orang3D_GeotechnicalDesign" in ifc_text


def test_o3d_v2_schema_roundtrip_and_v1_backward_compat(tmp_path: Path):
    """Verifies .o3d v2.0 full-state round-trip persistence and v1.0 legacy migration."""
    geom = RetainingWallGeometry(stem_height=7.0, heel_length=3.4, wall_length=8.0)
    soil = SoilProperties(unit_weight=19.5, friction_angle=35.0)
    seismic = SeismicParams(horizontal_pga=0.32, water_table_depth=4.0)
    results = AnalysisResults(fs_sliding=1.60, fs_overturning=2.45, fs_bearing=3.10)
    t = np.linspace(0.0, 2.0, 25)
    a = 0.2 * np.sin(t)
    slip = np.linspace(0.0, 1.2, 25)
    pore = np.linspace(10.0, 40.0, 25)

    shell = CurvedShellGeometry(radius=5.2, bay_span=4.1, panel_height=6.2, thickness=0.42)
    piers = PierAndPileGeometry(
        pier_width=0.9,
        pier_depth=1.4,
        pier_height=6.8,
        pile_diameter=1.1,
        pile_length=15.0,
        pile_spacing=3.0,
    )
    struts = StrutSupportSystem(strut_levels=[2.0, 4.4], inclination_angle_deg=22.0)
    arch = ArchitecturalWallSpec(morphology=ArchWallMorphology.COUNTERFORT)
    sur = AdjacentSurchargeParams(load_type=SurchargeLoadType.BUILDING_PAD_FOOTING, building_load_kn=520.0, setback_m=1.5)
    fea_cache = {"crest_disp_history_m": np.linspace(0.0, 0.02, 25), "time_history_s": t}

    v2_path = tmp_path / "session_v2.o3d"
    save_project_session(
        str(v2_path),
        geom=geom,
        soil=soil,
        seismic=seismic,
        results=results,
        time_arr=t,
        accel_arr=a,
        slip_arr=slip,
        pore_arr=pore,
        wall_mode=WallSystemMode.MULTI_STRUT_CURVED_SHELL,
        shell_geom=shell,
        pier_pile_geom=piers,
        strut_sys=struts,
        arch_spec=arch,
        surcharge_params=sur,
        num_bays=4,
        regional_standard=RegionalStandard.EUROCODE_7,
        unit_system=UnitSystem.IMPERIAL,
        theme_mode=ThemeMode.LIGHT,
        terrain_metadata={"mean_slope_deg": 24.5, "st_factor": 1.2},
        uq_results={"p_failure": 0.015, "n_samples": 100},
        fea_cache=fea_cache,
        provenance={"tier": "l2_kratos_fea"},
    )
    loaded = load_project_session(str(v2_path))
    assert loaded.schema_version == CURRENT_SCHEMA_VERSION == "2.0.0"
    assert loaded.wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL
    assert loaded.shell_geom.radius == pytest.approx(5.2)
    assert loaded.pier_pile_geom.pile_length == pytest.approx(15.0)
    assert loaded.strut_sys.strut_levels == [2.0, 4.4]
    assert loaded.arch_spec.morphology == ArchWallMorphology.COUNTERFORT
    assert loaded.surcharge_params.load_type == SurchargeLoadType.BUILDING_PAD_FOOTING
    assert loaded.surcharge_params.building_load_kn == pytest.approx(520.0)
    assert loaded.num_bays == 4
    assert loaded.regional_standard == RegionalStandard.EUROCODE_7
    assert loaded.unit_system == UnitSystem.IMPERIAL
    assert loaded.theme_mode == ThemeMode.LIGHT
    assert loaded.terrain_metadata["st_factor"] == pytest.approx(1.2)
    assert loaded.uq_results["p_failure"] == pytest.approx(0.015)
    assert "crest_disp_history_m" in loaded.fea_cache
    np.testing.assert_allclose(loaded.fea_cache["crest_disp_history_m"], fea_cache["crest_disp_history_m"])

    # Legacy v1.0.0 backward-compatibility check
    v1_path = tmp_path / "legacy_v1.o3d"
    save_project_session(
        str(v1_path),
        geom=geom,
        soil=soil,
        seismic=seismic,
        results=results,
        schema_version="1.0.0",
    )
    migrated = load_project_session(str(v1_path))
    assert migrated.schema_version == "2.0.0"
    assert migrated.wall_mode == WallSystemMode.CANTILEVER
    assert migrated.regional_standard == RegionalStandard.STANDARD


def test_main_window_phase9_export_dialogs_and_v2_session(qapp, monkeypatch, tmp_path: Path):
    """Exercises MainWindow Phase 9 export dialogs and v2.0 save/open UI integration."""
    window = MainWindow()
    try:
        monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

        # Configure non-default v2 state, save, mutate, and reload
        window.set_theme_mode(ThemeMode.LIGHT)
        window.set_unit_system(UnitSystem.IMPERIAL)
        window.audit_tab.set_standard(RegionalStandard.AASHTO_LRFD)
        o3d_path = tmp_path / "gui_v2.o3d"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(o3d_path), "*.o3d"))
        window._save_project()
        assert o3d_path.exists()

        window.set_theme_mode(ThemeMode.DARK)
        window.set_unit_system(UnitSystem.SI)
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(o3d_path), "*.o3d"))
        window._open_project()
        assert window.theme_mode == ThemeMode.LIGHT
        assert window.unit_system == UnitSystem.IMPERIAL
        assert window.audit_tab.current_standard == RegionalStandard.AASHTO_LRFD

        # GLB, IFC, 3D DXF, OpenSeesPy deck, Kratos deck, and Research Archive dialogs
        glb_path = tmp_path / "ui_wall.glb"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(glb_path), "*.glb"))
        window._export_glb_dialog()
        assert read_glb_summary(glb_path)["magic"] == "glTF"

        ifc_path = tmp_path / "ui_wall.ifc"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(ifc_path), "*.ifc"))
        window._export_ifc_dialog()
        assert "FILE_SCHEMA(('IFC4'));" in ifc_path.read_text(encoding="utf-8")

        dxf3d_path = tmp_path / "ui_wall_3d.dxf"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(dxf3d_path), "*.dxf"))
        window._export_dxf_dialog(include_3d=True)
        assert dxf3d_path.exists()

        ops_path = tmp_path / "ui_ops_deck.py"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(ops_path), "*.py"))
        window._export_opensees_deck_dialog()
        assert "UniformExcitation" in ops_path.read_text(encoding="utf-8")

        kratos_dir = tmp_path / "ui_kratos_deck"
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(kratos_dir))
        window._export_kratos_deck_dialog()
        assert (kratos_dir / "RetainingWallSSI.mdpa").exists()
        assert (kratos_dir / "ProjectParameters.json").exists()

        arch_path = tmp_path / "ui_archive.h5"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(arch_path), "*.h5"))
        window._export_research_archive_dialog()
        assert arch_path.exists()
        assert (tmp_path / "ui_archive_metadata.json").exists()
    finally:
        window.close()
        qapp.processEvents()
