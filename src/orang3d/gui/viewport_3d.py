"""
3D Scientific Viewport for orang3D using PyVista and pyvistaqt (Phase 7).
Provides:
- Hardware-accelerated VTK rendering embedded in PySide6
- Scalar stress heatmaps (Tensile Stress, Von Mises Stress, Pore-water Pressure)
- Curated scientific colormaps (plasma, viridis, coolwarm, magma)
- Dynamic deformation mesh warping with 1x-100x scale slider
- Animated Coulomb / Mononobe-Okabe active failure wedge
- Orthographic cutting planes (X, Y, Z slice planes) for junction stress inspection
- Dynamic vector glyphs for stem contact pressure and foundation bearing reaction
- Translucent water table plane with seismic wave ripple dynamics
- Robust actor lifecycle management preventing memory leaks
"""

from typing import Optional, Tuple
import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QDoubleSpinBox,
    QCheckBox,
    QLabel,
    QSlider,
    QPushButton,
    QFrame,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal
import pyvista as pv
from pyvistaqt import QtInteractor

from ..config import VIEWPORT_COLORS, THEME_DARK, THEME_LIGHT, THEMES, ThemeMode
from ..units import UnitSystem, from_si_value, unit_label
from ..mesher.terrain import TerrainRaster
from ..models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
)
from ..models.advanced_wall_params import (
    MultiStrutPiledWallModel,
    WallSystemMode,
)
from ..mesher.hex_mesher import (
    build_3d_wall_mesh,
    build_3d_soil_mesh,
    build_3d_wedge_mesh,
    build_contact_pressure_glyphs,
    build_bearing_pressure_glyphs,
)
from ..mesher.hybrid_assembler import assemble_multi_strut_piled_wall_mesh
from ..mesher.arch_wall_mesher import (
    build_architectural_wall_mesh,
    build_surcharge_3d_meshes,
)
from ..models.architectural_wall_params import ArchitecturalWallSpec
from ..physics.arch_wall_solver import ArchWallAnalysisSummary
from ..physics.shell_arching import ShellArchingResult
from ..physics.surcharge import AdjacentSurchargeParams, SurchargeLoadType


