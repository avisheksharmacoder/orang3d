"""
PySide6 Engineering Audit Tab displaying live Indian Standards (IS Code) compliance checklist (Phase 10).
"""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QFileDialog, QMessageBox
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt

from ...physics.is_codes.audit_engine import EngineeringAuditReport, run_full_retaining_wall_is_audit
from ...models.is_code_params import IndianDesignStandards


class ISDesignAuditTab(QWidget):
    """
    Live engineering compliance checklist displaying IS 456, IS 2911, and IS 800
    demand-to-capacity unity ratios with color-coded status badges:
    - Green (UR <= 0.90): PASS
    - Yellow (0.90 < UR <= 1.00): WARNING
    - Red (UR > 1.00): FAIL
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_report: Optional[EngineeringAuditReport] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 1. Status Banner
        banner_layout = QHBoxLayout()
        self.lbl_overall = QLabel("Overall Compliance Status: INITIALIZING...")
        self.lbl_overall.setFont(QFont("Arial", 11, QFont.Bold))
        banner_layout.addWidget(self.lbl_overall)
        banner_layout.addStretch()

        self.btn_export = QPushButton("Export Audit Sheet (.md)...")
        self.btn_export.clicked.connect(self._on_export_clicked)
        banner_layout.addWidget(self.btn_export)

        layout.addLayout(banner_layout)

        # 2. Compliance Table Widget
        self.table = QTableWidget()
        headers = [
            "Component", "Design Check", "IS Clause", "Demand", "Capacity",
            "Unit", "Unity Ratio (UR)", "Status", "Detailing / Remarks"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        # Populate initial default report
        initial_report = run_full_retaining_wall_is_audit(IndianDesignStandards())
        self.update_audit(report=initial_report)

    def update_audit(
        self,
        report: Optional[EngineeringAuditReport] = None,
        shell_geom=None,
        pier_pile_geom=None,
        struts=None,
        soil=None,
        seismic=None,
        standards=None,
    ):
        """Refreshes the checklist table with new audit report items or computes from parameters."""
        if report is None:
            stds = standards or IndianDesignStandards()
            p_height = shell_geom.panel_height if shell_geom else 6.0
            p_thick = shell_geom.thickness if shell_geom else 0.40
            d_pile = pier_pile_geom.pile_diameter if pier_pile_geom else 1.0
            l_pile = pier_pile_geom.pile_length if pier_pile_geom else 12.0
            c_soil = soil.cohesion if soil else 15.0
            phi_soil = soil.friction_angle if soil else 30.0
            gamma_soil = soil.unit_weight if soil else 18.5
            is_seis = (seismic.horizontal_pga > 0.05) if seismic else True

            report = run_full_retaining_wall_is_audit(
                standards=stds,
                panel_height_m=p_height,
                panel_thickness_m=p_thick,
                pile_diameter_m=d_pile,
                pile_length_m=l_pile,
                soil_cohesion_kPa=c_soil,
                soil_friction_deg=phi_soil,
                soil_unit_weight_kNm3=gamma_soil,
                is_seismic=is_seis,
            )

        self.current_report = report

        # Update Banner
        status = report.overall_status
        max_ur = report.max_unity_ratio
        gov = report.governing_clause

        if status == "PASS":
            self.lbl_overall.setText(f"Overall Compliance: PASSED (Max UR = {max_ur:.3f} | {gov})")
            self.lbl_overall.setStyleSheet("color: #2e7d32; font-weight: bold;")
        elif status == "WARNING":
            self.lbl_overall.setText(f"Overall Compliance: WARNING (Max UR = {max_ur:.3f} | {gov})")
            self.lbl_overall.setStyleSheet("color: #e65100; font-weight: bold;")
        else:
            self.lbl_overall.setText(f"Overall Compliance: FAILED (Max UR = {max_ur:.3f} | {gov})")
            self.lbl_overall.setStyleSheet("color: #c62828; font-weight: bold;")

        # Populate Table Rows
        self.table.setRowCount(len(report.items))
        for row, item in enumerate(report.items):
            self.table.setItem(row, 0, QTableWidgetItem(item.component))
            self.table.setItem(row, 1, QTableWidgetItem(item.check_title))
            self.table.setItem(row, 2, QTableWidgetItem(item.code_clause))
            self.table.setItem(row, 3, QTableWidgetItem(f"{item.demand:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{item.capacity:.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(item.unit))

            # Unity Ratio Item
            ur_item = QTableWidgetItem(f"{item.unity_ratio:.3f}")
            ur_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 6, ur_item)

            # Status Badge with Background Color
            status_item = QTableWidgetItem(item.status)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setFont(QFont("Arial", 9, QFont.Bold))

            if item.status == "PASS":
                status_item.setBackground(QColor(232, 245, 233)) # Light green
                status_item.setForeground(QColor(46, 125, 50))   # Dark green
            elif item.status == "WARNING":
                status_item.setBackground(QColor(255, 243, 224)) # Light orange
                status_item.setForeground(QColor(230, 81, 0))    # Dark orange
            else:
                status_item.setBackground(QColor(255, 235, 238)) # Light red
                status_item.setForeground(QColor(198, 40, 40))   # Dark red

            self.table.setItem(row, 7, status_item)
            self.table.setItem(row, 8, QTableWidgetItem(item.detailing_note))

    def _on_export_clicked(self):
        """Exports the markdown calculation sheet to file."""
        if not self.current_report:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Engineering Audit Report",
            "retaining_wall_is_audit_report.md",
            "Markdown Files (*.md);;Text Files (*.txt)"
        )
        if file_path:
            md_content = self.current_report.generate_markdown_audit_sheet()
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            QMessageBox.information(
                self,
                "Audit Sheet Exported",
                f"Engineering calculation audit sheet successfully exported to:\n{file_path}"
            )
