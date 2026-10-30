"""
Parameter Control Panel for Soil Strata and Water Table.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, 
    QGroupBox
)
from PySide6.QtCore import Qt, Signal
from ...models.wall_params import SoilProperties


class SoilPanel(QWidget):
    """
    Sidebar panel to tune geotechnical backfill and foundation soil parameters.
    """
    soilChanged = Signal(SoilProperties)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.soil = SoilProperties()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Backfill Group
        group_backfill = QGroupBox("Backfill Soil Properties")
        form_bf = QFormLayout(group_backfill)
        self.spin_phi = self._add_field(form_bf, "Friction Angle phi (°):", 15.0, 48.0, self.soil.friction_angle, 1.0)
        self.spin_delta = self._add_field(form_bf, "Wall Friction delta (°):", 0.0, 35.0, self.soil.wall_friction_angle, 1.0)
        self.spin_gamma = self._add_field(form_bf, "Unit Weight (kN/m³):", 12.0, 24.0, self.soil.unit_weight, 0.5)
        self.spin_gamma_sat = self._add_field(form_bf, "Sat. Weight (kN/m³):", 15.0, 26.0, self.soil.saturated_unit_weight, 0.5)
        layout.addWidget(group_backfill)

        # Foundation Group
        group_found = QGroupBox("Foundation Soil Bed")
        form_fd = QFormLayout(group_found)
        self.spin_phi_f = self._add_field(form_fd, "Found. Friction (°):", 15.0, 45.0, self.soil.foundation_friction_angle, 1.0)
        self.spin_c_f = self._add_field(form_fd, "Found. Cohesion (kPa):", 0.0, 150.0, self.soil.foundation_cohesion, 5.0)
        self.spin_q_allow = self._add_field(form_fd, "Allow. Bearing (kPa):", 50.0, 1000.0, self.soil.allowable_bearing_capacity, 25.0)
        layout.addWidget(group_found)

        layout.addStretch()

    def _add_field(self, form: QFormLayout, label: str, v_min: float, v_max: float, v_default: float, step: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(v_min, v_max)
        spin.setValue(v_default)
        spin.setSingleStep(step)
        spin.setDecimals(1)
        spin.valueChanged.connect(self._on_value_changed)
        form.addRow(label, spin)
        return spin

    def _on_value_changed(self):
        self.soil.friction_angle = self.spin_phi.value()
        self.soil.wall_friction_angle = self.spin_delta.value()
        self.soil.unit_weight = self.spin_gamma.value()
        self.soil.saturated_unit_weight = self.spin_gamma_sat.value()
        self.soil.foundation_friction_angle = self.spin_phi_f.value()
        self.soil.foundation_cohesion = self.spin_c_f.value()
        self.soil.allowable_bearing_capacity = self.spin_q_allow.value()

        self.soilChanged.emit(self.soil)

    def set_soil(self, soil: SoilProperties):
        """Updates panel controls to reflect external soil properties model."""
        self.soil = soil
        for spin in (self.spin_phi, self.spin_delta, self.spin_gamma,
                     self.spin_gamma_sat, self.spin_phi_f, self.spin_c_f, self.spin_q_allow):
            spin.blockSignals(True)

        self.spin_phi.setValue(soil.friction_angle)
        self.spin_delta.setValue(soil.wall_friction_angle)
        self.spin_gamma.setValue(soil.unit_weight)
        self.spin_gamma_sat.setValue(soil.saturated_unit_weight)
        self.spin_phi_f.setValue(soil.foundation_friction_angle)
        self.spin_c_f.setValue(soil.foundation_cohesion)
        self.spin_q_allow.setValue(soil.allowable_bearing_capacity)

        for spin in (self.spin_phi, self.spin_delta, self.spin_gamma,
                     self.spin_gamma_sat, self.spin_phi_f, self.spin_c_f, self.spin_q_allow):
            spin.blockSignals(False)
