"""
Parameter Control Panel for Retaining Wall Geometry.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, 
    QSlider, QLabel, QGroupBox
)
from PySide6.QtCore import Qt, Signal
from ...models.wall_params import RetainingWallGeometry


class GeometryPanel(QWidget):
    """
    Sidebar panel to tune cantilever retaining wall dimensions.
    Emits geometryChanged signal on any slider or spinbox adjustment.
    """
    geometryChanged = Signal(RetainingWallGeometry)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.geom = RetainingWallGeometry()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        group = QGroupBox("Wall Geometry (m)")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignLeft)

        # Helpers to create synced slider + double spinbox
        self.spin_height = self._add_field(form, "Stem Height:", 2.0, 15.0, self.geom.stem_height, 0.25)
        self.spin_t_top = self._add_field(form, "Stem Top Thick:", 0.2, 1.5, self.geom.stem_thickness_top, 0.05)
        self.spin_t_base = self._add_field(form, "Stem Base Thick:", 0.3, 3.0, self.geom.stem_thickness_base, 0.05)
        self.spin_toe = self._add_field(form, "Toe Width:", 0.4, 5.0, self.geom.toe_length, 0.1)
        self.spin_heel = self._add_field(form, "Heel Width:", 0.5, 8.0, self.geom.heel_length, 0.1)
        self.spin_footing = self._add_field(form, "Footing Thick:", 0.3, 2.5, self.geom.footing_thickness, 0.05)
        self.spin_key = self._add_field(form, "Shear Key Depth:", 0.0, 2.0, self.geom.shear_key_depth, 0.1)
        self.spin_len = self._add_field(form, "3D Wall Length:", 1.0, 25.0, self.geom.wall_length, 1.0)

        layout.addWidget(group)
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
        self.geom.stem_height = self.spin_height.value()
        self.geom.stem_thickness_top = self.spin_t_top.value()
        self.geom.stem_thickness_base = self.spin_t_base.value()
        self.geom.toe_length = self.spin_toe.value()
        self.geom.heel_length = self.spin_heel.value()
        self.geom.footing_thickness = self.spin_footing.value()
        self.geom.shear_key_depth = self.spin_key.value()
        self.geom.wall_length = self.spin_len.value()

        self.geometryChanged.emit(self.geom)

    def set_geometry(self, geom: RetainingWallGeometry):
        """Updates panel controls to reflect external geometry model."""
        self.geom = geom
        for spin in (self.spin_height, self.spin_t_top, self.spin_t_base,
                     self.spin_toe, self.spin_heel, self.spin_footing,
                     self.spin_key, self.spin_len):
            spin.blockSignals(True)

        self.spin_height.setValue(geom.stem_height)
        self.spin_t_top.setValue(geom.stem_thickness_top)
        self.spin_t_base.setValue(geom.stem_thickness_base)
        self.spin_toe.setValue(geom.toe_length)
        self.spin_heel.setValue(geom.heel_length)
        self.spin_footing.setValue(geom.footing_thickness)
        self.spin_key.setValue(geom.shear_key_depth)
        self.spin_len.setValue(geom.wall_length)

        for spin in (self.spin_height, self.spin_t_top, self.spin_t_base,
                     self.spin_toe, self.spin_heel, self.spin_footing,
                     self.spin_key, self.spin_len):
            spin.blockSignals(False)
