"""
Unified Engineering Audit Sheet Generator for Indian Standard (IS) Design Codes:
IS 456:2000, IS 2911 (Part 1/Sec 2: 2010), IS 800:2007, and IS 1893 (Part 1/3: 2016).
Provides structured compliance summaries, exact clause citations, unity ratios (UR),
and formatted calculation sheets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import numpy as np

from ...models.is_code_params import IndianDesignStandards
from .is_456 import design_is456_flexure, design_is456_shear, check_is456_crack_width
from .is_2911 import (
    calculate_is2911_axial_capacity,
    calculate_is2911_lateral_capacity,
    design_is2911_structural_pile,
)
from .is_800 import design_is800_steel_strut


@dataclass
class AuditCheckItem:
    """Individual code check compliance item."""
    component: str                 # 'RC Shell Panel', 'Bored Pile', 'Steel Strut', etc.
    check_title: str               # 'Flexural Capacity', 'Punching Shear', 'Buckling', etc.
    code_clause: str               # Exact code reference (e.g. 'IS 456:2000 Cl. 38.1 & Annex G')
    demand: float                  # Design demand force/moment/stress
    capacity: float                # Design capacity
    unit: str                      # 'kNm/m', 'kN', 'MPa', 'mm', '-'
    unity_ratio: float             # Demand / Capacity
    status: str                    # 'PASS', 'WARNING', or 'FAIL'
    detailing_note: str            # e.g. '2-layer T16 @ 125 mm c/c each face'
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EngineeringAuditReport:
    """Unified structural and geotechnical engineering audit report."""
    project_title: str
    wall_model_name: str
    standards: IndianDesignStandards
    items: List[AuditCheckItem]
    max_unity_ratio: float
    governing_clause: str
    overall_status: str            # 'PASS', 'WARNING', or 'FAIL'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_title": self.project_title,
            "wall_model_name": self.wall_model_name,
            "standards": self.standards.to_dict(),
            "items": [it.to_dict() for it in self.items],
            "max_unity_ratio": self.max_unity_ratio,
            "governing_clause": self.governing_clause,
            "overall_status": self.overall_status,
        }

    def generate_markdown_audit_sheet(self) -> str:
        """Generates a human-readable engineering calculation audit sheet in GitHub Markdown."""
        lines = [
            f"# Structural & Geotechnical Audit Report: {self.wall_model_name}",
            f"**Project:** {self.project_title}  ",
            f"**Design Standards:** IS 456:2000, IS 2911 (Part 1/Sec 2: 2010), IS 800:2007, IS 1893:2016  ",
            f"**Concrete Grade:** {self.standards.concrete_grade} | **Steel Grade:** {self.standards.steel_grade} | **Seismic Zone:** {self.standards.seismic_zone} (Z={self.standards.zone_factor})  ",
            f"**Overall Compliance Status:** **{self.overall_status}** (Max UR = {self.max_unity_ratio:.3f} under {self.governing_clause})  ",
            "",
            "---",
            "",
            "## Summary of Design Compliance Checks",
            "",
            "| Component | Design Check | IS Code Clause | Demand | Capacity | Unit | Unity Ratio (UR) | Status | Detailing / Remarks |",
            "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |",
        ]

        for it in self.items:
            status_badge = f"**{it.status}**"
            lines.append(
                f"| {it.component} | {it.check_title} | `{it.code_clause}` | {it.demand:.2f} | {it.capacity:.2f} | {it.unit} | **{it.unity_ratio:.3f}** | {status_badge} | {it.detailing_note} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## Engineering Verification Verdict",
            "",
        ])

        if self.overall_status == "PASS":
            lines.append(
                f"> **PASSED:** All structural components satisfy the Limit State requirements of the relevant Indian Standards with maximum unity ratio UR = {self.max_unity_ratio:.3f}."
            )
        elif self.overall_status == "WARNING":
            lines.append(
                f"> **WARNING:** One or more components operate close to capacity (0.90 <= UR <= 1.00). Governing check: {self.governing_clause}."
            )
        else:
            lines.append(
                f"> **FAILED:** One or more structural/geotechnical components exceed permissible limits (UR > 1.00). Governing failure: {self.governing_clause}. Redesign required."
            )

        return "\n".join(lines)


def run_full_retaining_wall_is_audit(
    standards: IndianDesignStandards,
    panel_height_m: float = 6.0,
    panel_thickness_m: float = 0.40,
    max_panel_moment_kNm_m: float = 120.0,
    max_panel_shear_kN_m: float = 85.0,
    pile_diameter_m: float = 1.0,
    pile_length_m: float = 12.0,
    pile_axial_load_kN: float = 800.0,
    pile_lateral_shear_kN: float = 120.0,
    soil_cohesion_kPa: float = 15.0,
    soil_friction_deg: float = 30.0,
    soil_unit_weight_kNm3: float = 18.5,
    strut_length_m: float = 8.0,
    strut_compression_kN: float = 450.0,
    strut_tension_reversal_kN: float = 60.0,
    strut_area_mm2: float = 12500.0,
    strut_radius_gyration_mm: float = 110.0,
    strut_z_modulus_cm3: float = 1200.0,
    project_title: str = "High-Voltage Uphill Retaining System",
    wall_model_name: str = "Multi-Strut Piled Curved Retaining Wall",
    is_seismic: bool = True,
) -> EngineeringAuditReport:
    """
    Executes a comprehensive Indian Standard audit across:
    1. IS 456 RC Shell Panel Flexural Strength (Cl. 38)
    2. IS 456 RC Shell Panel Minimum Steel (Cl. 26.5.2.1)
    3. IS 456 RC Shell Panel Shear Stress (Cl. 40 & Table 19)
    4. IS 456 RC Shell Panel Crack Width Limitation (Annex F)
    5. IS 2911 Bored Pile Axial Compression Capacity (Appendix B)
    6. IS 2911 Bored Pile Lateral Fixity & Deflection (Appendix C)
    7. IS 2911 Bored Pile Structural Rebar Detailing (Cl. 6.11)
    8. IS 800 Steel Strut Compressive Buckling (Cl. 7.1.2 & Table 9c)
    9. IS 800 Steel Strut Slenderness Ratio Limit (Table 3)
    10. IS 800 Steel Strut Seismic Tension Reversal (Cl. 6.2)
    11. IS 800 Steel Strut End Joint Connection (Cl. 10.3)
    """
    f_ck = standards.f_ck
    f_y = standards.f_y
    items: List[AuditCheckItem] = []

    # ---------------------------------------------------------
    # 1. IS 456 RC Shell Panel Checks
    # ---------------------------------------------------------
    b_mm = 1000.0 # Per meter run
    d_mm = (panel_thickness_m * 1000.0) - 50.0 # 50 mm clear cover
    d_gross_mm = panel_thickness_m * 1000.0

    # 1.1 Flexure
    flex_res = design_is456_flexure(
        m_u_kNm=max_panel_moment_kNm_m,
        b_mm=b_mm,
        d_mm=d_mm,
        D_mm=d_gross_mm,
        f_ck=f_ck,
        f_y=f_y,
        is_slab=True,
    )
    items.append(
        AuditCheckItem(
            component="RC Shell Panel",
            check_title="Flexural Moment Resistance",
            code_clause="IS 456:2000 Cl. 38.1 & Annex G",
            demand=flex_res.m_u_applied,
            capacity=flex_res.m_u_applied / max(flex_res.unity_ratio, 1e-4) if flex_res.unity_ratio > 1.0 else (flex_res.m_u_lim if not flex_res.is_doubly_reinforced else flex_res.m_u_applied),
            unit="kNm/m",
            unity_ratio=flex_res.unity_ratio,
            status=flex_res.status,
            detailing_note=flex_res.bar_callout,
            details=flex_res.to_dict(),
        )
    )

    # 1.2 Minimum Reinforcement
    min_pt_ratio = 0.0012 if f_y >= 415.0 else 0.0015
    ast_min_req = min_pt_ratio * b_mm * d_gross_mm
    ur_min_steel = ast_min_req / max(flex_res.a_st_provided, 1.0)
    items.append(
        AuditCheckItem(
            component="RC Shell Panel",
            check_title="Minimum Reinforcement (HYSD)",
            code_clause="IS 456:2000 Cl. 26.5.2.1",
            demand=ast_min_req,
            capacity=flex_res.a_st_provided,
            unit="mm2/m",
            unity_ratio=ur_min_steel,
            status="PASS" if ur_min_steel <= 1.0 else "FAIL",
            detailing_note=f"Ast provided = {flex_res.a_st_provided:.0f} mm2/m >= {ast_min_req:.0f} mm2/m",
            details={"a_st_min_mm2": ast_min_req, "a_st_provided_mm2": flex_res.a_st_provided},
        )
    )

    # 1.3 Shear
    shear_res = design_is456_shear(
        v_u_kN=max_panel_shear_kN_m,
        b_mm=b_mm,
        d_mm=d_mm,
        f_ck=f_ck,
        f_y=f_y,
        a_st_provided_mm2=flex_res.a_st_provided,
        is_slab=True,
        D_mm=d_gross_mm,
    )
    items.append(
        AuditCheckItem(
            component="RC Shell Panel",
            check_title="Transverse Shear Stress",
            code_clause="IS 456:2000 Cl. 40 & Table 19",
            demand=shear_res.tau_v,
            capacity=shear_res.tau_c if not shear_res.shear_rebar_required else shear_res.tau_c_max,
            unit="MPa",
            unity_ratio=shear_res.unity_ratio,
            status=shear_res.status,
            detailing_note=shear_res.stirrup_callout,
            details=shear_res.to_dict(),
        )
    )

    # 1.4 Crack Width Check
    # Estimate bar spacing from callout or Ast
    bar_dia = 16.0
    bar_area = (math.pi / 4.0) * (bar_dia ** 2)
    spacing_calc = (b_mm * bar_area) / (flex_res.a_st_provided / 2.0)
    crack_res = check_is456_crack_width(
        m_service_kNm=max_panel_moment_kNm_m / 1.5,
        b_mm=b_mm,
        d_mm=d_mm,
        D_mm=d_gross_mm,
        a_st_provided_mm2=flex_res.a_st_provided,
        bar_dia_mm=bar_dia,
        bar_spacing_mm=min(spacing_calc, 150.0),
        cover_mm=50.0,
        aggressive_environment=True,
    )
    items.append(
        AuditCheckItem(
            component="RC Shell Panel",
            check_title="Surface Crack Width Limit",
            code_clause="IS 456:2000 Annex F & Cl. 35.3.2",
            demand=crack_res.calculated_crack_width,
            capacity=crack_res.allowable_crack_width,
            unit="mm",
            unity_ratio=crack_res.unity_ratio,
            status=crack_res.status,
            detailing_note=f"w_cr = {crack_res.calculated_crack_width:.3f} mm <= {crack_res.allowable_crack_width} mm",
            details=crack_res.to_dict(),
        )
    )

    # ---------------------------------------------------------
    # 2. IS 2911 Bored Cast-in-Situ Pile Checks
    # ---------------------------------------------------------
    # 2.1 Axial Geotechnical Capacity
    axial_res = calculate_is2911_axial_capacity(
        pile_diameter_m=pile_diameter_m,
        pile_length_m=pile_length_m,
        cohesion_kPa=soil_cohesion_kPa,
        friction_angle_deg=soil_friction_deg,
        unit_weight_kNm3=soil_unit_weight_kNm3,
        applied_axial_kN=pile_axial_load_kN,
        is_seismic=is_seismic,
    )
    items.append(
        AuditCheckItem(
            component="Bored Pile",
            check_title="Axial Geotechnical Compression",
            code_clause="IS 2911:2010 Part 1/Sec 2 Appendix B",
            demand=axial_res.applied_axial_load,
            capacity=axial_res.safe_capacity,
            unit="kN",
            unity_ratio=axial_res.unity_ratio,
            status=axial_res.status,
            detailing_note=f"Q_safe = {axial_res.safe_capacity:.1f} kN (FS={axial_res.factor_of_safety})",
            details=axial_res.to_dict(),
        )
    )

    # 2.2 Lateral Pile Capacity & Depth of Fixity
    lat_res = calculate_is2911_lateral_capacity(
        pile_diameter_m=pile_diameter_m,
        pile_length_m=pile_length_m,
        f_ck=f_ck,
        subgrade_modulus_nh_kNm3=6000.0,
        applied_lateral_kN=pile_lateral_shear_kN,
        fixed_head=True,
    )
    items.append(
        AuditCheckItem(
            component="Bored Pile",
            check_title="Lateral Shear & Fixity Deflection",
            code_clause="IS 2911:2010 Part 1/Sec 2 Appendix C",
            demand=lat_res.applied_lateral_shear,
            capacity=lat_res.safe_lateral_capacity,
            unit="kN",
            unity_ratio=lat_res.unity_ratio,
            status=lat_res.status,
            detailing_note=f"zf = {lat_res.depth_of_fixity_zf:.2f} m, y = {lat_res.estimated_deflection*1000:.2f} mm <= 5.0 mm",
            details=lat_res.to_dict(),
        )
    )

    # 2.3 Structural Rebar Detailing
    struct_pile = design_is2911_structural_pile(
        pile_diameter_m=pile_diameter_m,
        pile_length_m=pile_length_m,
        f_ck=f_ck,
        f_y=f_y,
        applied_axial_kN=pile_axial_load_kN,
    )
    items.append(
        AuditCheckItem(
            component="Bored Pile",
            check_title="Structural Concrete Compression",
            code_clause="IS 2911:2010 Cl. 6.11 & IS 456 Cl. 39.3",
            demand=pile_axial_load_kN,
            capacity=struct_pile.axial_structural_capacity_kN,
            unit="kN",
            unity_ratio=struct_pile.unity_ratio,
            status=struct_pile.status,
            detailing_note=f"{struct_pile.rebar_cage_callout}; {struct_pile.helical_binder_callout}",
            details=struct_pile.to_dict(),
        )
    )

    # ---------------------------------------------------------
    # 3. IS 800 Structural Steel Strut Checks
    # ---------------------------------------------------------
    strut_res = design_is800_steel_strut(
        applied_compression_kN=strut_compression_kN,
        effective_length_m=strut_length_m,
        section_area_mm2=strut_area_mm2,
        radius_of_gyration_mm=strut_radius_gyration_mm,
        f_y=250.0,
        f_u=410.0,
        applied_tension_reversal_kN=strut_tension_reversal_kN,
        elastic_section_modulus_z_cm3=strut_z_modulus_cm3,
        buckling_curve="c",
        is_seismic=is_seismic,
    )

    # 3.1 Compression Buckling
    items.append(
        AuditCheckItem(
            component="Steel Strut",
            check_title="Axial Compressive Buckling",
            code_clause="IS 800:2007 Cl. 7.1.2 & Table 9c",
            demand=strut_res.compression_result.applied_compression_force,
            capacity=strut_res.compression_result.design_compressive_strength_pd,
            unit="kN",
            unity_ratio=strut_res.compression_result.unity_ratio,
            status=strut_res.compression_result.status,
            detailing_note=f"fcd = {strut_res.compression_result.design_compressive_stress_fcd:.1f} MPa (Curve c)",
            details=strut_res.compression_result.to_dict(),
        )
    )

    # 3.2 Slenderness Ratio Limit
    items.append(
        AuditCheckItem(
            component="Steel Strut",
            check_title="Maximum Slenderness Ratio (KL/r)",
            code_clause="IS 800:2007 Table 3",
            demand=strut_res.compression_result.slenderness_ratio,
            capacity=strut_res.compression_result.max_slenderness_limit,
            unit="-",
            unity_ratio=strut_res.compression_result.slenderness_ratio / strut_res.compression_result.max_slenderness_limit,
            status=strut_res.compression_result.slenderness_status,
            detailing_note=f"KL/r = {strut_res.compression_result.slenderness_ratio:.1f} <= {strut_res.compression_result.max_slenderness_limit:.0f}",
            details={"slenderness": strut_res.compression_result.slenderness_ratio},
        )
    )

    # 3.3 Seismic Tension Reversal
    items.append(
        AuditCheckItem(
            component="Steel Strut",
            check_title="Seismic Tension Reversal Yield",
            code_clause="IS 800:2007 Cl. 6.2",
            demand=strut_res.tension_result.applied_tension_demand,
            capacity=strut_res.tension_result.design_tension_capacity_td,
            unit="kN",
            unity_ratio=strut_res.tension_result.unity_ratio,
            status=strut_res.tension_result.status,
            detailing_note=f"Td = {strut_res.tension_result.design_tension_capacity_td:.1f} kN",
            details=strut_res.tension_result.to_dict(),
        )
    )

    # 3.4 Connection Detailing
    items.append(
        AuditCheckItem(
            component="Steel Strut",
            check_title="End Connection Joint Capacity",
            code_clause="IS 800:2007 Section 10",
            demand=strut_res.connection_result.applied_load_kN,
            capacity=strut_res.connection_result.connection_capacity_kN,
            unit="kN",
            unity_ratio=strut_res.connection_result.unity_ratio,
            status=strut_res.connection_result.status,
            detailing_note=f"{strut_res.connection_result.num_bolts_required}-M{int(strut_res.connection_result.bolt_diameter_mm)} Grade 8.8 bolts",
            details=strut_res.connection_result.to_dict(),
        )
    )

    # Evaluate governing failure / status
    max_ur = max(it.unity_ratio for it in items)
    gov_item = max(items, key=lambda it: it.unity_ratio)

    if any(it.status == "FAIL" for it in items):
        overall_status = "FAIL"
    elif any(it.status == "WARNING" for it in items) or max_ur >= 0.90:
        overall_status = "WARNING"
    else:
        overall_status = "PASS"

    return EngineeringAuditReport(
        project_title=project_title,
        wall_model_name=wall_model_name,
        standards=standards,
        items=items,
        max_unity_ratio=float(max_ur),
        governing_clause=f"{gov_item.component} ({gov_item.code_clause})",
        overall_status=overall_status,
    )
