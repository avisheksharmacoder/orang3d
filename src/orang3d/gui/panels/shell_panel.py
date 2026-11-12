"""
PySide6 Panel for Curved Shell Panel and Pier Geometry Tuning (SI & Imperial Unit Parity).
"""

from typing import List, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QSpinBox, QVBoxLayout, QWidget

from ...models.advanced_wall_params import CurvedShellGeometry, PierAndPileGeometry
from ...units import UnitSystem, from_si_value, to_si_value, unit_label


class ShellAndPierPanel(QWidget):
    """
    Sidebar control panel to tune cylindrical curved shell panels and piers.
    Maintains `self.shell_geom` and `self.pier_geom` canonically in SI (m).
    """

    shellChanged = Signal(CurvedShellGeometry, PierAndPileGeometry, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.shell_geom = CurvedShellGeometry()
        self.pier_geom = PierAndPileGeometry()
        self.num_bays = 3
        self.unit_system = UnitSystem.SI
        self._length_specs: List[Tuple[QFormLayout, str, float, float, float, QDoubleSpinBox, str]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 1. Shell Panel Geometry Group
        self.group_shell = QGroupBox("Curved Shell Panels (m)")
        form_shell = QFormLayout(self.group_shell)
        form_shell.setLabelAlignment(Qt.AlignLeft)

        self.spin_height = self._add_field(form_shell, "Panel Height H", 3.0, 15.0, self.shell_geom.panel_height, 0.25, "panel_height")
        self.spin_bay = self._add_field(form_shell, "Bay Span L_bay", 2.0, 6.0, self.shell_geom.bay_span, 0.25, "bay_span")
        self.spin_radius = self._add_field(form_shell, "Curvature Radius R", 2.0, 10.0, self.shell_geom.radius, 0.25, "radius")
        self.spin_thick = self._add_field(form_shell, "Shell Thickness t", 0.20, 0.80, self.shell_geom.thickness, 0.05, "thickness")

        self.spin_bays = QSpinBox()
        self.spin_bays.setRange(1, 6)
        self.spin_bays.setValue(self.num_bays)
        self.spin_bays.valueChanged.connect(self._on_value_changed)
        form_shell.addRow("Number of Bays:", self.spin_bays)
        layout.addWidget(self.group_shell)

        # 2. Pier Geometry Group
        self.group_pier = QGroupBox("Vertical Pier Dimensions (m)")
        form_pier = QFormLayout(self.group_pier)
        form_pier.setLabelAlignment(Qt.AlignLeft)

        self.spin_bp = self._add_field(form_pier, "Pier Width b_p", 0.40, 2.0, self.pier_geom.pier_width, 0.10, "pier_width")
        self.spin_dp = self._add_field(form_pier, "Pier Depth d_p", 0.50, 2.5, self.pier_geom.pier_depth, 0.10, "pier_depth")
        self.spin_hp = self._add_field(form_pier, "Pier Height h_p", 3.0, 16.0, self.pier_geom.pier_height, 0.25, "pier_height")
        layout.addWidget(self.group_pier)
        layout.addStretch()

    def _add_field(
        self, form: QFormLayout, label: str, v_min: float, v_max: float, v_default: float, step: float, attr: str
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(v_min, v_max)
        spin.setValue(v_default)
        spin.setSingleStep(step)
        spin.setDecimals(2)
        spin.valueChanged.connect(self._on_value_changed)
        form.addRow(f"{label}:", spin)
        self._length_specs.append((form, label, v_min, v_max, step, spin, attr))
        return spin

    def _on_value_changed(self):
        panel_h = to_si_value(self.spin_height.value(), "length", self.unit_system)
        pier_h = to_si_value(self.spin_hp.value(), "length", self.unit_system)
        if panel_h > pier_h:
            if self.sender() is self.spin_hp:
                panel_h = max(3.0, pier_h)
                self.spin_height.blockSignals(True)
                self.spin_height.setValue(from_si_value(panel_h, "length", self.unit_system))
                self.spin_height.blockSignals(False)
            else:
                pier_h = min(16.0, panel_h)
                self.spin_hp.blockSignals(True)
                self.spin_hp.setValue(from_si_value(pier_h, "length", self.unit_system))
                self.spin_hp.blockSignals(False)

        self.shell_geom = CurvedShellGeometry(
            radius=to_si_value(self.spin_radius.value(), "length", self.unit_system),
            bay_span=to_si_value(self.spin_bay.value(), "length", self.unit_system),
            panel_height=panel_h,
            thickness=to_si_value(self.spin_thick.value(), "length", self.unit_system),
        )
        self.pier_geom = PierAndPileGeometry(
            pier_width=to_si_value(self.spin_bp.value(), "length", self.unit_system),
            pier_depth=to_si_value(self.spin_dp.value(), "length", self.unit_system),
            pier_height=pier_h,
            pile_diameter=self.pier_geom.pile_diameter,
            pile_length=self.pier_geom.pile_length,
            rock_socket_length=self.pier_geom.rock_socket_length,
        )
        self.num_bays = self.spin_bays.value()
        self.shellChanged.emit(self.shell_geom, self.pier_geom, self.num_bays)

    def set_unit_system(self, unit_system: UnitSystem | str) -> None:
        """Switches shell and pier lengths between SI (m) and Imperial (ft)."""
        self.unit_system = UnitSystem(unit_system)
        u_lbl = unit_label("length", self.unit_system)
        self.group_shell.setTitle(f"Curved Shell Panels ({u_lbl})")
        self.group_pier.setTitle(f"Vertical Pier Dimensions ({u_lbl})")

        for form, title, lo, hi, step, spin, attr in self._length_specs:
            spin.blockSignals(True)
            spin.setRange(
                from_si_value(lo, "length", self.unit_system),
                from_si_value(hi, "length", self.unit_system),
            )
            spin.setSingleStep(from_si_value(step, "length", self.unit_system))
            src = self.shell_geom if hasattr(self.shell_geom, attr) else self.pier_geom
            spin.setValue(from_si_value(getattr(src, attr), "length", self.unit_system))
            lbl_w = form.labelForField(spin)
            if lbl_w is not None:
                lbl_w.setText(f"{title} ({u_lbl}):")
            spin.blockSignals(False)

    def set_shell_and_piers(
        self,
        shell_geom: CurvedShellGeometry,
        pier_geom: PierAndPileGeometry,
        num_bays: int = 3,
    ) -> None:
        """Programmatically populates shell and pier spinboxes in the active unit system."""
        widgets = (
            self.spin_height, self.spin_bay, self.spin_radius, self.spin_thick,
            self.spin_bays, self.spin_bp, self.spin_dp, self.spin_hp,
        )
        for w in widgets:
            w.blockSignals(True)
        try:
            self.shell_geom = shell_geom
            self.pier_geom = pier_geom
            self.num_bays = int(num_bays)
            self.spin_hp.setValue(from_si_value(pier_geom.pier_height, "length", self.unit_system))
            self.spin_height.setValue(from_si_value(shell_geom.panel_height, "length", self.unit_system))
            self.spin_bay.setValue(from_si_value(shell_geom.bay_span, "length", self.unit_system))
            self.spin_radius.setValue(from_si_value(shell_geom.radius, "length", self.unit_system))
            self.spin_thick.setValue(from_si_value(shell_geom.thickness, "length", self.unit_system))
            self.spin_bays.setValue(int(num_bays))
            self.spin_bp.setValue(from_si_value(pier_geom.pier_width, "length", self.unit_system))
            self.spin_dp.setValue(from_si_value(pier_geom.pier_depth, "length", self.unit_system))
        finally:
            for w in widgets:
                w.blockSignals(False)

    def get_geometry(self) -> tuple[CurvedShellGeometry, PierAndPileGeometry, int]:
        return self.shell_geom, self.pier_geom, self.num_bays
