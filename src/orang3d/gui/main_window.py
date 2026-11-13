"""
Main Application Window for orang3D.
Houses the PyVista 3D Viewport, PyQtGraph 2D Dashboard, and Parameter Dock Panels.
"""

from functools import partial
import time
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QToolBar, QStatusBar, QLabel, QPushButton, QSlider,
    QComboBox, QFileDialog, QMessageBox, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon

from ..config import APP_NAME, APP_SUBTITLE, APP_VERSION, THEME, THEMES, ThemeMode, RegionalStandard
from ..units import UnitSystem
from ..models.wall_params import RetainingWallGeometry, SoilProperties, SeismicParams, AnalysisResults
from ..physics.stability import evaluate_wall_stability
from ..physics.sizing_advisor import evaluate_sizing_advisor
from ..physics.arch_wall_solver import evaluate_architectural_wall
from ..physics.surcharge import (
    AdjacentSurchargeParams,
    SurchargeLoadType,
    calculate_adjacent_surcharge_profile,
    evaluate_wall_stability_with_surcharge,
)
from ..physics.shell_arching import compute_shell_arching_partition
from ..physics.bnwf_solver import BNWFSimulationWorker, OPENSEES_AVAILABLE
from ..physics.opensees_3d_solver import ConstitutiveModelType, OpenSees3DFEAWorker
from ..physics.surrogate_engine import SurrogateInputs, predict_surrogate
from ..physics.kratos_solver import KratosSimulationWorker, KRATOS_AVAILABLE
from ..signals.synthetic import generate_ricker_wavelet, generate_harmonic_sweep, compute_newmark_sliding_displacement
from ..signals.at2_parser import parse_at2_file
from .viewport_3d import Viewport3D
from .charts_2d import Charts2DWidget
from .panels import (
    GeometryPanel, SoilPanel, SeismicPanel,
    ShellAndPierPanel, StrutAndPilePanel, ArchWallAndSurchargePanel, TerrainAndStudioPanel,
    ISDesignAuditTab, BNWFAndPINNTab,
    UQFragilityTab, EquationInspectorTab, TheoryComparisonTab,
)
from .dialogs import CalibrationWizardDialog, SensitivitySweepDialog
from ..models.advanced_wall_params import (
    WallSystemMode, MultiStrutPiledWallModel, CurvedShellGeometry, PierAndPileGeometry, StrutSupportSystem
)
from ..models.architectural_wall_params import ArchitecturalWallSpec
from ..models.is_code_params import IndianDesignStandards
from ..models.presets import BenchmarkPreset, get_benchmark_presets, get_preset
from ..io.dxf_export import export_retaining_wall_dxf, RetainingWallDXFExporter, EZDXF_AVAILABLE
from ..io.serialization import save_project_session, load_project_session, CorruptProjectError
from ..io.deck_export import export_opensees_bnwf_deck, export_kratos_deck, export_research_archive
from ..io.bim_export import export_wall_to_glb, export_wall_to_ifc
from ..physics.solver_registry import SolverTier, build_provenance
from ..io.mesh_export import (
    export_grid_mesh,
    export_mesh_to_vtk,
    export_mesh_to_stl,
    export_mesh_to_obj,
    export_signals_to_csv,
)
from ..io.report_generator import generate_engineering_pdf_report


