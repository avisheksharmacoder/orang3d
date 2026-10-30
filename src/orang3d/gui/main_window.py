"""
Main Application Window for orang3D.
Houses the PyVista 3D Viewport, PyQtGraph 2D Dashboard, and Parameter Dock Panels.
"""

import time
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QToolBar, QStatusBar, QLabel, QPushButton, QSlider,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon

from ..config import APP_NAME, APP_SUBTITLE, APP_VERSION, THEME
from ..models.wall_params import RetainingWallGeometry, SoilProperties, SeismicParams, AnalysisResults
from ..physics.stability import evaluate_wall_stability
from ..physics.kratos_solver import KratosSimulationWorker, KRATOS_AVAILABLE
from ..signals.synthetic import generate_ricker_wavelet, generate_harmonic_sweep, compute_newmark_sliding_displacement
from ..signals.at2_parser import parse_at2_file
from .viewport_3d import Viewport3D
from .charts_2d import Charts2DWidget
from .panels import (
    GeometryPanel, SoilPanel, SeismicPanel,
    ShellAndPierPanel, StrutAndPilePanel, ISDesignAuditTab
)
from ..models.advanced_wall_params import (
    MultiStrutPiledWallModel, CurvedShellGeometry, PierAndPileGeometry, StrutSupportSystem
)
from ..models.is_code_params import IndianDesignStandards
from ..io.dxf_export import export_retaining_wall_dxf, RetainingWallDXFExporter, EZDXF_AVAILABLE
from ..io.serialization import save_project_session, load_project_session, CorruptProjectError
from ..io.mesh_export import export_mesh_to_vtk, export_mesh_to_stl, export_mesh_to_obj, export_signals_to_csv
from ..io.report_generator import generate_engineering_pdf_report


