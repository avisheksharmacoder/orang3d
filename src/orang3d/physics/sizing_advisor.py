"""
Interactive Geotechnical & Structural Sizing Advisor (Phase 8).

Evaluates limit-state deficiencies (sliding, overturning, bearing capacity,
stem flexural cracking) against the active design standard and computes minimal,
constructible geometric upgrades that bring all checks into compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, List, Optional
import numpy as np

from ..config import RegionalStandard, get_safety_thresholds
from ..models.wall_params import (
    AnalysisResults,
    RetainingWallGeometry,
    SeismicParams,
    SoilProperties,
)
from ..units import UnitSystem, from_si_value, unit_label
from .stability import evaluate_wall_stability
from .surcharge import AdjacentSurchargeParams, evaluate_wall_stability_with_surcharge


@dataclass
class SizingRecommendation:
    """Single actionable geometric modification returned by the Sizing Advisor."""

    limit_state: str
    parameter_name: str
    current_value_si: float
    recommended_value_si: float
    current_metric: float
    projected_metric: float
    target_metric: float
    message: str


@dataclass
class SizingAdviceReport:
    """Full Sizing Advisor diagnostic with per-check recommendations and passing geometry."""

    all_checks_passing: bool
    initial_results: AnalysisResults
    projected_results: AnalysisResults
    recommended_geom: RetainingWallGeometry
    recommendations: List[SizingRecommendation]
    summary_lines: List[str]


def _eval_stability(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    surcharge: Optional[AdjacentSurchargeParams] = None,
) -> AnalysisResults:
    if surcharge is None:
        return evaluate_wall_stability(geom, soil, seismic)
    res, _ = evaluate_wall_stability_with_surcharge(geom, soil, seismic, surcharge)
    return res


def _search_min_increment(
    geom: RetainingWallGeometry,
    attr: str,
    step: float,
    max_val: float,
    evaluator: Callable[[RetainingWallGeometry], AnalysisResults],
    predicate: Callable[[AnalysisResults], bool],
) -> tuple[RetainingWallGeometry, AnalysisResults]:
    """Steps a single geometric parameter upward until `predicate` is satisfied."""
    cand = geom
    res = evaluator(cand)
    val = float(getattr(cand, attr))
    while not predicate(res) and val + step <= max_val + 1e-9:
        val = round(val + step, 3)
        updates = {attr: val}
        if attr == "stem_thickness_base" and val < cand.stem_thickness_top:
            updates["stem_thickness_top"] = val
        if attr == "shear_key_depth" and cand.shear_key_width <= 0.0:
            updates["shear_key_width"] = max(0.35, round(0.75 * cand.stem_thickness_base, 2))
        cand = replace(cand, **updates)
        res = evaluator(cand)
    return cand, res


def evaluate_sizing_advisor(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    standard: RegionalStandard = RegionalStandard.STANDARD,
    surcharge: Optional[AdjacentSurchargeParams] = None,
    unit_system: UnitSystem | str = UnitSystem.SI,
) -> SizingAdviceReport:
    """
    Checks sliding, overturning, bearing, and stem cracking limit states and generates
    concrete geometric sizing recommendations guaranteed (within constructible bounds)
    to satisfy stability when applied.
    """
    u_sys = UnitSystem(unit_system)
    u_len = unit_label("length", u_sys)
    mode_key = "seismic" if seismic.horizontal_pga > 0.01 else "static"
    thresh = get_safety_thresholds(standard)

    t_slide = float(thresh[f"sliding_{mode_key}"])
    t_over = float(thresh[f"overturning_{mode_key}"])
    t_bear = float(thresh[f"bearing_{mode_key}"])

    def _ev(g: RetainingWallGeometry) -> AnalysisResults:
        return _eval_stability(g, soil, seismic, surcharge)

    init_res = _ev(geom)
    recs: List[SizingRecommendation] = []
    cand = replace(geom)
    cur_res = init_res

    def _fmt(v_si: float) -> str:
        return f"{from_si_value(v_si, 'length', u_sys):.2f} {u_len}"

    # Iterative polish loop ensures later thickening/key edits don't violate earlier checks
    for _ in range(3):
        # 1. Sliding deficiency -> extend heel length first, then add/deepen shear key if needed
        if cur_res.fs_sliding < t_slide:
            orig_fs = cur_res.fs_sliding
            orig_heel = cand.heel_length
            cand_heel, res_heel = _search_min_increment(
                cand, "heel_length", 0.20, max(12.0, 2.5 * cand.stem_height),
                _ev, lambda r: r.fs_sliding >= t_slide,
            )
            if res_heel.fs_sliding >= t_slide:
                cand, cur_res = cand_heel, res_heel
                recs.append(
                    SizingRecommendation(
                        limit_state="Sliding",
                        parameter_name="heel_length",
                        current_value_si=orig_heel,
                        recommended_value_si=cand.heel_length,
                        current_metric=orig_fs,
                        projected_metric=cur_res.fs_sliding,
                        target_metric=t_slide,
                        message=(
                            f"Increase heel length from {_fmt(orig_heel)} -> {_fmt(cand.heel_length)} "
                            f"to raise FS_sliding from {orig_fs:.2f} to {cur_res.fs_sliding:.2f} "
                            f"(target >= {t_slide:.2f})."
                        ),
                    )
                )
            else:
                # Extend heel partway & mobilize passive resistance via shear key
                cand = replace(cand, heel_length=round(min(cand.heel_length + 0.8, 1.5 * cand.stem_height), 2))
                orig_key = cand.shear_key_depth
                cand, cur_res = _search_min_increment(
                    cand, "shear_key_depth", 0.15, 2.0,
                    _ev, lambda r: r.fs_sliding >= t_slide,
                )
                recs.append(
                    SizingRecommendation(
                        limit_state="Sliding",
                        parameter_name="shear_key_depth",
                        current_value_si=orig_key,
                        recommended_value_si=cand.shear_key_depth,
                        current_metric=orig_fs,
                        projected_metric=cur_res.fs_sliding,
                        target_metric=t_slide,
                        message=(
                            f"Extend heel to {_fmt(cand.heel_length)} and set shear key depth to "
                            f"{_fmt(cand.shear_key_depth)} to raise FS_sliding from {orig_fs:.2f} "
                            f"to {cur_res.fs_sliding:.2f} (target >= {t_slide:.2f})."
                        ),
                    )
                )

        # 2. Overturning deficiency -> widen heel & toe
        if cur_res.fs_overturning < t_over:
            orig_fs = cur_res.fs_overturning
            orig_heel_ot = cand.heel_length
            cand, cur_res = _search_min_increment(
                cand, "heel_length", 0.20, max(12.0, 2.5 * cand.stem_height),
                _ev, lambda r: r.fs_overturning >= t_over,
            )
            if cur_res.fs_overturning < t_over:
                cand, cur_res = _search_min_increment(
                    cand, "toe_length", 0.20, max(6.0, 1.2 * cand.stem_height),
                    _ev, lambda r: r.fs_overturning >= t_over,
                )
            recs.append(
                SizingRecommendation(
                    limit_state="Overturning",
                    parameter_name="heel_length",
                    current_value_si=orig_heel_ot,
                    recommended_value_si=cand.heel_length,
                    current_metric=orig_fs,
                    projected_metric=cur_res.fs_overturning,
                    target_metric=t_over,
                    message=(
                        f"Widen base (heel {_fmt(cand.heel_length)}, toe {_fmt(cand.toe_length)}) "
                        f"to raise FS_overturning from {orig_fs:.2f} to {cur_res.fs_overturning:.2f} "
                        f"(target >= {t_over:.2f})."
                    ),
                )
            )

        # 3. Bearing capacity deficiency -> widen toe + thicken footing
        if cur_res.fs_bearing < t_bear:
            orig_fs = cur_res.fs_bearing
            orig_toe = cand.toe_length
            cand, cur_res = _search_min_increment(
                cand, "toe_length", 0.20, max(8.0, 1.5 * cand.stem_height),
                _ev, lambda r: r.fs_bearing >= t_bear,
            )
            if cur_res.fs_bearing < t_bear:
                cand, cur_res = _search_min_increment(
                    cand, "footing_thickness", 0.15, 2.0,
                    _ev, lambda r: r.fs_bearing >= t_bear,
                )
            recs.append(
                SizingRecommendation(
                    limit_state="Bearing",
                    parameter_name="toe_length",
                    current_value_si=orig_toe,
                    recommended_value_si=cand.toe_length,
                    current_metric=orig_fs,
                    projected_metric=cur_res.fs_bearing,
                    target_metric=t_bear,
                    message=(
                        f"Increase toe length from {_fmt(orig_toe)} -> {_fmt(cand.toe_length)} "
                        f"(footing thickness {_fmt(cand.footing_thickness)}) to raise FS_bearing "
                        f"from {orig_fs:.2f} to {cur_res.fs_bearing:.2f} (target >= {t_bear:.2f})."
                    ),
                )
            )

        # 4. Stem flexural cracking deficiency -> thicken stem base
        if cur_res.cracking_predicted:
            orig_sig = cur_res.concrete_tensile_stress
            orig_tb = cand.stem_thickness_base
            cand, cur_res = _search_min_increment(
                cand, "stem_thickness_base", 0.05, max(2.5, 0.35 * cand.stem_height),
                _ev, lambda r: not r.cracking_predicted,
            )
            recs.append(
                SizingRecommendation(
                    limit_state="Stem Flexure",
                    parameter_name="stem_thickness_base",
                    current_value_si=orig_tb,
                    recommended_value_si=cand.stem_thickness_base,
                    current_metric=orig_sig,
                    projected_metric=cur_res.concrete_tensile_stress,
                    target_metric=2.8,
                    message=(
                        f"Increase stem base thickness from {_fmt(orig_tb)} -> {_fmt(cand.stem_thickness_base)} "
                        f"to reduce tensile stress from {orig_sig:.2f} to {cur_res.concrete_tensile_stress:.2f} MPa "
                        f"(limit <= 2.80 MPa)."
                    ),
                )
            )

        if (
            cur_res.fs_sliding >= t_slide
            and cur_res.fs_overturning >= t_over
            and cur_res.fs_bearing >= t_bear
            and not cur_res.cracking_predicted
        ):
            break

    all_initial_ok = (
        init_res.fs_sliding >= t_slide
        and init_res.fs_overturning >= t_over
        and init_res.fs_bearing >= t_bear
        and not init_res.cracking_predicted
    )
    if all_initial_ok:
        lines = [
            f"All limit states PASS ({mode_key} thresholds: slide>={t_slide:.2f}, "
            f"overturn>={t_over:.2f}, bearing>={t_bear:.2f}, stem<=2.80 MPa)."
        ]
    else:
        lines = [rec.message for rec in recs] or ["No geometric adjustment identified within bounds."]

    return SizingAdviceReport(
        all_checks_passing=all_initial_ok,
        initial_results=init_res,
        projected_results=cur_res,
        recommended_geom=cand,
        recommendations=recs,
        summary_lines=lines,
    )
