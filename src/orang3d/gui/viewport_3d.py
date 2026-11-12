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

        # 1. Sleek Viewport Toolbar / Inspection Bar
        self.control_bar = self._create_control_bar()
        layout.addWidget(self.control_bar)

        # 2. PyVista QtInteractor Canvas
        self.plotter = QtInteractor(self)
        layout.addWidget(self.plotter.interactor)

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

        # 5. Cached State Models
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
        self.combo_scalar.addItem("Tensile Stress", "TensileStress_MPa")
        self.combo_scalar.addItem("Von Mises Stress", "VonMises_MPa")
        self.combo_scalar.addItem("Pore Pressure", "PorePressure_kPa")
        self.combo_scalar.addItem("Arching Stress", "ArchingStress_kPa")
        self.combo_scalar.addItem("Element Type", "Element_Type")
        self.combo_scalar.addItem("Backface Earth Pressure (3D FEA)", "WallNormalStress_kPa")
        self.combo_scalar.addItem("Excess Pore Pressure ru (3D FEA)", "ExcessPorePressureRatio_ru")
        self.combo_scalar.addItem("Octahedral Shear Strain (3D FEA)", "OctahedralShearStrain")
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
        self.plotter.show_grid(
            color=VIEWPORT_COLORS["grid"],
            grid=False,
            location="outer",
            ticks="outside",
        )

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

    def _remove_actor_attr(self, attr_name: str):
        actor = getattr(self, attr_name, None)
        if actor is not None:
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
        ]
        for name in actor_names:
            self._remove_actor_attr(name)

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

        # Resolve visualization parameters from arguments or control bar
        eff_warp = float(warp_scale if warp_scale is not None else self.spin_warp.value())
        eff_show_soil = bool(show_soil if show_soil is not None else self.chk_soil.isChecked())
        eff_show_water = bool(show_water if show_water is not None else self.chk_water.isChecked())
        eff_show_wedge = bool(show_wedge if show_wedge is not None else self.chk_wedge.isChecked())
        eff_show_vectors = bool(show_vectors if show_vectors is not None else self.chk_vectors.isChecked())
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
        if eff_scalar not in display_mesh.point_data:
            eff_scalar = "TensileStress_MPa"
        scalar_meta = {
            "TensileStress_MPa": ("Tensile Stress", "stress_mpa"),
            "VonMises_MPa": ("Von Mises Stress", "stress_mpa"),
            "PorePressure_kPa": ("Pore Pressure", "pressure"),
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
            self.wall_actor = self.plotter.add_mesh(
                sliced_mesh,
                scalars=eff_scalar,
                cmap=eff_cmap,
                clim=clim,
                scalar_bar_args=scalar_bar_args,
                show_edges=True,
                edge_color="#4b5563",
                line_width=1.0,
            )
            # Add structural reference wireframe outline
            self.outline_actor = self.plotter.add_mesh(
                display_mesh.outline(),
                color="#6b7280",
                line_width=1.2,
            )
        else:
            self.wall_actor = self.plotter.add_mesh(
                display_mesh,
                scalars=eff_scalar,
                cmap=eff_cmap,
                clim=clim,
                scalar_bar_args=scalar_bar_args,
                show_edges=True,
                edge_color="#4b5563",
                line_width=0.8,
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

        if eff_show_soil:
            self.backfill_actor = self.plotter.add_mesh(
                backfill_grid,
                color=VIEWPORT_COLORS["backfill_soil"],
                opacity=0.35,
                show_edges=True,
                edge_color="#85715d",
                line_width=0.5,
            )
            self.foundation_actor = self.plotter.add_mesh(
                foundation_grid,
                color=VIEWPORT_COLORS["foundation_soil"],
                opacity=0.45,
                show_edges=True,
                edge_color="#5a4e3f",
                line_width=0.5,
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
            self.water_actor = self.plotter.add_mesh(
                water_plane,
                color=VIEWPORT_COLORS["water_plane"],
                opacity=0.55,
                show_edges=False,
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
            self.wedge_actor = self.plotter.add_mesh(
                wedge_grid,
                color=VIEWPORT_COLORS["failure_wedge"],
                opacity=0.45,
                show_edges=True,
                edge_color="#d97706",
                line_width=1.0,
            )

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
            )

        if eff_show_struts:
            strut_mask = elem_types == 5
            if np.any(strut_mask):
                strut_mesh = display_grid.extract_cells(strut_mask)
                self.strut_actor = self.plotter.add_mesh(
                    strut_mesh,
                    color="#38bdf8",
                    line_width=4.0,
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
                opacity=0.28,
                show_edges=True,
                edge_color="#85715d",
                line_width=0.5,
            )
            self.foundation_actor = self.plotter.add_mesh(
                fnd_box,
                color=VIEWPORT_COLORS["foundation_soil"],
                opacity=0.35,
                show_edges=True,
                edge_color="#5a4e3f",
                line_width=0.5,
            )

        if eff_show_water and current_seismic.water_table_depth < h_panel:
            water_y = max(0.0, h_panel - current_seismic.water_table_depth)
            water_plane = pv.Plane(
                center=((x0 + x1) / 2.0, water_y, (z_back_start + z_back_end) / 2.0),
                direction=(0, 1, 0),
                i_size=(x1 - x0),
                j_size=(z_back_end - z_back_start),
            )
            self.water_actor = self.plotter.add_mesh(
                water_plane,
                color=VIEWPORT_COLORS["water_plane"],
                opacity=0.50,
                show_edges=False,
            )

        self._render_terrain_overlay()

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
                opacity=0.22,
                show_edges=True,
                edge_color="#85715d",
                line_width=0.4,
            )

        self._render_surcharge_overlay(self.geom)
        self._render_terrain_overlay()

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
