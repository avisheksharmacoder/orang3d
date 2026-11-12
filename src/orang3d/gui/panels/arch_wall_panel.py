"""
Architectural Wall Morphologies & Adjacent Building / Traffic Surcharge Panel (Phase 7).

Manages:
  1. 5 Architectural Wall Morphologies (Stepped/Terraced, L-Corner/Wingwall,
     Counterfort/Buttress, Curved Plan-View, MSE/Gabion/Crib)
  2. Adjacent Building Footing & Traffic Strip Surcharges (Boussinesq / 2:1)
  3. Full SI <-> Imperial display unit synchronization
"""

from __future__ import annotations

from typing import List, Tuple
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...models.architectural_wall_params import (
    ArchWallMorphology,
    ArchitecturalWallSpec,
    CornerWingwallParams,
    CounterfortWallParams,
    CurvedPlanWallParams,
    MSEGabionWallParams,
    SteppedTerracedWallParams,
)
from ...physics.surcharge import AdjacentSurchargeParams, SurchargeLoadType
from ...units import UnitSystem, from_si_value, to_si_value, unit_label


class ArchWallAndSurchargePanel(QWidget):
    """Sidebar configuration tab for Phase 7 architectural walls & building surcharges."""

    archConfigChanged = Signal(object, object)  # (ArchitecturalWallSpec, AdjacentSurchargeParams)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.unit_system: UnitSystem = UnitSystem.SI
        self.arch_spec = ArchitecturalWallSpec()
        self.surcharge_params = AdjacentSurchargeParams()
        self._unit_spins: List[Tuple[QDoubleSpinBox, str, float, float, float, str]] = []
        self._build_ui()

    def _make_dspin(
        self,
        si_val: float,
        si_min: float,
        si_max: float,
        si_step: float,
        decimals: int = 2,
        quantity: str = "length",
        suffix: str = "",
    ) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setDecimals(decimals)
        sp.setRange(si_min, si_max)
        sp.setSingleStep(si_step)
        sp.setValue(si_val)
        if suffix:
            sp.setSuffix(f" {suffix}")
        elif quantity:
            sp.setSuffix(f" {unit_label(quantity, self.unit_system)}")
        sp.valueChanged.connect(self._on_changed)
        if quantity:
            self._unit_spins.append((sp, quantity, si_min, si_max, si_step, suffix))
        return sp

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # ------------------------------------------------------------------
        # 1. Architectural Wall Morphology
        # ------------------------------------------------------------------
        self.grp_arch = QGroupBox("Architectural Wall Morphology (SI: m)")
        arch_lay = QVBoxLayout(self.grp_arch)

        top_form = QFormLayout()
        self.combo_morphology = QComboBox()
        self.combo_morphology.addItem("Stepped / Terraced Tiers", ArchWallMorphology.STEPPED_TERRACED)
        self.combo_morphology.addItem("L-Corner & Wingwall", ArchWallMorphology.CORNER_WINGWALL)
        self.combo_morphology.addItem("Counterfort / Buttress", ArchWallMorphology.COUNTERFORT)
        self.combo_morphology.addItem("Curved Plan-View", ArchWallMorphology.CURVED_PLAN)
        self.combo_morphology.addItem("MSE / Gabion / Crib", ArchWallMorphology.MSE_GABION_CRIB)
        self.combo_morphology.currentIndexChanged.connect(self._on_morphology_changed)
        top_form.addRow("Typology:", self.combo_morphology)
        arch_lay.addLayout(top_form)

        self.morph_stack = QStackedWidget()

        # Page 0: Stepped / Terraced
        p_step = QWidget()
        f_step = QFormLayout(p_step)
        self.spin_tiers = QSpinBox()
        self.spin_tiers.setRange(2, 4)
        self.spin_tiers.setValue(self.arch_spec.stepped.num_tiers)
        self.spin_tiers.valueChanged.connect(self._on_changed)
        self.spin_tier_h = self._make_dspin(self.arch_spec.stepped.tier_height, 1.0, 6.0, 0.25, 2, "length")
        self.spin_bench_w = self._make_dspin(self.arch_spec.stepped.bench_width, 0.3, 8.0, 0.2, 2, "length")
        f_step.addRow("Number of Tiers:", self.spin_tiers)
        f_step.addRow("Tier Height H_i:", self.spin_tier_h)
        f_step.addRow("Bench Width W_bench:", self.spin_bench_w)
        self.morph_stack.addWidget(p_step)

        # Page 1: Corner & Wingwall
        p_cor = QWidget()
        f_cor = QFormLayout(p_cor)
        self.spin_corner_ang = self._make_dspin(self.arch_spec.corner.corner_angle_deg, 60.0, 150.0, 5.0, 1, "", "°")
        self.spin_primary_len = self._make_dspin(self.arch_spec.corner.primary_length, 2.0, 20.0, 0.5, 2, "length")
        self.spin_wing_len = self._make_dspin(self.arch_spec.corner.wing_length, 2.0, 20.0, 0.5, 2, "length")
        self.spin_corner_h = self._make_dspin(self.arch_spec.corner.stem_height, 2.0, 14.0, 0.5, 2, "length")
        self.spin_fillet_w = self._make_dspin(self.arch_spec.corner.stiffener_fillet_width, 0.0, 2.5, 0.1, 2, "length")
        f_cor.addRow("Corner Angle α:", self.spin_corner_ang)
        f_cor.addRow("Primary Length:", self.spin_primary_len)
        f_cor.addRow("Wing Length:", self.spin_wing_len)
        f_cor.addRow("Stem Height:", self.spin_corner_h)
        f_cor.addRow("Stiffener Fillet:", self.spin_fillet_w)
        self.morph_stack.addWidget(p_cor)

        # Page 2: Counterfort / Buttress
        p_cf = QWidget()
        f_cf = QFormLayout(p_cf)
        self.chk_buttress = QCheckBox("Front Buttress (vs. Rear Counterfort)")
        self.chk_buttress.setChecked(self.arch_spec.counterfort.is_buttress)
        self.chk_buttress.toggled.connect(self._on_changed)
        self.spin_cf_h = self._make_dspin(self.arch_spec.counterfort.wall_height, 3.0, 16.0, 0.5, 2, "length")
        self.spin_cf_s = self._make_dspin(self.arch_spec.counterfort.counterfort_spacing, 1.5, 8.0, 0.25, 2, "length")
        self.spin_cf_t = self._make_dspin(self.arch_spec.counterfort.counterfort_thickness, 0.2, 1.2, 0.05, 2, "length")
        f_cf.addRow(self.chk_buttress)
        f_cf.addRow("Wall Height:", self.spin_cf_h)
        f_cf.addRow("Spacing s_cf:", self.spin_cf_s)
        f_cf.addRow("Rib Thickness t_cf:", self.spin_cf_t)
        self.morph_stack.addWidget(p_cf)

        # Page 3: Curved Plan-View
        p_cp = QWidget()
        f_cp = QFormLayout(p_cp)
        self.chk_concave = QCheckBox("Concave Toward Backfill (Arching)")
        self.chk_concave.setChecked(self.arch_spec.curved_plan.concave_to_backfill)
        self.chk_concave.toggled.connect(self._on_changed)
        self.spin_plan_r = self._make_dspin(self.arch_spec.curved_plan.plan_radius, 4.0, 40.0, 0.5, 2, "length")
        self.spin_plan_ang = self._make_dspin(self.arch_spec.curved_plan.sweep_angle_deg, 15.0, 140.0, 5.0, 1, "", "°")
        self.spin_plan_h = self._make_dspin(self.arch_spec.curved_plan.stem_height, 2.0, 12.0, 0.5, 2, "length")
        f_cp.addRow(self.chk_concave)
        f_cp.addRow("Plan Radius R_plan:", self.spin_plan_r)
        f_cp.addRow("Sweep Angle:", self.spin_plan_ang)
        f_cp.addRow("Stem Height:", self.spin_plan_h)
        self.morph_stack.addWidget(p_cp)

        # Page 4: MSE / Gabion / Crib
        p_mse = QWidget()
        f_mse = QFormLayout(p_mse)
        self.combo_mse_sub = QComboBox()
        self.combo_mse_sub.addItem("MSE Geogrid", "mse_geogrid")
        self.combo_mse_sub.addItem("Gabion Baskets", "gabion")
        self.combo_mse_sub.addItem("Modular Crib Wall", "crib")
        self.combo_mse_sub.currentIndexChanged.connect(self._on_changed)
        self.spin_mse_courses = QSpinBox()
        self.spin_mse_courses.setRange(2, 16)
        self.spin_mse_courses.setValue(self.arch_spec.mse.num_courses)
        self.spin_mse_courses.valueChanged.connect(self._on_changed)
        self.spin_mse_batter = self._make_dspin(self.arch_spec.mse.batter_deg, 0.0, 18.0, 1.0, 1, "", "°")
        self.spin_mse_lr = self._make_dspin(self.arch_spec.mse.reinforcement_length, 1.5, 12.0, 0.25, 2, "length")
        self.spin_mse_t = self._make_dspin(self.arch_spec.mse.tensile_capacity_kn_per_m, 10.0, 200.0, 5.0, 1, "force_per_length")
        f_mse.addRow("Subtype:", self.combo_mse_sub)
        f_mse.addRow("Modular Courses:", self.spin_mse_courses)
        f_mse.addRow("Batter Angle:", self.spin_mse_batter)
        f_mse.addRow("Grid Length L_r:", self.spin_mse_lr)
        f_mse.addRow("Grid Capacity T_all:", self.spin_mse_t)
        self.morph_stack.addWidget(p_mse)

        arch_lay.addWidget(self.morph_stack)

        self.lbl_arch_summary = QLabel("Switch top toolbar System -> 'Architectural Walls' to inspect 3D mesh.")
        self.lbl_arch_summary.setWordWrap(True)
        self.lbl_arch_summary.setStyleSheet("color: #93c5fd; font-size: 11px;")
        arch_lay.addWidget(self.lbl_arch_summary)
        layout.addWidget(self.grp_arch)

        # ------------------------------------------------------------------
        # 2. Adjacent Building & Traffic Surcharge
        # ------------------------------------------------------------------
        self.grp_sur = QGroupBox("Adjacent Building & Traffic Surcharge")
        sur_form = QFormLayout(self.grp_sur)

        self.combo_sur_type = QComboBox()
        self.combo_sur_type.addItem("None (Soil Backfill Only)", SurchargeLoadType.NONE)
        self.combo_sur_type.addItem("Uniform Traffic / Strip Load", SurchargeLoadType.UNIFORM_TRAFFIC)
        self.combo_sur_type.addItem("Building Shallow Strip Footing", SurchargeLoadType.BUILDING_STRIP_FOOTING)
        self.combo_sur_type.addItem("Building Isolated Pad Footing", SurchargeLoadType.BUILDING_PAD_FOOTING)
        self.combo_sur_type.currentIndexChanged.connect(self._on_changed)

        self.spin_q_surf = self._make_dspin(self.surcharge_params.uniform_q_kpa, 0.0, 200.0, 2.5, 1, "pressure")
        self.spin_q_bld = self._make_dspin(self.surcharge_params.building_load_kn, 0.0, 5000.0, 25.0, 1, "force")
        self.spin_bf = self._make_dspin(self.surcharge_params.footing_width_m, 0.4, 15.0, 0.25, 2, "length")
        self.spin_lf = self._make_dspin(self.surcharge_params.footing_length_m, 0.4, 25.0, 0.25, 2, "length")
        self.spin_xf = self._make_dspin(self.surcharge_params.setback_m, 0.1, 15.0, 0.25, 2, "length")
        self.spin_df = self._make_dspin(self.surcharge_params.embedment_m, 0.0, 6.0, 0.2, 2, "length")

        sur_form.addRow("Load Type:", self.combo_sur_type)
        sur_form.addRow("Traffic Surcharge q_surf:", self.spin_q_surf)
        sur_form.addRow("Building Load Q_bld:", self.spin_q_bld)
        sur_form.addRow("Footing Width B_f:", self.spin_bf)
        sur_form.addRow("Footing Length L_f:", self.spin_lf)
        sur_form.addRow("Setback x_f:", self.spin_xf)
        sur_form.addRow("Embedment D_f:", self.spin_df)

        self.lbl_sur_summary = QLabel("Surcharge inactive.")
        self.lbl_sur_summary.setWordWrap(True)
        self.lbl_sur_summary.setStyleSheet("color: #fcd34d; font-size: 11px;")
        sur_form.addRow(self.lbl_sur_summary)

        layout.addWidget(self.grp_sur)
        layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _on_morphology_changed(self, idx: int) -> None:
        self.morph_stack.setCurrentIndex(max(0, min(idx, self.morph_stack.count() - 1)))
        self._on_changed()

    def _to_si(self, sp: QDoubleSpinBox, quantity: str) -> float:
        return to_si_value(sp.value(), quantity, self.unit_system) if quantity else sp.value()

    def _collect_models(self) -> Tuple[ArchitecturalWallSpec, AdjacentSurchargeParams]:
        morph = ArchWallMorphology(self.combo_morphology.currentData())
        t_step = SteppedTerracedWallParams(
            num_tiers=self.spin_tiers.value(),
            tier_height=self._to_si(self.spin_tier_h, "length"),
            bench_width=self._to_si(self.spin_bench_w, "length"),
        )
        t_cor = CornerWingwallParams(
            corner_angle_deg=self.spin_corner_ang.value(),
            primary_length=self._to_si(self.spin_primary_len, "length"),
            wing_length=self._to_si(self.spin_wing_len, "length"),
            stem_height=self._to_si(self.spin_corner_h, "length"),
            stiffener_fillet_width=self._to_si(self.spin_fillet_w, "length"),
        )
        t_cf = CounterfortWallParams(
            wall_height=self._to_si(self.spin_cf_h, "length"),
            counterfort_spacing=self._to_si(self.spin_cf_s, "length"),
            counterfort_thickness=self._to_si(self.spin_cf_t, "length"),
            is_buttress=self.chk_buttress.isChecked(),
        )
        t_cp = CurvedPlanWallParams(
            plan_radius=self._to_si(self.spin_plan_r, "length"),
            sweep_angle_deg=self.spin_plan_ang.value(),
            stem_height=self._to_si(self.spin_plan_h, "length"),
            concave_to_backfill=self.chk_concave.isChecked(),
        )
        t_mse = MSEGabionWallParams(
            wall_subtype=str(self.combo_mse_sub.currentData()),
            num_courses=self.spin_mse_courses.value(),
            batter_deg=self.spin_mse_batter.value(),
            reinforcement_length=self._to_si(self.spin_mse_lr, "length"),
            tensile_capacity_kn_per_m=self._to_si(self.spin_mse_t, "force_per_length"),
        )
        spec = ArchitecturalWallSpec(
            morphology=morph,
            stepped=t_step,
            corner=t_cor,
            counterfort=t_cf,
            curved_plan=t_cp,
            mse=t_mse,
        )
        sur = AdjacentSurchargeParams(
            load_type=SurchargeLoadType(self.combo_sur_type.currentData()),
            uniform_q_kpa=self._to_si(self.spin_q_surf, "pressure"),
            building_load_kn=self._to_si(self.spin_q_bld, "force"),
            footing_width_m=self._to_si(self.spin_bf, "length"),
            footing_length_m=self._to_si(self.spin_lf, "length"),
            setback_m=self._to_si(self.spin_xf, "length"),
            embedment_m=self._to_si(self.spin_df, "length"),
        )
        self.arch_spec = spec
        self.surcharge_params = sur
        return spec, sur

    def _on_changed(self, *_args) -> None:
        spec, sur = self._collect_models()
        self.archConfigChanged.emit(spec, sur)

    def update_readouts(self, arch_text: str, surcharge_thrust_kn_m: float, y_bar_m: float) -> None:
        """Updates KPI summary banners in active display units."""
        self.lbl_arch_summary.setText(arch_text)
        if self.surcharge_params.load_type == SurchargeLoadType.NONE:
            self.lbl_sur_summary.setText("Surcharge inactive.")
        else:
            p_disp = from_si_value(surcharge_thrust_kn_m, "force_per_length", self.unit_system)
            y_disp = from_si_value(y_bar_m, "length", self.unit_system)
            u_f = unit_label("force_per_length", self.unit_system)
            u_l = unit_label("length", self.unit_system)
            self.lbl_sur_summary.setText(
                f"Active Surcharge Thrust: {p_disp:.2f} {u_f} @ ȳ={y_disp:.2f} {u_l}"
            )

    def set_unit_system(self, unit_system: UnitSystem | str) -> None:
        """Converts displayed architectural and surcharge spinboxes preserving SI values."""
        new_u = UnitSystem(unit_system)
        if new_u == self.unit_system:
            return
        old_u = self.unit_system
        self.unit_system = new_u

        u_len = unit_label("length", new_u)
        self.grp_arch.setTitle(f"Architectural Wall Morphology ({u_len})")

        for sp, quantity, si_min, si_max, si_step, custom_suf in self._unit_spins:
            if not quantity:
                continue
            si_val = to_si_value(sp.value(), quantity, old_u)
            sp.blockSignals(True)
            sp.setRange(from_si_value(si_min, quantity, new_u), from_si_value(si_max, quantity, new_u))
            sp.setSingleStep(from_si_value(si_step, quantity, new_u))
            sp.setValue(from_si_value(si_val, quantity, new_u))
            sp.setSuffix(f" {custom_suf or unit_label(quantity, new_u)}")
            sp.blockSignals(False)

