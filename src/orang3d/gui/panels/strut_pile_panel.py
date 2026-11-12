"""
PySide6 Panel for Strut Support System and Bored Pile Foundation Tuning
(SI & Imperial Unit Parity).
"""

from typing import List, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QSpinBox, QVBoxLayout, QWidget

from ...models.advanced_wall_params import PierAndPileGeometry, StrutSupportSystem
from ...units import UnitSystem, from_si_value, to_si_value, unit_label


class StrutAndPilePanel(QWidget):
    """
    Sidebar control panel to tune steel struts and bored piles.
    Maintains `self.struts` and `self.pier_pile` canonically in SI (m).
    """

    strutPileChanged = Signal(StrutSupportSystem, PierAndPileGeometry)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.struts = StrutSupportSystem()
        self.pier_pile = PierAndPileGeometry()
        self.unit_system = UnitSystem.SI
        self._length_specs: List[Tuple[QFormLayout, str, float, float, float, QDoubleSpinBox]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 1. Bored Pile Foundation Group
        self.group_pile = QGroupBox("Bored Pile Foundation (m)")
        form_pile = QFormLayout(self.group_pile)
        form_pile.setLabelAlignment(Qt.AlignLeft)

        self.spin_dpile = self._add_field(form_pile, "Pile Diameter D_p", 0.60, 2.0, self.pier_pile.pile_diameter, 0.10, is_length=True)
        self.spin_lpile = self._add_field(form_pile, "Embedment Length L_pile", 4.0, 30.0, self.pier_pile.pile_length, 0.50, is_length=True)
        self.spin_socket = self._add_field(form_pile, "Rock Socketing Length", 0.50, 6.0, self.pier_pile.rock_socket_length, 0.25, is_length=True)
        layout.addWidget(self.group_pile)

        # 2. Steel Struts Group
        self.group_strut = QGroupBox("Steel Strut Support System")
        form_strut = QFormLayout(self.group_strut)
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

        lvl2_default = self.struts.strut_levels[1] if len(self.struts.strut_levels) > 1 else 5.0
        self.spin_level1 = self._add_field(form_strut, "Level 1 Elevation", 1.0, 6.0, self.struts.strut_levels[0], 0.25, is_length=True)
        self.spin_level2 = self._add_field(form_strut, "Level 2 Elevation", 2.0, 12.0, lvl2_default, 0.25, is_length=True)
        self.spin_rake = self._add_field(form_strut, "Strut Rake Angle (deg):", 0.0, 45.0, self.struts.inclination_angle_deg, 2.5, is_length=False)

        layout.addWidget(self.group_strut)
        layout.addStretch()

    def _add_field(
        self,
        form: QFormLayout,
        label: str,
        v_min: float,
        v_max: float,
        v_default: float,
        step: float,
        is_length: bool = True,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(v_min, v_max)
        spin.setValue(v_default)
        spin.setSingleStep(step)
        spin.setDecimals(2)
        spin.valueChanged.connect(self._on_value_changed)
        lbl_str = f"{label} (m):" if is_length else label
        form.addRow(lbl_str, spin)
        if is_length:
            self._length_specs.append((form, label, v_min, v_max, step, spin))
        return spin

    def _on_strut_count_changed(self):
        self.spin_level2.setEnabled(self.spin_nstruts.value() >= 2)
        self._on_value_changed()

    def _on_value_changed(self):
        n = self.spin_nstruts.value()
        levels = [to_si_value(self.spin_level1.value(), "length", self.unit_system)]
        if n >= 2:
            levels.append(to_si_value(self.spin_level2.value(), "length", self.unit_system))
        if n >= 3:
            levels.append(levels[-1] + 2.5)

        self.struts = StrutSupportSystem(
            strut_levels=levels,
            inclination_angle_deg=self.spin_rake.value(),
        )
        d_p = to_si_value(self.spin_dpile.value(), "length", self.unit_system)
        s_p = max(self.pier_pile.pile_spacing, 2.5 * d_p)
        self.pier_pile = PierAndPileGeometry(
            pier_width=self.pier_pile.pier_width,
            pier_depth=self.pier_pile.pier_depth,
            pier_height=self.pier_pile.pier_height,
            pile_diameter=d_p,
            pile_length=to_si_value(self.spin_lpile.value(), "length", self.unit_system),
            pile_spacing=s_p,
            rock_socket_length=to_si_value(self.spin_socket.value(), "length", self.unit_system),
        )
        self.strutPileChanged.emit(self.struts, self.pier_pile)

    def _si_value_for_spin(self, spin: QDoubleSpinBox) -> float:
        if spin is self.spin_dpile:
            return self.pier_pile.pile_diameter
        if spin is self.spin_lpile:
            return self.pier_pile.pile_length
        if spin is self.spin_socket:
            return self.pier_pile.rock_socket_length
        if spin is self.spin_level1:
            return self.struts.strut_levels[0]
        return self.struts.strut_levels[1] if len(self.struts.strut_levels) > 1 else 5.0

    def set_unit_system(self, unit_system: UnitSystem | str) -> None:
        """Switches pile and strut depth/length spinboxes between m (SI) and ft (Imperial)."""
        self.unit_system = UnitSystem(unit_system)
        u_lbl = unit_label("length", self.unit_system)
        self.group_pile.setTitle(f"Bored Pile Foundation ({u_lbl})")

        for form, title, lo, hi, step, spin in self._length_specs:
            spin.blockSignals(True)
            spin.setRange(
                from_si_value(lo, "length", self.unit_system),
                from_si_value(hi, "length", self.unit_system),
            )
            spin.setSingleStep(from_si_value(step, "length", self.unit_system))
            spin.setValue(from_si_value(self._si_value_for_spin(spin), "length", self.unit_system))
            lbl_w = form.labelForField(spin)
            if lbl_w is not None:
                lbl_w.setText(f"{title} ({u_lbl}):")
            spin.blockSignals(False)

    def set_strut_and_piles(
        self,
        struts: StrutSupportSystem,
        pier_pile: PierAndPileGeometry,
    ) -> None:
        """Programmatically populates strut and bored pile controls in active units."""
        widgets = (
            self.combo_section, self.spin_nstruts, self.spin_level1, self.spin_level2,
            self.spin_rake, self.spin_dpile, self.spin_lpile, self.spin_socket,
        )
        for w in widgets:
            w.blockSignals(True)
        try:
            self.struts = struts
            self.pier_pile = pier_pile
            n_lvl = max(1, min(3, len(struts.strut_levels)))
            self.spin_nstruts.setValue(n_lvl)
            self.spin_level2.setEnabled(n_lvl >= 2)
            self.spin_level1.setValue(from_si_value(struts.strut_levels[0], "length", self.unit_system))
            if len(struts.strut_levels) > 1:
                self.spin_level2.setValue(from_si_value(struts.strut_levels[1], "length", self.unit_system))
            self.spin_rake.setValue(struts.inclination_angle_deg)
            self.spin_dpile.setValue(from_si_value(pier_pile.pile_diameter, "length", self.unit_system))
            self.spin_lpile.setValue(from_si_value(pier_pile.pile_length, "length", self.unit_system))
            self.spin_socket.setValue(from_si_value(pier_pile.rock_socket_length, "length", self.unit_system))
        finally:
            for w in widgets:
                w.blockSignals(False)

    def get_struts_and_piles(self) -> tuple[StrutSupportSystem, PierAndPileGeometry]:
        return self.struts, self.pier_pile
