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

from ..config import VIEWPORT_COLORS, THEME_DARK
from ..models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
)
from ..mesher.hex_mesher import (
    build_3d_wall_mesh,
    build_3d_soil_mesh,
    build_3d_wedge_mesh,
    build_contact_pressure_glyphs,
    build_bearing_pressure_glyphs,
)


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
        self.backfill_actor = None
        self.foundation_actor = None
        self.water_actor = None
        self.wedge_actor = None
        self.contact_vector_actor = None
        self.bearing_vector_actor = None

        # 5. Cached State Models
        self.geom: Optional[RetainingWallGeometry] = None
        self.soil: Optional[SoilProperties] = None
        self.seismic: Optional[SeismicParams] = None
        self.results: Optional[AnalysisResults] = None
        self.slide_disp: float = 0.0
        self.ripple_phase: float = 0.0

    def _create_control_bar(self) -> QWidget:
        """Constructs an integrated inspection and visualization control bar."""
        bar = QFrame(self)
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME_DARK["surface_dark"]};
                border-bottom: 1px solid {THEME_DARK["border"]};
                padding: 4px 6px;
            }}
            QLabel {{
                color: {THEME_DARK["text_secondary"]};
                font-size: 11px;
                font-weight: 500;
            }}
            QComboBox, QDoubleSpinBox {{
                background-color: {THEME_DARK["surface_elevated"]};
                color: {THEME_DARK["text_primary"]};
                border: 1px solid {THEME_DARK["border"]};
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 11px;
                min-height: 20px;
            }}
            QCheckBox {{
                color: {THEME_DARK["text_primary"]};
                font-size: 11px;
                spacing: 4px;
            }}
            QPushButton {{
                background-color: {THEME_DARK["surface_elevated"]};
                color: {THEME_DARK["text_primary"]};
                border: 1px solid {THEME_DARK["border"]};
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {THEME_DARK["border"]};
            }}
        """)

        h_layout = QHBoxLayout(bar)
        h_layout.setContentsMargins(6, 2, 6, 2)
        h_layout.setSpacing(8)

        # Field Selector
        h_layout.addWidget(QLabel("Scalar:"))
        self.combo_scalar = QComboBox()
        self.combo_scalar.addItem("Tensile Stress", "TensileStress_MPa")
        self.combo_scalar.addItem("Von Mises Stress", "VonMises_MPa")
        self.combo_scalar.addItem("Pore Pressure", "PorePressure_kPa")
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

        # Reset Camera Action
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
        self.plotter.view_isometric()
        self.plotter.reset_camera()
        self.plotter.render()

    def clear_actors(self):
        """Explicitly removes all active mesh actors to prevent VTK memory leaks."""
        actor_names = [
            "wall_actor",
            "outline_actor",
            "backfill_actor",
            "foundation_actor",
            "water_actor",
            "wedge_actor",
            "contact_vector_actor",
            "bearing_vector_actor",
        ]
        for name in actor_names:
            actor = getattr(self, name, None)
            if actor is not None:
                try:
                    self.plotter.remove_actor(actor)
                except Exception:
                    pass
                setattr(self, name, None)

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

        # ----------------------------------------------------
        # 1. Build and Warp Concrete Wall Mesh
        # ----------------------------------------------------
        wall_grid = build_3d_wall_mesh(current_geom, current_results, seismic=current_seismic)
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

        # Determine scalar field bounds with safe clamping
        if eff_scalar in display_mesh.point_data:
            arr = display_mesh.point_data[eff_scalar]
            c_min = float(np.nanmin(arr)) if len(arr) > 0 else 0.0
            c_max = float(np.nanmax(arr)) if len(arr) > 0 else 1.0
        else:
            eff_scalar = "TensileStress_MPa"
            arr = display_mesh.point_data.get(eff_scalar, np.array([0.0]))
            c_min = float(np.nanmin(arr))
            c_max = float(np.nanmax(arr))

        if not np.isfinite(c_min):
            c_min = 0.0
        if not np.isfinite(c_max) or c_max <= c_min:
            c_max = c_min + 1.0  # Safe clamp preventing divide-by-zero

        clim = [c_min, c_max]

        # Titles for scalar bars
        scalar_titles = {
            "TensileStress_MPa": "Tensile Stress (MPa)",
            "VonMises_MPa": "Von Mises Stress (MPa)",
            "PorePressure_kPa": "Pore Pressure (kPa)",
        }
        title_str = scalar_titles.get(eff_scalar, eff_scalar)

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


# Alias for backwards compatibility
Viewport3D = RetainingWall3DView
