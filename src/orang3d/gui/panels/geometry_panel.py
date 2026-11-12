"""
Parameter Control Panel for Retaining Wall Geometry (SI & Imperial Unit Parity).
"""

from typing import Dict, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QVBoxLayout, QWidget

from ...models.wall_params import RetainingWallGeometry
from ...units import UnitSystem, from_si_value, to_si_value, unit_label


class GeometryPanel(QWidget):
    """
    Sidebar panel to tune cantilever retaining wall dimensions.
    Maintains `self.geom` canonically in SI (meters) while displaying SI or Imperial units.
    """

    geometryChanged = Signal(RetainingWallGeometry)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.geom = RetainingWallGeometry()
        self.unit_system = UnitSystem.SI

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.group = QGroupBox("Wall Geometry (m)")
        self.form = QFormLayout(self.group)
        self.form.setLabelAlignment(Qt.AlignLeft)

        self._specs: Dict[str, Tuple[str, float, float, float, QDoubleSpinBox]] = {}
        defs = [
            ("stem_height", "Stem Height", 2.0, 15.0, self.geom.stem_height, 0.25),
            ("stem_thickness_top", "Stem Top Thick", 0.2, 1.5, self.geom.stem_thickness_top, 0.05),
            ("stem_thickness_base", "Stem Base Thick", 0.3, 3.0, self.geom.stem_thickness_base, 0.05),
            ("toe_length", "Toe Width", 0.4, 5.0, self.geom.toe_length, 0.10),
            ("heel_length", "Heel Width", 0.5, 8.0, self.geom.heel_length, 0.10),
            ("footing_thickness", "Footing Thick", 0.3, 2.5, self.geom.footing_thickness, 0.05),
            ("shear_key_depth", "Shear Key Depth", 0.0, 2.0, self.geom.shear_key_depth, 0.10),
            ("wall_length", "3D Wall Length", 1.0, 25.0, self.geom.wall_length, 1.0),
        ]
        for attr, title, lo, hi, default_val, step in defs:
            spin = self._add_field(f"{title} (m):", lo, hi, default_val, step)
            self._specs[attr] = (title, lo, hi, step, spin)

        # Keep backward-compatible attribute aliases
        self.spin_height = self._specs["stem_height"][4]
        self.spin_t_top = self._specs["stem_thickness_top"][4]
        self.spin_t_base = self._specs["stem_thickness_base"][4]
        self.spin_toe = self._specs["toe_length"][4]
        self.spin_heel = self._specs["heel_length"][4]
        self.spin_footing = self._specs["footing_thickness"][4]
        self.spin_key = self._specs["shear_key_depth"][4]
        self.spin_len = self._specs["wall_length"][4]

        layout.addWidget(self.group)
        layout.addStretch()

    def _add_field(
        self, label: str, v_min: float, v_max: float, v_default: float, step: float
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(v_min, v_max)
        spin.setValue(v_default)
        spin.setSingleStep(step)
        spin.setDecimals(2)
        spin.valueChanged.connect(self._on_value_changed)
        self.form.addRow(label, spin)
        return spin

    def _on_value_changed(self):
        for attr, (_, _, _, _, spin) in self._specs.items():
            setattr(self.geom, attr, to_si_value(spin.value(), "length", self.unit_system))
        self.geometryChanged.emit(self.geom)

    def set_unit_system(self, unit_system: UnitSystem | str) -> None:
        """Switches labels, ranges, and displayed values between SI (m) and Imperial (ft)."""
        self.unit_system = UnitSystem(unit_system)
        u_lbl = unit_label("length", self.unit_system)
        self.group.setTitle(f"Wall Geometry ({u_lbl})")

        for attr, (title, lo, hi, step, spin) in self._specs.items():
            spin.blockSignals(True)
            spin.setRange(
                from_si_value(lo, "length", self.unit_system),
                from_si_value(hi, "length", self.unit_system),
            )
            spin.setSingleStep(from_si_value(step, "length", self.unit_system))
            spin.setValue(from_si_value(getattr(self.geom, attr), "length", self.unit_system))
            lbl_widget = self.form.labelForField(spin)
            if lbl_widget is not None:
                lbl_widget.setText(f"{title} ({u_lbl}):")
            spin.blockSignals(False)

    def set_geometry(self, geom: RetainingWallGeometry):
        """Updates panel controls to reflect an external canonical-SI geometry model."""
        self.geom = geom
        for attr, (_, _, _, _, spin) in self._specs.items():
            spin.blockSignals(True)
            spin.setValue(from_si_value(getattr(geom, attr), "length", self.unit_system))
            spin.blockSignals(False)