class MainWindow(QMainWindow):
    """
    Primary desktop window for orang3D.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - {APP_SUBTITLE} (v{APP_VERSION})")
        self.resize(1400, 900)

        # State models
        self.geom = RetainingWallGeometry()
        self.soil = SoilProperties()
        self.seismic = SeismicParams()
        self.results = AnalysisResults()

        # Advanced curved shell & strut-pile models (Phase 10)
        self.shell_geom = CurvedShellGeometry()
        self.pier_pile_geom = PierAndPileGeometry()
        self.strut_sys = StrutSupportSystem()
        self.standards = IndianDesignStandards()
        self.num_bays = 3

        # Dynamic simulation & waveform state
        self.time_arr = np.array([])
        self.accel_arr = np.array([])
        self.slip_arr = np.array([])
        self.pore_arr = np.array([])
        self.playhead_idx = 0
        self.is_playing = False

        # Apply application-wide dark styling
        self._apply_dark_theme()

        # Build UI layout
        self._init_ui()

        # Animation timer (60 FPS ~ 16ms)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_animation_step)

        # Initial signal and calculation run
        self._regenerate_signals()
        self.recompute_and_render()

    def _apply_dark_theme(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {THEME["background_dark"]};
                color: {THEME["text_primary"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }}
            QTabWidget::pane {{
                border: 1px solid {THEME["border"]};
                background: {THEME["surface_dark"]};
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background: {THEME["surface_dark"]};
                color: {THEME["text_secondary"]};
                padding: 8px 16px;
                border: 1px solid {THEME["border"]};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background: {THEME["surface_elevated"]};
                color: {THEME["accent_orange"]};
                font-weight: bold;
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {THEME["border"]};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 14px;
                background-color: {THEME["surface_dark"]};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: {THEME["accent_orange"]};
            }}
            QDoubleSpinBox, QComboBox, QLineEdit {{
                background-color: {THEME["surface_elevated"]};
                color: {THEME["text_primary"]};
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QPushButton {{
                background-color: {THEME["accent_orange"]};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {THEME["accent_orange_hover"]};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {THEME["surface_elevated"]};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {THEME["accent_orange"]};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }}
            QStatusBar {{
                background-color: {THEME["surface_dark"]};
                color: {THEME["text_secondary"]};
                border-top: 1px solid {THEME["border"]};
            }}
        """)

    def _init_ui(self):
        # Menu Bar
        menu_bar = self.menuBar()
        menu_file = menu_bar.addMenu("&File")

        act_open = menu_file.addAction("Open Session (.o3d)...")
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._open_project)

        act_save = menu_file.addAction("Save Session (.o3d)...")
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._save_project)

        menu_file.addSeparator()

        act_report = menu_file.addAction("Generate Engineering PDF Report...")
        act_report.setShortcut("Ctrl+P")
        act_report.triggered.connect(self._generate_report_dialog)

        menu_file.addSeparator()
        act_exit = menu_file.addAction("Exit")
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)

        menu_export = menu_bar.addMenu("&Export")
        act_exp_dxf = menu_export.addAction("Export AutoCAD DXF (.DXF)...")
        act_exp_dxf.triggered.connect(self._export_dxf_dialog)
        act_exp_vtk = menu_export.addAction("Export 3D Mesh (.VTK)...")
        act_exp_vtk.triggered.connect(lambda: self._export_mesh_dialog("vtk"))
        act_exp_stl = menu_export.addAction("Export 3D Mesh (.STL)...")
        act_exp_stl.triggered.connect(lambda: self._export_mesh_dialog("stl"))
        act_exp_obj = menu_export.addAction("Export 3D Mesh (.OBJ)...")
        act_exp_obj.triggered.connect(lambda: self._export_mesh_dialog("obj"))
        menu_export.addSeparator()
        act_exp_csv = menu_export.addAction("Export Seismic Waveforms (.CSV)...")
        act_exp_csv.triggered.connect(self._export_csv_dialog)

        # Top Toolbar
        toolbar = QToolBar("Controls", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        btn_open = QPushButton("📂 Open")
        btn_open.setToolTip("Open saved .o3d project session (Ctrl+O)")
        btn_open.clicked.connect(self._open_project)
        toolbar.addWidget(btn_open)

        btn_save = QPushButton("💾 Save")
        btn_save.setToolTip("Save project session as .o3d bundle (Ctrl+S)")
        btn_save.clicked.connect(self._save_project)
        toolbar.addWidget(btn_save)

        btn_report = QPushButton("📄 PDF Report")
        btn_report.setToolTip("Generate comprehensive geotechnical calculation report (Ctrl+P)")
        btn_report.clicked.connect(self._generate_report_dialog)
        toolbar.addWidget(btn_report)

        btn_dxf = QPushButton("📐 AutoCAD DXF")
        btn_dxf.setToolTip("Export detailed layered AutoCAD DXF construction drawings with reinforcement detailing")
        btn_dxf.clicked.connect(self._export_dxf_dialog)
        toolbar.addWidget(btn_dxf)

        toolbar.addSeparator()

        btn_reset_cam = QPushButton("Reset 3D Camera")
        btn_reset_cam.clicked.connect(lambda: self.viewport_3d.plotter.reset_camera())
        toolbar.addWidget(btn_reset_cam)

        toolbar.addSeparator()

        self.btn_play = QPushButton("▶ Play Seismic Wave")
        self.btn_play.clicked.connect(self._toggle_playback)
        toolbar.addWidget(self.btn_play)

        toolbar.addWidget(QLabel("  Timeline:"))
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.valueChanged.connect(self._on_scrubber_moved)
        self.timeline_slider.setMinimumWidth(250)
        toolbar.addWidget(self.timeline_slider)

        toolbar.addSeparator()

        self.btn_kratos = QPushButton("⚙ Run Kratos GeoMechanics FEA")
        self.btn_kratos.setToolTip("Run multi-threaded deep dynamic Soil-Structure Interaction FEA with KratosMultiphysics (100% OSS)")
        self.btn_kratos.clicked.connect(self._run_kratos_simulation)
        toolbar.addWidget(self.btn_kratos)

        toolbar.addSeparator()

        btn_export = QPushButton("Export 3D Mesh")
        btn_export.clicked.connect(lambda: self._export_mesh_dialog("vtk"))
        toolbar.addWidget(btn_export)

        # Central Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Horizontal Splitter: Left = Parameter Tabs, Right = Viewport + Charts
        h_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(h_splitter)

        # Left Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setMaximumWidth(420)
        self.tabs.setMinimumWidth(340)

        self.panel_geom = GeometryPanel()
        self.panel_geom.geometryChanged.connect(self._on_geom_changed)
        self.tabs.addTab(self.panel_geom, "Cantilever Wall")

        self.panel_shell = ShellAndPierPanel()
        self.panel_shell.shellChanged.connect(self._on_shell_changed)
        self.tabs.addTab(self.panel_shell, "Curved Shell")

        self.panel_strut = StrutAndPilePanel()
        self.panel_strut.strutPileChanged.connect(self._on_strut_pile_changed)
        self.tabs.addTab(self.panel_strut, "Strut & Piles")

        self.panel_soil = SoilPanel()
        self.panel_soil.soilChanged.connect(self._on_soil_changed)
        self.tabs.addTab(self.panel_soil, "Soil Strata")

        self.panel_seismic = SeismicPanel()
        self.panel_seismic.seismicChanged.connect(self._on_seismic_changed)
        self.panel_seismic.recordLoaded.connect(self._on_at2_loaded)
        self.tabs.addTab(self.panel_seismic, "Disaster / Seismic")

        h_splitter.addWidget(self.tabs)

        # Right Vertical Splitter: Top = 3D Viewport, Bottom = Tabbed 2D Charts / IS Audit
        v_splitter = QSplitter(Qt.Vertical)
        h_splitter.addWidget(v_splitter)

        self.viewport_3d = Viewport3D(self)
        v_splitter.addWidget(self.viewport_3d)

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setMinimumHeight(240)

        self.charts_2d = Charts2DWidget(self)
        self.charts_2d.playheadMoved.connect(self._on_chart_playhead_moved)
        self.charts_2d.playbackToggled.connect(self._sync_playback_toggle)
        self.charts_2d.stepForwardClicked.connect(self._step_forward)
        self.charts_2d.stepBackwardClicked.connect(self._step_backward)
        self.charts_2d.speedChanged.connect(self._on_playback_speed_changed)
        self.bottom_tabs.addTab(self.charts_2d, "📊 Seismic Waveforms & Dynamics")

        self.audit_tab = ISDesignAuditTab(self)
        self.bottom_tabs.addTab(self.audit_tab, "📋 IS Design Audit (IS 456 / 2911 / 800)")

        v_splitter.addWidget(self.bottom_tabs)

        # Splitter ratios
        v_splitter.setStretchFactor(0, 7)
        v_splitter.setStretchFactor(1, 3)
        h_splitter.setStretchFactor(0, 2)
        h_splitter.setStretchFactor(1, 8)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_fps = QLabel("Analytical Solve: < 1 ms | 60 FPS")
        self.status_bar.addPermanentWidget(self.lbl_fps)

    def _regenerate_signals(self):
        """Regenerates the accelerogram and Newmark sliding curve."""
        source_idx = self.panel_seismic.combo_source.currentIndex()
        pga = max(0.01, self.seismic.horizontal_pga)

        if source_idx == 0:
            self.time_arr, self.accel_arr = generate_ricker_wavelet(pga_g=pga, duration_sec=8.0)
        elif source_idx == 1:
            self.time_arr, self.accel_arr = generate_harmonic_sweep(pga_g=pga, duration_sec=12.0)
        # Yield acceleration approximation based on static sliding capacity
        ky = max(0.05, (self.results.fs_sliding * 0.5) if self.results.fs_sliding > 0 else 0.2)
        self.slip_arr, _ = compute_newmark_sliding_displacement(self.time_arr, self.accel_arr, yield_acceleration_ky=ky)

        # Dynamic pore-water pressure generation
        h_w = max(0.0, self.geom.total_height - self.seismic.water_table_depth)
        u_static = 9.81 * h_w
        if len(self.accel_arr) > 0:
            arias_cum = np.cumsum(self.accel_arr ** 2)
            arias_norm = arias_cum / max(1e-6, arias_cum[-1])
            delta_u = self.seismic.pore_pressure_ratio_ru * (self.soil.unit_weight * self.geom.total_height)
            self.pore_arr = u_static + (delta_u * arias_norm)
        else:
            self.pore_arr = np.array([])

        self.timeline_slider.setRange(0, len(self.time_arr) - 1)
        self.charts_2d.update_signals(self.time_arr, self.accel_arr, self.slip_arr, pore_arr=self.pore_arr, playhead_t=0.0)

    def recompute_and_render(self):
        """Executes the high-speed vectorized analytical physics engine and refreshes 3D view."""
        t_start = time.perf_counter()

        # 1. Physics computation (< 1 ms)
        self.results = evaluate_wall_stability(self.geom, self.soil, self.seismic)

        # 2. Update 3D Viewport
        self.viewport_3d.update_scene(self.geom, self.soil, self.seismic, self.results)

        # 3. Update 2D Dashboard Cards
        self.charts_2d.update_safety_metrics(self.results)

        # 4. Update IS Design Code Audit Checklist
        self._update_is_audit()

        t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        self.lbl_fps.setText(f"Analytical Solve: {t_elapsed_ms:.2f} ms | High-Speed 60 FPS")

    def _on_geom_changed(self, geom: RetainingWallGeometry):
        self.geom = geom
        self.recompute_and_render()
        self._regenerate_signals()

    def _on_shell_changed(self, shell_geom: CurvedShellGeometry, pier_geom: PierAndPileGeometry, num_bays: int):
        self.shell_geom = shell_geom
        self.pier_pile_geom.pier_width = pier_geom.pier_width
        self.pier_pile_geom.pier_depth = pier_geom.pier_depth
        self.pier_pile_geom.pier_height = pier_geom.pier_height
        self.num_bays = num_bays
        self._update_is_audit()

    def _on_strut_pile_changed(self, strut_sys: StrutSupportSystem, pier_pile: PierAndPileGeometry):
        self.strut_sys = strut_sys
        self.pier_pile_geom.pile_diameter = pier_pile.pile_diameter
        self.pier_pile_geom.pile_length = pier_pile.pile_length
        self.pier_pile_geom.rock_socket_length = pier_pile.rock_socket_length
        self._update_is_audit()

    def _update_is_audit(self):
        if hasattr(self, "audit_tab") and self.audit_tab is not None:
            self.audit_tab.update_audit(
                shell_geom=self.shell_geom,
                pier_pile_geom=self.pier_pile_geom,
                struts=self.strut_sys,
                soil=self.soil,
                seismic=self.seismic,
                standards=self.standards,
            )

    def _on_soil_changed(self, soil: SoilProperties):
        self.soil = soil
        self.recompute_and_render()
        self._regenerate_signals()

    def _on_seismic_changed(self, seismic: SeismicParams):
        self.seismic = seismic
        self.recompute_and_render()
        self._regenerate_signals()

    def _on_at2_loaded(self, path: str):
        try:
            self.time_arr, self.accel_arr, meta = parse_at2_file(path)
            ky = max(0.05, self.results.fs_sliding * 0.5)
            self.slip_arr, _ = compute_newmark_sliding_displacement(self.time_arr, self.accel_arr, yield_acceleration_ky=ky)
            self.timeline_slider.setRange(0, len(self.time_arr) - 1)
            self.charts_2d.update_signals(self.time_arr, self.accel_arr, self.slip_arr, playhead_t=0.0)
            self.status_bar.showMessage(f"Loaded earthquake record: {meta['event']} (PGA={meta['pga_g']:.3f}g)", 6000)
        except Exception as e:
            QMessageBox.critical(self, "Error Loading .AT2", f"Failed to parse strong-motion file:\n{e}")

    def _toggle_playback(self):
        self.is_playing = not self.is_playing
        speed = self.charts_2d.get_playback_speed()
        interval = max(2, int(16.0 / speed))

        if self.is_playing:
            self.btn_play.setText("⏸ Pause")
            self.charts_2d.btn_play.setText("⏸ Pause")
            self.anim_timer.start(interval)
        else:
            self.btn_play.setText("▶ Play Seismic Wave")
            self.charts_2d.btn_play.setText("▶ Play")
            self.anim_timer.stop()

    def _sync_playback_toggle(self, playing: bool):
        if self.is_playing != playing:
            self._toggle_playback()

    def _step_forward(self):
        if len(self.time_arr) > 0:
            next_idx = min(len(self.time_arr) - 1, self.playhead_idx + 1)
            self._on_scrubber_moved(next_idx)

    def _step_backward(self):
        if len(self.time_arr) > 0:
            prev_idx = max(0, self.playhead_idx - 1)
            self._on_scrubber_moved(prev_idx)

    def _on_playback_speed_changed(self, factor: float):
        if self.is_playing:
            interval = max(2, int(16.0 / factor))
            self.anim_timer.setInterval(interval)

    def _on_chart_playhead_moved(self, t: float):
        if len(self.time_arr) > 0:
            idx = int(np.clip(np.searchsorted(self.time_arr, t), 0, len(self.time_arr) - 1))
            self._on_scrubber_moved(idx)

    def _on_animation_step(self):
        if len(self.time_arr) == 0:
            return

        if self.playhead_idx + 1 >= len(self.time_arr):
            if not self.charts_2d.is_looping():
                self._toggle_playback()
                return
            self.playhead_idx = 0
        else:
            self.playhead_idx += 1

        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(self.playhead_idx)
        self.timeline_slider.blockSignals(False)

        current_t = self.time_arr[self.playhead_idx]
        current_accel = abs(self.accel_arr[self.playhead_idx])
        self.charts_2d.set_playhead(current_t)

        # Dynamic inertia pulsing
        self.seismic.horizontal_pga = float(current_accel)
        self.results = evaluate_wall_stability(self.geom, self.soil, self.seismic)
        slide_m = float(self.slip_arr[self.playhead_idx] / 100.0) if len(self.slip_arr) > self.playhead_idx else 0.0
        ripple = float(current_t * 6.0)
        self.viewport_3d.update_scene(
            self.geom,
            self.soil,
            self.seismic,
            self.results,
            warp_scale=1.5,
            slide_disp=slide_m,
            ripple_phase=ripple,
        )
        self.charts_2d.update_safety_metrics(self.results)

    def _on_scrubber_moved(self, val: int):
        if len(self.time_arr) > val:
            self.playhead_idx = val
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(val)
            self.timeline_slider.blockSignals(False)
            current_t = self.time_arr[val]
            self.charts_2d.set_playhead(current_t)
            slide_m = float(self.slip_arr[val] / 100.0) if len(self.slip_arr) > val else 0.0
            ripple = float(current_t * 6.0)
            self.viewport_3d.update_scene(
                self.geom,
                self.soil,
                self.seismic,
                self.results,
                slide_disp=slide_m,
                ripple_phase=ripple,
            )

    def _save_project(self):
        """Saves current geometry, soil, seismic parameters, results and signals to a .o3d bundle."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project Session",
            "retaining_wall_session.o3d",
            "orang3D Project Session (*.o3d);;All Files (*)",
        )
        if path:
            try:
                save_project_session(
                    path,
                    geom=self.geom,
                    soil=self.soil,
                    seismic=self.seismic,
                    results=self.results,
                    time_arr=self.time_arr,
                    accel_arr=self.accel_arr,
                    slip_arr=self.slip_arr,
                    pore_arr=self.pore_arr,
                )
                self.status_bar.showMessage(f"Project session saved successfully: {path}", 5000)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save project session:\n{e}")

    def _open_project(self):
        """Loads and applies an existing .o3d project session bundle."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project Session",
            "",
            "orang3D Project Session (*.o3d);;All Files (*)",
        )
        if path:
            try:
                session = load_project_session(path)
                self.geom = session.geom
                self.soil = session.soil
                self.seismic = session.seismic
                self.results = session.results
                self.time_arr = session.time_arr
                self.accel_arr = session.accel_arr
                self.slip_arr = session.slip_arr
                self.pore_arr = session.pore_arr

                self.panel_geom.set_geometry(self.geom)
                self.panel_soil.set_soil(self.soil)
                self.panel_seismic.set_seismic(self.seismic)

                self.charts_2d.update_signals(
                    time_arr=self.time_arr,
                    accel_arr=self.accel_arr,
                    slip_arr=self.slip_arr,
                    pore_arr=self.pore_arr,
                )
                self.charts_2d.update_safety_metrics(self.results)
                self.viewport_3d.update_scene(
                    self.geom, self.soil, self.seismic, self.results, slide_disp=0.0
                )
                self.status_bar.showMessage(f"Project session loaded: {path}", 5000)
            except CorruptProjectError as e:
                QMessageBox.critical(self, "Load Error", f"Corrupted or invalid project session file:\n{e}")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to open project session:\n{e}")

    def _export_mesh_dialog(self, fmt: str = "vtk"):
        """Exports 3D continuum mesh to VTK, STL, or Wavefront OBJ formats."""
        ext = fmt.lower()
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export 3D Mesh (.{ext.upper()})",
            f"retaining_wall.{ext}",
            f"{ext.upper()} Files (*.{ext});;All Files (*)",
        )
        if path:
            from ..mesher.hex_mesher import build_3d_wall_mesh
            mesh = build_3d_wall_mesh(self.geom, self.results)
            if ext == "vtk":
                export_mesh_to_vtk(mesh, path)
            elif ext == "stl":
                export_mesh_to_stl(mesh, path)
            elif ext == "obj":
                export_mesh_to_obj(mesh, path)
            self.status_bar.showMessage(f"Successfully exported 3D mesh to {path}", 5000)

    def _export_csv_dialog(self):
        """Exports seismic accelerogram and dynamic curves to RFC-4180 CSV."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Seismic Waveforms",
            "seismic_curves.csv",
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            export_signals_to_csv(
                path,
                time_arr=self.time_arr,
                accel_arr=self.accel_arr,
                slip_arr=self.slip_arr,
                pore_arr=self.pore_arr,
            )
            self.status_bar.showMessage(f"Successfully exported seismic curves to {path}", 5000)

    def _export_dxf_dialog(self):
        """Exports layered AutoCAD DXF construction drawing."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export AutoCAD DXF Construction Drawing",
            "retaining_wall_cad.dxf",
            "AutoCAD DXF Files (*.dxf);;All Files (*)",
        )
        if path:
            try:
                model = MultiStrutPiledWallModel(
                    shell=self.shell_geom,
                    piers=self.pier_pile_geom,
                    struts=self.strut_sys,
                )
                out = export_retaining_wall_dxf(
                    model=model,
                    file_path=path,
                    project_title=f"{APP_NAME} - Multi-Strut Piled Retaining Wall",
                    drawing_number="DWG-O3D-001",
                    num_bays=getattr(self, "num_bays", 3),
                )
                self.status_bar.showMessage(f"DXF Drawing exported successfully: {out}", 5000)
                QMessageBox.information(self, "CAD Export Complete", f"Layered AutoCAD DXF created:\n{out}")
            except Exception as e:
                QMessageBox.critical(self, "CAD Export Error", f"Failed to generate DXF:\n{e}")

    def _generate_report_dialog(self):
        """Generates comprehensive geotechnical calculation PDF report."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Generate Engineering PDF Report",
            "retaining_wall_report.pdf",
            "PDF Documents (*.pdf);;All Files (*)",
        )
        if path:
            try:
                generate_engineering_pdf_report(
                    output_path=path,
                    geom=self.geom,
                    soil=self.soil,
                    seismic=self.seismic,
                    results=self.results,
                    time_arr=self.time_arr,
                    slip_arr=self.slip_arr,
                )
                self.status_bar.showMessage(f"PDF Engineering Report generated: {path}", 5000)
                QMessageBox.information(
                    self,
                    "Report Generated",
                    f"Engineering calculation report successfully generated:\n{path}",
                )
            except Exception as e:
                QMessageBox.critical(self, "Report Error", f"Failed to generate PDF report:\n{e}")

    def _run_kratos_simulation(self):
        """Launches asynchronous Kratos GeoMechanics dynamic FEA simulation."""
        if not KRATOS_AVAILABLE:
            QMessageBox.warning(self, "Kratos Unavailable", "KratosMultiphysics is not installed.")
            return

        if len(self.time_arr) == 0:
            self._regenerate_signals()

        self.btn_kratos.setEnabled(False)
        self.btn_kratos.setText("⏳ Kratos Solving...")
        self.status_bar.showMessage("Executing Kratos GeoMechanics dynamic simulation in background thread...")

        self.kratos_worker = KratosSimulationWorker(
            geom=self.geom,
            soil=self.soil,
            seismic=self.seismic,
            time_arr=self.time_arr,
            accel_arr=self.accel_arr,
            parent=self,
        )
        self.kratos_worker.stepCompleted.connect(self._on_kratos_step)
        self.kratos_worker.simulationFinished.connect(self._on_kratos_finished)
        self.kratos_worker.simulationError.connect(self._on_kratos_error)
        self.kratos_worker.start()

    def _on_kratos_step(self, step: int, t: float, crest_disp: float, pore_p: float):
        self.status_bar.showMessage(f"Kratos FEA Step {step}/{len(self.time_arr)} (t={t:.2f}s | Crest Deflection={crest_disp*100:.2f} cm | Pore Pressure={pore_p:.1f} kPa)")

    def _on_kratos_finished(self, summary: dict):
        self.btn_kratos.setEnabled(True)
        self.btn_kratos.setText("⚙ Run Kratos GeoMechanics FEA")
        msg = f"Kratos FEA Completed: {summary['total_steps']} steps solved! Max Crest Deflection: {summary['max_crest_disp_cm']:.2f} cm"
        self.status_bar.showMessage(msg, 8000)
        QMessageBox.information(self, "Kratos FEA Complete", msg)

    def _on_kratos_error(self, err: str):
        self.btn_kratos.setEnabled(True)
        self.btn_kratos.setText("⚙ Run Kratos GeoMechanics FEA")
        QMessageBox.critical(self, "Kratos Solver Error", f"FEA simulation encountered an error:\n{err}")

    def closeEvent(self, event):
        if hasattr(self, "viewport_3d") and self.viewport_3d is not None:
            try:
                self.viewport_3d.close()
            except Exception:
                pass
        super().closeEvent(event)

