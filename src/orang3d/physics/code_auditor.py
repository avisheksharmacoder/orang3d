"""
Unified Multi-Code International Design Audit Engine (v3 Phase 6).

Supports four major international retaining wall and structural design frameworks
behind a single `DesignCodeAuditor` interface:
  1. Indian Standards: IS 456:2000, IS 2911, IS 800:2007, IS 1893:2016, IS 14458
  2. Eurocode 7 & 8: EN 1997-1 (DA1-C1 / DA1-C2), EN 1998-5 (EC8), EN 1992-1-1
  3. AASHTO LRFD Bridge Design Specifications (9th Ed.): Strength I & Extreme Event I
  4. ACI 318-19: Stem Flexure, One-Way Shear, Minimum Steel & Development Length
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Tuple, Union

from ..config import RegionalStandard, get_safety_thresholds
from ..models.advanced_wall_params import (
    CurvedShellGeometry,
    PierAndPileGeometry,
    StrutSupportSystem,
)
from ..models.is_code_params import IndianDesignStandards
from ..models.wall_params import (
    AnalysisResults,
    RetainingWallGeometry,
    SeismicParams,
    SoilProperties,
)
from ..units import UnitSystem, from_si_value, unit_label
from .is_codes.audit_engine import (
    AuditCheckItem,
    run_full_retaining_wall_is_audit,
)
from .mononobe_okabe import (
    compute_lateral_thrusts,
    compute_mononobe_okabe,
    compute_rankine_earth_pressures,
)
from .stability import compute_ultimate_bearing_capacity, evaluate_wall_stability


STANDARD_LABELS: Dict[RegionalStandard, str] = {
    RegionalStandard.IS_14458: "Indian Standards (IS 456 / 2911 / 800 / 1893 / 14458)",
    RegionalStandard.EUROCODE_7: "Eurocode 7 & 8 (EN 1997-1 DA1 / EN 1998-5 / EN 1992-1-1)",
    RegionalStandard.AASHTO_LRFD: "AASHTO LRFD Bridge Design Specs (Strength I & Extreme Event I)",
    RegionalStandard.ACI_318: "ACI 318-19 Building Code Requirements for Structural Concrete",
    RegionalStandard.STANDARD: "Standard Benchmark Thresholds",
}


def _status_from_ur(ur: float, warn_cutoff: float = 0.90) -> str:
    """Maps a demand/capacity unity ratio to PASS / WARNING / FAIL."""
    if ur <= warn_cutoff:
        return "PASS"
    if ur <= 1.0:
        return "WARNING"
    return "FAIL"


def _compute_wall_vertical_dead_weights(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
) -> Tuple[float, float, float]:
    """Returns `(w_concrete, w_soil_heel, total_dead)` in kN/m."""
    gamma_c = geom.concrete_unit_weight
    w_footing = geom.base_width * geom.footing_thickness * gamma_c
    w_stem = (
        0.5
        * (geom.stem_thickness_top + geom.stem_thickness_base)
        * geom.stem_height
        * gamma_c
    )
    w_key = geom.shear_key_width * geom.shear_key_depth * gamma_c
    w_concrete = w_footing + w_stem + w_key
    w_soil_heel = geom.heel_length * geom.stem_height * soil.unit_weight
    return w_concrete, w_soil_heel, w_concrete + w_soil_heel


def _compute_sliding_resistance_unfactored(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    vertical_load_eff: float,
    phi_found_deg: float,
    c_found_kpa: float,
) -> float:
    """Computes nominal sliding resistance R_n (kN/m) with friction, adhesion & toe passive."""
    phi_b = math.radians(phi_found_deg * 0.75)
    c_a = c_found_kpa * 0.6
    _, kp_found = compute_rankine_earth_pressures(phi_found_deg)
    d_embed = geom.footing_thickness + geom.shear_key_depth
    p_passive = 0.5 * soil.foundation_unit_weight * (d_embed ** 2) * kp_found
    if geom.shear_key_depth > 0:
        y1 = geom.footing_thickness
        y2 = y1 + geom.shear_key_depth
        p_passive += 0.5 * soil.foundation_unit_weight * (y2 ** 2 - y1 ** 2) * kp_found
    return float(vertical_load_eff * math.tan(phi_b) + c_a * geom.base_width + p_passive)


def _display_item_in_unit_system(item: AuditCheckItem, unit_system: UnitSystem) -> AuditCheckItem:
    """Converts a canonical-SI AuditCheckItem's demand/capacity into the display unit system."""
    if unit_system == UnitSystem.SI:
        return item
    kind_map = {
        "kN": "force",
        "kN/m": "force_per_m",
        "kNm": "moment",
        "kNm/m": "moment_per_m",
        "kPa": "pressure",
        "MPa": "stress_mpa",
        "m": "length",
        "mm": "disp_mm",
        "cm": "disp_cm",
    }
    kind = kind_map.get(item.unit)
    if kind is None:
        return item
    return AuditCheckItem(
        component=item.component,
        check_title=item.check_title,
        code_clause=item.code_clause,
        demand=from_si_value(item.demand, kind, unit_system),
        capacity=from_si_value(item.capacity, kind, unit_system),
        unit=unit_label(kind, unit_system),
        unity_ratio=item.unity_ratio,
        status=item.status,
        detailing_note=item.detailing_note,
        details=dict(item.details),
    )


