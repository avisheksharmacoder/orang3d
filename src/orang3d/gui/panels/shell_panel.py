"""
PySide6 Panel for Curved Shell Panel and Pier Geometry Tuning (Phase 10).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox,
    QSpinBox, QLabel, QGroupBox, QSlider
)
from PySide6.QtCore import Qt, Signal

from ...models.advanced_wall_params import CurvedShellGeometry, PierAndPileGeometry


class ShellAndPierPanel(QWidget):
    """
    Sidebar control panel to interactively tune cylindrical curved shell panels,
    bay span, curvature radius, and vertical retaining piers.
    """
    shellChanged = Signal(CurvedShellGeometry, PierAndPileGeometry, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.shell_geom = CurvedShellGeometry()
        self.pier_geom = PierAndPileGeometry()
        self.num_bays = 3

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 1. Shell Panel Geometry Group
        group_shell = QGroupBox("Curved Shell Panels (m)")
        form_shell = QFormLayout(group_shell)
        form_shell.setLabelAlignment(Qt.AlignLeft)

        self.spin_height = self._add_field(form_shell, "Panel Height H:", 3.0, 15.0, self.shell_geom.panel_height, 0.25)
        self.spin_bay = self._add_field(form_shell, "Bay Span L_bay:", 2.0, 6.0, self.shell_geom.bay_span, 0.25)
        self.spin_radius = self._add_field(form_shell, "Curvature Radius R:", 2.0, 10.0, self.shell_geom.radius, 0.25)
        self.spin_thick = self._add_field(form_shell, "Shell Thickness t:", 0.20, 0.80, self.shell_geom.thickness, 0.05)

        self.spin_bays = QSpinBox()
        self.spin_bays.setRange(1, 6)
        self.spin_bays.setValue(self.num_bays)
        self.spin_bays.valueChanged.connect(self._on_value_changed)
        form_shell.addRow("Number of Bays:", self.spin_bays)

        layout.addWidget(group_shell)

        # 2. Pier Geometry Group
        group_pier = QGroupBox("Vertical Pier Dimensions (m)")
        form_pier = QFormLayout(group_pier)
        form_pier.setLabelAlignment(Qt.AlignLeft)

        self.spin_bp = self._add_field(form_pier, "Pier Width b_p:", 0.40, 2.0, self.pier_geom.pier_width, 0.10)
        self.spin_dp = self._add_field(form_pier, "Pier Depth d_p:", 0.50, 2.5, self.pier_geom.pier_depth, 0.10)
        self.spin_hp = self._add_field(form_pier, "Pier Height h_p:", 3.0, 16.0, self.pier_geom.pier_height, 0.25)

        layout.addWidget(group_pier)
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

    def _on_value_changed(self):
        """Updates dataclasses and emits shellChanged signal."""
        self.shell_geom = CurvedShellGeometry(
            radius=self.spin_radius.value(),
            bay_span=self.spin_bay.value(),
            panel_height=self.spin_height.value(),
            thickness=self.spin_thick.value(),
        )
        self.pier_geom = PierAndPileGeometry(
            pier_width=self.spin_bp.value(),
            pier_depth=self.spin_dp.value(),
            pier_height=self.spin_hp.value(),
            pile_diameter=self.pier_geom.pile_diameter,
            pile_length=self.pier_geom.pile_length,
            rock_socket_length=self.pier_geom.rock_socket_length,
        )
        self.num_bays = self.spin_bays.value()
        self.shellChanged.emit(self.shell_geom, self.pier_geom, self.num_bays)

    def get_geometry(self) -> tuple[CurvedShellGeometry, PierAndPileGeometry, int]:
        return self.shell_geom, self.pier_geom, self.num_bays
