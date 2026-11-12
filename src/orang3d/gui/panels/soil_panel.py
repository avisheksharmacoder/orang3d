"""
Parameter Control Panel for Soil Strata and Water Table (SI & Imperial Unit Parity).
"""

from typing import Dict, Tuple
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QTabWidget, QVBoxLayout, QWidget

from ...models.wall_params import SoilProperties
from ...units import UnitSystem, from_si_value, to_si_value, unit_label
from .advanced_soil_panel import AdvancedSoilPanel


class SoilPanel(QWidget):
    """
    Sidebar panel to tune geotechnical backfill and foundation soil parameters,
    maintaining `self.soil` canonically in SI while rendering SI or Imperial units.
    """

    soilChanged = Signal(SoilProperties)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.soil = SoilProperties()
        self.unit_system = UnitSystem.SI

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)

        self.soil_sub_tabs = QTabWidget(self)
        basic_tab = QWidget()
        layout = QVBoxLayout(basic_tab)
        layout.setContentsMargins(6, 6, 6, 6)

        self._specs: Dict[str, Tuple[QFormLayout, str, str, float, float, float, int, QDoubleSpinBox]] = {}

        # Backfill Group
        group_backfill = QGroupBox("Backfill Soil Properties")
        form_bf = QFormLayout(group_backfill)
        self._register_field(form_bf, "friction_angle", "Friction Angle phi", "angle", 15.0, 48.0, self.soil.friction_angle, 1.0, 1)
        self._register_field(form_bf, "wall_friction_angle", "Wall Friction delta", "angle", 0.0, 35.0, self.soil.wall_friction_angle, 1.0, 1)
        self._register_field(form_bf, "unit_weight", "Unit Weight", "unit_weight", 12.0, 24.0, self.soil.unit_weight, 0.5, 1)
        self._register_field(form_bf, "saturated_unit_weight", "Sat. Weight", "unit_weight", 15.0, 26.0, self.soil.saturated_unit_weight, 0.5, 1)
        layout.addWidget(group_backfill)

        # Foundation Group
        group_found = QGroupBox("Foundation Soil Bed")
        form_fd = QFormLayout(group_found)
        self._register_field(form_fd, "foundation_friction_angle", "Found. Friction", "angle", 15.0, 45.0, self.soil.foundation_friction_angle, 1.0, 1)
        self._register_field(form_fd, "foundation_cohesion", "Found. Cohesion", "pressure", 0.0, 150.0, self.soil.foundation_cohesion, 5.0, 1)
        self._register_field(form_fd, "allowable_bearing_capacity", "Allow. Bearing", "pressure", 50.0, 1000.0, self.soil.allowable_bearing_capacity, 25.0, 1)
        layout.addWidget(group_found)

        layout.addStretch()

        self.spin_phi = self._specs["friction_angle"][7]
        self.spin_delta = self._specs["wall_friction_angle"][7]
        self.spin_gamma = self._specs["unit_weight"][7]
        self.spin_gamma_sat = self._specs["saturated_unit_weight"][7]
        self.spin_phi_f = self._specs["foundation_friction_angle"][7]
        self.spin_c_f = self._specs["foundation_cohesion"][7]
        self.spin_q_allow = self._specs["allowable_bearing_capacity"][7]

        self.adv_soil_panel = AdvancedSoilPanel(self)
        self.soil_sub_tabs.addTab(basic_tab, "Mohr-Coulomb Strata")
        self.soil_sub_tabs.addTab(self.adv_soil_panel, "Cyclic & Unsaturated")
        outer_layout.addWidget(self.soil_sub_tabs)

    def _register_field(
        self,
        form: QFormLayout,
        attr: str,
        title: str,
        kind: str,
        v_min: float,
        v_max: float,
        v_default: float,
        step: float,
        decimals: int,
    ) -> None:
        spin = QDoubleSpinBox()
        spin.setRange(v_min, v_max)
        spin.setValue(v_default)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.valueChanged.connect(self._on_value_changed)
        u_lbl = "°" if kind == "angle" else unit_label(kind, self.unit_system)
        form.addRow(f"{title} ({u_lbl}):", spin)
        self._specs[attr] = (form, title, kind, v_min, v_max, step, decimals, spin)

    def _on_value_changed(self):
        for attr, (_, _, kind, _, _, _, _, spin) in self._specs.items():
            setattr(self.soil, attr, to_si_value(spin.value(), kind, self.unit_system))
        self.soilChanged.emit(self.soil)

    def set_unit_system(self, unit_system: UnitSystem | str) -> None:
        """Switches unit-weight (kN/m³ <-> pcf) and stress (kPa <-> ksf) displays cleanly."""
        self.unit_system = UnitSystem(unit_system)
        for attr, (form, title, kind, lo, hi, step, base_dec, spin) in self._specs.items():
            if kind == "angle":
                continue
            spin.blockSignals(True)
            spin.setDecimals(3 if (self.unit_system == UnitSystem.IMPERIAL and kind == "pressure") else base_dec)
            spin.setRange(
                from_si_value(lo, kind, self.unit_system),
                from_si_value(hi, kind, self.unit_system),
            )
            spin.setSingleStep(from_si_value(step, kind, self.unit_system))
            spin.setValue(from_si_value(getattr(self.soil, attr), kind, self.unit_system))
            u_lbl = unit_label(kind, self.unit_system)
            lbl_widget = form.labelForField(spin)
            if lbl_widget is not None:
                lbl_widget.setText(f"{title} ({u_lbl}):")
            spin.blockSignals(False)

    def set_soil(self, soil: SoilProperties):
        """Updates panel controls to reflect an external canonical-SI soil model."""
        self.soil = soil
        for attr, (_, _, kind, _, _, _, _, spin) in self._specs.items():
            spin.blockSignals(True)
            spin.setValue(from_si_value(getattr(soil, attr), kind, self.unit_system))
            spin.blockSignals(False)