@dataclass
class MultiCodeAuditReport:
    """Unified multi-code structural and geotechnical compliance report."""

    standard: RegionalStandard
    standard_label: str
    project_title: str
    wall_model_name: str
    items: List[AuditCheckItem]
    max_unity_ratio: float
    governing_clause: str
    overall_status: str

    def items_in_units(self, unit_system: Union[UnitSystem, str] = UnitSystem.SI) -> List[AuditCheckItem]:
        """Returns items converted for UI table display without altering unity ratios."""
        u_sys = UnitSystem(unit_system)
        return [_display_item_in_unit_system(it, u_sys) for it in self.items]

    def generate_markdown_audit_sheet(
        self,
        unit_system: Union[UnitSystem, str] = UnitSystem.SI,
    ) -> str:
        """Generates a formatted GitHub Markdown calculation audit sheet."""
        u_sys = UnitSystem(unit_system)
        display_items = self.items_in_units(u_sys)
        lines = [
            f"# Multi-Code Design Audit Report: {self.wall_model_name}",
            f"**Project:** {self.project_title}  ",
            f"**Design Standard:** {self.standard_label}  ",
            f"**Unit System:** {u_sys.value.upper()}  ",
            (
                f"**Overall Compliance Status:** **{self.overall_status}** "
                f"(Max UR = {self.max_unity_ratio:.3f} under `{self.governing_clause}`)  "
            ),
            "",
            "| Component | Design Check | Code Clause | Demand | Capacity | Unit | Unity Ratio (UR) | Status | Detailing / Remarks |",
            "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |",
        ]
        for it in display_items:
            lines.append(
                f"| {it.component} | {it.check_title} | `{it.code_clause}` | "
                f"{it.demand:.2f} | {it.capacity:.2f} | {it.unit} | "
                f"**{it.unity_ratio:.3f}** | **{it.status}** | {it.detailing_note} |"
            )
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, object]:
        return {
            "standard": self.standard.value,
            "standard_label": self.standard_label,
            "project_title": self.project_title,
            "wall_model_name": self.wall_model_name,
            "items": [it.to_dict() for it in self.items],
            "max_unity_ratio": self.max_unity_ratio,
            "governing_clause": self.governing_clause,
            "overall_status": self.overall_status,
        }