class StabilityHUDOverlay(QFrame):
    """
    Tier 1.1: Frosted-Glass On-Screen Heads-Up Display (HUD) overlay for the 3D scene.
    Presents real-time geotechnical limit state evaluations, safety factors, and
    governing pass/fail diagnostics directly on the canvas.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed: bool = False
        self._init_ui()
        self.apply_theme(ThemeMode.DARK)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Header row: Status Badge + Collapse Toggle
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        self.status_badge = QLabel("🟢 ALL SYSTEMS SAFE")
        self.status_badge.setStyleSheet(
            "font-weight: 700; font-size: 11px; padding: 2px 6px; border-radius: 4px;"
        )
        header_row.addWidget(self.status_badge)

        header_row.addStretch()

        self.btn_collapse = QPushButton("–")
        self.btn_collapse.setFixedSize(20, 20)
        self.btn_collapse.setToolTip("Collapse/Expand Stability HUD")
        self.btn_collapse.clicked.connect(self.toggle_collapse)
        header_row.addWidget(self.btn_collapse)
        layout.addLayout(header_row)

        # Detailed Limit States & Metrics Container
        self.detail_container = QWidget(self)
        det_layout = QVBoxLayout(self.detail_container)
        det_layout.setContentsMargins(0, 4, 0, 0)
        det_layout.setSpacing(3)

        self.lbl_fs_sliding = QLabel("Sliding FS:      -- (Limit ≥ 1.40)")
        self.lbl_fs_overturning = QLabel("Overturning FS:  -- (Limit ≥ 1.50)")
        self.lbl_fs_bearing = QLabel("Bearing FS:      -- (Limit ≥ 2.50)")
        self.lbl_geometry = QLabel("Geometry:        --")
        self.lbl_deflection = QLabel("Crest Defl:      --")

        for lbl in (
            self.lbl_fs_sliding,
            self.lbl_fs_overturning,
            self.lbl_fs_bearing,
            self.lbl_geometry,
            self.lbl_deflection,
        ):
            lbl.setStyleSheet("font-family: monospace; font-size: 11px;")
            det_layout.addWidget(lbl)

        layout.addWidget(self.detail_container)

    def toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        self.detail_container.setVisible(not self.is_collapsed)
        self.btn_collapse.setText("+" if self.is_collapsed else "–")
        self.adjustSize()

    def update_metrics(
        self,
        geom: Optional[RetainingWallGeometry] = None,
        results: Optional[AnalysisResults] = None,
        seismic: Optional[SeismicParams] = None,
        unit_system: UnitSystem = UnitSystem.SI,
    ):
        if results is None:
            self.status_badge.setText("⚪ AWAITING STABILITY")
            return

        fs_s = float(results.fs_sliding)
        fs_o = float(results.fs_overturning)
        fs_b = float(results.fs_bearing)

        is_safe = (fs_s >= 1.40) and (fs_o >= 1.50) and (fs_b >= 2.50)
        is_fail = (fs_s < 1.0) or (fs_o < 1.0) or (fs_b < 1.0)

        if is_safe:
            self.status_badge.setText("🟢 ALL SYSTEMS SAFE")
            self.status_badge.setStyleSheet(
                "background-color: rgba(16, 185, 129, 0.25); color: #34d399; font-weight: 700; "
                "font-size: 11px; padding: 2px 6px; border-radius: 4px; border: 1px solid #059669;"
            )
        elif is_fail:
            self.status_badge.setText("🔴 STABILITY FAIL")
            self.status_badge.setStyleSheet(
                "background-color: rgba(239, 68, 68, 0.25); color: #f87171; font-weight: 700; "
                "font-size: 11px; padding: 2px 6px; border-radius: 4px; border: 1px solid #dc2626;"
            )
        else:
            self.status_badge.setText("🟡 MARGINAL STABILITY")
            self.status_badge.setStyleSheet(
                "background-color: rgba(245, 158, 11, 0.25); color: #fbbf24; font-weight: 700; "
                "font-size: 11px; padding: 2px 6px; border-radius: 4px; border: 1px solid #d97706;"
            )

        self.lbl_fs_sliding.setText(f"Sliding FS:     {fs_s:5.2f} (≥ 1.40) [{'OK' if fs_s >= 1.40 else 'FAIL'}]")
        self.lbl_fs_overturning.setText(f"Overturn FS:    {fs_o:5.2f} (≥ 1.50) [{'OK' if fs_o >= 1.50 else 'FAIL'}]")
        self.lbl_fs_bearing.setText(f"Bearing FS:     {fs_b:5.2f} (≥ 2.50) [{'OK' if fs_b >= 2.50 else 'FAIL'}]")

        if geom is not None:
            h_val = from_si_value(geom.total_height, "length", unit_system)
            b_val = from_si_value(geom.base_width, "length", unit_system)
            u_len = unit_label("length", unit_system)
            self.lbl_geometry.setText(f"Geometry:       H={h_val:.2f}{u_len} | B={b_val:.2f}{u_len}")

        pga = seismic.horizontal_pga if seismic else 0.0
        h_tot = geom.total_height if geom else 6.0
        disp_mm = (0.008 * (h_tot ** 1.3) * (1.0 + 2.5 * pga)) * 1000.0
        self.lbl_deflection.setText(f"Crest Defl:     {disp_mm:4.1f} mm")
        self.adjustSize()

    def apply_theme(self, theme_mode: ThemeMode | str):
        is_light = ThemeMode(theme_mode) == ThemeMode.LIGHT
        bg = "rgba(248, 250, 252, 0.94)" if is_light else "rgba(15, 23, 42, 0.90)"
        border = "#cbd5e1" if is_light else "#334155"
        text = "#0f172a" if is_light else "#f8fafc"
        btn_bg = "#e2e8f0" if is_light else "#1e293b"
        self.setStyleSheet(f"""
            StabilityHUDOverlay {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text};
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 3px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {border};
            }}
        """)


class FloatingQuickCameraBar(QFrame):
    """
    Tier 1.3: Floating quick-action camera bar centered at the bottom of the canvas.
    Provides 1-click access to Isometric, Plan, Front, and Cross-Section views,
    fitting to extents, 3D label toggle, and snapshot capture.
    """

    def __init__(self, parent=None, parent_view=None):
        super().__init__(parent)
        self.parent_view = parent_view
        self._init_ui()
        self.apply_theme(ThemeMode.DARK)

    def _init_ui(self):
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(6, 4, 6, 4)
        h_layout.setSpacing(5)

        self.btn_iso = QPushButton("🏠 Iso")
        self.btn_plan = QPushButton("⬆ Plan")
        self.btn_front = QPushButton("➡ Front")
        self.btn_section = QPushButton("📐 Section")
        self.btn_fit = QPushButton("🔍 Fit")
        self.btn_labels = QPushButton("🏷 Labels")
        self.btn_snapshot = QPushButton("📷 4K")

        for btn in (
            self.btn_iso,
            self.btn_plan,
            self.btn_front,
            self.btn_section,
            self.btn_fit,
            self.btn_labels,
            self.btn_snapshot,
        ):
            btn.setFixedHeight(24)
            h_layout.addWidget(btn)

        if self.parent_view is not None:
            self.btn_iso.clicked.connect(lambda: self.parent_view.set_camera_preset("isometric"))
            self.btn_plan.clicked.connect(lambda: self.parent_view.set_camera_preset("plan"))
            self.btn_front.clicked.connect(lambda: self.parent_view.set_camera_preset("front"))
            self.btn_section.clicked.connect(lambda: self.parent_view.set_camera_preset("cross_section"))
            self.btn_fit.clicked.connect(self.parent_view.reset_camera)
            self.btn_labels.clicked.connect(self._toggle_labels)
            self.btn_snapshot.clicked.connect(self._on_snapshot_clicked)

    def _toggle_labels(self):
        if self.parent_view and hasattr(self.parent_view, "chk_labels"):
            self.parent_view.chk_labels.toggle()

    def _on_snapshot_clicked(self):
        if self.parent_view is not None:
            from datetime import datetime
            path = f"viewport_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            self.parent_view.save_high_res_snapshot(path)

    def apply_theme(self, theme_mode: ThemeMode | str):
        is_light = ThemeMode(theme_mode) == ThemeMode.LIGHT
        bg = "rgba(248, 250, 252, 0.92)" if is_light else "rgba(15, 23, 42, 0.88)"
        border = "#cbd5e1" if is_light else "#334155"
        text = "#0f172a" if is_light else "#f8fafc"
        btn_bg = "#e2e8f0" if is_light else "#1e293b"
        self.setStyleSheet(f"""
            FloatingQuickCameraBar {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 2px 7px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {border};
            }}
        """)


class ProbeInspectorOverlay(QFrame):
    """
    Tier 2.1: Probed Point Inspector Tooltip Card.
    Displays localized 3D world coordinates, structural component name,
    active scalar stress, and deflection at the user-clicked point.
    """

    def __init__(self, parent=None, on_close=None):
        super().__init__(parent)
        self.on_close = on_close
        self._init_ui()
        self.apply_theme(ThemeMode.DARK)
        self.hide()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        # Header
        h_row = QHBoxLayout()
        h_row.setContentsMargins(0, 0, 0, 0)
        lbl_title = QLabel("📍 POINT INSPECTOR")
        lbl_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #f43f5e;")
        h_row.addWidget(lbl_title)
        h_row.addStretch()

        btn_close = QPushButton("×")
        btn_close.setFixedSize(18, 18)
        btn_close.clicked.connect(self._handle_close)
        h_row.addWidget(btn_close)
        layout.addLayout(h_row)

        self.lbl_coords = QLabel("Point:      --")
        self.lbl_component = QLabel("Region:     --")
        self.lbl_scalar = QLabel("Stress:     --")
        self.lbl_diagnostic = QLabel("Threshold:  --")
        self.lbl_deflection = QLabel("Deflection: --")

        for lbl in (
            self.lbl_coords,
            self.lbl_component,
            self.lbl_scalar,
            self.lbl_diagnostic,
            self.lbl_deflection,
        ):
            lbl.setStyleSheet("font-family: monospace; font-size: 11px;")
            layout.addWidget(lbl)

    def _handle_close(self):
        self.hide()
        if self.on_close:
            self.on_close()

    def update_probe(self, info: dict, unit_system: UnitSystem = UnitSystem.SI):
        x, y, z = info["x"], info["y"], info["z"]
        u_len = unit_label("length", unit_system)
        x_d = from_si_value(x, "length", unit_system)
        y_d = from_si_value(y, "length", unit_system)
        z_d = from_si_value(z, "length", unit_system)

        self.lbl_coords.setText(f"Coords:     X:{x_d:.2f}{u_len}, Y:{y_d:.2f}{u_len}, Z:{z_d:.2f}{u_len}")
        self.lbl_component.setText(f"Region:     {info.get('component', 'Structure')}")

        scalar_name = info.get("scalar_name", "Stress")
        scalar_val = info.get("scalar_value", 0.0)
        self.lbl_scalar.setText(f"{scalar_name}: {scalar_val:.2f}")

        diag = info.get("diagnostic", "[EVALUATED]")
        self.lbl_diagnostic.setText(f"Status:     {diag}")

        defl_mm = info.get("deflection_mm", 0.0)
        self.lbl_deflection.setText(f"Deflection: {defl_mm:.1f} mm")
        self.adjustSize()
        self.show()

    def apply_theme(self, theme_mode: ThemeMode | str):
        is_light = ThemeMode(theme_mode) == ThemeMode.LIGHT
        bg = "rgba(248, 250, 252, 0.94)" if is_light else "rgba(15, 23, 42, 0.90)"
        border = "#cbd5e1" if is_light else "#334155"
        text = "#0f172a" if is_light else "#f8fafc"
        btn_bg = "#e2e8f0" if is_light else "#1e293b"
        self.setStyleSheet(f"""
            ProbeInspectorOverlay {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text};
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 3px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {border};
            }}
        """)


class RetainingWall3DView(QWidget):
    """
    Advanced 3D Scientific Viewport widget hosting the PyVista QtInteractor.
    """

    viewUpdated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Sleek Viewport Toolbar / Inspection Bar in responsive horizontal scroll area
        self.control_bar = self._create_control_bar()
        self.control_scroll = QScrollArea(self)
        self.control_scroll.setWidget(self.control_bar)
        self.control_scroll.setWidgetResizable(True)
        self.control_scroll.setFixedHeight(38)
        self.control_scroll.setFrameShape(QFrame.NoFrame)
        self.control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.control_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.control_scroll.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.control_scroll)

        # 2. PyVista QtInteractor Canvas
        self.plotter = QtInteractor(self)
        layout.addWidget(self.plotter.interactor)

        # Overlays: HUD, Quick Camera Bar, and Probe Inspector
        self.hud_card = StabilityHUDOverlay(self.plotter.interactor)
        self.quick_camera_bar = FloatingQuickCameraBar(self.plotter.interactor, parent_view=self)
        self.probe_card = ProbeInspectorOverlay(self.plotter.interactor, on_close=self.clear_probe)

        # 3. Viewport Scene Setup
        self._init_viewport_scene()

        # 4. Actor Handles for Safe Lifecycle Management
        self.wall_actor = None
        self.outline_actor = None
        self.multi_strut_actor = None
        self.strut_actor = None
        self.backfill_actor = None
        self.foundation_actor = None
        self.water_actor = None
        self.wedge_actor = None
        self.contact_vector_actor = None
        self.bearing_vector_actor = None
        self.continuum_actor = None
        self.continuum_soil_actor = None
        self.surcharge_actor = None
        self.surcharge_super_actor = None
        self.terrain_actor = None
        self.terrain_contour_actor = None
        self.labels_actor = None
        self.probe_marker_actor = None
        self.fbd_actor = None
        self.fbd_label_actor = None
        self.fbd_data: Optional[dict] = None
        self.dim_actor = None
        self.dim_label_actor = None
        self.dim_data: Optional[dict] = None

        # 5. Cached State Models & Display Properties
        self.current_wall_opacity: float = 1.0
        self.current_explode_factor: float = 0.0
        self.wall_mode: WallSystemMode = WallSystemMode.CANTILEVER
        self.geom: Optional[RetainingWallGeometry] = None
        self.soil: Optional[SoilProperties] = None
        self.seismic: Optional[SeismicParams] = None
        self.results: Optional[AnalysisResults] = None
        self.multi_strut_model: Optional[MultiStrutPiledWallModel] = None
        self.num_bays: int = 3
        self.arching_result: Optional[ShellArchingResult] = None
        self.arch_spec: Optional[ArchitecturalWallSpec] = None
        self.arch_summary: Optional[ArchWallAnalysisSummary] = None
        self.surcharge_params: Optional[AdjacentSurchargeParams] = None
        self.terrain_raster: Optional[TerrainRaster] = None
        self.show_terrain: bool = True
        self.active_wall_mesh: Optional[pv.UnstructuredGrid] = None
        self.active_backfill_mesh: Optional[pv.DataSet] = None
        self.active_foundation_mesh: Optional[pv.DataSet] = None
        self.active_wedge_mesh: Optional[pv.DataSet] = None
        self.continuum_result = None
        self.continuum_step_idx: int = -1
        self.slide_disp: float = 0.0
        self.ripple_phase: float = 0.0
        self.unit_system: UnitSystem = UnitSystem.SI
        self.theme_mode: ThemeMode = ThemeMode.DARK

    def set_unit_system(self, unit_system: UnitSystem | str) -> None:
        """Switches 3D scalar bar titles and display units between SI and Imperial."""
        self.unit_system = UnitSystem(unit_system)
        self.refresh()

    def _prepare_display_scalars(
        self, mesh: pv.DataSet, eff_scalar: str, base_title: str, kind: str
    ) -> Tuple[str, str, float, float]:
        """Returns `(display_scalar_key, bar_title, c_min, c_max)` in active display units."""
        arr = np.asarray(mesh.point_data.get(eff_scalar, [0.0]), dtype=np.float32)
        if self.unit_system == UnitSystem.SI or kind in ("", "ratio"):
            disp_key = eff_scalar
            title_str = f"{base_title} ({unit_label(kind, self.unit_system)})" if kind else base_title
        else:
            disp_key = f"__disp_{eff_scalar}"
            factor = from_si_value(1.0, kind, self.unit_system)
            mesh.point_data[disp_key] = (arr * factor).astype(np.float32)
            arr = mesh.point_data[disp_key]
            title_str = f"{base_title} ({unit_label(kind, self.unit_system)})"
        c_min = float(np.nanmin(arr)) if len(arr) > 0 else 0.0
        c_max = float(np.nanmax(arr)) if len(arr) > 0 else 1.0
        if not np.isfinite(c_min):
            c_min = 0.0
        if not np.isfinite(c_max) or c_max <= c_min:
            c_max = c_min + 1.0
        return disp_key, title_str, c_min, c_max

    def _control_bar_qss(self, theme_dict: dict) -> str:
        return f"""
            QFrame {{
                background-color: {theme_dict["surface_dark"]};
                border-bottom: 1px solid {theme_dict["border"]};
                padding: 4px 6px;
            }}
            QLabel {{
                color: {theme_dict["text_secondary"]};
                font-size: 11px;
                font-weight: 500;
            }}
            QComboBox, QDoubleSpinBox {{
                background-color: {theme_dict["surface_elevated"]};
                color: {theme_dict["text_primary"]};
                border: 1px solid {theme_dict["border"]};
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 11px;
                min-height: 20px;
            }}
            QCheckBox {{
                color: {theme_dict["text_primary"]};
                font-size: 11px;
                spacing: 4px;
            }}
            QPushButton {{
                background-color: {theme_dict["surface_elevated"]};
                color: {theme_dict["text_primary"]};
                border: 1px solid {theme_dict["border"]};
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme_dict["border"]};
            }}
        """

    def _create_control_bar(self) -> QWidget:
        """Constructs an integrated inspection and visualization control bar."""
        bar = QFrame(self)
        bar.setStyleSheet(self._control_bar_qss(THEME_DARK))

        h_layout = QHBoxLayout(bar)
        h_layout.setContentsMargins(6, 2, 6, 2)
        h_layout.setSpacing(8)

        # Field Selector
        h_layout.addWidget(QLabel("Scalar:"))
        self.combo_scalar = QComboBox()
        self.combo_scalar.addItem("Realistic Materials (CAD)", "RealisticMaterials")
        self.combo_scalar.addItem("Tensile Stress", "TensileStress_MPa")
        self.combo_scalar.addItem("Von Mises Stress", "VonMises_MPa")
        self.combo_scalar.addItem("Pore Pressure", "PorePressure_kPa")
        self.combo_scalar.addItem("Arching Stress", "ArchingStress_kPa")
        self.combo_scalar.addItem("Element Type", "Element_Type")
        self.combo_scalar.addItem("Backface Earth Pressure (3D FEA)", "WallNormalStress_kPa")
        self.combo_scalar.addItem("Excess Pore Pressure ru (3D FEA)", "ExcessPorePressureRatio_ru")
        self.combo_scalar.addItem("Octahedral Shear Strain (3D FEA)", "OctahedralShearStrain")
        self.combo_scalar.addItem("Safety Unity Ratio (UR)", "SafetyUnityRatio")
        self.combo_scalar.currentIndexChanged.connect(self.refresh)
        h_layout.addWidget(self.combo_scalar)

        # Colormap Selector
        h_layout.addWidget(QLabel("Colormap:"))
        self.combo_cmap = QComboBox()
        self.combo_cmap.addItems(["plasma", "viridis", "coolwarm", "magma"])
        self.combo_cmap.currentIndexChanged.connect(self.refresh)
        h_layout.addWidget(self.combo_cmap)

        # Deformation Warp Factor Slider / SpinBox
        h_layout.addWidget(QLabel("Warp:"))
        self.spin_warp = QDoubleSpinBox()
        self.spin_warp.setRange(0.0, 100.0)
        self.spin_warp.setSingleStep(0.5)
        self.spin_warp.setValue(1.0)
        self.spin_warp.setSuffix("×")
        self.spin_warp.valueChanged.connect(self.refresh)
        h_layout.addWidget(self.spin_warp)

        # Structure Opacity / X-Ray Mode Slider
        h_layout.addWidget(QLabel("Opacity:"))
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(10, 100)
        self.slider_opacity.setValue(100)
        self.slider_opacity.setMaximumWidth(70)
        self.slider_opacity.setToolTip("Structure Opacity & X-Ray Mode (10% to 100%)")
        self.slider_opacity.valueChanged.connect(self._on_opacity_changed)
        h_layout.addWidget(self.slider_opacity)

        # Feature Toggles
        self.chk_soil = QCheckBox("Soil")
        self.chk_soil.setChecked(True)
        self.chk_soil.toggled.connect(self.refresh)
        h_layout.addWidget(self.chk_soil)

        self.chk_water = QCheckBox("Water")
        self.chk_water.setChecked(True)
        self.chk_water.toggled.connect(self.refresh)
        h_layout.addWidget(self.chk_water)

        self.chk_wedge = QCheckBox("Failure Wedge")
        self.chk_wedge.setChecked(False)
        self.chk_wedge.toggled.connect(self.refresh)
        h_layout.addWidget(self.chk_wedge)

        self.chk_vectors = QCheckBox("Pressure Glyphs")
        self.chk_vectors.setChecked(False)
        self.chk_vectors.toggled.connect(self.refresh)
        h_layout.addWidget(self.chk_vectors)

        self.chk_piles = QCheckBox("Piles")
        self.chk_piles.setChecked(True)
        self.chk_piles.toggled.connect(self.refresh)
        h_layout.addWidget(self.chk_piles)

        self.chk_struts = QCheckBox("Struts")
        self.chk_struts.setChecked(True)
        self.chk_struts.toggled.connect(self.refresh)
        h_layout.addWidget(self.chk_struts)

        # Tier 1 Overlays: HUD and 3D Labels
        self.chk_hud = QCheckBox("HUD")
        self.chk_hud.setChecked(True)
        self.chk_hud.toggled.connect(
            lambda checked: self.hud_card.setVisible(checked) if hasattr(self, "hud_card") else None
        )
        h_layout.addWidget(self.chk_hud)

        self.chk_labels = QCheckBox("Labels")
        self.chk_labels.setChecked(False)
        self.chk_labels.toggled.connect(self.refresh)
        h_layout.addWidget(self.chk_labels)

        # Tier 3 Advanced Mechanics: FBD, Dims, and Exploded Assembly
        self.chk_fbd = QCheckBox("FBD")
        self.chk_fbd.setChecked(False)
        self.chk_fbd.setToolTip("3D Free-Body Diagram Resultant Forces (P_ae, W_c, W_s, R_v, F_r)")
        self.chk_fbd.toggled.connect(self.refresh)
        h_layout.addWidget(self.chk_fbd)

        self.chk_dims = QCheckBox("Dims")
        self.chk_dims.setChecked(False)
        self.chk_dims.setToolTip("3D CAD Dimension Rulers & Geometry Callouts (H, B)")
        self.chk_dims.toggled.connect(self.refresh)
        h_layout.addWidget(self.chk_dims)

        h_layout.addWidget(QLabel("Explode:"))
        self.slider_explode = QSlider(Qt.Horizontal)
        self.slider_explode.setRange(0, 100)
        self.slider_explode.setValue(0)
        self.slider_explode.setMaximumWidth(70)
        self.slider_explode.setToolTip("Exploded Assembly Disassembly (0% to 100%)")
        self.slider_explode.valueChanged.connect(self._on_explode_changed)
        h_layout.addWidget(self.slider_explode)

        # Slicing Plane Tool
        h_layout.addWidget(QLabel("Slice:"))
        self.combo_slice = QComboBox()
        self.combo_slice.addItem("Off", "none")
        self.combo_slice.addItem("X Cut", "x")
        self.combo_slice.addItem("Y Cut", "y")
        self.combo_slice.addItem("Z Cut", "z")
        self.combo_slice.currentIndexChanged.connect(self.refresh)
        h_layout.addWidget(self.combo_slice)

        self.slider_slice = QSlider(Qt.Horizontal)
        self.slider_slice.setRange(0, 100)
        self.slider_slice.setValue(50)
        self.slider_slice.setMaximumWidth(90)
        self.slider_slice.setToolTip("Slice Position (0% to 100%)")
        self.slider_slice.valueChanged.connect(self.refresh)
        h_layout.addWidget(self.slider_slice)

        h_layout.addStretch()

        # Camera Preset Selector & Reset Camera
        h_layout.addWidget(QLabel("Cam:"))
        self.combo_camera = QComboBox()
        self.combo_camera.addItem("Isometric", "isometric")
        self.combo_camera.addItem("Plan", "plan")
        self.combo_camera.addItem("Front Elevation", "front")
        self.combo_camera.addItem("Cross-Section", "cross_section")
        self.combo_camera.currentIndexChanged.connect(
            lambda: self.set_camera_preset(str(self.combo_camera.currentData()))
        )
        h_layout.addWidget(self.combo_camera)

        btn_reset = QPushButton("Reset Camera")
        btn_reset.clicked.connect(self.reset_camera)
        h_layout.addWidget(btn_reset)

        return bar

    def _init_viewport_scene(self):
        """Sets up background color, lighting, camera, and coordinate axes."""
        self.plotter.set_background(VIEWPORT_COLORS["background"])
        self.plotter.add_axes(interactive=False, line_width=2)
        self.plotter.enable_anti_aliasing("fxaa")
        try:
            self.plotter.enable_eye_dome_lighting()
        except Exception:
            pass
        self.plotter.show_grid(
            color=VIEWPORT_COLORS["grid"],
            grid=False,
            location="outer",
            ticks="outside",
        )
        try:
            self.plotter.enable_point_picking(
                callback=self._on_mesh_probed,
                show_point=False,
                show_message=False,
            )
        except Exception:
            pass

    def reset_camera(self):
        """Restores isometric camera view framing the structure."""
        self.set_camera_preset("isometric")

    def set_theme_mode(self, theme_mode: ThemeMode | str) -> None:
        """Switches 3D viewport background, control bar QSS, and linework between Dark Engineering and Light Studio."""
        self.theme_mode = ThemeMode(theme_mode)
        is_light = self.theme_mode == ThemeMode.LIGHT
        bg_hex = "#f8fafc" if is_light else VIEWPORT_COLORS["background"]
        self.plotter.set_background(bg_hex)
        if hasattr(self, "control_bar") and self.control_bar is not None:
            self.control_bar.setStyleSheet(self._control_bar_qss(THEMES[self.theme_mode]))
        if hasattr(self, "hud_card") and self.hud_card is not None:
            self.hud_card.apply_theme(self.theme_mode)
        if hasattr(self, "quick_camera_bar") and self.quick_camera_bar is not None:
            self.quick_camera_bar.apply_theme(self.theme_mode)
        if hasattr(self, "probe_card") and self.probe_card is not None:
            self.probe_card.apply_theme(self.theme_mode)
        self.refresh()

    def set_camera_preset(self, preset: str) -> None:
        """Applies named architectural camera projection ('isometric', 'plan', 'front', 'cross_section')."""
        key = str(preset).lower().strip()
        if hasattr(self, "combo_camera"):
            idx = self.combo_camera.findData(key)
            if idx >= 0 and self.combo_camera.currentIndex() != idx:
                self.combo_camera.blockSignals(True)
                self.combo_camera.setCurrentIndex(idx)
                self.combo_camera.blockSignals(False)

        if key == "plan":
            self.plotter.view_xz()
            self.plotter.camera.elevation = 90.0
            self.plotter.camera.azimuth = 0.0
        elif key in ("front", "front_elevation"):
            self.plotter.view_yz()
            self.plotter.camera.azimuth = 180.0
            self.plotter.camera.elevation = 0.0
        elif key in ("cross_section", "section"):
            self.plotter.view_xy()
        else:
            self.plotter.view_isometric()

        self.plotter.reset_camera()
        self.plotter.render()

    def save_high_res_snapshot(
        self, filepath: str, width: int = 3840, height: int = 2160
    ) -> str:
        """Exports a high-resolution PNG render (defaults to 4K 3840x2160)."""
        self.plotter.render()
        self.plotter.screenshot(filepath)

        try:
            from PIL import Image
            with Image.open(filepath) as img:
                if img.size != (int(width), int(height)):
                    resized = img.resize((int(width), int(height)), Image.Resampling.LANCZOS)
                    resized.save(filepath)
        except Exception:
            pass
        return filepath

    def set_terrain(
        self, terrain: Optional[TerrainRaster], show_terrain: bool = True
    ) -> None:
        """Caches an imported TerrainRaster and refreshes the draped 3D scene."""
        self.terrain_raster = terrain
        self.show_terrain = bool(show_terrain)
        self.refresh()

    def _render_terrain_overlay(self) -> None:
        """Aligns DEM terrain into Viewport3D space and renders surface + elevation contours."""
        self._remove_actor_attr("terrain_actor")
        self._remove_actor_attr("terrain_contour_actor")
        if self.terrain_raster is None or not self.show_terrain:
            return

        # Crop/align DEM grid cleanly around retaining wall origin
        raw_grid = self.terrain_raster.to_pyvista_mesh()
        pts = np.asarray(raw_grid.points, dtype=np.float64).copy()
        xmin, ymin, xmax, ymax = self.terrain_raster.bounds
        x_mid = 0.5 * (xmin + xmax)
        y_mid = 0.5 * (ymin + ymax)
        z_anchor = self.terrain_raster.elevation_at(x_mid, y_mid)

        # Shift into Viewport3D coordinates: X=across-slope, Y=elevation, Z=along-wall
        x_off = (self.geom.toe_length + self.geom.stem_thickness_base) if self.geom else 1.5
        z_off = (0.5 * self.geom.wall_length) if self.geom else 5.0
        span_scale = min(1.0, 28.0 / max(1.0, xmax - xmin))

        vp_pts = np.empty_like(pts)
        vp_pts[:, 0] = x_off + (pts[:, 0] - x_mid) * span_scale + 4.0
        vp_pts[:, 1] = (pts[:, 2] - z_anchor) * span_scale
        vp_pts[:, 2] = z_off + (pts[:, 1] - y_mid) * span_scale

        aligned = raw_grid.copy()
        aligned.points = vp_pts
        aligned.point_data["Elevation_m"] = aligned.point_data["Elevation"]

        self.terrain_actor = self.plotter.add_mesh(
            aligned,
            scalars="Elevation_m",
            cmap="terrain",
            opacity=0.45,
            show_scalar_bar=False,
            show_edges=False,
        )
        try:
            contours = aligned.contour(isosurfaces=7, scalars="Elevation_m")
            if contours is not None and contours.n_points > 0:
                line_color = "#1e293b" if self.theme_mode == ThemeMode.LIGHT else "#e2e8f0"
                self.terrain_contour_actor = self.plotter.add_mesh(
                    contours,
                    color=line_color,
                    line_width=1.4,
                )
        except Exception:
            pass

    def _render_component_labels(self) -> None:
        """Tier 1.2: Renders toggleable 3D callouts and anatomical leader lines."""
        self._remove_actor_attr("labels_actor")
        if not hasattr(self, "chk_labels") or not self.chk_labels.isChecked():
            return

        pts_list = []
        labels_list = []

        if self.wall_mode == WallSystemMode.CANTILEVER and self.geom is not None:
            g = self.geom
            z_mid = 0.5 * g.wall_length
            x_stem_cen = g.toe_length + 0.5 * g.stem_thickness_base

            # 1. Wall Crest
            pts_list.append([x_stem_cen, g.total_height, z_mid])
            labels_list.append(f"Wall Crest (y={g.total_height:.2f}m)")

            # 2. Critical Stem Base Junction
            pts_list.append([x_stem_cen, g.footing_thickness, z_mid])
            labels_list.append("Stem Base (M_max)")

            # 3. Footing Toe
            pts_list.append([0.5 * g.toe_length, 0.5 * g.footing_thickness, z_mid])
            labels_list.append("Footing Toe")

            # 4. Footing Heel
            x_heel_mid = g.toe_length + g.stem_thickness_base + 0.5 * g.heel_length
            pts_list.append([x_heel_mid, 0.5 * g.footing_thickness, z_mid])
            labels_list.append("Footing Heel")

            # 5. Retained Backfill
            x_bf = g.toe_length + g.stem_thickness_base + 0.65 * g.heel_length
            pts_list.append([x_bf, g.footing_thickness + 0.5 * g.stem_height, z_mid])
            labels_list.append("Retained Backfill")

            # 6. Water Table
            if self.seismic and self.seismic.water_table_depth < g.total_height:
                y_wat = max(0.0, g.total_height - self.seismic.water_table_depth)
                pts_list.append([x_bf, y_wat, z_mid])
                labels_list.append(f"Water Table (-{self.seismic.water_table_depth:.1f}m)")

            # 7. Failure Wedge
            if hasattr(self, "chk_wedge") and self.chk_wedge.isChecked() and self.soil:
                theta_deg = 45.0 + 0.5 * self.soil.friction_angle
                x_wedge = g.toe_length + g.stem_thickness_base + 0.3 * g.stem_height
                y_wedge = g.footing_thickness + 0.4 * g.stem_height
                pts_list.append([x_wedge, y_wedge, z_mid])
                labels_list.append(f"Active Wedge (θ={theta_deg:.1f}°)")

        elif self.wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL and self.multi_strut_model is not None:
            m = self.multi_strut_model
            h = float(m.shell.panel_height)
            pts_list.append([0.0, h, m.pier_pile.pier_depth])
            labels_list.append(f"Shell Crest (H={h:.2f}m)")
            pts_list.append([0.0, 0.5 * h, 0.0])
            labels_list.append("Soldier Pier")
            pts_list.append([0.0, -0.5 * m.pier_pile.pile_length, 0.0])
            labels_list.append("Bored Pile")

        elif self.wall_mode == WallSystemMode.ARCHITECTURAL and self.arch_spec is not None:
            spec = self.arch_spec
            pts_list.append([0.0, spec.total_height, 0.5 * spec.wall_length])
            labels_list.append(f"Arch Crest ({spec.morphology.name})")

        if pts_list:
            pts_arr = np.array(pts_list, dtype=np.float32)
            try:
                is_light = self.theme_mode == ThemeMode.LIGHT
                self.labels_actor = self.plotter.add_point_labels(
                    pts_arr,
                    labels_list,
                    font_size=10,
                    text_color="#0f172a" if is_light else "#ffffff",
                    point_color="#38bdf8",
                    point_size=7,
                    render_points_as_spheres=True,
                    always_visible=True,
                    shape="rounded_rect",
                    shape_color="#f8fafc" if is_light else "#0f172a",
                    shape_opacity=0.88,
                )
            except Exception:
                pass

    def _render_free_body_diagram(
        self,
        current_geom: Optional[RetainingWallGeometry],
        current_soil: Optional[SoilProperties],
        current_seismic: Optional[SeismicParams],
        current_results: Optional[AnalysisResults],
    ) -> None:
        """Tier 3.1: Free-Body Diagram resultant vectors (P_ae, W_c, W_s, R_v, F_r) and force equilibrium."""
        self._remove_actor_attr("fbd_actor")
        self._remove_actor_attr("fbd_label_actor")
        if not hasattr(self, "chk_fbd") or not self.chk_fbd.isChecked():
            self.fbd_data = None
            return

        if self.wall_mode != WallSystemMode.CANTILEVER or current_geom is None or current_results is None:
            return

        g = current_geom
        s = current_soil if current_soil is not None else SoilProperties()
        r = current_results
        z_mid = 0.5 * g.wall_length
        b_width = g.base_width

        # 1. Active Earth Thrust Resultant (P_ae)
        p_ae = float(r.total_thrust)
        delta_rad = np.radians(min(20.0, float(s.friction_angle) * (2.0 / 3.0)))
        p_ae_x = p_ae * np.cos(delta_rad)
        p_ae_y = p_ae * np.sin(delta_rad)

        # 2. Concrete Dead Weight (W_c)
        gamma_c = 24.0  # kN/m^3
        a_stem = 0.5 * (g.stem_thickness_base + g.stem_thickness_top) * g.stem_height
        a_footing = b_width * g.footing_thickness
        w_c = (a_stem + a_footing) * gamma_c
        x_footing = 0.5 * b_width
        x_stem = g.toe_length + 0.5 * g.stem_thickness_base
        total_a = a_stem + a_footing
        x_c = (a_footing * x_footing + a_stem * x_stem) / max(1e-4, total_a)
        y_c = (
            a_footing * (0.5 * g.footing_thickness)
            + a_stem * (g.footing_thickness + 0.45 * g.stem_height)
        ) / max(1e-4, total_a)

        # 3. Soil Dead Weight over Heel (W_s)
        gamma_s = float(s.unit_weight)
        a_s = g.heel_length * g.stem_height
        w_s = a_s * gamma_s
        x_s = g.toe_length + g.stem_thickness_base + 0.5 * g.heel_length
        y_s = g.footing_thickness + 0.5 * g.stem_height

        # 4. Vertical Base Reaction (R_v)
        r_v = w_c + w_s + p_ae_y
        x_r = float(np.clip(0.4 * b_width, 0.1 * b_width, 0.85 * b_width))

        # 5. Base Sliding Friction Resistance (F_r)
        tan_delta_b = np.tan(np.radians(float(s.friction_angle) * (2.0 / 3.0)))
        f_r = r_v * tan_delta_b
        if f_r <= 0.0:
            f_r = float(r.fs_sliding) * p_ae_x

        self.fbd_data = {
            "P_ae": p_ae,
            "P_ae_x": p_ae_x,
            "P_ae_y": p_ae_y,
            "W_c": w_c,
            "W_s": w_s,
            "R_v": r_v,
            "F_r": f_r,
        }

        # Visual arrows scaling
        f_ref = max(p_ae, w_c, w_s, r_v, 1.0)
        def calc_scale(val):
            return float(np.clip(1.2 + 1.8 * (val / f_ref), 1.2, 3.2))

        # Arrow 1: Active Thrust P_ae (acting at virtual backface, pointing down-left)
        p_target = np.array([b_width, g.footing_thickness + (1.0 / 3.0) * g.stem_height, z_mid])
        l_p = calc_scale(p_ae)
        dir_p = np.array([-np.cos(delta_rad), -np.sin(delta_rad), 0.0])
        dir_p = dir_p / max(1e-4, np.linalg.norm(dir_p))
        start_p = p_target - l_p * dir_p
        arrow_p = pv.Arrow(start=tuple(start_p), direction=tuple(dir_p), scale=l_p, tip_length=0.25, tip_radius=0.12, shaft_radius=0.05)

        # Arrow 2: Concrete Weight W_c (acting at wall centroid, pointing down)
        l_wc = calc_scale(w_c)
        start_wc = (x_c, y_c + 0.5 * l_wc, z_mid)
        arrow_wc = pv.Arrow(start=start_wc, direction=(0.0, -1.0, 0.0), scale=l_wc, tip_length=0.25, tip_radius=0.12, shaft_radius=0.05)

        # Arrow 3: Soil Weight W_s (acting over heel, pointing down)
        l_ws = calc_scale(w_s)
        start_ws = (x_s, y_s + 0.5 * l_ws, z_mid)
        arrow_ws = pv.Arrow(start=start_ws, direction=(0.0, -1.0, 0.0), scale=l_ws, tip_length=0.25, tip_radius=0.12, shaft_radius=0.05)

        # Arrow 4: Base Reaction R_v (acting at footing base, pointing up)
        l_rv = calc_scale(r_v)
        start_rv = (x_r, -l_rv, z_mid)
        arrow_rv = pv.Arrow(start=start_rv, direction=(0.0, 1.0, 0.0), scale=l_rv, tip_length=0.25, tip_radius=0.12, shaft_radius=0.05)

        # Arrow 5: Friction Resistance F_r (acting at footing base, pointing right +X)
        l_fr = calc_scale(f_r)
        start_fr = (x_r - l_fr, 0.0, z_mid)
        arrow_fr = pv.Arrow(start=start_fr, direction=(1.0, 0.0, 0.0), scale=l_fr, tip_length=0.25, tip_radius=0.12, shaft_radius=0.05)

        combined_arrows = arrow_p + arrow_wc + arrow_ws + arrow_rv + arrow_fr
        self.fbd_actor = self.plotter.add_mesh(
            combined_arrows,
            color="#f59e0b",
            show_edges=False,
            smooth_shading=True,
        )

        pts = np.array([
            start_p,
            start_wc,
            start_ws,
            start_rv,
            start_fr,
        ], dtype=np.float32)
        labels = [
            f"P_ae = {p_ae:.1f} kN/m",
            f"W_c = {w_c:.1f} kN/m",
            f"W_s = {w_s:.1f} kN/m",
            f"R_v = {r_v:.1f} kN/m",
            f"F_r = {f_r:.1f} kN/m",
        ]
        try:
            is_light = self.theme_mode == ThemeMode.LIGHT
            self.fbd_label_actor = self.plotter.add_point_labels(
                pts,
                labels,
                font_size=10,
                text_color="#0f172a" if is_light else "#ffffff",
                point_color="#f59e0b",
                point_size=5,
                shape="rounded_rect",
                shape_color="#fef3c7" if is_light else "#78350f",
                shape_opacity=0.85,
                always_visible=True,
            )
        except Exception:
            pass

    def _render_dimension_rulers(self, current_geom: Optional[RetainingWallGeometry]) -> None:
        """Tier 3.3: 3D CAD Dimension Rulers & Annotations (Total Height H, Base Width B, Toe/Heel)."""
        self._remove_actor_attr("dim_actor")
        self._remove_actor_attr("dim_label_actor")
        if not hasattr(self, "chk_dims") or not self.chk_dims.isChecked():
            self.dim_data = None
            return

        if self.wall_mode != WallSystemMode.CANTILEVER or current_geom is None:
            return

        g = current_geom
        z_mid = 0.5 * g.wall_length
        h = float(g.total_height)
        b = float(g.base_width)
        b_toe = float(g.toe_length)
        b_heel = float(g.heel_length)

        self.dim_data = {
            "total_height": h,
            "base_width": b,
            "toe_length": b_toe,
            "heel_length": b_heel,
        }

        # 1. Height dimension line (offset left in front of toe: x = -0.6)
        x_dim_h = -0.6
        h_line = pv.Line((x_dim_h, 0.0, z_mid), (x_dim_h, h, z_mid))
        h_tick_b = pv.Line((x_dim_h - 0.25, 0.0, z_mid), (x_dim_h + 0.25, 0.0, z_mid))
        h_tick_t = pv.Line((x_dim_h - 0.25, h, z_mid), (x_dim_h + 0.25, h, z_mid))
        h_wit_b = pv.Line((x_dim_h, 0.0, z_mid), (0.0, 0.0, z_mid))
        h_wit_t = pv.Line((x_dim_h, h, z_mid), (g.toe_length, h, z_mid))

        # 2. Base width dimension line (offset below footing: y = -0.5)
        y_dim_b = -0.5
        b_line = pv.Line((0.0, y_dim_b, z_mid), (b, y_dim_b, z_mid))
        b_tick_l = pv.Line((0.0, y_dim_b - 0.25, z_mid), (0.0, y_dim_b + 0.25, z_mid))
        b_tick_r = pv.Line((b, y_dim_b - 0.25, z_mid), (b, y_dim_b + 0.25, z_mid))
        b_wit_l = pv.Line((0.0, 0.0, z_mid), (0.0, y_dim_b, z_mid))
        b_wit_r = pv.Line((b, 0.0, z_mid), (b, y_dim_b, z_mid))

        combined_lines = (
            h_line + h_tick_b + h_tick_t + h_wit_b + h_wit_t
            + b_line + b_tick_l + b_tick_r + b_wit_l + b_wit_r
        )

        self.dim_actor = self.plotter.add_mesh(
            combined_lines,
            color="#38bdf8",
            line_width=2.5,
            show_edges=False,
        )

        pts = np.array([
            [x_dim_h - 0.4, 0.5 * h, z_mid],
            [0.5 * b, y_dim_b - 0.4, z_mid],
        ], dtype=np.float32)
        labels = [
            f"H = {h:.2f} m",
            f"B = {b:.2f} m",
        ]
        try:
            is_light = self.theme_mode == ThemeMode.LIGHT
            self.dim_label_actor = self.plotter.add_point_labels(
                pts,
                labels,
                font_size=10,
                text_color="#0f172a" if is_light else "#ffffff",
                point_color="#38bdf8",
                point_size=5,
                shape="rounded_rect",
                shape_color="#e0f2fe" if is_light else "#0369a1",
                shape_opacity=0.85,
                always_visible=True,
            )
        except Exception:
            pass

    def _remove_actor_attr(self, attr_name: str):
        actor = getattr(self, attr_name, None)
        if actor is not None:
            if isinstance(actor, (list, tuple)):
                for a in actor:
                    try:
                        self.plotter.remove_actor(a)
                    except Exception:
                        pass
            else:
                try:
                    self.plotter.remove_actor(actor)
                except Exception:
                    pass
            setattr(self, attr_name, None)

    def clear_actors(self):
        """Explicitly removes all active mesh actors to prevent VTK memory leaks."""
        actor_names = [
            "wall_actor",
            "outline_actor",
            "multi_strut_actor",
            "strut_actor",
            "backfill_actor",
            "foundation_actor",
            "water_actor",
            "wedge_actor",
            "contact_vector_actor",
            "bearing_vector_actor",
            "continuum_actor",
            "continuum_soil_actor",
            "surcharge_actor",
            "surcharge_super_actor",
            "terrain_actor",
            "terrain_contour_actor",
            "labels_actor",
            "probe_marker_actor",
            "fbd_actor",
            "fbd_label_actor",
            "dim_actor",
            "dim_label_actor",
        ]
        for name in actor_names:
            self._remove_actor_attr(name)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_overlays()

    def _reposition_overlays(self):
        if hasattr(self, "hud_card") and self.hud_card is not None:
            self.hud_card.move(14, 14)
            self.hud_card.raise_()

        if hasattr(self, "probe_card") and self.probe_card is not None and self.probe_card.isVisible():
            cw = self.plotter.interactor.width()
            bw = self.probe_card.sizeHint().width()
            self.probe_card.move(max(10, cw - bw - 14), 14)
            self.probe_card.raise_()

        if hasattr(self, "quick_camera_bar") and self.quick_camera_bar is not None:
            cw = self.plotter.interactor.width()
            ch = self.plotter.interactor.height()
            bw = self.quick_camera_bar.sizeHint().width()
            bh = self.quick_camera_bar.sizeHint().height()
            x = max(10, (cw - bw) // 2)
            y = max(10, ch - bh - 14)
            self.quick_camera_bar.setGeometry(x, y, bw, bh)
            self.quick_camera_bar.raise_()

    def _on_opacity_changed(self, val: int) -> None:
        """Tier 2.2: Continuous X-Ray / transparency slider adjustment."""
        self.current_wall_opacity = val / 100.0
        if self.wall_actor is not None:
            try:
                self.wall_actor.GetProperty().SetOpacity(self.current_wall_opacity)
                self.plotter.render()
            except Exception:
                pass

    def _on_explode_changed(self, val: int) -> None:
        """Tier 3.2: Handles exploded assembly disassembly slider adjustments."""
        self.current_explode_factor = val / 100.0
        self.refresh()

    def probe_point(self, x: float, y: float, z: float) -> Optional[dict]:
        """Tier 2.1: Probes stress and displacement at world coordinates (x, y, z)."""
        self.clear_probe()

        component = "Cantilever Stem"
        if self.geom:
            g = self.geom
            if y < g.footing_thickness:
                if x < g.toe_length:
                    component = "Footing Toe Slab"
                elif x > (g.toe_length + g.stem_thickness_base):
                    component = "Footing Heel Slab"
                else:
                    component = "Footing Junction Base"
            else:
                stem_mid = g.toe_length + 0.5 * g.stem_thickness_base
                component = "Stem (Backface / Tension)" if x >= stem_mid else "Stem (Frontface / Compression)"

        # Scalar lookup
        eff_scalar = str(self.combo_scalar.currentData())
        scalar_val = 0.0
        defl_mm = 0.0

        if self.active_wall_mesh is not None and self.active_wall_mesh.n_points > 0:
            pts = self.active_wall_mesh.points
            dists = np.sum((pts - np.array([x, y, z])) ** 2, axis=1)
            closest_idx = int(np.argmin(dists))

            if eff_scalar in self.active_wall_mesh.point_data:
                scalar_val = float(self.active_wall_mesh.point_data[eff_scalar][closest_idx])
            elif "TensileStress_MPa" in self.active_wall_mesh.point_data:
                scalar_val = float(self.active_wall_mesh.point_data["TensileStress_MPa"][closest_idx])

            if "Deformation_m" in self.active_wall_mesh.point_data:
                defl_vec = self.active_wall_mesh.point_data["Deformation_m"][closest_idx]
                defl_mm = float(np.linalg.norm(defl_vec)) * 1000.0

        diagnostic = "Below Cracking Limit (≤ 2.80 MPa) [OK]" if scalar_val <= 2.80 else "Exceeds Cracking Limit (> 2.80 MPa) [CRACKED]"

        info = {
            "x": x,
            "y": y,
            "z": z,
            "component": component,
            "scalar_name": str(self.combo_scalar.currentText()),
            "scalar_value": scalar_val,
            "deflection_mm": defl_mm,
            "diagnostic": diagnostic,
        }

        # Place 3D glowing sphere probe marker
        try:
            marker_mesh = pv.Sphere(radius=0.10, center=(x, y, z))
            self.probe_marker_actor = self.plotter.add_mesh(
                marker_mesh,
                color="#f43f5e",
                emissive=True,
                show_edges=False,
            )
            self.plotter.render()
        except Exception:
            pass

        if hasattr(self, "probe_card") and self.probe_card is not None:
            self.probe_card.update_probe(info, self.unit_system)
            self._reposition_overlays()

        return info

    def clear_probe(self):
        """Clears 3D probe marker sphere and hides probe inspector card."""
        self._remove_actor_attr("probe_marker_actor")
        if hasattr(self, "probe_card") and self.probe_card is not None:
            self.probe_card.hide()
        if hasattr(self, "plotter") and self.plotter is not None:
            self.plotter.render()

    def _on_mesh_probed(self, point):
        """Internal callback invoked when clicking on the 3D mesh."""
        if point is not None and len(point) == 3:
            self.probe_point(float(point[0]), float(point[1]), float(point[2]))

    def closeEvent(self, event):
        self.clear_actors()
        if hasattr(self, "plotter") and self.plotter is not None:
            try:
                self.plotter.close()
            except Exception:
                pass
        super().closeEvent(event)

    def refresh(self):
        """Re-renders the scene using the currently cached model states and UI settings."""
        if self.continuum_result is not None:
            self.update_continuum_fea_scene(
                self.continuum_result,
                step_idx=self.continuum_step_idx,
            )
            return
        if (
            self.wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL
            and self.multi_strut_model is not None
        ):
            self.update_multi_strut_scene(
                model=self.multi_strut_model,
                soil=self.soil,
                seismic=self.seismic,
                num_bays=self.num_bays,
                arching_result=self.arching_result,
            )
            return

        if (
            self.wall_mode == WallSystemMode.ARCHITECTURAL
            and self.arch_spec is not None
        ):
            self.update_architectural_scene(
                spec=self.arch_spec,
                soil=self.soil,
                seismic=self.seismic,
                summary=self.arch_summary,
                surcharge=self.surcharge_params,
            )
            return

        if self.geom is None or self.results is None:
            return
        self.update_scene(
            geom=self.geom,
            soil=self.soil,
            seismic=self.seismic,
            results=self.results,
            slide_disp=self.slide_disp,
            ripple_phase=self.ripple_phase,
        )

    def update_scene(
        self,
        geom: Optional[RetainingWallGeometry] = None,
        soil: Optional[SoilProperties] = None,
        seismic: Optional[SeismicParams] = None,
        results: Optional[AnalysisResults] = None,
        warp_scale: Optional[float] = None,
        show_soil: Optional[bool] = None,
        show_water: Optional[bool] = None,
        show_wedge: Optional[bool] = None,
        show_vectors: Optional[bool] = None,
        show_fbd: Optional[bool] = None,
        show_dims: Optional[bool] = None,
        explode_factor: Optional[float] = None,
        scalar_name: Optional[str] = None,
        colormap: Optional[str] = None,
        slice_axis: Optional[str] = None,
        slice_pos: Optional[float] = None,
        slide_disp: Optional[float] = None,
        ripple_phase: Optional[float] = None,
        surcharge: Optional[AdjacentSurchargeParams] = None,
    ):
        """
        Recomputes meshes and refreshes the 3D scene in < 2ms with full actor lifecycle management.
        """
        # Cache or resolve states
        if geom is not None:
            self.geom = geom
        if soil is not None:
            self.soil = soil
        if seismic is not None:
            self.seismic = seismic
        if results is not None:
            self.results = results
        if slide_disp is not None:
            self.slide_disp = slide_disp
        if ripple_phase is not None:
            self.ripple_phase = ripple_phase
        if surcharge is not None:
            self.surcharge_params = surcharge

        if (
            self.wall_mode == WallSystemMode.ARCHITECTURAL
            and self.arch_spec is not None
        ):
            self.update_architectural_scene(
                spec=self.arch_spec,
                soil=self.soil,
                seismic=self.seismic,
                summary=self.arch_summary,
                surcharge=self.surcharge_params,
            )
            return

        if self.geom is None or self.results is None:
            return

        current_geom = self.geom
        current_soil = self.soil if self.soil is not None else SoilProperties()
        current_seismic = self.seismic if self.seismic is not None else SeismicParams()
        current_results = self.results

        # Sync checkboxes and slider controls if explicitly provided
        if show_soil is not None and hasattr(self, "chk_soil"):
            self.chk_soil.blockSignals(True)
            self.chk_soil.setChecked(show_soil)
            self.chk_soil.blockSignals(False)

        if show_water is not None and hasattr(self, "chk_water"):
            self.chk_water.blockSignals(True)
            self.chk_water.setChecked(show_water)
            self.chk_water.blockSignals(False)

        if show_wedge is not None and hasattr(self, "chk_wedge"):
            self.chk_wedge.blockSignals(True)
            self.chk_wedge.setChecked(show_wedge)
            self.chk_wedge.blockSignals(False)

        if show_vectors is not None and hasattr(self, "chk_vectors"):
            self.chk_vectors.blockSignals(True)
            self.chk_vectors.setChecked(show_vectors)
            self.chk_vectors.blockSignals(False)

        if show_fbd is not None and hasattr(self, "chk_fbd"):
            self.chk_fbd.blockSignals(True)
            self.chk_fbd.setChecked(show_fbd)
            self.chk_fbd.blockSignals(False)

        if show_dims is not None and hasattr(self, "chk_dims"):
            self.chk_dims.blockSignals(True)
            self.chk_dims.setChecked(show_dims)
            self.chk_dims.blockSignals(False)

        if explode_factor is not None and hasattr(self, "slider_explode"):
            self.slider_explode.blockSignals(True)
            self.slider_explode.setValue(int(explode_factor * 100))
            self.slider_explode.blockSignals(False)

        # Resolve visualization parameters from arguments or control bar
        eff_warp = float(warp_scale if warp_scale is not None else self.spin_warp.value())
        eff_show_soil = bool(show_soil if show_soil is not None else self.chk_soil.isChecked())
        eff_show_water = bool(show_water if show_water is not None else self.chk_water.isChecked())
        eff_show_wedge = bool(show_wedge if show_wedge is not None else self.chk_wedge.isChecked())
        eff_show_vectors = bool(show_vectors if show_vectors is not None else self.chk_vectors.isChecked())
        eff_explode = float(
            explode_factor
            if explode_factor is not None
            else ((self.slider_explode.value() / 100.0) if hasattr(self, "slider_explode") else 0.0)
        )
        self.current_explode_factor = eff_explode
        eff_scalar = str(scalar_name if scalar_name is not None else self.combo_scalar.currentData())
        eff_cmap = str(colormap if colormap is not None else self.combo_cmap.currentText())

        eff_slice_axis = str(slice_axis if slice_axis is not None else self.combo_slice.currentData())
        eff_slice_val = float(slice_pos if slice_pos is not None else (self.slider_slice.value() / 100.0))

        # Save active camera position to prevent view jumps
        cam_pos = self.plotter.camera_position

        self.continuum_result = None
        self.wall_mode = WallSystemMode.CANTILEVER
        self._remove_actor_attr("multi_strut_actor")
        self._remove_actor_attr("strut_actor")
        self._remove_actor_attr("continuum_actor")
        self._remove_actor_attr("continuum_soil_actor")

        # ----------------------------------------------------
        # 1. Build and Warp Concrete Wall Mesh
        # ----------------------------------------------------
        wall_grid = build_3d_wall_mesh(current_geom, current_results, seismic=current_seismic)
        # Compute Code Safety Unity Ratio (UR = sigma_tensile / f_cr)
        if "TensileStress_MPa" in wall_grid.point_data:
            sig_t = np.asarray(wall_grid.point_data["TensileStress_MPa"], dtype=np.float32)
            ur = np.clip(np.maximum(0.0, sig_t) / 2.80, 0.0, 5.0)
            wall_grid.point_data["SafetyUnityRatio"] = ur.astype(np.float32)
        else:
            wall_grid.point_data["SafetyUnityRatio"] = np.zeros(wall_grid.n_points, dtype=np.float32)

        self.active_wall_mesh = wall_grid
        if eff_warp > 0.0 and "Deformation_m" in wall_grid.point_data:
            display_mesh = wall_grid.warp_by_vector("Deformation_m", factor=eff_warp)
        else:
            display_mesh = wall_grid

        # ----------------------------------------------------
        # 2. Orthographic Slicing or Full Solid Rendering
        # ----------------------------------------------------
        if self.wall_actor is not None:
            try:
                self.plotter.remove_actor(self.wall_actor)
            except Exception:
                pass
            self.wall_actor = None

        if self.outline_actor is not None:
            try:
                self.plotter.remove_actor(self.outline_actor)
            except Exception:
                pass
            self.outline_actor = None

        # Determine scalar field bounds and display units cleanly
        is_realistic = (eff_scalar == "RealisticMaterials")
        if not is_realistic:
            if eff_scalar not in display_mesh.point_data:
                eff_scalar = "TensileStress_MPa"
            scalar_meta = {
                "TensileStress_MPa": ("Tensile Stress", "stress_mpa"),
                "VonMises_MPa": ("Von Mises Stress", "stress_mpa"),
                "PorePressure_kPa": ("Pore Pressure", "pressure"),
                "SafetyUnityRatio": ("Safety Unity Ratio (UR)", "ratio"),
            }
            base_title, u_kind = scalar_meta.get(eff_scalar, (eff_scalar, ""))
            disp_scalar_key, title_str, c_min, c_max = self._prepare_display_scalars(
                display_mesh, eff_scalar, base_title, u_kind
            )
            clim = [c_min, c_max]
            eff_scalar = disp_scalar_key

            scalar_bar_args = {
                "title": title_str,
                "title_font_size": 11,
                "label_font_size": 9,
                "shadow": True,
                "n_labels": 5,
                "italic": False,
                "fmt": "%.2f",
                "position_x": 0.82,
                "position_y": 0.05,
                "width": 0.12,
                "height": 0.4,
            }

        # Apply cutting plane if active
        if eff_slice_axis in ["x", "y", "z"]:
            bounds = display_mesh.bounds  # (xmin, xmax, ymin, ymax, zmin, zmax)
            if eff_slice_axis == "x":
                normal = (1, 0, 0)
                origin_val = bounds[0] + eff_slice_val * (bounds[1] - bounds[0])
                origin = (origin_val, (bounds[2] + bounds[3]) / 2.0, (bounds[4] + bounds[5]) / 2.0)
            elif eff_slice_axis == "y":
                normal = (0, 1, 0)
                origin_val = bounds[2] + eff_slice_val * (bounds[3] - bounds[2])
                origin = ((bounds[0] + bounds[1]) / 2.0, origin_val, (bounds[4] + bounds[5]) / 2.0)
            else:  # "z"
                normal = (0, 0, 1)
                origin_val = bounds[4] + eff_slice_val * (bounds[5] - bounds[4])
                origin = ((bounds[0] + bounds[1]) / 2.0, (bounds[2] + bounds[3]) / 2.0, origin_val)

            sliced_mesh = display_mesh.slice(normal=normal, origin=origin)
            if is_realistic:
                self.wall_actor = self.plotter.add_mesh(
                    sliced_mesh,
                    color=VIEWPORT_COLORS["wall_concrete"],
                    opacity=self.current_wall_opacity,
                    show_edges=True,
                    edge_color="#475569",
                    line_width=1.0,
                    specular=0.35,
                    ambient=0.25,
                    diffuse=0.85,
                    smooth_shading=True,
                    show_scalar_bar=False,
                )
            else:
                self.wall_actor = self.plotter.add_mesh(
                    sliced_mesh,
                    scalars=eff_scalar,
                    cmap=eff_cmap,
                    clim=clim,
                    opacity=self.current_wall_opacity,
                    scalar_bar_args=scalar_bar_args,
                    show_edges=True,
                    edge_color="#475569",
                    line_width=1.0,
                    specular=0.25,
                    ambient=0.25,
                    diffuse=0.85,
                    smooth_shading=True,
                )
            # Add structural reference wireframe outline
            self.outline_actor = self.plotter.add_mesh(
                display_mesh.outline(),
                color="#64748b",
                line_width=1.2,
            )
        else:
            if is_realistic:
                self.wall_actor = self.plotter.add_mesh(
                    display_mesh,
                    color=VIEWPORT_COLORS["wall_concrete"],
                    opacity=self.current_wall_opacity,
                    show_edges=True,
                    edge_color="#475569",
                    line_width=0.8,
                    specular=0.35,
                    ambient=0.25,
                    diffuse=0.85,
                    smooth_shading=True,
                    show_scalar_bar=False,
                )
            else:
                self.wall_actor = self.plotter.add_mesh(
                    display_mesh,
                    scalars=eff_scalar,
                    cmap=eff_cmap,
                    clim=clim,
                    opacity=self.current_wall_opacity,
                    scalar_bar_args=scalar_bar_args,
                    show_edges=True,
                    edge_color="#334155",
                    line_width=0.8,
                    specular=0.25,
                    ambient=0.25,
                    diffuse=0.85,
                    smooth_shading=True,
                )

        # ----------------------------------------------------
        # 3. Soil Strata Meshes (Backfill and Foundation)
        # ----------------------------------------------------
        if self.backfill_actor is not None:
            try:
                self.plotter.remove_actor(self.backfill_actor)
            except Exception:
                pass
            self.backfill_actor = None

        if self.foundation_actor is not None:
            try:
                self.plotter.remove_actor(self.foundation_actor)
            except Exception:
                pass
            self.foundation_actor = None

        backfill_grid, foundation_grid, water_plane = build_3d_soil_mesh(
            current_geom, current_soil, current_seismic, current_results, ripple_phase=self.ripple_phase
        )

        # Tier 3.2: Exploded Assembly Translation
        if eff_explode > 0.0:
            d_backfill = np.array([4.0 * eff_explode, 0.0, 0.0])
            d_foundation = np.array([0.0, -3.0 * eff_explode, 0.0])
            backfill_grid.translate(d_backfill, inplace=True)
            water_plane.translate(d_backfill, inplace=True)
            foundation_grid.translate(d_foundation, inplace=True)

        self.active_backfill_mesh = backfill_grid
        self.active_foundation_mesh = foundation_grid

        if eff_show_soil:
            self.backfill_actor = self.plotter.add_mesh(
                backfill_grid,
                color=VIEWPORT_COLORS["backfill_soil"],
                opacity=0.40,
                specular=0.15,
                ambient=0.25,
                diffuse=0.85,
                smooth_shading=True,
                show_edges=True,
                edge_color="#9c6644",
                line_width=0.7,
            )
            self.foundation_actor = self.plotter.add_mesh(
                foundation_grid,
                color=VIEWPORT_COLORS["foundation_soil"],
                opacity=0.55,
                specular=0.20,
                ambient=0.25,
                diffuse=0.85,
                smooth_shading=True,
                show_edges=True,
                edge_color="#334155",
                line_width=0.7,
            )

        # ----------------------------------------------------
        # 4. Translucent Water Table Plane with Waves
        # ----------------------------------------------------
        if self.water_actor is not None:
            try:
                self.plotter.remove_actor(self.water_actor)
            except Exception:
                pass
            self.water_actor = None

        if eff_show_water and current_seismic.water_table_depth < current_geom.total_height:
            if "Water_Ripple" in water_plane.point_data:
                self.water_actor = self.plotter.add_mesh(
                    water_plane,
                    scalars="Water_Ripple",
                    cmap="Blues",
                    clim=[0.0, 1.0],
                    opacity=0.65,
                    specular=0.85,
                    specular_power=35,
                    ambient=0.30,
                    diffuse=0.85,
                    show_scalar_bar=False,
                    smooth_shading=True,
                    show_edges=True,
                    edge_color="#38bdf8",
                    line_width=0.4,
                )
            else:
                self.water_actor = self.plotter.add_mesh(
                    water_plane,
                    color=VIEWPORT_COLORS["water_plane"],
                    opacity=0.65,
                    specular=0.85,
                    specular_power=35,
                    ambient=0.30,
                    diffuse=0.85,
                    smooth_shading=True,
                    show_edges=True,
                    edge_color="#38bdf8",
                    line_width=0.4,
                )

        # ----------------------------------------------------
        # 5. Animated Active Failure Wedge
        # ----------------------------------------------------
        if self.wedge_actor is not None:
            try:
                self.plotter.remove_actor(self.wedge_actor)
            except Exception:
                pass
            self.wedge_actor = None

        if eff_show_wedge:
            wedge_grid = build_3d_wedge_mesh(
                current_geom,
                current_soil,
                current_seismic,
                current_results,
                slide_disp=self.slide_disp,
            )
            if eff_explode > 0.0:
                d_wedge = np.array([6.0 * eff_explode, 2.0 * eff_explode, 0.0])
                wedge_grid.translate(d_wedge, inplace=True)
            self.active_wedge_mesh = wedge_grid
            self.wedge_actor = self.plotter.add_mesh(
                wedge_grid,
                color=VIEWPORT_COLORS["failure_wedge"],
                opacity=0.52,
                specular=0.35,
                ambient=0.30,
                diffuse=0.85,
                show_edges=True,
                edge_color="#be123c",
                line_width=1.0,
                smooth_shading=True,
            )
        else:
            self.active_wedge_mesh = None

        # ----------------------------------------------------
        # 6. Contact and Bearing Pressure Vector Glyphs
        # ----------------------------------------------------
        if self.contact_vector_actor is not None:
            try:
                self.plotter.remove_actor(self.contact_vector_actor)
            except Exception:
                pass
            self.contact_vector_actor = None

        if self.bearing_vector_actor is not None:
            try:
                self.plotter.remove_actor(self.bearing_vector_actor)
            except Exception:
                pass
            self.bearing_vector_actor = None

        if eff_show_vectors:
            contact_glyphs = build_contact_pressure_glyphs(
                current_geom, current_soil, current_seismic, current_results
            )
            if contact_glyphs is not None and contact_glyphs.n_points > 0:
                self.contact_vector_actor = self.plotter.add_mesh(
                    contact_glyphs,
                    color=VIEWPORT_COLORS.get("contact_vector", "#38bdf8"),
                    line_width=1.5,
                )

            bearing_glyphs = build_bearing_pressure_glyphs(
                current_geom, current_soil, current_results
            )
            if bearing_glyphs is not None and bearing_glyphs.n_points > 0:
                self.bearing_vector_actor = self.plotter.add_mesh(
                    bearing_glyphs,
                    color=VIEWPORT_COLORS.get("bearing_vector", "#34d399"),
                    line_width=1.5,
                )

        self._render_surcharge_overlay(current_geom)
        self._render_terrain_overlay()
        self._render_free_body_diagram(current_geom, current_soil, current_seismic, current_results)
        self._render_dimension_rulers(current_geom)
        self._render_component_labels()
        if hasattr(self, "hud_card") and self.hud_card is not None:
            self.hud_card.update_metrics(current_geom, current_results, current_seismic, self.unit_system)
        self._reposition_overlays()

        # ----------------------------------------------------
        # 7. Camera Preservation & Render
        # ----------------------------------------------------
        if cam_pos is not None and cam_pos[0] != (0.0, 0.0, 1.0):
            self.plotter.camera_position = cam_pos
        else:
            self.plotter.view_isometric()
            self.plotter.reset_camera()

        self.plotter.render()
        self.viewUpdated.emit()

    def update_multi_strut_scene(
        self,
        model: MultiStrutPiledWallModel,
        soil: Optional[SoilProperties] = None,
        seismic: Optional[SeismicParams] = None,
        num_bays: int = 3,
        arching_result: Optional[ShellArchingResult] = None,
        warp_scale: Optional[float] = None,
        show_soil: Optional[bool] = None,
        show_water: Optional[bool] = None,
        show_piles: Optional[bool] = None,
        show_struts: Optional[bool] = None,
        colormap: Optional[str] = None,
    ):
        """
        Renders the v2 multi-bay curved shell, vertical piers, pile caps, bored piles,
        and raking steel struts using hybrid_assembler.py (< 2 ms).
        """
        self.wall_mode = WallSystemMode.MULTI_STRUT_CURVED_SHELL
        self.multi_strut_model = model
        self.num_bays = max(1, int(num_bays))
        if soil is not None:
            self.soil = soil
        if seismic is not None:
            self.seismic = seismic
        if arching_result is not None:
            self.arching_result = arching_result

        current_soil = self.soil if self.soil is not None else SoilProperties()
        current_seismic = self.seismic if self.seismic is not None else SeismicParams()

        eff_warp = float(warp_scale if warp_scale is not None else self.spin_warp.value())
        eff_show_soil = bool(show_soil if show_soil is not None else self.chk_soil.isChecked())
        eff_show_water = bool(show_water if show_water is not None else self.chk_water.isChecked())
        eff_show_piles = bool(show_piles if show_piles is not None else self.chk_piles.isChecked())
        eff_show_struts = bool(show_struts if show_struts is not None else self.chk_struts.isChecked())
        eff_cmap = str(colormap if colormap is not None else self.combo_cmap.currentText())

        cam_pos = self.plotter.camera_position

        self.continuum_result = None
        # Remove cantilever-only and previous multi-strut actors
        for actor_attr in (
            "wall_actor",
            "outline_actor",
            "multi_strut_actor",
            "strut_actor",
            "continuum_actor",
            "continuum_soil_actor",
            "backfill_actor",
            "foundation_actor",
            "water_actor",
            "wedge_actor",
            "contact_vector_actor",
            "bearing_vector_actor",
            "surcharge_actor",
            "surcharge_super_actor",
        ):
            self._remove_actor_attr(actor_attr)

        # 1. Assemble 3D Multi-Bay Hybrid Mesh
        hybrid_grid = assemble_multi_strut_piled_wall_mesh(model, num_bays=self.num_bays)
        pts = hybrid_grid.points
        h_panel = max(0.5, float(model.shell.panel_height))

        # Attach Arching Stress scalar field (kPa) and lateral Deformation_m for warping
        if self.arching_result is not None and len(self.arching_result.depths) > 1:
            depths_from_crest = np.clip(h_panel - pts[:, 1], 0.0, h_panel)
            arching_kpa = np.interp(
                depths_from_crest,
                self.arching_result.depths,
                self.arching_result.sigma_h_profile,
            )
            arching_kpa = np.where(pts[:, 1] >= 0.0, arching_kpa, 0.0)
        else:
            arching_kpa = np.where(pts[:, 1] >= 0.0, 18.0 * np.clip(h_panel - pts[:, 1], 0.0, h_panel) * 0.25, 0.0)

        hybrid_grid.point_data["ArchingStress_kPa"] = arching_kpa.astype(np.float32)

        # Representative propped/cantilever lateral deflection vector (-Z forward)
        y_norm = np.clip(pts[:, 1] / h_panel, 0.0, 1.0)
        disp_scale = 0.015 * (1.0 + 3.0 * current_seismic.horizontal_pga)
        deform = np.zeros_like(pts, dtype=np.float32)
        deform[:, 2] = -(disp_scale * (y_norm ** 1.5))
        hybrid_grid.point_data["Deformation_m"] = deform
        self.active_wall_mesh = hybrid_grid

        if eff_warp > 0.0:
            display_grid = hybrid_grid.warp_by_vector("Deformation_m", factor=eff_warp)
        else:
            display_grid = hybrid_grid

        elem_types = display_grid.cell_data.get("Element_Type", np.ones(display_grid.n_cells, dtype=np.int32))
        solid_mask = np.isin(elem_types, [1, 2, 3, 4] if eff_show_piles else [1, 2, 3])
        if np.any(solid_mask):
            solid_mesh = display_grid.extract_cells(solid_mask)
            is_realistic = (eff_scalar == "RealisticMaterials")
            if is_realistic:
                self.multi_strut_actor = self.plotter.add_mesh(
                    solid_mesh,
                    color=VIEWPORT_COLORS["wall_concrete"],
                    opacity=self.current_wall_opacity,
                    show_edges=True,
                    edge_color="#475569",
                    line_width=0.8,
                    specular=0.35,
                    ambient=0.25,
                    diffuse=0.85,
                    smooth_shading=True,
                    show_scalar_bar=False,
                )
            else:
                disp_key, arch_title, c_min, c_max = self._prepare_display_scalars(
                    solid_mesh, "ArchingStress_kPa", "Arching Pressure", "pressure"
                )
                self.multi_strut_actor = self.plotter.add_mesh(
                    solid_mesh,
                    scalars=disp_key,
                    cmap=eff_cmap,
                    clim=[c_min, c_max],
                    scalar_bar_args={
                        "title": arch_title,
                        "title_font_size": 11,
                        "label_font_size": 9,
                        "n_labels": 5,
                        "fmt": "%.1f",
                        "position_x": 0.82,
                        "position_y": 0.05,
                        "width": 0.12,
                        "height": 0.4,
                    },
                    show_edges=True,
                    edge_color="#374151",
                    line_width=0.6,
                    specular=0.25,
                    ambient=0.25,
                    diffuse=0.85,
                    smooth_shading=True,
                )

        if eff_show_struts:
            strut_mask = elem_types == 5
            if np.any(strut_mask):
                strut_mesh = display_grid.extract_cells(strut_mask)
                self.strut_actor = self.plotter.add_mesh(
                    strut_mesh,
                    color=VIEWPORT_COLORS.get("strut_steel", "#0284c7"),
                    line_width=4.0,
                    specular=0.60,
                    ambient=0.30,
                )

        # 2. Surrounding Soil & Water Context
        bounds = display_grid.bounds  # (xmin, xmax, ymin, ymax, zmin, zmax)
        x0, x1 = bounds[0] - 1.0, bounds[1] + 1.0
        z_back_start = model.pier_pile.pier_depth
        z_back_end = z_back_start + 1.5 * h_panel
        if eff_show_soil:
            bf_box = pv.Box(bounds=(x0, x1, 0.0, h_panel, z_back_start, z_back_end)).triangulate()
            fnd_box = pv.Box(
                bounds=(x0, x1, -max(4.0, model.pier_pile.pile_length + 1.5), 0.0, -3.0, z_back_end)
            ).triangulate()
            self.backfill_actor = self.plotter.add_mesh(
                bf_box,
                color=VIEWPORT_COLORS["backfill_soil"],
                opacity=0.40,
                specular=0.15,
                ambient=0.25,
                diffuse=0.85,
                smooth_shading=True,
                show_edges=True,
                edge_color="#9c6644",
                line_width=0.7,
            )
            self.foundation_actor = self.plotter.add_mesh(
                fnd_box,
                color=VIEWPORT_COLORS["foundation_soil"],
                opacity=0.55,
                specular=0.20,
                ambient=0.25,
                diffuse=0.85,
                smooth_shading=True,
                show_edges=True,
                edge_color="#334155",
                line_width=0.7,
            )

        if eff_show_water and current_seismic.water_table_depth < h_panel:
            water_y = max(0.0, h_panel - current_seismic.water_table_depth)
            water_plane = pv.Plane(
                center=((x0 + x1) / 2.0, water_y, (z_back_start + z_back_end) / 2.0),
                direction=(0, 1, 0),
                i_size=(x1 - x0),
                j_size=(z_back_end - z_back_start),
                i_resolution=32,
                j_resolution=32,
            )
            pts_w = water_plane.points.copy()
            k_x = 2.0 * np.pi / max(1.0, (x1 - x0) / 2.5)
            k_z = 2.0 * np.pi / max(1.0, (z_back_end - z_back_start) / 2.0)
            ripple = 0.02 * np.sin(k_x * pts_w[:, 0] + self.ripple_phase) + 0.015 * np.cos(k_z * pts_w[:, 2] + 0.7 * self.ripple_phase)
            pts_w[:, 1] += ripple
            water_plane.points = pts_w
            norm_r = (ripple - np.min(ripple)) / (np.max(ripple) - np.min(ripple) + 1e-6)
            water_plane.point_data["Water_Ripple"] = norm_r.astype(np.float32)
            self.water_actor = self.plotter.add_mesh(
                water_plane,
                scalars="Water_Ripple",
                cmap="Blues",
                clim=[0.0, 1.0],
                opacity=0.65,
                specular=0.85,
                specular_power=35,
                ambient=0.30,
                diffuse=0.85,
                show_scalar_bar=False,
                smooth_shading=True,
                show_edges=True,
                edge_color="#38bdf8",
                line_width=0.4,
            )

        self._render_terrain_overlay()
        self._render_component_labels()
        if hasattr(self, "hud_card") and self.hud_card is not None:
            self.hud_card.update_metrics(self.geom, self.results, current_seismic, self.unit_system)
        self._reposition_overlays()

        if cam_pos is not None and cam_pos[0] != (0.0, 0.0, 1.0):
            self.plotter.camera_position = cam_pos
        else:
            self.plotter.view_isometric()
            self.plotter.reset_camera()

        self.plotter.render()
        self.viewUpdated.emit()

    def _render_surcharge_overlay(self, geom: Optional[RetainingWallGeometry]) -> None:
        """Renders translucent 3D building footing / traffic surcharge blocks on backfill."""
        self._remove_actor_attr("surcharge_actor")
        self._remove_actor_attr("surcharge_super_actor")
        if (
            geom is None
            or self.surcharge_params is None
            or self.surcharge_params.load_type == SurchargeLoadType.NONE
        ):
            return

        footing_grid, super_grid = build_surcharge_3d_meshes(geom, self.surcharge_params)
        if footing_grid is not None:
            self.surcharge_actor = self.plotter.add_mesh(
                footing_grid,
                color="#f59e0b",
                opacity=0.65,
                show_edges=True,
                edge_color="#b45309",
                line_width=1.2,
            )
        if super_grid is not None:
            self.surcharge_super_actor = self.plotter.add_mesh(
                super_grid,
                color="#38bdf8",
                opacity=0.25,
                show_edges=True,
                edge_color="#0284c7",
                line_width=1.0,
            )

    def update_architectural_scene(
        self,
        spec: Optional[ArchitecturalWallSpec] = None,
        soil: Optional[SoilProperties] = None,
        seismic: Optional[SeismicParams] = None,
        summary: Optional[ArchWallAnalysisSummary] = None,
        surcharge: Optional[AdjacentSurchargeParams] = None,
        warp_scale: Optional[float] = None,
        scalar_name: Optional[str] = None,
        colormap: Optional[str] = None,
        show_soil: Optional[bool] = None,
    ) -> None:
        """Renders any of the 5 Phase 7 architectural retaining wall morphologies."""
        if spec is not None:
            self.arch_spec = spec
        if soil is not None:
            self.soil = soil
        if seismic is not None:
            self.seismic = seismic
        if summary is not None:
            self.arch_summary = summary
        if surcharge is not None:
            self.surcharge_params = surcharge

        if self.arch_spec is None:
            return

        self.wall_mode = WallSystemMode.ARCHITECTURAL
        self.continuum_result = None
        eff_warp = float(warp_scale if warp_scale is not None else self.spin_warp.value())
        eff_scalar = str(scalar_name if scalar_name is not None else self.combo_scalar.currentData())
        eff_cmap = str(colormap if colormap is not None else self.combo_cmap.currentText())
        eff_show_soil = bool(show_soil if show_soil is not None else self.chk_soil.isChecked())

        cam_pos = self.plotter.camera_position
        self.clear_actors()

        arch_grid = build_architectural_wall_mesh(self.arch_spec, summary=self.arch_summary)
        self.active_wall_mesh = arch_grid
        display_mesh = (
            arch_grid.warp_by_vector("Deformation_m", factor=eff_warp)
            if eff_warp > 0.0 and "Deformation_m" in arch_grid.point_data
            else arch_grid
        )

        is_realistic = (eff_scalar == "RealisticMaterials")
        if is_realistic:
            self.wall_actor = self.plotter.add_mesh(
                display_mesh,
                color=VIEWPORT_COLORS["wall_concrete"],
                opacity=self.current_wall_opacity,
                show_edges=True,
                edge_color="#475569",
                line_width=0.8,
                specular=0.35,
                ambient=0.25,
                diffuse=0.85,
                smooth_shading=True,
                show_scalar_bar=False,
            )
        else:
            if eff_scalar not in display_mesh.point_data:
                eff_scalar = "TensileStress_MPa"
            scalar_meta = {
                "TensileStress_MPa": ("Tensile Stress", "stress_mpa"),
                "VonMises_MPa": ("Von Mises Stress", "stress_mpa"),
                "PorePressure_kPa": ("Pore Pressure", "pressure"),
            }
            base_title, u_kind = scalar_meta.get(eff_scalar, (eff_scalar, ""))
            disp_key, title_str, c_min, c_max = self._prepare_display_scalars(
                display_mesh, eff_scalar, base_title, u_kind
            )
            is_light = self.theme_mode == ThemeMode.LIGHT
            self.wall_actor = self.plotter.add_mesh(
                display_mesh,
                scalars=disp_key,
                cmap=eff_cmap,
                clim=[c_min, c_max],
                scalar_bar_args={"title": title_str, "color": "#1e293b" if is_light else "white"},
                show_edges=True,
                edge_color="#1e293b" if is_light else "#4b5563",
                line_width=1.0 if is_light else 0.9,
                smooth_shading=True,
            )

        if eff_show_soil and self.geom is not None:
            b = display_mesh.bounds
            pad = 0.8
            bf_box = pv.Box(
                bounds=(b[1] - 0.1, b[1] + 4.0, max(0.0, b[2]), max(1.0, b[3] - 0.1), b[4] - pad, b[5] + pad)
            ).triangulate()
            self.backfill_actor = self.plotter.add_mesh(
                bf_box,
                color=VIEWPORT_COLORS["backfill_soil"],
                opacity=0.40,
                specular=0.15,
                ambient=0.25,
                diffuse=0.85,
                smooth_shading=True,
                show_edges=True,
                edge_color="#9c6644",
                line_width=0.7,
            )

        self._render_surcharge_overlay(self.geom)
        self._render_terrain_overlay()
        self._render_component_labels()
        if hasattr(self, "hud_card") and self.hud_card is not None:
            self.hud_card.update_metrics(self.geom, self.results, current_seismic, self.unit_system)
        self._reposition_overlays()

        if cam_pos is not None and cam_pos[0] != (0.0, 0.0, 1.0):
            self.plotter.camera_position = cam_pos
        else:
            self.plotter.view_isometric()
            self.plotter.reset_camera()

        self.plotter.render()
        self.viewUpdated.emit()

    def update_continuum_fea_scene(
        self,
        fea_result,
        step_idx: int = -1,
        warp_scale: Optional[float] = None,
        scalar_name: Optional[str] = None,
        colormap: Optional[str] = None,
        show_soil: Optional[bool] = None,
    ):
        """
        Renders true 3D continuum FEA hexahedral results (`ContinuumFEAResult`)
        with deformed mesh warping, backface earth pressure contours, excess
        pore-pressure ratio `r_u`, or octahedral shear strain contours.
        """
        if fea_result is None:
            return
        self.continuum_result = fea_result
        self.continuum_step_idx = step_idx

        eff_warp = float(warp_scale if warp_scale is not None else self.spin_warp.value())
        eff_scalar = str(scalar_name if scalar_name is not None else self.combo_scalar.currentData())
        eff_cmap = str(colormap if colormap is not None else self.combo_cmap.currentText())
        eff_show_soil = bool(show_soil if show_soil is not None else self.chk_soil.isChecked())

        cam_pos = self.plotter.camera_position
        self.clear_actors()

        grid = fea_result.grid_at_timestep(step_idx)
        if eff_warp > 0.0 and "Displacement_m" in grid.point_data:
            display_grid = grid.warp_by_vector("Displacement_m", factor=eff_warp)
        else:
            display_grid = grid

        if eff_scalar not in display_grid.point_data and eff_scalar not in display_grid.cell_data:
            eff_scalar = "WallNormalStress_kPa"

        if eff_scalar in display_grid.point_data:
            vals = np.asarray(display_grid.point_data[eff_scalar], dtype=float)
        else:
            vals = np.asarray(display_grid.cell_data.get(eff_scalar, np.array([0.0])), dtype=float)

        c_min = float(np.nanmin(vals)) if len(vals) > 0 else 0.0
        c_max = float(np.nanmax(vals)) if len(vals) > 0 else 1.0
        if not np.isfinite(c_min):
            c_min = 0.0
        if not np.isfinite(c_max) or c_max <= c_min:
            c_max = c_min + 1.0
        clim = [c_min, c_max]

        dom_ids = np.asarray(display_grid.cell_data.get("Domain_ID", np.ones(display_grid.n_cells)))
        wall_mask = dom_ids == 1
        soil_mask = dom_ids != 1

        if eff_scalar == "WallNormalStress_kPa":
            disp_key, fea_title, c_min, c_max = self._prepare_display_scalars(
                display_grid, eff_scalar, "Wall Normal Stress", "pressure"
            )
            eff_scalar = disp_key
            clim = [c_min, c_max]
        else:
            fea_title = eff_scalar

        if np.any(wall_mask):
            wall_sub = display_grid.extract_cells(wall_mask)
            self.active_wall_mesh = wall_sub
            self.continuum_actor = self.plotter.add_mesh(
                wall_sub,
                scalars=eff_scalar,
                cmap=eff_cmap,
                clim=clim,
                show_edges=True,
                edge_color="#1f2937",
                line_width=0.8,
                scalar_bar_args={"title": fea_title, "color": "white"},
            )
        else:
            self.active_wall_mesh = display_grid
            self.continuum_actor = self.plotter.add_mesh(
                display_grid,
                scalars=eff_scalar,
                cmap=eff_cmap,
                clim=clim,
                show_edges=True,
                scalar_bar_args={"title": fea_title, "color": "white"},
            )

        if eff_show_soil and np.any(soil_mask):
            soil_sub = display_grid.extract_cells(soil_mask)
            soil_scalars = (
                eff_scalar
                if eff_scalar in ("ExcessPorePressureRatio_ru", "OctahedralShearStrain")
                else None
            )
            self.continuum_soil_actor = self.plotter.add_mesh(
                soil_sub,
                scalars=soil_scalars,
                cmap=eff_cmap if soil_scalars else None,
                clim=clim if soil_scalars else None,
                color=None if soil_scalars else VIEWPORT_COLORS["backfill_soil"],
                opacity=0.25 if soil_scalars is None else 0.42,
                show_edges=True,
                edge_color="#5a4e3f",
                line_width=0.4,
            )

        if cam_pos is not None and cam_pos[0] != (0.0, 0.0, 1.0):
            self.plotter.camera_position = cam_pos
        else:
            self.plotter.view_isometric()
            self.plotter.reset_camera()

        self.plotter.render()
        self.viewUpdated.emit()

    def set_continuum_timestep(self, step_idx: int):
        """Updates the active 3D continuum FEA mesh display to timestep index `step_idx`."""
        if self.continuum_result is not None:
            self.update_continuum_fea_scene(self.continuum_result, step_idx=step_idx)


# Alias for backwards compatibility
Viewport3D = RetainingWall3DView
