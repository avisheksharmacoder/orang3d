"""
Parameter Control Panel for Earthquake Disasters, Water Table, and Liquefaction.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, 
    QSlider, QLabel, QGroupBox, QComboBox, QPushButton, QHBoxLayout, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from ...models.wall_params import SeismicParams


class SeismicPanel(QWidget):
    """
    Sidebar panel to tune earthquake acceleration, water table flooding, and liquefaction.
    """
    seismicChanged = Signal(SeismicParams)
    recordLoaded = Signal(str) # Filepath to .AT2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.seismic = SeismicParams()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # 1. Seismic Parameters Group
        group_quake = QGroupBox("Seismic Intensity (g)")
        form_q = QFormLayout(group_quake)
        self.spin_kh = self._add_field(form_q, "Horizontal kh (g):", 0.0, 1.0, self.seismic.horizontal_pga, 0.02)
        self.spin_kv = self._add_field(form_q, "Vertical kv (g):", 0.0, 0.6, self.seismic.vertical_pga, 0.01)
        self.spin_beta = self._add_field(form_q, "Backfill Slope (°):", 0.0, 25.0, self.seismic.backfill_slope, 1.0)
        layout.addWidget(group_quake)

        # 2. Disaster Environmental Conditions Group
        group_disaster = QGroupBox("Disaster Triggers")
        form_d = QFormLayout(group_disaster)
        self.spin_water = self._add_field(form_d, "Water Depth (m):", 0.0, 15.0, self.seismic.water_table_depth, 0.25)
        
        # Liquefaction Slider (0% - 100%)
        self.lbl_liq = QLabel("0%")
        self.slider_liq = QSlider(Qt.Horizontal)
        self.slider_liq.setRange(0, 100)
        self.slider_liq.setValue(int(self.seismic.liquefaction_factor * 100))
        self.slider_liq.valueChanged.connect(self._on_liq_changed)
        h_liq = QHBoxLayout()
        h_liq.addWidget(self.slider_liq)
        h_liq.addWidget(self.lbl_liq)
        form_d.addRow("Liquefaction:", h_liq)
        layout.addWidget(group_disaster)

        # 3. Earthquake Input Selection
        group_rec = QGroupBox("Earthquake Waveform Input")
        v_rec = QVBoxLayout(group_rec)
        self.combo_source = QComboBox()
        self.combo_source.addItems([
            "Synthetic: Ricker Pulse (2.5 Hz)",
            "Synthetic: Harmonic Chirp (1 - 8 Hz)",
            "Load Historical .AT2 Record..."
        ])
        self.combo_source.currentIndexChanged.connect(self._on_source_changed)
        v_rec.addWidget(self.combo_source)

        self.btn_load = QPushButton("Select .AT2 Record File")
        self.btn_load.setVisible(False)
        self.btn_load.clicked.connect(self._browse_at2)
        v_rec.addWidget(self.btn_load)
        layout.addWidget(group_rec)

        layout.addStretch()

    def _add_field(self, form: QFormLayout, label: str, v_min: float, v_max: float, v_default: float, step: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(v_min, v_max)
        spin.setValue(v_default)
        spin.setSingleStep(step)
        spin.setDecimals(3)
        spin.valueChanged.connect(self._on_value_changed)
        form.addRow(label, spin)
        return spin

    def _on_liq_changed(self, val: int):
        factor = val / 100.0
        self.seismic.liquefaction_factor = factor
        self.lbl_liq.setText(f"{val}%")
        self.seismicChanged.emit(self.seismic)

    def _on_value_changed(self):
        self.seismic.horizontal_pga = self.spin_kh.value()
        self.seismic.vertical_pga = self.spin_kv.value()
        self.seismic.backfill_slope = self.spin_beta.value()
        self.seismic.water_table_depth = self.spin_water.value()
        self.seismicChanged.emit(self.seismic)

    def _on_source_changed(self, index: int):
        self.btn_load.setVisible(index == 2)
        self.seismicChanged.emit(self.seismic)

    def _browse_at2(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PEER Strong-Motion Record", "", "AT2 Files (*.AT2 *.at2);;All Files (*)")
        if path:
            self.recordLoaded.emit(path)

    def set_seismic(self, seismic: SeismicParams):
        """Updates panel controls to reflect external seismic parameters model."""
        self.seismic = seismic
        for spin in (self.spin_kh, self.spin_kv, self.spin_beta, self.spin_water):
            spin.blockSignals(True)
        self.slider_liq.blockSignals(True)

        self.spin_kh.setValue(seismic.horizontal_pga)
        self.spin_kv.setValue(seismic.vertical_pga)
        self.spin_beta.setValue(seismic.backfill_slope)
        self.spin_water.setValue(seismic.water_table_depth)
        liq_pct = int(seismic.liquefaction_factor * 100)
        self.slider_liq.setValue(liq_pct)
        self.lbl_liq.setText(f"{liq_pct}%")

        for spin in (self.spin_kh, self.spin_kv, self.spin_beta, self.spin_water):
            spin.blockSignals(False)
        self.slider_liq.blockSignals(False)
