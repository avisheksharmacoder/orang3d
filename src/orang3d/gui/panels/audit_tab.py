"""
PySide6 Engineering Design Audit Tab (v3 Phase 6).

Supports switching seamlessly across international design codes:
  - Indian Standards (IS 456:2000, IS 2911, IS 800:2007, IS 1893:2016, IS 14458)
  - Eurocode 7 & 8 (EN 1997-1 DA1-C1/C2, EN 1998-5, EN 1992-1-1)
  - AASHTO LRFD Bridge Design Specifications (Strength I & Extreme Event I)
  - ACI 318-19 Building Code Requirements for Structural Concrete

Also respects the active UI UnitSystem (SI vs. Imperial) for demand/capacity display
while evaluating every code limit state canonically in SI.
"""

from __future__ import annotations

from typing import Optional, Union
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...config import RegionalStandard
from ...models.is_code_params import IndianDesignStandards
from ...physics.code_auditor import (
    DesignCodeAuditor,
    MultiCodeAuditReport,
    STANDARD_LABELS,
)
from ...physics.is_codes.audit_engine import EngineeringAuditReport
from ...units import UnitSystem


class DesignAuditTab(QWidget):
    """
    Live multi-code engineering compliance checklist with Design Code Selector
    and dynamic SI/Imperial unit formatting.
    """

    standardChanged = Signal(RegionalStandard)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_standard: RegionalStandard = RegionalStandard.IS_14458
        self.unit_system: UnitSystem = UnitSystem.SI
        self.current_report: Optional[Union[EngineeringAuditReport, MultiCodeAuditReport]] = None
        self._last_ctx: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 1. Top Bar: Code Selector + Status Banner + Export (responsive 2-row layout)
        banner_container = QVBoxLayout()
        banner_container.setContentsMargins(0, 0, 0, 0)
        banner_container.setSpacing(4)

        row_code = QHBoxLayout()
        row_code.addWidget(QLabel("Design Code:"))
        self.combo_standard = QComboBox()
        for std in (
            RegionalStandard.IS_14458,
            RegionalStandard.EUROCODE_7,
            RegionalStandard.AASHTO_LRFD,
            RegionalStandard.ACI_318,
        ):
            self.combo_standard.addItem(STANDARD_LABELS[std], std)
        self.combo_standard.currentIndexChanged.connect(self._on_standard_changed)
        row_code.addWidget(self.combo_standard)
        row_code.addStretch()

        self.btn_export = QPushButton("Export Audit Sheet (.md)...")
        self.btn_export.clicked.connect(self._on_export_clicked)
        row_code.addWidget(self.btn_export)
        banner_container.addLayout(row_code)

        row_status = QHBoxLayout()
        self.lbl_overall = QLabel("Overall Compliance Status: INITIALIZING...")
        self.lbl_overall.setFont(QFont("Arial", 10, QFont.Bold))
        row_status.addWidget(self.lbl_overall)
        row_status.addStretch()
        banner_container.addLayout(row_status)

        layout.addLayout(banner_container)

        # 2. Compliance Table Widget
        self.table = QTableWidget()
        headers = [
            "Component", "Design Check", "Code Clause", "Demand", "Capacity",
            "Unit", "Unity Ratio (UR)", "Status", "Detailing / Remarks",
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        # Populate initial default report
        self.update_audit()

    def _on_standard_changed(self):
        std = self.combo_standard.currentData()
        if std is not None:
            self.current_standard = RegionalStandard(std)
            self.standardChanged.emit(self.current_standard)
            self.update_audit(**self._last_ctx)

    def set_standard(self, standard: Union[RegionalStandard, str]) -> None:
        """Programmatically selects the active design standard."""
        std = RegionalStandard(standard) if isinstance(standard, str) else standard
        idx = self.combo_standard.findData(std)
        if idx >= 0:
            self.combo_standard.blockSignals(True)
            self.combo_standard.setCurrentIndex(idx)
            self.combo_standard.blockSignals(False)
        self.current_standard = std
        self.update_audit(**self._last_ctx)

    def set_unit_system(self, unit_system: Union[UnitSystem, str]) -> None:
        """Switches demand/capacity display units without mutating unity ratios."""
        self.unit_system = UnitSystem(unit_system)
        self._render_current_report()

    def update_audit(
        self,
        report: Optional[Union[EngineeringAuditReport, MultiCodeAuditReport]] = None,
        geom=None,
        shell_geom=None,
        pier_pile_geom=None,
        struts=None,
        soil=None,
        seismic=None,
        results=None,
        standards: Optional[IndianDesignStandards] = None,
    ):
        """Refreshes the checklist table from an explicit report or active model parameters."""
        if report is None:
            self._last_ctx = {
                "geom": geom,
                "shell_geom": shell_geom,
                "pier_pile_geom": pier_pile_geom,
                "struts": struts,
                "soil": soil,
                "seismic": seismic,
                "results": results,
                "standards": standards,
            }
            report = DesignCodeAuditor.run_audit(
                standard=self.current_standard,
                geom=geom,
                soil=soil,
                seismic=seismic,
                results=results,
                shell_geom=shell_geom,
                pier_pile_geom=pier_pile_geom,
                strut_sys=struts,
                standards=standards,
            )
        self.current_report = report
        self._render_current_report()

    def _render_current_report(self) -> None:
        """Renders `self.current_report` in the active unit system."""
        report = self.current_report
        if report is None:
            return

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

        if isinstance(report, MultiCodeAuditReport):
            items = report.items_in_units(self.unit_system)
        else:
            items = list(report.items)

        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(item.component))
            self.table.setItem(row, 1, QTableWidgetItem(item.check_title))
            self.table.setItem(row, 2, QTableWidgetItem(item.code_clause))
            self.table.setItem(row, 3, QTableWidgetItem(f"{item.demand:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{item.capacity:.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(item.unit))

            ur_item = QTableWidgetItem(f"{item.unity_ratio:.3f}")
            ur_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 6, ur_item)

            status_item = QTableWidgetItem(item.status)
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setFont(QFont("Arial", 9, QFont.Bold))
            if item.status == "PASS":
                status_item.setBackground(QColor(232, 245, 233))
                status_item.setForeground(QColor(46, 125, 50))
            elif item.status == "WARNING":
                status_item.setBackground(QColor(255, 243, 224))
                status_item.setForeground(QColor(230, 81, 0))
            else:
                status_item.setBackground(QColor(255, 235, 238))
                status_item.setForeground(QColor(198, 40, 40))

            self.table.setItem(row, 7, status_item)
            self.table.setItem(row, 8, QTableWidgetItem(item.detailing_note))

    def _on_export_clicked(self):
        """Exports the markdown calculation sheet to file."""
        if not self.current_report:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Engineering Audit Report",
            "retaining_wall_audit_report.md",
            "Markdown Files (*.md);;Text Files (*.txt)",
        )
        if file_path:
            if isinstance(self.current_report, MultiCodeAuditReport):
                md_content = self.current_report.generate_markdown_audit_sheet(self.unit_system)
            else:
                md_content = self.current_report.generate_markdown_audit_sheet()
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            QMessageBox.information(
                self,
                "Audit Sheet Exported",
                f"Engineering calculation audit sheet successfully exported to:\n{file_path}",
            )


# Backward-compatible alias preserved for all earlier phases/tests
ISDesignAuditTab = DesignAuditTab
