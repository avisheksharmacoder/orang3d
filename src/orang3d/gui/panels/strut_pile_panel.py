"""
PySide6 Panel for Strut Support System and Bored Pile Foundation Tuning (Phase 10).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox,
    QSpinBox, QComboBox, QGroupBox
)
from PySide6.QtCore import Qt, Signal

from ...models.advanced_wall_params import StrutSupportSystem, PierAndPileGeometry


class StrutAndPilePanel(QWidget):
    """
    Sidebar control panel to interactively tune raking structural steel struts,
    bored pile foundation embedment depth, and rock socketing.
    """
    strutPileChanged = Signal(StrutSupportSystem, PierAndPileGeometry)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.struts = StrutSupportSystem()
        self.pier_pile = PierAndPileGeometry()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 1. Bored Pile Foundation Group
        group_pile = QGroupBox("Bored Pile Foundation (m)")
        form_pile = QFormLayout(group_pile)
        form_pile.setLabelAlignment(Qt.AlignLeft)

        self.spin_dpile = self._add_field(form_pile, "Pile Diameter D_p:", 0.60, 2.0, self.pier_pile.pile_diameter, 0.10)
        self.spin_lpile = self._add_field(form_pile, "Embedment Length L_pile:", 4.0, 30.0, self.pier_pile.pile_length, 0.50)
        self.spin_socket = self._add_field(form_pile, "Rock Socketing Length:", 0.50, 6.0, self.pier_pile.rock_socket_length, 0.25)

        layout.addWidget(group_pile)

        # 2. Steel Struts Group
        group_strut = QGroupBox("Steel Strut Support System")
        form_strut = QFormLayout(group_strut)
        form_strut.setLabelAlignment(Qt.AlignLeft)

        self.combo_section = QComboBox()
        self.combo_section.addItems([
            "CHS 355.6x12.5 (Fe 250)",
            "CHS 406.4x14.2 (Fe 250)",
            "CHS 457.0x16.0 (Fe 250)",
            "ISMB 400 (Fe 250)",
            "ISMB 500 (Fe 250)",
        ])
        self.combo_section.currentTextChanged.connect(self._on_value_changed)
        form_strut.addRow("Steel Section:", self.combo_section)

        self.spin_nstruts = QSpinBox()
        self.spin_nstruts.setRange(1, 3)
        self.spin_nstruts.setValue(len(self.struts.strut_levels))
        self.spin_nstruts.valueChanged.connect(self._on_strut_count_changed)
        form_strut.addRow("Number of Strut Levels:", self.spin_nstruts)

        self.spin_level1 = self._add_field(form_strut, "Level 1 Elevation (m):", 1.0, 6.0, self.struts.strut_levels[0], 0.25)
        self.spin_level2 = self._add_field(form_strut, "Level 2 Elevation (m):", 2.0, 12.0, self.struts.strut_levels[1] if len(self.struts.strut_levels) > 1 else 5.0, 0.25)
        self.spin_rake = self._add_field(form_strut, "Strut Rake Angle (deg):", 0.0, 45.0, self.struts.inclination_angle_deg, 2.5)

        layout.addWidget(group_strut)
        layout.addStretch()

    def _add_field(self, form: QFormLayout, label: str, v_min: float, v_max: float, v_default: float, step: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(v_min, v_max)
        spin.setValue(v_default)
        spin.setSingleStep(step)
        spin.setDecimals(2)
        spin.valueChanged.connect(self._on_value_changed)
        form.addRow(label, spin)
        return spin

    def _on_strut_count_changed(self):
        n = self.spin_nstruts.value()
        self.spin_level2.setEnabled(n >= 2)
        self._on_value_changed()

    def _on_value_changed(self):
        n = self.spin_nstruts.value()
        levels = [self.spin_level1.value()]
        if n >= 2:
            levels.append(self.spin_level2.value())
        if n >= 3:
            levels.append(self.spin_level2.value() + 2.5)

        self.struts = StrutSupportSystem(
            strut_levels=levels,
            inclination_angle_deg=self.spin_rake.value(),
        )
        d_p = self.spin_dpile.value()
        s_p = max(self.pier_pile.pile_spacing, 2.5 * d_p)
        self.pier_pile = PierAndPileGeometry(
            pier_width=self.pier_pile.pier_width,
            pier_depth=self.pier_pile.pier_depth,
            pier_height=self.pier_pile.pier_height,
            pile_diameter=d_p,
            pile_length=self.spin_lpile.value(),
            pile_spacing=s_p,
            rock_socket_length=self.spin_socket.value(),
        )
        self.strutPileChanged.emit(self.struts, self.pier_pile)

    def get_struts_and_piles(self) -> tuple[StrutSupportSystem, PierAndPileGeometry]:
        return self.struts, self.pier_pile