class DesignCodeAuditor:
    """Stateless multi-code auditor evaluating IS, Eurocode 7/8, AASHTO LRFD, and ACI 318."""

    @staticmethod
    def _finalize(
        standard: RegionalStandard,
        project_title: str,
        wall_model_name: str,
        items: List[AuditCheckItem],
    ) -> MultiCodeAuditReport:
        max_ur = max((it.unity_ratio for it in items), default=0.0)
        gov_item = max(items, key=lambda it: it.unity_ratio)
        if any(it.status == "FAIL" for it in items):
            overall = "FAIL"
        elif any(it.status == "WARNING" for it in items) or max_ur >= 0.90:
            overall = "WARNING"
        else:
            overall = "PASS"

        return MultiCodeAuditReport(
            standard=standard,
            standard_label=STANDARD_LABELS.get(standard, standard.value),
            project_title=project_title,
            wall_model_name=wall_model_name,
            items=items,
            max_unity_ratio=float(max_ur),
            governing_clause=f"{gov_item.component} ({gov_item.code_clause})",
            overall_status=overall,
        )

    @classmethod
    def run_audit(
        cls,
        standard: Union[RegionalStandard, str] = RegionalStandard.IS_14458,
        geom: Optional[RetainingWallGeometry] = None,
        soil: Optional[SoilProperties] = None,
        seismic: Optional[SeismicParams] = None,
        results: Optional[AnalysisResults] = None,
        shell_geom: Optional[CurvedShellGeometry] = None,
        pier_pile_geom: Optional[PierAndPileGeometry] = None,
        strut_sys: Optional[StrutSupportSystem] = None,
        standards: Optional[IndianDesignStandards] = None,
        soil_factor_S: float = 1.15,
        topography_factor_ST: float = 1.0,
        ec8_r_factor: float = 1.5,
        concrete_strength_mpa: float = 28.0,
        steel_yield_mpa: float = 415.0,
        project_title: str = "Retaining Wall Multi-Code Audit",
    ) -> MultiCodeAuditReport:
        """Executes a complete structural & geotechnical audit under the selected code."""
        std = RegionalStandard(standard) if isinstance(standard, str) else standard
        g = geom or RetainingWallGeometry()
        s = soil or SoilProperties()
        e = seismic or SeismicParams()
        r = results if results is not None else evaluate_wall_stability(g, s, e)

        if std in (RegionalStandard.IS_14458, RegionalStandard.STANDARD):
            return cls._audit_indian_standards(
                std, g, s, e, r, shell_geom, pier_pile_geom, standards, project_title
            )
        if std == RegionalStandard.EUROCODE_7:
            return cls._audit_eurocode(
                g, s, e, r, soil_factor_S, topography_factor_ST, ec8_r_factor,
                concrete_strength_mpa, steel_yield_mpa, project_title,
            )
        if std == RegionalStandard.AASHTO_LRFD:
            return cls._audit_aashto(
                g, s, e, r, concrete_strength_mpa, steel_yield_mpa, project_title,
            )
        if std == RegionalStandard.ACI_318:
            return cls._audit_aci318(
                g, s, e, r, concrete_strength_mpa, steel_yield_mpa, project_title,
            )
        raise ValueError(f"Unsupported audit standard: {std}")

    @classmethod
    def _audit_indian_standards(
        cls,
        std: RegionalStandard,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        results: AnalysisResults,
        shell_geom: Optional[CurvedShellGeometry],
        pier_pile_geom: Optional[PierAndPileGeometry],
        standards: Optional[IndianDesignStandards],
        project_title: str,
    ) -> MultiCodeAuditReport:
        stds = standards or IndianDesignStandards()
        is_seis = seismic.horizontal_pga > 0.05
        p_h = shell_geom.panel_height if shell_geom else geom.stem_height
        p_t = shell_geom.thickness if shell_geom else geom.stem_thickness_base
        d_pile = pier_pile_geom.pile_diameter if pier_pile_geom else 0.9
        l_pile = pier_pile_geom.pile_length if pier_pile_geom else 12.0

        is_rep = run_full_retaining_wall_is_audit(
            standards=stds,
            panel_height_m=p_h,
            panel_thickness_m=p_t,
            pile_diameter_m=d_pile,
            pile_length_m=l_pile,
            soil_cohesion_kPa=soil.cohesion,
            soil_friction_deg=soil.friction_angle,
            soil_unit_weight_kNm3=soil.unit_weight,
            is_seismic=is_seis,
            project_title=project_title,
        )
        items = list(is_rep.items)

        thresholds = get_safety_thresholds(std)
        req_slide = thresholds["sliding_seismic"] if is_seis else thresholds["sliding_static"]
        req_ot = thresholds["overturning_seismic"] if is_seis else thresholds["overturning_static"]
        req_bear = thresholds["bearing_seismic"] if is_seis else thresholds["bearing_static"]

        ur_slide = req_slide / max(1e-3, results.fs_sliding)
        ur_ot = req_ot / max(1e-3, results.fs_overturning)
        ur_bear = req_bear / max(1e-3, results.fs_bearing)

        items.extend([
            AuditCheckItem(
                component="Wall Stability",
                check_title="Global Base Sliding Resistance",
                code_clause="IS 14458-1 / IS 1893:2016 Cl. 7",
                demand=req_slide,
                capacity=results.fs_sliding,
                unit="FS",
                unity_ratio=ur_slide,
                status=_status_from_ur(ur_slide),
                detailing_note=f"FS_slide = {results.fs_sliding:.2f} >= {req_slide:.2f}",
            ),
            AuditCheckItem(
                component="Wall Stability",
                check_title="Toe Overturning Stability",
                code_clause="IS 14458-1 Cl. 8.3",
                demand=req_ot,
                capacity=results.fs_overturning,
                unit="FS",
                unity_ratio=ur_ot,
                status=_status_from_ur(ur_ot),
                detailing_note=f"FS_OT = {results.fs_overturning:.2f} >= {req_ot:.2f}",
            ),
            AuditCheckItem(
                component="Foundation Soil",
                check_title="Meyerhof Bearing Capacity",
                code_clause="IS 6403 / IS 14458-1",
                demand=req_bear,
                capacity=results.fs_bearing,
                unit="FS",
                unity_ratio=ur_bear,
                status=_status_from_ur(ur_bear),
                detailing_note=f"q_max = {results.max_bearing_pressure:.1f} kPa, FS = {results.fs_bearing:.2f}",
            ),
        ])
        return cls._finalize(std, project_title, is_rep.wall_model_name, items)

    @classmethod
    def _audit_eurocode(
        cls,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        results: AnalysisResults,
        soil_factor_S: float,
        topography_factor_ST: float,
        ec8_r_factor: float,
        f_ck_mpa: float,
        f_yk_mpa: float,
        project_title: str,
    ) -> MultiCodeAuditReport:
        w_conc, _, w_dead = _compute_wall_vertical_dead_weights(geom, soil)
        kv_fac = max(0.1, 1.0 - seismic.vertical_pga)
        v_eff = w_dead * kv_fac
        wall_inertia = w_conc * seismic.horizontal_pga
        p_static, _, _, _ = compute_lateral_thrusts(
            wall_height=geom.total_height,
            gamma=soil.unit_weight,
            gamma_sat=soil.saturated_unit_weight,
            k_ae=results.k_a_static,
            k_a=results.k_a_static,
            water_table_depth=seismic.water_table_depth,
            kv=0.0,
        )
        p_dyn_inc = max(0.0, results.total_thrust - p_static)

        # DA1-C1: A1 (gamma_G=1.35, gamma_Q=1.50) + M1 (1.0) + R1 (1.0)
        h_d_c1 = 1.35 * p_static + 1.50 * (p_dyn_inc + wall_inertia)
        r_slide_c1 = _compute_sliding_resistance_unfactored(
            geom, soil, v_eff, soil.foundation_friction_angle, soil.foundation_cohesion
        )
        ur_slide_c1 = h_d_c1 / max(1e-3, r_slide_c1)

        q_ult_c1, _ = compute_ultimate_bearing_capacity(
            base_width=geom.base_width,
            vertical_load=v_eff,
            horizontal_load=max(1e-3, results.total_thrust + wall_inertia),
            eccentricity=results.eccentricity,
            embedment_depth=geom.footing_thickness,
            foundation_phi=soil.foundation_friction_angle,
            foundation_cohesion=soil.foundation_cohesion,
            foundation_unit_weight=soil.foundation_unit_weight,
        )
        b_eff = max(0.15, geom.base_width - 2.0 * abs(results.eccentricity))
        r_bear_c1 = q_ult_c1 * b_eff
        v_d_c1 = 1.35 * v_eff
        ur_bear_c1 = v_d_c1 / max(1e-3, r_bear_c1)

        # DA1-C2: A2 (gamma_G=1.0, gamma_Q=1.30) + M2 (gamma_phi=1.25, gamma_c=1.25)
        phi_d = math.degrees(math.atan(math.tan(math.radians(soil.friction_angle)) / 1.25))
        phi_fd = math.degrees(math.atan(math.tan(math.radians(soil.foundation_friction_angle)) / 1.25))
        c_fd = soil.foundation_cohesion / 1.25
        delta_d = min(soil.wall_friction_angle, max(0.0, phi_d - 0.1))
        beta_d = min(seismic.backfill_slope, max(0.0, phi_d - 0.5))
        kae_d, ka_d, _ = compute_mononobe_okabe(
            phi_d, delta_d, seismic.horizontal_pga, seismic.vertical_pga, beta_deg=beta_d
        )
        p_tot_m2, _, _, _ = compute_lateral_thrusts(
            geom.total_height, soil.unit_weight, soil.saturated_unit_weight,
            kae_d, ka_d, seismic.water_table_depth, kv=seismic.vertical_pga,
        )
        h_d_c2 = 1.0 * p_tot_m2 + 1.30 * wall_inertia
        r_slide_c2 = _compute_sliding_resistance_unfactored(geom, soil, v_eff, phi_fd, c_fd)
        ur_slide_c2 = h_d_c2 / max(1e-3, r_slide_c2)

        q_ult_c2, _ = compute_ultimate_bearing_capacity(
            base_width=geom.base_width,
            vertical_load=v_eff,
            horizontal_load=max(1e-3, p_tot_m2 + wall_inertia),
            eccentricity=results.eccentricity,
            embedment_depth=geom.footing_thickness,
            foundation_phi=phi_fd,
            foundation_cohesion=c_fd,
            foundation_unit_weight=soil.foundation_unit_weight,
        )
        r_bear_c2 = q_ult_c2 * b_eff
        ur_bear_c2 = v_eff / max(1e-3, r_bear_c2)

        # EC8 Pseudo-static check EN 1998-5 Cl. 7.3.2
        alpha_ag = max(0.01, seismic.horizontal_pga)
        kh_ec8 = alpha_ag * soil_factor_S * topography_factor_ST / max(1.0, ec8_r_factor)
        kae_ec8, ka_ec8, _ = compute_mononobe_okabe(
            phi_d, delta_d, kh_ec8, 0.5 * kh_ec8, beta_deg=beta_d
        )
        p_ec8, _, _, _ = compute_lateral_thrusts(
            geom.total_height, soil.unit_weight, soil.saturated_unit_weight,
            kae_ec8, ka_ec8, seismic.water_table_depth, kv=0.5 * kh_ec8,
        )
        ur_ec8_slide = (p_ec8 + w_conc * kh_ec8) / max(1e-3, r_slide_c2)

        # EN 1992-1-1 RC Stem Flexure & Shear
        d_eff_m = max(0.15, geom.stem_thickness_base - 0.06)
        b_m = 1.0
        f_cd_kpa = (0.85 * f_ck_mpa / 1.50) * 1000.0
        f_yd_kpa = (f_yk_mpa / 1.15) * 1000.0
        as_prov = 0.008 * b_m * d_eff_m  # 0.8% characteristic flexural ratio
        z_arm = 0.90 * d_eff_m
        m_rd = min(as_prov * f_yd_kpa * z_arm, 0.25 * f_cd_kpa * b_m * (d_eff_m ** 2))
        m_ed = 1.35 * results.max_bending_moment
        ur_ec2_flex = m_ed / max(1e-3, m_rd)

        k_sz = min(2.0, 1.0 + math.sqrt(200.0 / (d_eff_m * 1000.0)))
        rho_l = min(0.02, as_prov / (b_m * d_eff_m))
        v_rdc_mpa = max(0.035 * (k_sz ** 1.5) * math.sqrt(f_ck_mpa), 0.12 * k_sz * ((100.0 * rho_l * f_ck_mpa) ** (1.0 / 3.0)))
        v_rdc = v_rdc_mpa * 1000.0 * b_m * d_eff_m
        v_ed = 1.35 * results.max_shear_force
        ur_ec2_shear = v_ed / max(1e-3, v_rdc)

        f_ctm = 0.30 * (f_ck_mpa ** (2.0 / 3.0))
        ur_ec2_crack = results.concrete_tensile_stress / max(0.5, f_ctm)

        items = [
            AuditCheckItem(
                component="Geo ULS (DA1-C1)",
                check_title="Sliding Resistance (A1+M1+R1)",
                code_clause="EN 1997-1 Cl. 6.5.3 (DA1-C1)",
                demand=h_d_c1,
                capacity=r_slide_c1,
                unit="kN/m",
                unity_ratio=ur_slide_c1,
                status=_status_from_ur(ur_slide_c1),
                detailing_note="gamma_G=1.35, gamma_Q=1.50, gamma_R=1.00",
            ),
            AuditCheckItem(
                component="Geo ULS (DA1-C2)",
                check_title="Sliding Resistance (A2+M2+R1)",
                code_clause="EN 1997-1 Cl. 6.5.3 (DA1-C2)",
                demand=h_d_c2,
                capacity=r_slide_c2,
                unit="kN/m",
                unity_ratio=ur_slide_c2,
                status=_status_from_ur(ur_slide_c2),
                detailing_note=f"Factored phi'_d={phi_d:.1f} deg, phi'_fd={phi_fd:.1f} deg (gamma_phi=1.25)",
            ),
            AuditCheckItem(
                component="Geo ULS (DA1-C1/C2)",
                check_title="Governing Bearing Resistance",
                code_clause="EN 1997-1 Cl. 6.5.2 & Annex D",
                demand=max(v_d_c1, v_eff),
                capacity=min(r_bear_c1, r_bear_c2),
                unit="kN/m",
                unity_ratio=max(ur_bear_c1, ur_bear_c2),
                status=_status_from_ur(max(ur_bear_c1, ur_bear_c2)),
                detailing_note=f"Effective width B'={b_eff:.2f} m; q_ult,d={min(q_ult_c1, q_ult_c2):.1f} kPa",
            ),
            AuditCheckItem(
                component="Seismic (EC8)",
                check_title="Pseudo-Static Wall Sliding",
                code_clause="EN 1998-5 Cl. 7.3.2 & Annex E.4",
                demand=p_ec8 + w_conc * kh_ec8,
                capacity=r_slide_c2,
                unit="kN/m",
                unity_ratio=ur_ec8_slide,
                status=_status_from_ur(ur_ec8_slide),
                detailing_note=f"k_h = alpha*S*ST/r = {kh_ec8:.3f}g (S={soil_factor_S:.2f}, ST={topography_factor_ST:.2f}, r={ec8_r_factor:.1f})",
            ),
            AuditCheckItem(
                component="RC Stem (EC2)",
                check_title="ULS Flexural Resistance M_Rd",
                code_clause="EN 1992-1-1 Cl. 6.1",
                demand=m_ed,
                capacity=m_rd,
                unit="kNm/m",
                unity_ratio=ur_ec2_flex,
                status=_status_from_ur(ur_ec2_flex),
                detailing_note="gamma_c=1.50, gamma_s=1.15; rho=0.80%",
            ),
            AuditCheckItem(
                component="RC Stem (EC2)",
                check_title="ULS One-Way Shear Resistance V_Rd,c",
                code_clause="EN 1992-1-1 Cl. 6.2.2",
                demand=v_ed,
                capacity=v_rdc,
                unit="kN/m",
                unity_ratio=ur_ec2_shear,
                status=_status_from_ur(ur_ec2_shear),
                detailing_note=f"Unreinforced concrete shear capacity d={d_eff_m*1000:.0f} mm",
            ),
            AuditCheckItem(
                component="RC Stem (EC2)",
                check_title="SLS Flexural Cracking Check",
                code_clause="EN 1992-1-1 Cl. 7.3.4",
                demand=results.concrete_tensile_stress,
                capacity=f_ctm,
                unit="MPa",
                unity_ratio=ur_ec2_crack,
                status=_status_from_ur(ur_ec2_crack),
                detailing_note=f"f_ctm = {f_ctm:.2f} MPa",
            ),
        ]
        return cls._finalize(RegionalStandard.EUROCODE_7, project_title, "Eurocode 7/8 Wall Check", items)

    @classmethod
    def _audit_aashto(
        cls,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        results: AnalysisResults,
        f_c_mpa: float,
        f_y_mpa: float,
        project_title: str,
    ) -> MultiCodeAuditReport:
        w_conc, _, w_dead = _compute_wall_vertical_dead_weights(geom, soil)
        kv_fac = max(0.1, 1.0 - seismic.vertical_pga)
        v_eff = w_dead * kv_fac
        wall_inertia = w_conc * seismic.horizontal_pga

        r_slide_n = _compute_sliding_resistance_unfactored(
            geom, soil, v_eff, soil.foundation_friction_angle, soil.foundation_cohesion
        )
        p_static, _, _, _ = compute_lateral_thrusts(
            geom.total_height, soil.unit_weight, soil.saturated_unit_weight,
            results.k_a_static, results.k_a_static, seismic.water_table_depth, kv=0.0,
        )

        # Strength I Sliding: gamma_EH=1.50, phi_tau=0.80
        v_u_slide_str = 1.50 * p_static
        r_r_slide_str = 0.80 * r_slide_n
        ur_slide_str = v_u_slide_str / max(1e-3, r_r_slide_str)

        # Extreme Event I Sliding: gamma_EH=1.00, gamma_EQ=1.00, phi_tau=1.00
        v_u_slide_ext = results.total_thrust + wall_inertia
        r_r_slide_ext = 1.00 * r_slide_n
        ur_slide_ext = v_u_slide_ext / max(1e-3, r_r_slide_ext)

        # Eccentricity Limit: e <= B/3 (soil) or 0.45B (rock)
        is_rock = soil.foundation_cohesion >= 50.0 and soil.foundation_friction_angle >= 38.0
        e_lim = (0.45 if is_rock else (1.0 / 3.0)) * geom.base_width
        ur_ecc = abs(results.eccentricity) / max(1e-3, e_lim)

        # Bearing Resistance: Extreme Event I (phi_b=0.90) & Strength I (phi_b=0.45)
        q_ult, _ = compute_ultimate_bearing_capacity(
            base_width=geom.base_width,
            vertical_load=v_eff,
            horizontal_load=max(1e-3, v_u_slide_ext),
            eccentricity=results.eccentricity,
            embedment_depth=geom.footing_thickness,
            foundation_phi=soil.foundation_friction_angle,
            foundation_cohesion=soil.foundation_cohesion,
            foundation_unit_weight=soil.foundation_unit_weight,
        )
        b_eff = max(0.15, geom.base_width - 2.0 * abs(results.eccentricity))
        q_factored_ext = v_eff / b_eff
        q_res_ext = 0.90 * q_ult
        ur_bear_ext = q_factored_ext / max(1e-3, q_res_ext)

        # Stem Flexure Strength I (phi_f = 0.90)
        d_eff_m = max(0.15, geom.stem_thickness_base - 0.065)
        as_prov = 0.009 * 1.0 * d_eff_m
        m_n = as_prov * (f_y_mpa * 1000.0) * (0.90 * d_eff_m)
        phi_mn = 0.90 * m_n
        m_u = 1.50 * results.max_bending_moment
        ur_flex = m_u / max(1e-3, phi_mn)

        items = [
            AuditCheckItem(
                component="AASHTO Strength I",
                check_title="Static Sliding Resistance",
                code_clause="AASHTO LRFD Table 3.4.1-1 & Cl. 10.6.3.4",
                demand=v_u_slide_str,
                capacity=r_r_slide_str,
                unit="kN/m",
                unity_ratio=ur_slide_str,
                status=_status_from_ur(ur_slide_str),
                detailing_note="gamma_EH=1.50, phi_tau=0.80",
            ),
            AuditCheckItem(
                component="AASHTO Extreme Event I",
                check_title="Seismic Sliding Limit State",
                code_clause="AASHTO LRFD Table 3.4.1-1 & Cl. 11.6.5",
                demand=v_u_slide_ext,
                capacity=r_r_slide_ext,
                unit="kN/m",
                unity_ratio=ur_slide_ext,
                status=_status_from_ur(ur_slide_ext),
                detailing_note="gamma_EQ=1.00, phi_tau=1.00",
            ),
            AuditCheckItem(
                component="AASHTO Eccentricity",
                check_title="Base Resultant Eccentricity",
                code_clause="AASHTO LRFD Cl. 11.6.3.3",
                demand=abs(results.eccentricity),
                capacity=e_lim,
                unit="m",
                unity_ratio=ur_ecc,
                status=_status_from_ur(ur_ecc),
                detailing_note=f"e <= {'0.45B (rock)' if is_rock else 'B/3 (soil)'} = {e_lim:.3f} m",
            ),
            AuditCheckItem(
                component="AASHTO Bearing",
                check_title="Extreme Event I Bearing Pressure",
                code_clause="AASHTO LRFD Cl. 10.6.3.1 & 11.6.3.2",
                demand=q_factored_ext,
                capacity=q_res_ext,
                unit="kPa",
                unity_ratio=ur_bear_ext,
                status=_status_from_ur(ur_bear_ext),
                detailing_note="phi_b=0.90 over Meyerhof effective width B'",
            ),
            AuditCheckItem(
                component="AASHTO Concrete",
                check_title="Stem Flexural Resistance phi_f*M_n",
                code_clause="AASHTO LRFD Cl. 5.6.3",
                demand=m_u,
                capacity=phi_mn,
                unit="kNm/m",
                unity_ratio=ur_flex,
                status=_status_from_ur(ur_flex),
                detailing_note=f"phi_f=0.90, gamma_EH=1.50, fc'={f_c_mpa:.0f} MPa",
            ),
        ]
        return cls._finalize(RegionalStandard.AASHTO_LRFD, project_title, "AASHTO LRFD Wall Audit", items)

    @classmethod
    def _audit_aci318(
        cls,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        results: AnalysisResults,
        f_c_mpa: float,
        f_y_mpa: float,
        project_title: str,
    ) -> MultiCodeAuditReport:
        b_m = 1.0
        h_stem_t = geom.stem_thickness_base
        cover = 0.05  # 50 mm earth-face cover
        d_eff_m = max(0.15, h_stem_t - cover - 0.01)

        # 1. Factored Flexural Strength phi_f * M_n >= M_u (U = 1.6 H)
        m_u = 1.60 * results.max_bending_moment
        rho_steel = 0.0085
        as_prov = rho_steel * b_m * d_eff_m  # m^2/m
        a_block = (as_prov * f_y_mpa) / (0.85 * f_c_mpa * b_m)
        m_n = as_prov * (f_y_mpa * 1000.0) * (d_eff_m - 0.5 * a_block)
        phi_mn = 0.90 * m_n
        ur_flex = m_u / max(1e-3, phi_mn)

        # 2. One-way Shear Strength phi_v * V_c >= V_u (Sec. 22.5.5.1)
        v_u = 1.60 * results.max_shear_force
        v_c_kn = 0.17 * math.sqrt(f_c_mpa) * (b_m * 1000.0) * (d_eff_m * 1000.0) / 1000.0
        phi_vc = 0.75 * v_c_kn
        ur_shear = v_u / max(1e-3, phi_vc)

        # 3. Minimum Shrinkage & Temperature Steel (Sec. 11.6 & 24.4.3.2)
        rho_min = 0.0018 if f_y_mpa >= 420.0 else 0.0020
        as_min_mm2 = rho_min * 1000.0 * (h_stem_t * 1000.0)
        as_prov_mm2 = as_prov * 1e6
        ur_min_steel = as_min_mm2 / max(1.0, as_prov_mm2)

        # 4. Tension Development Length at Stem-Footing Cold Joint (Sec. 25.4.2.3)
        bar_dia_mm = 16.0  # #5 / 16 mm dowel bars
        l_d_mm = (f_y_mpa / (1.1 * 1.0 * math.sqrt(f_c_mpa))) * bar_dia_mm
        l_avail_mm = max(50.0, (geom.footing_thickness - 0.075) * 1000.0)
        ur_dev = l_d_mm / max(1.0, l_avail_mm)

        items = [
            AuditCheckItem(
                component="ACI 318 Stem",
                check_title="One-Way Flexural Capacity (phi*Mn)",
                code_clause="ACI 318-19 Sec. 22.2 & 9.5",
                demand=m_u,
                capacity=phi_mn,
                unit="kNm/m",
                unity_ratio=ur_flex,
                status=_status_from_ur(ur_flex),
                detailing_note=f"U=1.6H, phi_f=0.90, As={as_prov_mm2:.0f} mm^2/m",
            ),
            AuditCheckItem(
                component="ACI 318 Stem",
                check_title="One-Way Concrete Shear (phi*Vc)",
                code_clause="ACI 318-19 Sec. 22.5.5.1",
                demand=v_u,
                capacity=phi_vc,
                unit="kN/m",
                unity_ratio=ur_shear,
                status=_status_from_ur(ur_shear),
                detailing_note=f"phi_v=0.75, 0.17*sqrt(fc')*b*d (fc'={f_c_mpa:.0f} MPa)",
            ),
            AuditCheckItem(
                component="ACI 318 Detailing",
                check_title="Min Shrinkage & Temperature Steel",
                code_clause="ACI 318-19 Sec. 11.6 & 24.4.3.2",
                demand=as_min_mm2,
                capacity=as_prov_mm2,
                unit="mm^2/m",
                unity_ratio=ur_min_steel,
                status=_status_from_ur(ur_min_steel),
                detailing_note=f"rho_min={rho_min:.4f}; As,min={as_min_mm2:.0f} mm^2/m",
            ),
            AuditCheckItem(
                component="ACI 318 Joint",
                check_title="Stem-Footing Dowel Development l_d",
                code_clause="ACI 318-19 Sec. 25.4.2.3",
                demand=l_d_mm,
                capacity=l_avail_mm,
                unit="mm",
                unity_ratio=ur_dev,
                status=_status_from_ur(ur_dev),
                detailing_note=f"Straight #5 (16mm) dowel l_d={l_d_mm:.0f} mm vs D_f-cover={l_avail_mm:.0f} mm",
            ),
        ]
        return cls._finalize(RegionalStandard.ACI_318, project_title, "ACI 318-19 Concrete Wall Audit", items)

