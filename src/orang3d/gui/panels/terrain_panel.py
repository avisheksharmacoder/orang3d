"""
Site Topography Importer & Interactive Sizing Advisor Panel (Phase 8).

Features:
  1. Import ESRI .asc, XYZ .csv, Wavefront .obj, or GeoTIFF (.tif) terrain models.
  2. Auto-extract local slope angle beta, Eurocode 8 / IS 1893 topographic seismic
     amplification factor S_T, and stepped/variable wall cut-line profile.
  3. Toggle 3D draped terrain mesh + elevation contours in Viewport3D.
  4. Interactive Sizing Advisor evaluating failing limit states with 1-click fix.
"""

from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...mesher.terrain import (
    TerrainRaster,
    WallCutProfile,
    auto_profile_wall_along_terrain,
    generate_synthetic_slope,
    load_terrain_file,
)
from ...physics.sizing_advisor import SizingAdviceReport
from ...signals.topography import compute_topographic_amplification_factor
from ...units import UnitSystem, from_si_value, unit_label


class TerrainAndStudioPanel(QWidget):
    """Sidebar panel for Site Topography Import, Topographic S_T, and Sizing Advisor."""

    terrainUpdated = Signal(object, bool, float, float)  # (TerrainRaster, show_3d, beta_deg, st_factor)
    applyRecommendedGeometryRequested = Signal(object)   # RetainingWallGeometry
    refreshAdvisorRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.unit_system: UnitSystem = UnitSystem.SI
        self.current_terrain: Optional[TerrainRaster] = None
        self.current_cut_profile: Optional[WallCutProfile] = None
        self.current_advice: Optional[SizingAdviceReport] = None
        self.mean_slope_deg: float = 0.0
        self.st_factor: float = 1.0
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # ------------------------------------------------------------------
        # 1. Site Topography & Sloped Terrain Importer
        # ------------------------------------------------------------------
        self.grp_terrain = QGroupBox("Site Topography & Draped DEM")
        t_lay = QVBoxLayout(self.grp_terrain)

        btn_row = QHBoxLayout()
        self.btn_load_terrain = QPushButton("Import Terrain (.asc / .csv / .obj)...")
        self.btn_load_terrain.clicked.connect(self._on_browse_terrain)
        self.btn_gen_slope = QPushButton("Sample 24° Slope")
        self.btn_gen_slope.clicked.connect(lambda: self.generate_sample_terrain("planar", 24.0))
        btn_row.addWidget(self.btn_load_terrain)
        btn_row.addWidget(self.btn_gen_slope)
        t_lay.addLayout(btn_row)

        form = QFormLayout()
        self.combo_feature = QComboBox()
        self.combo_feature.addItem("Ridge / Escarpment (S_T <= 1.4)", "ridge")
        self.combo_feature.addItem("Isolated Cliff / Slope (S_T <= 1.2)", "cliff")
        self.combo_feature.currentIndexChanged.connect(self._recompute_terrain_metrics)
        form.addRow("Topographic Feature:", self.combo_feature)
        t_lay.addLayout(form)

        self.chk_show_terrain = QCheckBox("Show Draped 3D Terrain & Elevation Contours")
        self.chk_show_terrain.setChecked(True)
        self.chk_show_terrain.toggled.connect(self._emit_terrain_state)
        t_lay.addWidget(self.chk_show_terrain)

        self.lbl_terrain_info = QLabel("No terrain loaded. Load .asc/.csv/.obj or generate sample hill slope.")
        self.lbl_terrain_info.setWordWrap(True)
        self.lbl_terrain_info.setStyleSheet("color: #93c5fd; font-size: 11px;")
        t_lay.addWidget(self.lbl_terrain_info)

        self.lbl_cut_profile = QLabel("")
        self.lbl_cut_profile.setWordWrap(True)
        self.lbl_cut_profile.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        t_lay.addWidget(self.lbl_cut_profile)

        layout.addWidget(self.grp_terrain)

        # ------------------------------------------------------------------
        # 2. Interactive Sizing Advisor
        # ------------------------------------------------------------------
        self.grp_advisor = QGroupBox("Interactive Geotechnical Sizing Advisor")
        a_lay = QVBoxLayout(self.grp_advisor)

        self.lbl_advisor = QLabel("Click 'Evaluate Sizing' to inspect active limit-state compliance.")
        self.lbl_advisor.setWordWrap(True)
        self.lbl_advisor.setStyleSheet("font-size: 11px; padding: 4px;")
        a_lay.addWidget(self.lbl_advisor)

        adv_btns = QHBoxLayout()
        self.btn_eval_advisor = QPushButton("Evaluate Sizing")
        self.btn_eval_advisor.clicked.connect(lambda: self.refreshAdvisorRequested.emit())
        self.btn_apply_advice = QPushButton("Apply Recommended Geometry")
        self.btn_apply_advice.setEnabled(False)
        self.btn_apply_advice.clicked.connect(self._on_apply_advice)
        adv_btns.addWidget(self.btn_eval_advisor)
        adv_btns.addWidget(self.btn_apply_advice)
        a_lay.addLayout(adv_btns)

        layout.addWidget(self.grp_advisor)
        layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _on_browse_terrain(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Site Terrain DEM / Survey",
            "",
            "Terrain Files (*.asc *.csv *.xyz *.obj *.tif *.tiff);;All Files (*)",
        )
        if path:
            self.load_terrain_from_path(path)

    def load_terrain_from_path(self, filepath: str) -> TerrainRaster:
        """Loads a .asc, .csv/.xyz, .obj, or .tif site terrain and extracts slope invariants."""
        raster = load_terrain_file(filepath)
        self.set_terrain(raster)
        return raster

    def generate_sample_terrain(self, slope_type: str = "planar", slope_angle_deg: float = 24.0) -> TerrainRaster:
        """Generates and activates a synthetic hill-slope terrain raster."""
        raster = generate_synthetic_slope(
            slope_type=slope_type,
            length_x=40.0,
            width_y=24.0,
            resolution=2.0,
            slope_angle_deg=slope_angle_deg,
            crest_elevation=18.0,
        )
        self.set_terrain(raster)
        return raster

    def set_terrain(self, terrain: Optional[TerrainRaster]) -> None:
        """Attaches an already parsed TerrainRaster and recomputes cut-line & S_T metrics."""
        self.current_terrain = terrain
        self._recompute_terrain_metrics()

    def _recompute_terrain_metrics(self) -> None:
        if self.current_terrain is None:
            self.current_cut_profile = None
            self.mean_slope_deg = 0.0
            self.st_factor = 1.0
            self.lbl_terrain_info.setText("No terrain loaded.")
            self.lbl_cut_profile.setText("")
            self._emit_terrain_state()
            return

        prof = auto_profile_wall_along_terrain(self.current_terrain, num_segments=4)
        self.current_cut_profile = prof
        self.mean_slope_deg = prof.mean_slope_deg

        feature = str(self.combo_feature.currentData() or "ridge")
        hill_h = max(2.0, self.current_terrain.max_elevation - self.current_terrain.min_elevation)
        self.st_factor = compute_topographic_amplification_factor(
            slope_angle_deg=prof.mean_slope_deg,
            crest_distance=prof.crest_distance_m,
            hill_height=hill_h,
            feature_type=feature,
        )
        self._refresh_terrain_labels()
        self._emit_terrain_state()

    def _refresh_terrain_labels(self) -> None:
        if self.current_terrain is None or self.current_cut_profile is None:
            return
        u_l = unit_label("length", self.unit_system)
        zmin = from_si_value(self.current_terrain.min_elevation, "length", self.unit_system)
        zmax = from_si_value(self.current_terrain.max_elevation, "length", self.unit_system)
        self.lbl_terrain_info.setText(
            f"DEM Loaded | Elev: [{zmin:.2f}, {zmax:.2f}] {u_l} | "
            f"Mean Slope β = {self.mean_slope_deg:.1f}° | "
            f"Topographic Seismic S_T = {self.st_factor:.2f}"
        )
        stations_str = " -> ".join(
            f"{from_si_value(g, 'length', self.unit_system):.1f}"
            for g in self.current_cut_profile.ground_elevations_m
        )
        heights_str = " -> ".join(
            f"{from_si_value(h, 'length', self.unit_system):.1f}"
            for h in self.current_cut_profile.retained_heights_m
        )
        self.lbl_cut_profile.setText(
            f"Cut-Line Stepped Grade ({u_l}): {stations_str}\n"
            f"Auto-Profiled Wall Heights ({u_l}): {heights_str}"
        )

    def _emit_terrain_state(self) -> None:
        self.terrainUpdated.emit(
            self.current_terrain,
            bool(self.chk_show_terrain.isChecked()),
            float(self.mean_slope_deg),
            float(self.st_factor),
        )

    def update_advisor(self, report: SizingAdviceReport) -> None:
        """Displays Sizing Advisor recommendations and enables/disables 1-click fix."""
        self.current_advice = report
        if report.all_checks_passing:
            self.lbl_advisor.setStyleSheet("color: #34d399; font-size: 11px; padding: 4px;")
            self.btn_apply_advice.setEnabled(False)
        else:
            self.lbl_advisor.setStyleSheet("color: #fca5a5; font-size: 11px; padding: 4px;")
            self.btn_apply_advice.setEnabled(bool(report.recommendations))
        self.lbl_advisor.setText("\n".join(f"• {line}" for line in report.summary_lines))

    def _on_apply_advice(self) -> None:
        if self.current_advice is not None:
            self.applyRecommendedGeometryRequested.emit(self.current_advice.recommended_geom)

    def set_unit_system(self, unit_system: UnitSystem | str) -> None:
        """Updates terrain and advisor readouts between SI and Imperial units."""
        self.unit_system = UnitSystem(unit_system)
        self._refresh_terrain_labels()