class MainWindow(QMainWindow):
    """
    Primary desktop window for orang3D.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - {APP_SUBTITLE} (v{APP_VERSION})")

        # Explicit Window Flags ensuring Maximize, Minimize, and Close buttons are active
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )

        # Standard 16:9 desktop viewport ratio (1440x810 default, min 1152x648)
        self.resize(1440, 810)
        self.setMinimumSize(1152, 648)

        # State models
        self.geom = RetainingWallGeometry()
        self.soil = SoilProperties()
        self.seismic = SeismicParams()
        self.results = AnalysisResults()

        # Advanced curved shell & strut-pile models (Phase 10 / v3 Phase 2)
        self.wall_mode: WallSystemMode = WallSystemMode.CANTILEVER
        self.shell_geom = CurvedShellGeometry()
        self.pier_pile_geom = PierAndPileGeometry()
        self.strut_sys = StrutSupportSystem()
        self.standards = IndianDesignStandards()
        self.num_bays = 3
        self.arching_results = None
        self.last_pinn_prediction = None
        self.arch_spec = ArchitecturalWallSpec()
        self.surcharge_params = AdjacentSurchargeParams()
        self.last_arch_summary = None
        self.last_surcharge_result = None
        self.bnwf_worker = None
        self.fea_3d_worker = None
        self.last_continuum_fea_result = None
        self.kratos_worker = None
        self._active_preset_note = ""
        self.unit_system: UnitSystem = UnitSystem.SI
        self.theme_mode: ThemeMode = ThemeMode.DARK
        self.current_terrain = None
        self.last_sizing_advice = None

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
        self._apply_theme_palette(ThemeMode.DARK)

    def _apply_theme_palette(self, theme_mode: ThemeMode | str) -> None:
        mode = ThemeMode(theme_mode)
        t = THEMES[mode]
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {t["background_dark"]};
                color: {t["text_primary"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }}
            QTabWidget::pane {{
                border: 1px solid {t["border"]};
                background: {t["surface_dark"]};
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background: {t["surface_dark"]};
                color: {t["text_secondary"]};
                padding: 8px 16px;
                border: 1px solid {t["border"]};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background: {t["surface_elevated"]};
                color: {t["accent_orange"]};
                font-weight: bold;
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {t["border"]};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 14px;
                background-color: {t["surface_dark"]};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: {t["accent_orange"]};
            }}
            QDoubleSpinBox, QComboBox, QLineEdit {{
                background-color: {t["surface_elevated"]};
                color: {t["text_primary"]};
                border: 1px solid {t["border"]};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QPushButton {{
                background-color: {t["accent_orange"]};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t["accent_orange_hover"]};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {t["surface_elevated"]};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {t["accent_orange"]};
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
                background-color: {t["surface_dark"]};
                color: {t["text_secondary"]};
                border-top: 1px solid {t["border"]};
            }}
        """)

    def set_theme_mode(self, theme_mode: ThemeMode | str) -> None:
        """Switches UI theme between Dark Engineering and Light Studio modes."""
        self.theme_mode = ThemeMode(theme_mode)
        self._apply_theme_palette(self.theme_mode)
        if hasattr(self, "viewport_3d") and self.viewport_3d is not None:
            self.viewport_3d.set_theme_mode(self.theme_mode)
        if hasattr(self, "act_theme_dark") and hasattr(self, "act_theme_light"):
            self.act_theme_dark.setChecked(self.theme_mode == ThemeMode.DARK)
            self.act_theme_light.setChecked(self.theme_mode == ThemeMode.LIGHT)

    def reset_to_16_9_ratio(self, base_width: int = 1440) -> None:
        """Restores the application window to a crisp 16:9 widescreen desktop aspect ratio."""
        if self.isMaximized():
            self.showNormal()
        height = int(round(base_width * (9.0 / 16.0)))
        self.resize(base_width, height)

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

        menu_presets = menu_file.addMenu("Load Benchmark Preset...")
        self.preset_actions = {}
        for preset in get_benchmark_presets():
            act_preset = menu_presets.addAction(preset.title)
            act_preset.setToolTip(preset.reference)
            act_preset.triggered.connect(partial(self._on_preset_triggered, preset.preset_id))
            self.preset_actions[preset.preset_id] = act_preset

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
        act_exp_dxf.triggered.connect(lambda: self._export_dxf_dialog(include_3d=False))
        act_exp_dxf3d = menu_export.addAction("Export 3D CAD Assembly (.DXF)...")
        act_exp_dxf3d.triggered.connect(lambda: self._export_dxf_dialog(include_3d=True))
        act_exp_vtk = menu_export.addAction("Export 3D Mesh (.VTK)...")
        act_exp_vtk.triggered.connect(lambda: self._export_mesh_dialog("vtk"))
        act_exp_stl = menu_export.addAction("Export 3D Mesh (.STL)...")
        act_exp_stl.triggered.connect(lambda: self._export_mesh_dialog("stl"))
        act_exp_obj = menu_export.addAction("Export 3D Mesh (.OBJ)...")
        act_exp_obj.triggered.connect(lambda: self._export_mesh_dialog("obj"))
        act_exp_glb = menu_export.addAction("Export Architectural 3D BIM (.GLB)...")
        act_exp_glb.triggered.connect(self._export_glb_dialog)
        act_exp_ifc = menu_export.addAction("Export IFC 4 BIM Model (.IFC)...")
        act_exp_ifc.triggered.connect(self._export_ifc_dialog)
        menu_export.addSeparator()
        act_exp_csv = menu_export.addAction("Export Seismic Waveforms (.CSV)...")
        act_exp_csv.triggered.connect(self._export_csv_dialog)
        menu_export.addSeparator()
        act_exp_ops = menu_export.addAction("Export OpenSeesPy BNWF Deck (.py)...")
        act_exp_ops.triggered.connect(self._export_opensees_deck_dialog)
        act_exp_kratos = menu_export.addAction("Export Kratos GeoMechanics Deck...")
        act_exp_kratos.triggered.connect(self._export_kratos_deck_dialog)
        act_exp_archive = menu_export.addAction("Export Research Archive (.h5 + .json)...")
        act_exp_archive.triggered.connect(self._export_research_archive_dialog)

        menu_tools = menu_bar.addMenu("&Tools")
        self.act_lab_calibration = menu_tools.addAction("Lab Soil Calibration Wizard (CSV)...")
        self.act_lab_calibration.triggered.connect(self._open_calibration_wizard)
        self.act_sensitivity_sweep = menu_tools.addAction("Parametric Sensitivity Sweep...")
        self.act_sensitivity_sweep.triggered.connect(self._open_sensitivity_sweep)

        menu_view = menu_bar.addMenu("&View")
        menu_theme = menu_view.addMenu("Theme")
        self.act_theme_dark = menu_theme.addAction("Dark Engineering")
        self.act_theme_dark.setCheckable(True)
        self.act_theme_dark.setChecked(True)
        self.act_theme_dark.triggered.connect(lambda: self.set_theme_mode(ThemeMode.DARK))

        self.act_theme_light = menu_theme.addAction("Light Studio")
        self.act_theme_light.setCheckable(True)
        self.act_theme_light.setChecked(False)
        self.act_theme_light.triggered.connect(lambda: self.set_theme_mode(ThemeMode.LIGHT))

        menu_cam = menu_view.addMenu("Camera Presets")
        for label, key in (
            ("Isometric", "isometric"),
            ("Plan", "plan"),
            ("Front Elevation", "front"),
            ("Cross-Section", "cross_section"),
        ):
            act_cam = menu_cam.addAction(label)
            act_cam.triggered.connect(partial(self._set_camera_preset_safe, key))

        menu_view.addSeparator()
        self.act_maximize = menu_view.addAction("Maximize Window")
        self.act_maximize.setShortcut("F11")
        self.act_maximize.triggered.connect(
            lambda: self.showNormal() if self.isMaximized() else self.showMaximized()
        )

        menu_aspect = menu_view.addMenu("Window Aspect Ratio (16:9)")
        act_16_9_std = menu_aspect.addAction("Standard 16:9 (1440 × 810)")
        act_16_9_std.triggered.connect(lambda: self.reset_to_16_9_ratio(1440))
        act_16_9_compact = menu_aspect.addAction("Compact 16:9 (1280 × 720)")
        act_16_9_compact.triggered.connect(lambda: self.reset_to_16_9_ratio(1280))
        act_16_9_large = menu_aspect.addAction("Large 16:9 (1600 × 900)")
        act_16_9_large.triggered.connect(lambda: self.reset_to_16_9_ratio(1600))
        act_16_9_fhd = menu_aspect.addAction("Full HD 16:9 (1920 × 1080)")
        act_16_9_fhd.triggered.connect(lambda: self.reset_to_16_9_ratio(1920))

        menu_view.addSeparator()
        self.act_snapshot_4k = menu_view.addAction("Save 4K Viewport Render (.png)...")
        self.act_snapshot_4k.triggered.connect(self._save_4k_snapshot_dialog)

        # Row 1: Project & System Toolbar
        self.toolbar = QToolBar("Project & System Controls", self)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        btn_open = QPushButton("📂 Open")
        btn_open.setToolTip("Open saved .o3d project session (Ctrl+O)")
        btn_open.clicked.connect(self._open_project)
        self.toolbar.addWidget(btn_open)

        btn_save = QPushButton("💾 Save")
        btn_save.setToolTip("Save project session as .o3d bundle (Ctrl+S)")
        btn_save.clicked.connect(self._save_project)
        self.toolbar.addWidget(btn_save)

        btn_report = QPushButton("📄 PDF Report")
        btn_report.setToolTip("Generate comprehensive geotechnical calculation report (Ctrl+P)")
        btn_report.clicked.connect(self._generate_report_dialog)
        self.toolbar.addWidget(btn_report)

        btn_dxf = QPushButton("📐 AutoCAD DXF")
        btn_dxf.setToolTip("Export detailed layered AutoCAD DXF construction drawings with reinforcement detailing")
        btn_dxf.clicked.connect(self._export_dxf_dialog)
        self.toolbar.addWidget(btn_dxf)

        self.toolbar.addSeparator()

        self.toolbar.addWidget(QLabel("System:"))
        self.combo_wall_mode = QComboBox()
        self.combo_wall_mode.addItem("Cantilever Wall", WallSystemMode.CANTILEVER)
        self.combo_wall_mode.addItem("Curved Shell + Piles", WallSystemMode.MULTI_STRUT_CURVED_SHELL)
        self.combo_wall_mode.addItem("Architectural Walls", WallSystemMode.ARCHITECTURAL)
        self.combo_wall_mode.currentIndexChanged.connect(self._on_wall_mode_changed)
        self.toolbar.addWidget(self.combo_wall_mode)

        self.toolbar.addWidget(QLabel("  Units:"))
        self.combo_units = QComboBox()
        self.combo_units.addItem("SI (m, kN, kPa)", UnitSystem.SI)
        self.combo_units.addItem("Imperial (ft, kip, ksf)", UnitSystem.IMPERIAL)
        self.combo_units.currentIndexChanged.connect(self._on_unit_system_changed)
        self.toolbar.addWidget(self.combo_units)

        self.toolbar.addSeparator()

        btn_reset_cam = QPushButton("Reset 3D Camera")
        btn_reset_cam.clicked.connect(lambda: self.viewport_3d.plotter.reset_camera())
        self.toolbar.addWidget(btn_reset_cam)

        btn_export = QPushButton("Export 3D Mesh")
        btn_export.clicked.connect(lambda: self._export_mesh_dialog("vtk"))
        self.toolbar.addWidget(btn_export)

        # Row 2: Simulation & SSI Analysis Toolbar (breaks to a balanced second row for 16:9 displays)
        self.addToolBarBreak()
        self.sim_toolbar = QToolBar("Simulation & SSI Analysis Controls", self)
        self.sim_toolbar.setMovable(False)
        self.addToolBar(self.sim_toolbar)

        self.btn_play = QPushButton("▶ Play Wave")
        self.btn_play.setToolTip("Play / pause simulated dynamic seismic ground motion wave")
        self.btn_play.clicked.connect(self._toggle_playback)
        self.sim_toolbar.addWidget(self.btn_play)

        self.sim_toolbar.addWidget(QLabel("  Timeline:"))
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.valueChanged.connect(self._on_scrubber_moved)
        self.timeline_slider.setMinimumWidth(150)
        self.sim_toolbar.addWidget(self.timeline_slider)

        self.sim_toolbar.addSeparator()

        self.combo_bnwf_mode = QComboBox()
        self.combo_bnwf_mode.addItem("BNWF Dynamic", "dynamic")
        self.combo_bnwf_mode.addItem("BNWF Pushover", "pushover")
        self.sim_toolbar.addWidget(self.combo_bnwf_mode)

        self.btn_bnwf = QPushButton("🧱 2D BNWF")
        self.btn_bnwf.setToolTip("Run nonlinear OpenSeesPy 2D Beam-on-Nonlinear-Winkler-Foundation (p-y/t-z/q-z) analysis")
        self.btn_bnwf.clicked.connect(self._run_bnwf_simulation)
        self.sim_toolbar.addWidget(self.btn_bnwf)

        self.sim_toolbar.addSeparator()

        self.combo_3d_model = QComboBox()
        self.combo_3d_model.addItem("3D PDMY02", ConstitutiveModelType.PDMY02)
        self.combo_3d_model.addItem("3D PIMY", ConstitutiveModelType.PIMY)
        self.combo_3d_model.addItem("3D Elastic", ConstitutiveModelType.ELASTIC_ISOTROPIC)
        self.sim_toolbar.addWidget(self.combo_3d_model)

        self.combo_3d_axes = QComboBox()
        self.combo_3d_axes.addItem("1D (X)", "1D")
        self.combo_3d_axes.addItem("2D (X+Y)", "2D")
        self.combo_3d_axes.addItem("3D (X+Z+Y)", "3D")
        self.sim_toolbar.addWidget(self.combo_3d_axes)

        self.btn_fea_3d = QPushButton("🧊 3D FEA")
        self.btn_fea_3d.setToolTip("Run full 3D OpenSeesPy continuum SSI FEA (stdBrick/brickUP + Coulomb interface + Lysmer dashpots)")
        self.btn_fea_3d.clicked.connect(self._run_3d_fea_simulation)
        self.sim_toolbar.addWidget(self.btn_fea_3d)

        self.sim_toolbar.addSeparator()

        self.btn_kratos = QPushButton("⚙ Kratos SSI")
        self.btn_kratos.setToolTip("Run multi-threaded deep dynamic Soil-Structure Interaction FEA with KratosMultiphysics (100% OSS)")
        self.btn_kratos.clicked.connect(self._run_kratos_simulation)
        self.sim_toolbar.addWidget(self.btn_kratos)

        # Central Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Horizontal Splitter: Left = Parameter Tabs, Right = Viewport + Charts
        h_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(h_splitter)

        # Left Tab Widget (Scrollable containers to preserve 16:9 vertical proportions)
        self.tabs = QTabWidget()
        self.tabs.setMaximumWidth(420)
        self.tabs.setMinimumWidth(330)

        def _make_scrollable(widget: QWidget) -> QScrollArea:
            sa = QScrollArea()
            sa.setWidget(widget)
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.NoFrame)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            sa.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            sa.setStyleSheet("background: transparent; border: none;")
            return sa

        self.panel_geom = GeometryPanel()
        self.panel_geom.geometryChanged.connect(self._on_geom_changed)
        self.tabs.addTab(_make_scrollable(self.panel_geom), "Cantilever Wall")

        self.panel_shell = ShellAndPierPanel()
        self.panel_shell.shellChanged.connect(self._on_shell_changed)
        self.tabs.addTab(_make_scrollable(self.panel_shell), "Curved Shell")

        self.panel_strut = StrutAndPilePanel()
        self.panel_strut.strutPileChanged.connect(self._on_strut_pile_changed)
        self.tabs.addTab(_make_scrollable(self.panel_strut), "Strut & Piles")

        self.panel_soil = SoilPanel()
        self.panel_soil.soilChanged.connect(self._on_soil_changed)
        self.panel_adv_soil = self.panel_soil.adv_soil_panel
        self.panel_adv_soil.openCalibrationWizardRequested.connect(self._open_calibration_wizard)
        self.tabs.addTab(_make_scrollable(self.panel_soil), "Soil Strata")

        self.panel_seismic = SeismicPanel()
        self.panel_seismic.seismicChanged.connect(self._on_seismic_changed)
        self.panel_seismic.recordLoaded.connect(self._on_at2_loaded)
        self.tabs.addTab(_make_scrollable(self.panel_seismic), "Disaster / Seismic")

        self.panel_arch = ArchWallAndSurchargePanel()
        self.panel_arch.archConfigChanged.connect(self._on_arch_config_changed)
        self.tabs.addTab(_make_scrollable(self.panel_arch), "Arch. & Surcharge")

        self.panel_terrain = TerrainAndStudioPanel()
        self.panel_terrain.terrainUpdated.connect(self._on_terrain_updated)
        self.panel_terrain.refreshAdvisorRequested.connect(self._refresh_sizing_advisor)
        self.panel_terrain.applyRecommendedGeometryRequested.connect(self._on_apply_recommended_geometry)
        self.tabs.addTab(_make_scrollable(self.panel_terrain), "Terrain & Studio")
        self.tabs.currentChanged.connect(self._on_left_tab_changed)

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
        self.bottom_tabs.addTab(self.audit_tab, "📋 Design Audit (IS / EC7 / AASHTO / ACI)")

        self.bnwf_pinn_tab = BNWFAndPINNTab(self)
        self.bnwf_pinn_tab.pinnToggled.connect(lambda _: self._update_pinn_surrogate())
        self.bottom_tabs.addTab(self.bnwf_pinn_tab, "🔬 BNWF & PINN Envelope")

        self.uq_fragility_tab = UQFragilityTab(self)
        self.bottom_tabs.addTab(self.uq_fragility_tab, "📈 UQ & Seismic Fragility")

        self.equation_inspector_tab = EquationInspectorTab(self)
        self.bottom_tabs.addTab(self.equation_inspector_tab, "📐 Show the Math")

        self.comparison_tab = TheoryComparisonTab(self)
        self.bottom_tabs.addTab(self.comparison_tab, "⚖ Theory vs. FEA")

        v_splitter.addWidget(self.bottom_tabs)

        # Splitter ratios and initial 16:9 desktop allocations
        v_splitter.setStretchFactor(0, 7)
        v_splitter.setStretchFactor(1, 3)
        h_splitter.setStretchFactor(0, 2)
        h_splitter.setStretchFactor(1, 8)
        h_splitter.setSizes([360, 1080])
        v_splitter.setSizes([480, 260])

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

    def _current_multi_strut_model(self) -> MultiStrutPiledWallModel:
        """Builds the active MultiStrutPiledWallModel from panel state."""
        if self.pier_pile_geom.pier_height < self.shell_geom.panel_height:
            self.pier_pile_geom.pier_height = self.shell_geom.panel_height

        pier_h = self.pier_pile_geom.pier_height
        valid_levels = [lvl for lvl in self.strut_sys.strut_levels if 0.0 < lvl < pier_h]
        struts = self.strut_sys
        if len(valid_levels) != len(self.strut_sys.strut_levels):
            struts = StrutSupportSystem(
                strut_levels=valid_levels or [round(0.4 * pier_h, 2)],
                inclination_angle=self.strut_sys.inclination_angle,
                cross_section_area=self.strut_sys.cross_section_area,
                moment_of_inertia=self.strut_sys.moment_of_inertia,
                elastic_modulus=self.strut_sys.elastic_modulus,
                yield_strength=self.strut_sys.yield_strength,
                pre_stress_load=self.strut_sys.pre_stress_load,
                allowable_slenderness=self.strut_sys.allowable_slenderness,
                unbraced_length=self.strut_sys.unbraced_length,
                steel_grade=self.strut_sys.steel_grade,
            )

        return MultiStrutPiledWallModel(
            shell=self.shell_geom,
            piers=self.pier_pile_geom,
            struts=struts,
        )

    def _render_active_3d_scene(
        self,
        warp_scale: float | None = None,
        slide_disp: float = 0.0,
        ripple_phase: float = 0.0,
    ) -> None:
        """Renders Cantilever, Multi-Strut Curved Shell, or Architectural 3D scene."""
        if self.wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL:
            self.arching_results = compute_shell_arching_partition(self.shell_geom, self.soil)
            self.viewport_3d.update_multi_strut_scene(
                model=self._current_multi_strut_model(),
                soil=self.soil,
                seismic=self.seismic,
                num_bays=self.num_bays,
                arching_result=self.arching_results,
                warp_scale=warp_scale,
            )
        elif self.wall_mode == WallSystemMode.ARCHITECTURAL:
            self.viewport_3d.update_architectural_scene(
                spec=self.arch_spec,
                soil=self.soil,
                seismic=self.seismic,
                summary=self.last_arch_summary,
                surcharge=self.surcharge_params,
                warp_scale=warp_scale,
            )
        else:
            self.viewport_3d.update_scene(
                self.geom,
                self.soil,
                self.seismic,
                self.results,
                warp_scale=warp_scale,
                slide_disp=slide_disp,
                ripple_phase=ripple_phase,
                surcharge=self.surcharge_params,
            )

    def _update_pinn_surrogate(self) -> None:
        """Evaluates the sub-millisecond PINN surrogate and updates the BNWF/PINN tab."""
        if not hasattr(self, "bnwf_pinn_tab") or self.bnwf_pinn_tab is None:
            return
        if not self.bnwf_pinn_tab.is_pinn_enabled():
            return

        inputs = SurrogateInputs(
            panel_height=self.shell_geom.panel_height,
            bay_span=self.shell_geom.bay_span,
            shell_radius=self.shell_geom.radius,
            cohesion=self.soil.cohesion,
            friction_angle=self.soil.friction_angle,
            unit_weight=self.soil.unit_weight,
            pga_g=max(0.01, self.seismic.horizontal_pga),
            num_struts=len(self.strut_sys.strut_levels),
            pile_diameter=self.pier_pile_geom.pile_diameter,
            pile_length=self.pier_pile_geom.pile_length,
            wall_thickness=self.shell_geom.thickness,
        )
        self.last_pinn_prediction = predict_surrogate(inputs)
        self.bnwf_pinn_tab.update_pinn_prediction(self.last_pinn_prediction)

    def _on_wall_mode_changed(self, _index: int) -> None:
        raw_mode = self.combo_wall_mode.currentData()
        if raw_mode is None:
            return
        mode = WallSystemMode(raw_mode)
        if mode != self.wall_mode:
            self.wall_mode = mode
            self.recompute_and_render()

    def _on_left_tab_changed(self, index: int) -> None:
        if index == 0 and self.wall_mode != WallSystemMode.CANTILEVER:
            self.combo_wall_mode.setCurrentIndex(0)
        elif index in (1, 2) and self.wall_mode != WallSystemMode.MULTI_STRUT_CURVED_SHELL:
            self.combo_wall_mode.setCurrentIndex(1)

    def recompute_and_render(self):
        """Executes the high-speed vectorized analytical physics engine and refreshes 3D view."""
        t_start = time.perf_counter()

        # 1. Physics computation (< 1 ms)
        if self.wall_mode == WallSystemMode.ARCHITECTURAL:
            self.last_arch_summary = evaluate_architectural_wall(
                self.arch_spec, self.soil, self.seismic, use_3d_fea=False
            )
            self.results = self.last_arch_summary.analysis_results
            self.last_surcharge_result = (
                calculate_adjacent_surcharge_profile(
                    self.surcharge_params, self.geom.total_height, self.soil, self.seismic
                )
                if self.surcharge_params.load_type != SurchargeLoadType.NONE
                else None
            )
        elif self.surcharge_params.load_type != SurchargeLoadType.NONE:
            self.results, self.last_surcharge_result = evaluate_wall_stability_with_surcharge(
                self.geom, self.soil, self.seismic, self.surcharge_params
            )
        else:
            self.results = evaluate_wall_stability(self.geom, self.soil, self.seismic)
            self.last_surcharge_result = None

        if hasattr(self, "panel_arch") and self.panel_arch is not None:
            arch_msg = (
                self.last_arch_summary.summary_text
                if self.last_arch_summary is not None
                else "Switch top toolbar System -> 'Architectural Walls' to inspect 3D mesh."
            )
            p_sur = self.last_surcharge_result.total_thrust_kn_per_m if self.last_surcharge_result else 0.0
            y_sur = self.last_surcharge_result.resultant_elevation_m if self.last_surcharge_result else 0.0
            self.panel_arch.update_readouts(arch_msg, p_sur, y_sur)

        # 2. Update 3D Viewport (active system mode)
        self._render_active_3d_scene()

        # 3. Update 2D Dashboard Cards
        self.charts_2d.update_safety_metrics(self.results)

        # 4. Update IS Design Code Audit Checklist, PINN Surrogate, & Soil/UQ Context
        self._update_is_audit()
        self._update_pinn_surrogate()
        if hasattr(self, "panel_adv_soil") and self.panel_adv_soil is not None:
            self.panel_adv_soil.set_context(self.geom, self.soil)
        if hasattr(self, "uq_fragility_tab") and self.uq_fragility_tab is not None:
            self.uq_fragility_tab.set_context(
                self.geom, self.soil, self.seismic,
                shell_geom=self.shell_geom,
                pier_geom=self.pier_pile_geom,
                strut_sys=self.strut_sys,
            )
        if hasattr(self, "equation_inspector_tab") and self.equation_inspector_tab is not None:
            self.equation_inspector_tab.update_equations(
                geom=self.geom,
                soil=self.soil,
                seismic=self.seismic,
                results=self.results,
                shell_geom=self.shell_geom,
                arching_result=self.arching_results,
                wall_mode=self.wall_mode,
                preset_note=self._active_preset_note,
            )
        self._update_comparison_tab()
        self._refresh_sizing_advisor()

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
        self.recompute_and_render()

    def _on_strut_pile_changed(self, strut_sys: StrutSupportSystem, pier_pile: PierAndPileGeometry):
        self.strut_sys = strut_sys
        self.pier_pile_geom.pile_diameter = pier_pile.pile_diameter
        self.pier_pile_geom.pile_length = pier_pile.pile_length
        self.pier_pile_geom.rock_socket_length = pier_pile.rock_socket_length
        self.recompute_and_render()

    def _on_arch_config_changed(self, arch_spec: ArchitecturalWallSpec, surcharge_params: AdjacentSurchargeParams):
        prev_morph = self.arch_spec.morphology
        self.arch_spec = arch_spec
        self.surcharge_params = surcharge_params
        if arch_spec.morphology != prev_morph and self.wall_mode != WallSystemMode.ARCHITECTURAL:
            idx = self.combo_wall_mode.findData(WallSystemMode.ARCHITECTURAL)
            if idx >= 0:
                self.combo_wall_mode.setCurrentIndex(idx)
                return
        self.recompute_and_render()

    def _set_camera_preset_safe(self, preset: str) -> None:
        if hasattr(self, "viewport_3d") and self.viewport_3d is not None:
            self.viewport_3d.set_camera_preset(preset)

    def _save_4k_snapshot_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save 4K Viewport Render", "orang3d_studio_render_4k.png", "PNG Images (*.png)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        self.viewport_3d.save_high_res_snapshot(path, width=3840, height=2160)
        self.status_bar.showMessage(f"Saved 4K viewport render: {path}", 6000)

    def _on_terrain_updated(self, terrain, show_3d: bool, beta_deg: float, st_factor: float) -> None:
        self.current_terrain = terrain
        if hasattr(self, "viewport_3d") and self.viewport_3d is not None:
            self.viewport_3d.set_terrain(terrain, show_terrain=show_3d)
        if terrain is not None:
            self.status_bar.showMessage(
                f"Site terrain active: slope β={beta_deg:.1f}° | EC8/IS1893 S_T={st_factor:.2f}",
                6000,
            )

    def _refresh_sizing_advisor(self) -> None:
        if not hasattr(self, "panel_terrain") or self.panel_terrain is None:
            return
        std = (
            self.audit_tab.current_standard
            if hasattr(self, "audit_tab") and self.audit_tab is not None
            else RegionalStandard.STANDARD
        )
        sur = (
            self.surcharge_params
            if self.surcharge_params.load_type != SurchargeLoadType.NONE
            else None
        )
        advice = evaluate_sizing_advisor(
            geom=self.geom,
            soil=self.soil,
            seismic=self.seismic,
            standard=std,
            surcharge=sur,
            unit_system=self.unit_system,
        )
        self.last_sizing_advice = advice
        self.panel_terrain.update_advisor(advice)

    def _on_apply_recommended_geometry(self, new_geom: RetainingWallGeometry) -> None:
        self.geom = new_geom
        self.panel_geom.set_geometry(new_geom)
        self.recompute_and_render()
        self._regenerate_signals()
        self.status_bar.showMessage("Applied Sizing Advisor geometry recommendations.", 5000)

    def _on_unit_system_changed(self):
        u_sys = self.combo_units.currentData()
        if u_sys is not None:
            self.set_unit_system(UnitSystem(u_sys))

    def set_unit_system(self, unit_system: UnitSystem | str) -> None:
        """Switches UI controls, charts, 3D colorbars, and audit tables between SI and Imperial."""
        self.unit_system = UnitSystem(unit_system)
        if hasattr(self, "combo_units"):
            idx = self.combo_units.findData(self.unit_system)
            if idx >= 0 and self.combo_units.currentIndex() != idx:
                self.combo_units.blockSignals(True)
                self.combo_units.setCurrentIndex(idx)
                self.combo_units.blockSignals(False)

        for panel in (
            self.panel_geom,
            self.panel_soil,
            self.panel_seismic,
            self.panel_shell,
            self.panel_strut,
            self.panel_arch,
            self.panel_terrain,
            self.charts_2d,
            self.viewport_3d,
            self.audit_tab,
            self.comparison_tab,
        ):
            if hasattr(panel, "set_unit_system"):
                panel.set_unit_system(self.unit_system)

        self.status_bar.showMessage(
            f"Active display units: {'SI (m, kN, kPa)' if self.unit_system == UnitSystem.SI else 'Imperial (ft, kip, ksf)'}",
            5000,
        )

    def _update_is_audit(self):
        if hasattr(self, "audit_tab") and self.audit_tab is not None:
            self.audit_tab.update_audit(
                geom=self.geom,
                shell_geom=self.shell_geom,
                pier_pile_geom=self.pier_pile_geom,
                struts=self.strut_sys,
                soil=self.soil,
                seismic=self.seismic,
                results=self.results,
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
        if self.last_continuum_fea_result is not None and len(self.time_arr) > 0:
            n_fea = len(self.last_continuum_fea_result.time)
            if n_fea > 0:
                idx_fea = min(n_fea - 1, int(round(self.playhead_idx * (n_fea - 1) / max(1, len(self.time_arr) - 1))))
                self.viewport_3d.update_continuum_fea_scene(self.last_continuum_fea_result, step_idx=idx_fea)
        else:
            self._render_active_3d_scene(
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
            if self.last_continuum_fea_result is not None:
                n_fea = len(self.last_continuum_fea_result.time)
                if n_fea > 0:
                    idx_fea = min(n_fea - 1, int(round(val * (n_fea - 1) / max(1, len(self.time_arr) - 1))))
                    self.viewport_3d.update_continuum_fea_scene(self.last_continuum_fea_result, step_idx=idx_fea)
            else:
                self._render_active_3d_scene(
                    slide_disp=slide_m,
                    ripple_phase=ripple,
                )

    def _save_project(self):
        """Saves complete v2.0 project session (models, theme, units, surcharge, terrain, FEA cache)."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project Session",
            "retaining_wall_session.o3d",
            "orang3D Project Session (*.o3d);;All Files (*)",
        )
        if path:
            try:
                terrain_meta = {}
                if hasattr(self, "panel_terrain") and self.panel_terrain is not None and self.panel_terrain.current_terrain is not None:
                    terrain_meta = {
                        "mean_slope_deg": float(self.panel_terrain.mean_slope_deg),
                        "st_factor": float(self.panel_terrain.st_factor),
                        "bounds": list(self.panel_terrain.current_terrain.bounds),
                    }
                std = (
                    self.audit_tab.current_standard
                    if hasattr(self, "audit_tab") and self.audit_tab is not None
                    else RegionalStandard.STANDARD
                )
                fea_cache = {}
                if getattr(self, "last_continuum_result", None) is not None and len(self.last_continuum_result.crest_disp_history) > 0:
                    fea_cache["crest_disp_history_m"] = np.asarray(self.last_continuum_result.crest_disp_history, dtype=np.float64)
                    fea_cache["time_history_s"] = np.asarray(self.last_continuum_result.time_history, dtype=np.float64)
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
                    wall_mode=self.wall_mode,
                    shell_geom=self.shell_geom,
                    pier_pile_geom=self.pier_pile_geom,
                    strut_sys=self.strut_sys,
                    arch_spec=self.arch_spec,
                    surcharge_params=self.surcharge_params,
                    num_bays=getattr(self, "num_bays", 3),
                    regional_standard=std,
                    unit_system=self.unit_system,
                    theme_mode=self.theme_mode,
                    terrain_metadata=terrain_meta,
                    fea_cache=fea_cache,
                )
                self.status_bar.showMessage(f"Project session saved successfully: {path}", 5000)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save project session:\n{e}")

    def _open_project(self):
        """Loads and applies an existing v1/v2 .o3d project session bundle."""
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
                self.shell_geom = session.shell_geom
                self.pier_pile_geom = session.pier_pile_geom
                self.strut_sys = session.strut_sys
                self.arch_spec = session.arch_spec
                self.surcharge_params = session.surcharge_params
                self.num_bays = session.num_bays
                self.wall_mode = session.wall_mode

                self.panel_geom.set_geometry(self.geom)
                self.panel_soil.set_soil(self.soil)
                self.panel_seismic.set_seismic(self.seismic)
                if hasattr(self, "panel_shell"):
                    self.panel_shell.set_shell_and_piers(self.shell_geom, self.pier_pile_geom, self.num_bays)
                if hasattr(self, "panel_strut"):
                    self.panel_strut.set_strut_and_piles(self.strut_sys, self.pier_pile_geom)
                if hasattr(self, "audit_tab"):
                    self.audit_tab.set_standard(session.regional_standard)
                self.set_theme_mode(session.theme_mode)
                self.set_unit_system(session.unit_system)
                if hasattr(self, "combo_wall_mode"):
                    idx_m = self.combo_wall_mode.findData(self.wall_mode)
                    if idx_m >= 0:
                        self.combo_wall_mode.blockSignals(True)
                        self.combo_wall_mode.setCurrentIndex(idx_m)
                        self.combo_wall_mode.blockSignals(False)

                self.charts_2d.update_signals(
                    time_arr=self.time_arr,
                    accel_arr=self.accel_arr,
                    slip_arr=self.slip_arr,
                    pore_arr=self.pore_arr,
                )
                self.recompute_and_render()
                self.status_bar.showMessage(f"Project session loaded (v{session.schema_version}): {path}", 5000)
            except CorruptProjectError as e:
                QMessageBox.critical(self, "Load Error", f"Corrupted or invalid project session file:\n{e}")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to open project session:\n{e}")

    def _export_mesh_dialog(self, fmt: str = "vtk"):
        """Exports active 3D wall mesh (Cantilever or Multi-Strut Shell) to VTK, STL, or OBJ."""
        ext = fmt.lower()
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export 3D Mesh (.{ext.upper()})",
            f"retaining_wall.{ext}",
            f"{ext.upper()} Files (*.{ext});;All Files (*)",
        )
        if not path:
            return
        try:
            if (
                self.wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL
                and self.viewport_3d.active_wall_mesh is not None
            ):
                export_grid_mesh(self.viewport_3d.active_wall_mesh, path, fmt=ext)
            elif ext == "vtk":
                export_mesh_to_vtk(self.geom, self.results, path)
            elif ext == "stl":
                export_mesh_to_stl(self.geom, self.results, path)
            elif ext == "obj":
                export_mesh_to_obj(self.geom, self.results, path)
            else:
                from ..mesher.hex_mesher import build_3d_wall_mesh
                export_grid_mesh(build_3d_wall_mesh(self.geom, self.results), path, fmt=ext)
            self.status_bar.showMessage(f"Successfully exported 3D mesh to {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Mesh Export Error", f"Failed to export 3D mesh:\n{e}")

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

    def _export_dxf_dialog(self, include_3d: bool = False):
        """Exports layered AutoCAD DXF construction drawing (with optional 3D entities)."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export AutoCAD DXF Construction Drawing",
            "retaining_wall_3d.dxf" if include_3d else "retaining_wall_cad.dxf",
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
                    include_3d=include_3d,
                )
                self.status_bar.showMessage(f"DXF Drawing exported successfully: {out}", 5000)
                QMessageBox.information(self, "CAD Export Complete", f"Layered AutoCAD DXF created:\n{out}")
            except Exception as e:
                QMessageBox.critical(self, "CAD Export Error", f"Failed to generate DXF:\n{e}")

    def _export_glb_dialog(self):
        """Exports active 3D retaining wall mesh to binary glTF 2.0 (.glb)."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Architectural 3D BIM (.GLB)",
            "retaining_wall.glb",
            "glTF Binary (*.glb);;All Files (*)",
        )
        if not path:
            return
        try:
            active_mesh = getattr(self.viewport_3d, "active_wall_mesh", None)
            arch_spec = self.arch_spec if self.wall_mode == WallSystemMode.ARCHITECTURAL else None
            out = export_wall_to_glb(
                path,
                self.geom,
                self.results,
                arch_spec=arch_spec,
                active_mesh=active_mesh,
            )
            self.status_bar.showMessage(f"Exported 3D GLB model: {out}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "GLB Export Error", f"Failed to export GLB:\n{e}")

    def _export_ifc_dialog(self):
        """Exports retaining wall assembly to IFC 4 BIM format (.ifc)."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export IFC 4 BIM Model",
            "retaining_wall.ifc",
            "IFC 4 Files (*.ifc);;All Files (*)",
        )
        if not path:
            return
        try:
            ms_model = (
                MultiStrutPiledWallModel(
                    shell=self.shell_geom,
                    piers=self.pier_pile_geom,
                    struts=self.strut_sys,
                )
                if self.wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL
                else None
            )
            std = self.audit_tab.current_standard.value if hasattr(self, "audit_tab") else "STANDARD"
            out = export_wall_to_ifc(
                path,
                self.geom,
                self.results,
                multi_strut_model=ms_model,
                num_bays=getattr(self, "num_bays", 3),
                standard_name=std,
            )
            self.status_bar.showMessage(f"Exported IFC 4 BIM model: {out}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "IFC Export Error", f"Failed to export IFC 4:\n{e}")

    def _export_opensees_deck_dialog(self):
        """Exports standalone runnable OpenSeesPy 2D BNWF verification script (.py)."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Runnable OpenSeesPy Deck",
            "bnwf_verification_deck.py",
            "Python Scripts (*.py);;All Files (*)",
        )
        if not path:
            return
        try:
            model = MultiStrutPiledWallModel(
                shell=self.shell_geom,
                piers=self.pier_pile_geom,
                struts=self.strut_sys,
            )
            slope_deg = float(self.panel_terrain.mean_slope_deg) if hasattr(self, "panel_terrain") else 0.0
            out = export_opensees_bnwf_deck(
                path,
                model=model,
                soil=self.soil,
                time_arr=self.time_arr,
                accel_arr=self.accel_arr,
                slope_angle=slope_deg,
            )
            self.status_bar.showMessage(f"Exported OpenSeesPy verification deck: {out}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Deck Export Error", f"Failed to export OpenSeesPy deck:\n{e}")

    def _export_kratos_deck_dialog(self):
        """Exports Kratos GeoMechanics MDPA + ProjectParameters.json folder."""
        out_dir = QFileDialog.getExistingDirectory(self, "Select Folder for Kratos GeoMechanics Deck")
        if not out_dir:
            return
        try:
            files = export_kratos_deck(
                out_dir,
                geom=self.geom,
                soil=self.soil,
                seismic=self.seismic,
                time_arr=self.time_arr,
                accel_arr=self.accel_arr,
            )
            self.status_bar.showMessage(f"Exported Kratos deck to {out_dir}", 5000)
            QMessageBox.information(self, "Kratos Deck Exported", "\n".join(files.values()))
        except Exception as e:
            QMessageBox.critical(self, "Kratos Deck Error", f"Failed to export Kratos deck:\n{e}")

    def _export_research_archive_dialog(self):
        """Exports HDF5 simulation tensors + companion JSON provenance manifest."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Research HDF5 Archive",
            "orang3d_research_archive.h5",
            "HDF5 Archives (*.h5);;All Files (*)",
        )
        if not path:
            return
        try:
            prov = build_provenance(
                SolverTier.L0_ANALYTICAL,
                element_types=["MononobeOkabe", "NewmarkSlidingBlock"],
                constitutive_model="Limit Equilibrium",
            )
            out = export_research_archive(
                path,
                geom=self.geom,
                soil=self.soil,
                seismic=self.seismic,
                results=self.results,
                provenance=prov,
                time_arr=self.time_arr,
                accel_arr=self.accel_arr,
                slip_arr=self.slip_arr,
                pore_arr=self.pore_arr,
            )
            self.status_bar.showMessage(f"Exported research archive: {out['hdf5']}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Archive Export Error", f"Failed to export archive:\n{e}")

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
                    filepath=path,
                    geom=self.geom,
                    soil=self.soil,
                    seismic=self.seismic,
                    results=self.results,
                    regional_standard=self.audit_tab.current_standard,
                    time_arr=self.time_arr,
                    slip_arr=self.slip_arr,
                    unit_system=self.unit_system,
                )
                self.status_bar.showMessage(f"PDF Engineering Report generated: {path}", 5000)
                QMessageBox.information(
                    self,
                    "Report Generated",
                    f"Engineering calculation report successfully generated:\n{path}",
                )
            except Exception as e:
                QMessageBox.critical(self, "Report Error", f"Failed to generate PDF report:\n{e}")

    def _run_bnwf_simulation(self):
        """Launches or cancels asynchronous OpenSeesPy 2D BNWF SSI simulation."""
        if self.bnwf_worker is not None and self.bnwf_worker.isRunning():
            self.bnwf_worker.cancel()
            self.btn_bnwf.setEnabled(False)
            self.btn_bnwf.setText("⏳ Cancelling...")
            self.status_bar.showMessage("Cancelling OpenSees 2D BNWF simulation...")
            return

        if not OPENSEES_AVAILABLE:
            QMessageBox.warning(self, "OpenSeesPy Unavailable", "OpenSeesPy is not installed.")
            return

        if len(self.time_arr) < 2:
            self._regenerate_signals()

        bnwf_mode = str(self.combo_bnwf_mode.currentData() or "dynamic")
        self.btn_bnwf.setText("⏹ Cancel BNWF")
        self.status_bar.showMessage(f"Running OpenSeesPy 2D BNWF ({bnwf_mode}) in background thread...")

        self.bnwf_worker = BNWFSimulationWorker(
            model=self._current_multi_strut_model(),
            soil=self.soil,
            time_arr=self.time_arr,
            accel_arr=self.accel_arr,
            slope_angle=self.seismic.backfill_slope,
            mode=bnwf_mode,
            parent=self,
        )
        self.bnwf_worker.stageCompleted.connect(self._on_bnwf_stage)
        self.bnwf_worker.stepCompleted.connect(self._on_bnwf_step)
        self.bnwf_worker.simulationFinished.connect(self._on_bnwf_finished)
        self.bnwf_worker.simulationError.connect(self._on_bnwf_error)
        self.bnwf_worker.start()

    def _on_bnwf_stage(self, stage_idx: int, stage_name: str):
        self.status_bar.showMessage(f"OpenSees BNWF Stage {stage_idx}: {stage_name}")

    def _on_bnwf_step(self, step: int, t: float, crest_u: float, max_m: float):
        self.status_bar.showMessage(
            f"OpenSees BNWF Step {step}/{len(self.time_arr)} "
            f"(t={t:.2f}s | Crest Disp={crest_u*100:.2f} cm | Max Moment={max_m:.1f} kNm)"
        )

    def _on_bnwf_finished(self, summary: dict):
        self.btn_bnwf.setEnabled(True)
        self.btn_bnwf.setText("🧱 Run 2D BNWF")

        status = summary.get("status", "UNKNOWN")
        if status == "CANCELLED":
            self.status_bar.showMessage("OpenSees 2D BNWF simulation cancelled.", 5000)
            return

        elapsed = float(summary.get("elapsed_seconds", 0.0))
        if summary.get("mode") == "pushover" and "pushover" in summary:
            self.bnwf_pinn_tab.update_bnwf_pushover(summary["pushover"], elapsed_seconds=elapsed)
        elif "result" in summary and summary["result"] is not None:
            self.bnwf_pinn_tab.update_bnwf_dynamic(summary["result"], elapsed_seconds=elapsed)
            if hasattr(self, "comparison_tab") and self.comparison_tab is not None:
                self.comparison_tab.set_bnwf_result(summary["result"])
                self._update_comparison_tab()

        self.bottom_tabs.setCurrentWidget(self.bnwf_pinn_tab)
        msg = (
            f"OpenSees BNWF Complete ({status}): {summary.get('total_steps', 0)} steps | "
            f"Max Crest Disp: {summary.get('max_crest_disp_cm', 0.0):.2f} cm"
        )
        self.status_bar.showMessage(msg, 8000)

    def _on_bnwf_error(self, err: str):
        self.btn_bnwf.setEnabled(True)
        self.btn_bnwf.setText("🧱 Run 2D BNWF")
        QMessageBox.critical(self, "OpenSees BNWF Error", f"2D BNWF simulation failed:\n{err}")

    def _run_3d_fea_simulation(self):
        """Launches or cancels asynchronous OpenSeesPy 3D Continuum SSI FEA simulation."""
        if self.fea_3d_worker is not None and self.fea_3d_worker.isRunning():
            self.fea_3d_worker.cancel()
            self.btn_fea_3d.setEnabled(False)
            self.btn_fea_3d.setText("⏳ Cancelling...")
            self.status_bar.showMessage("Cancelling OpenSees 3D Continuum FEA...")
            return

        if not OPENSEES_AVAILABLE:
            QMessageBox.warning(self, "OpenSeesPy Unavailable", "OpenSeesPy is not installed.")
            return

        if len(self.time_arr) < 2:
            self._regenerate_signals()

        # Subsample if very dense so interactive desktop solve completes smoothly
        stride = max(1, len(self.time_arr) // 60)
        t_sub = self.time_arr[::stride]
        ax_sub = self.accel_arr[::stride]
        axes_mode = str(self.combo_3d_axes.currentData() or "1D")
        ay_sub = 0.50 * ax_sub if axes_mode in ("2D", "3D") else None
        az_sub = 0.65 * ax_sub if axes_mode == "3D" else None
        c_model = self.combo_3d_model.currentData() or ConstitutiveModelType.PDMY02
        use_up = self.seismic.water_table_depth < self.geom.total_height

        self.btn_fea_3d.setText("⏹ Cancel 3D FEA")
        self.status_bar.showMessage(
            f"Running OpenSeesPy 3D Continuum FEA ({c_model.value}, {axes_mode}, u-p={use_up})..."
        )

        self.fea_3d_worker = OpenSees3DFEAWorker(
            geom=self.geom,
            soil=self.soil,
            seismic=self.seismic,
            time_arr=t_sub,
            accel_x_g=ax_sub,
            accel_y_g=ay_sub,
            accel_z_g=az_sub,
            constitutive_model=c_model,
            use_up=use_up,
            wall_mode=self.wall_mode,
            multi_strut_model=self._current_multi_strut_model()
            if self.wall_mode == WallSystemMode.MULTI_STRUT_CURVED_SHELL
            else None,
            parent=self,
        )
        self.fea_3d_worker.stepCompleted.connect(self._on_3d_fea_step)
        self.fea_3d_worker.simulationFinished.connect(self._on_3d_fea_finished)
        self.fea_3d_worker.simulationError.connect(self._on_3d_fea_error)
        self.fea_3d_worker.start()

    def _on_3d_fea_step(self, step: int, t: float, crest_u: float, thrust_kn_m: float):
        self.status_bar.showMessage(
            f"3D Continuum FEA Step {step + 1} (t={t:.2f}s | Crest Disp={crest_u * 100:.2f} cm | "
            f"Thrust={thrust_kn_m:.1f} kN/m)"
        )

    def _on_3d_fea_finished(self, summary: dict):
        self.btn_fea_3d.setEnabled(True)
        self.btn_fea_3d.setText("🧊 Run 3D FEA")
        status = summary.get("status", "UNKNOWN")
        if status == "CANCELLED":
            self.status_bar.showMessage("OpenSees 3D Continuum FEA cancelled.", 5000)
            return

        res = summary.get("result")
        if res is not None:
            self.last_continuum_fea_result = res
            idx_wall_p = self.viewport_3d.combo_scalar.findData("WallNormalStress_kPa")
            if idx_wall_p >= 0:
                self.viewport_3d.combo_scalar.blockSignals(True)
                self.viewport_3d.combo_scalar.setCurrentIndex(idx_wall_p)
                self.viewport_3d.combo_scalar.blockSignals(False)
            self.viewport_3d.update_continuum_fea_scene(
                res, step_idx=-1, scalar_name="WallNormalStress_kPa"
            )
            if hasattr(self, "comparison_tab") and self.comparison_tab is not None:
                self.comparison_tab.set_fea_result(res)
                self._update_comparison_tab()

        msg = (
            f"OpenSees 3D FEA ({status}): {summary.get('total_steps', 0)} steps | "
            f"Max Crest Disp={summary.get('max_crest_disp_cm', 0.0):.2f} cm | "
            f"Peak Thrust={summary.get('peak_thrust_kn_m', 0.0):.1f} kN/m | "
            f"Corner Ratio={summary.get('corner_concentration_ratio', 1.0):.2f}"
        )
        self.status_bar.showMessage(msg, 10000)

    def _on_3d_fea_error(self, err: str):
        self.btn_fea_3d.setEnabled(True)
        self.btn_fea_3d.setText("🧊 Run 3D FEA")
        QMessageBox.critical(self, "OpenSees 3D FEA Error", f"3D Continuum FEA failed:\n{err}")

    def _update_comparison_tab(self) -> None:
        """Refreshes Theory vs. BNWF vs. 3D FEA comparison plots and metrics."""
        if not hasattr(self, "comparison_tab") or self.comparison_tab is None:
            return
        self.comparison_tab.update_comparison(
            geom=self.geom,
            soil=self.soil,
            seismic=self.seismic,
            results=self.results,
            shell_geom=self.shell_geom,
            arching_result=self.arching_results,
        )

    def _on_preset_triggered(self, preset_id: str, _checked: bool = False) -> None:
        """Menu callback wrapper to load a benchmark preset cleanly."""
        self.load_preset(preset_id)

    def load_preset(self, preset_id: str) -> BenchmarkPreset:
        """Loads a curated textbook/centrifuge benchmark preset into active state and UI."""
        preset = get_preset(preset_id)
        self.geom = preset.geom
        self.soil = preset.soil
        self.seismic = preset.seismic
        self.shell_geom = preset.shell_geom
        self.pier_pile_geom = preset.pier_pile_geom
        self.strut_sys = preset.strut_sys
        self.num_bays = preset.num_bays
        self.wall_mode = preset.wall_mode
        self.arching_results = None
        self.last_continuum_fea_result = None
        self._active_preset_note = (
            f"<b>Preset Loaded:</b> {preset.title} ({preset.reference}) — "
            f"{preset.pedagogical_focus}"
        )

        # Sync left panels & toolbar mode without redundant intermediate recomputations
        idx_mode = self.combo_wall_mode.findData(preset.wall_mode)
        if idx_mode >= 0:
            self.combo_wall_mode.blockSignals(True)
            self.combo_wall_mode.setCurrentIndex(idx_mode)
            self.combo_wall_mode.blockSignals(False)

        self.panel_geom.set_geometry(preset.geom)
        self.panel_soil.set_soil(preset.soil)
        self.panel_seismic.set_seismic(preset.seismic)
        self.panel_shell.set_shell_and_piers(preset.shell_geom, preset.pier_pile_geom, preset.num_bays)
        self.panel_strut.set_strut_and_piles(preset.strut_sys, preset.pier_pile_geom)

        if hasattr(self, "comparison_tab") and self.comparison_tab is not None:
            self.comparison_tab.set_bnwf_result(None)
            self.comparison_tab.set_fea_result(None)

        self.recompute_and_render()
        self._regenerate_signals()
        self.status_bar.showMessage(f"Loaded benchmark preset: {preset.title}", 8000)
        return preset

    def _open_sensitivity_sweep(self) -> None:
        """Opens the Phase 5 Parametric Sensitivity Sweep dialog."""
        dlg = SensitivitySweepDialog(
            geom=self.geom,
            soil=self.soil,
            seismic=self.seismic,
            shell_geom=self.shell_geom,
            parent=self,
        )
        dlg.exec()

    def _open_calibration_wizard(self):
        """Opens the Phase 4 Lab Soil Calibration Wizard dialog and applies updates."""
        dlg = CalibrationWizardDialog(soil=self.soil, parent=self)
        dlg.calibrationApplied.connect(self._on_calibration_applied)
        dlg.exec()

    def _on_calibration_applied(self, test_type: str, payload: dict):
        """Pushes calibrated parameters from the Lab Wizard into SoilProperties & UI."""
        if test_type == CalibrationWizardDialog.TEST_RESONANT and hasattr(self, "panel_adv_soil"):
            self.panel_adv_soil.apply_calibrated_cyclic(
                gamma_r=payload.get("gamma_r"),
                curvature_a=payload.get("curvature_a"),
                d_min=payload.get("d_min"),
                d_max=payload.get("d_max"),
            )
        elif test_type == CalibrationWizardDialog.TEST_SWCC and hasattr(self, "panel_adv_soil"):
            if "swcc" in payload and payload["swcc"] is not None:
                self.panel_adv_soil.apply_calibrated_swcc(payload["swcc"])
        else:
            self.panel_soil.set_soil(self.soil)
        self.recompute_and_render()
        self.status_bar.showMessage(f"Applied {test_type} calibration to active project.", 6000)

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
        if hasattr(self, "uq_fragility_tab") and self.uq_fragility_tab is not None:
            self.uq_fragility_tab.cancel_worker()
        for worker in (self.bnwf_worker, self.fea_3d_worker, self.kratos_worker):
            if worker is not None and worker.isRunning():
                try:
                    worker.cancel()
                    worker.wait(1000)
                except Exception:
                    pass
        if hasattr(self, "viewport_3d") and self.viewport_3d is not None:
            try:
                self.viewport_3d.close()
            except Exception:
                pass
        super().closeEvent(event)

