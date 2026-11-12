"""
Theory vs. BNWF vs. 3D FEA Comparison Dashboard Tab (v3 Phase 5).

Overlays depth profiles (z = 0 -> H) from multiple analytical and numerical tiers:
  1. Classical Rankine Static Active Pressure sigma_a(z)
  2. Mononobe-Okabe / Seed-Whitman Dynamic Pressure sigma_ae(z)
  3. Curved Shell Horizontal Arching Pressure sigma_h(z)
  4. OpenSees 2D BNWF Bending Moment M(y) / Deflection Envelope vs. Classical Stem M(y)
  5. OpenSees 3D / Kratos Continuum FEA Backface Pressure sigma_xx(z) (Mid-Bay vs. Corner)

Reports quantitative discrepancy metrics (% peak thrust difference, % max moment
difference, normalized resultant height h_res / H, and 3D corner concentration ratio).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...config import THEME
from ...models.advanced_wall_params import CurvedShellGeometry
from ...models.wall_params import (
    AnalysisResults,
    RetainingWallGeometry,
    SeismicParams,
    SoilProperties,
)
from ...physics.bnwf_solver import BNWFSimulationResult
from ...physics.mononobe_okabe import (
    compute_lateral_thrusts,
    compute_liquefaction_degradation,
    compute_mononobe_okabe,
    compute_rankine_earth_pressures,
)
from ...physics.opensees_3d_solver import ContinuumFEAResult
from ...physics.shell_arching import ShellArchingResult, compute_shell_arching_partition
from ...physics.structural import StemStructuralProfile, compute_stem_internal_profiles
from ...units import UnitSystem, from_si_value, unit_label


@dataclass
class SolverComparisonMetrics:
    """Structured depth profiles and quantitative discrepancy metrics across solver tiers."""

    depths_m: np.ndarray
    rankine_pressure_kpa: np.ndarray
    mo_dynamic_pressure_kpa: np.ndarray
    arching_pressure_kpa: np.ndarray
    stem_elevations_m: np.ndarray
    stem_moment_knm_m: np.ndarray
    stem_deflection_mm: np.ndarray = field(default_factory=lambda: np.array([]))
    bnwf_elevations_m: np.ndarray = field(default_factory=lambda: np.array([]))
    bnwf_moment_knm_m: np.ndarray = field(default_factory=lambda: np.array([]))
    fea_mid_depths_m: np.ndarray = field(default_factory=lambda: np.array([]))
    fea_mid_pressure_kpa: np.ndarray = field(default_factory=lambda: np.array([]))
    fea_corner_depths_m: np.ndarray = field(default_factory=lambda: np.array([]))
    fea_corner_pressure_kpa: np.ndarray = field(default_factory=lambda: np.array([]))

    mo_total_thrust_kn_m: float = 0.0
    mo_h_res_over_H: float = 0.333
    arching_reduction_pct: float = 0.0
    fea_peak_thrust_kn_m: Optional[float] = None
    fea_thrust_diff_pct: Optional[float] = None
    fea_h_res_over_H: Optional[float] = None
    fea_corner_ratio: Optional[float] = None
    bnwf_max_moment_knm: Optional[float] = None
    bnwf_moment_diff_pct: Optional[float] = None


def _bin_backface_stress_by_depth(
    coords: np.ndarray,
    stresses: np.ndarray,
    wall_height: float,
    wall_length: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Splits 3D backface normal stresses into mid-bay vs. corner depth profiles."""
    if len(coords) == 0 or len(stresses) == 0:
        empty = np.array([], dtype=np.float64)
        return empty, empty, empty, empty

    z_long = coords[:, 2]
    l_eff = max(float(np.max(z_long) - np.min(z_long)), wall_length, 1e-3)
    z_min = float(np.min(z_long))
    z_mid = z_min + 0.5 * l_eff

    mid_mask = np.abs(z_long - z_mid) <= (0.25 * l_eff + 1e-4)
    corner_mask = (z_long <= z_min + 0.25 * l_eff + 1e-4) | (
        z_long >= z_min + 0.75 * l_eff - 1e-4
    )
    if not np.any(mid_mask):
        mid_mask = np.ones(len(coords), dtype=bool)
    if not np.any(corner_mask):
        corner_mask = mid_mask

    def _aggregate(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        sub_y = np.round(coords[mask, 1], 3)
        sub_p = stresses[mask]
        unique_y = np.sort(np.unique(sub_y))[::-1]  # Top to base
        depths = np.clip(wall_height - unique_y, 0.0, wall_height)
        vals = np.array([float(np.mean(sub_p[sub_y == y])) for y in unique_y], dtype=np.float64)
        order = np.argsort(depths)
        return depths[order], vals[order]

    d_mid, p_mid = _aggregate(mid_mask)
    d_cor, p_cor = _aggregate(corner_mask)
    return d_mid, p_mid, d_cor, p_cor


def compute_theory_vs_solver_comparison(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    results: Optional[AnalysisResults] = None,
    shell_geom: Optional[CurvedShellGeometry] = None,
    arching_result: Optional[ShellArchingResult] = None,
    stem_profile: Optional[StemStructuralProfile] = None,
    bnwf_result: Optional[BNWFSimulationResult] = None,
    fea_result: Optional[ContinuumFEAResult] = None,
    n_points: int = 50,
) -> SolverComparisonMetrics:
    """Computes overlaid depth profiles and % discrepancies between Theory, BNWF, and 3D FEA."""
    H = geom.total_height
    depths = np.linspace(0.0, H, n_points, dtype=np.float64)

    phi_eff, c_eff = compute_liquefaction_degradation(
        soil.friction_angle, soil.cohesion, seismic.liquefaction_factor
    )
    delta_eff = min(soil.wall_friction_angle, max(0.0, phi_eff - 0.1))
    beta_eff = min(seismic.backfill_slope, max(0.0, phi_eff - 0.5))

    ka_rank, _ = compute_rankine_earth_pressures(phi_eff, c=c_eff)
    k_ae, k_a_coul, _ = compute_mononobe_okabe(
        phi_deg=phi_eff,
        delta_deg=delta_eff,
        kh=seismic.horizontal_pga,
        kv=seismic.vertical_pga,
        beta_deg=beta_eff,
        liquefaction_factor=0.0,
    )

    h_w = max(0.0, min(seismic.water_table_depth, H))
    h_sub = H - h_w
    gamma_w = 9.81
    gamma_eff = (
        soil.unit_weight
        if h_sub <= 0.0
        else (
            soil.unit_weight * (h_w / H)
            + (soil.saturated_unit_weight - gamma_w) * (h_sub / H)
        )
    )

    # 1. Rankine static earth pressure
    sigma_rankine = np.maximum(
        0.0, gamma_eff * depths * ka_rank - 2.0 * c_eff * np.sqrt(ka_rank)
    )

    # 2. Mononobe-Okabe + Seed-Whitman (1970) equivalent linear dynamic profile
    # Static triangle acting at H/3 + Seed-Whitman trapezoid acting at 0.6H (z_cent = 0.4H)
    kv_factor = max(0.01, 1.0 - seismic.vertical_pga)
    delta_p_ae = 0.5 * gamma_eff * (H ** 2) * max(0.0, k_ae - k_a_coul) * kv_factor
    sigma_static = np.maximum(0.0, gamma_eff * depths * k_a_coul)
    sigma_dyn_inc = (delta_p_ae / max(1e-3, H)) * (1.6 - 1.2 * (depths / max(1e-3, H)))
    u_water = gamma_w * np.maximum(0.0, depths - h_w)
    sigma_mo = np.maximum(0.0, sigma_static + sigma_dyn_inc + u_water)

    total_thrust, h_res, _, _ = compute_lateral_thrusts(
        wall_height=H,
        gamma=soil.unit_weight,
        gamma_sat=soil.saturated_unit_weight,
        k_ae=k_ae,
        k_a=k_a_coul,
        water_table_depth=seismic.water_table_depth,
        kv=seismic.vertical_pga,
    )

    # 3. Curved shell horizontal arching pressure profile
    if arching_result is None:
        sg = shell_geom if shell_geom is not None else CurvedShellGeometry(panel_height=H)
        arching_result = compute_shell_arching_partition(sg, soil, num_depth_points=n_points)

    z_arch = arching_result.depths
    if len(z_arch) > 1 and abs(float(z_arch[-1]) - H) > 1e-3:
        z_scaled = z_arch * (H / max(1e-3, float(z_arch[-1])))
        sigma_arch = np.interp(depths, z_scaled, arching_result.sigma_h_profile)
    else:
        sigma_arch = np.interp(depths, z_arch, arching_result.sigma_h_profile)

    # 4. Classical stem bending moment profile M(y)
    if stem_profile is None:
        stem_profile = compute_stem_internal_profiles(geom, soil, seismic, n_points=n_points)

    metrics = SolverComparisonMetrics(
        depths_m=depths,
        rankine_pressure_kpa=sigma_rankine,
        mo_dynamic_pressure_kpa=sigma_mo,
        arching_pressure_kpa=sigma_arch,
        stem_elevations_m=stem_profile.heights,
        stem_moment_knm_m=stem_profile.bending_moments,
        mo_total_thrust_kn_m=float(results.total_thrust if results is not None else total_thrust),
        mo_h_res_over_H=float((results.thrust_height if results is not None else h_res) / max(1e-3, H)),
        arching_reduction_pct=float(arching_result.arching_ratio * 100.0),
    )

    # 5. OpenSees 2D BNWF comparison
    if bnwf_result is not None:
        max_m_theory = max(1e-3, float(stem_profile.max_bending_moment))
        bnwf_max_m = float(bnwf_result.max_moment_knm)
        metrics.bnwf_max_moment_knm = bnwf_max_m
        metrics.bnwf_moment_diff_pct = ((bnwf_max_m - max_m_theory) / max_m_theory) * 100.0

        if bnwf_result.bending_moment_profile:
            elevs = sorted(bnwf_result.bending_moment_profile.keys())
            m_env = [
                float(np.max(np.abs(bnwf_result.bending_moment_profile[y])))
                if len(bnwf_result.bending_moment_profile[y]) > 0
                else 0.0
                for y in elevs
            ]
            metrics.bnwf_elevations_m = np.asarray(elevs, dtype=np.float64)
            metrics.bnwf_moment_knm_m = np.asarray(m_env, dtype=np.float64)

    # 6. OpenSees 3D / Kratos Continuum FEA comparison
    if fea_result is not None and len(fea_result.total_thrust_kn_m) > 0:
        idx_peak = int(np.argmax(np.abs(fea_result.total_thrust_kn_m)))
        p_fea_peak = float(fea_result.total_thrust_kn_m[idx_peak])
        p_mo = max(1e-3, metrics.mo_total_thrust_kn_m)
        metrics.fea_peak_thrust_kn_m = p_fea_peak
        metrics.fea_thrust_diff_pct = ((p_fea_peak - p_mo) / p_mo) * 100.0
        metrics.fea_corner_ratio = float(fea_result.corner_concentration_ratio)
        if len(fea_result.thrust_elevation_m) > idx_peak:
            metrics.fea_h_res_over_H = float(fea_result.thrust_elevation_m[idx_peak]) / max(1e-3, H)

        if (
            fea_result.backface_coords.shape[0] > 0
            and fea_result.backface_normal_stress_kpa.shape[0] > idx_peak
        ):
            d_mid, p_mid, d_cor, p_cor = _bin_backface_stress_by_depth(
                fea_result.backface_coords,
                fea_result.backface_normal_stress_kpa[idx_peak],
                wall_height=H,
                wall_length=geom.wall_length,
            )
            metrics.fea_mid_depths_m = d_mid
            metrics.fea_mid_pressure_kpa = p_mid
            metrics.fea_corner_depths_m = d_cor
            metrics.fea_corner_pressure_kpa = p_cor

    return metrics


class TheoryComparisonTab(QWidget):
    """Side-by-side multi-solver verification tab comparing Theory, BNWF, and 3D FEA."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._last_metrics: Optional[SolverComparisonMetrics] = None
        self._bnwf_result: Optional[BNWFSimulationResult] = None
        self._fea_result: Optional[ContinuumFEAResult] = None
        self.unit_system: UnitSystem = UnitSystem.SI

        master = QHBoxLayout(self)
        master.setContentsMargins(6, 6, 6, 6)
        master.setSpacing(10)

        pg.setConfigOption("background", THEME["surface_dark"])
        pg.setConfigOption("foreground", THEME["text_primary"])
        pg.setConfigOptions(antialias=True)

        # Plot 1: Lateral Pressure vs Depth (inverted Y: z = 0 crest at top -> H base)
        self.pressure_plot = pg.PlotWidget(title="Lateral Pressure sigma_h(z) vs Depth")
        self.pressure_plot.showGrid(x=True, y=True, alpha=0.25)
        self.pressure_plot.setLabel("bottom", "Lateral Pressure sigma_h", units="kPa")
        self.pressure_plot.setLabel("left", "Depth z below Crest", units="m")
        self.pressure_plot.invertY(True)
        self.pressure_legend = self.pressure_plot.addLegend(offset=(10, 10))

        self.curve_rankine = self.pressure_plot.plot(
            pen=pg.mkPen(THEME["text_secondary"], width=2, style=pg.QtCore.Qt.DashLine),
            name="Rankine Static",
        )
        self.curve_mo = self.pressure_plot.plot(
            pen=pg.mkPen(THEME["accent_orange"], width=2.5),
            name="M-O / Seed-Whitman",
        )
        self.curve_arching = self.pressure_plot.plot(
            pen=pg.mkPen(THEME["accent_green"], width=2),
            name="Shell Arching",
        )
        self.curve_fea_mid = self.pressure_plot.plot(
            pen=pg.mkPen(THEME["accent_blue"], width=2),
            symbol="o",
            symbolSize=5,
            name="3D FEA Mid-Bay",
        )
        self.curve_fea_corner = self.pressure_plot.plot(
            pen=pg.mkPen(THEME["accent_red"], width=2),
            symbol="t",
            symbolSize=5,
            name="3D FEA Corner",
        )
        master.addWidget(self.pressure_plot, stretch=2)

        # Plot 2: Bending Moment M(y) vs Stem Elevation
        self.moment_plot = pg.PlotWidget(title="Bending Moment Profile M(y)")
        self.moment_plot.showGrid(x=True, y=True, alpha=0.25)
        self.moment_plot.setLabel("bottom", "Bending Moment M", units="kNm/m")
        self.moment_plot.setLabel("left", "Stem Elevation y", units="m")
        self.moment_legend = self.moment_plot.addLegend(offset=(10, 10))

        self.curve_stem_moment = self.moment_plot.plot(
            pen=pg.mkPen(THEME["accent_orange"], width=2.5),
            name="Classical Stem M(y)",
        )
        self.curve_bnwf_moment = self.moment_plot.plot(
            pen=pg.mkPen(THEME["accent_blue"], width=2),
            symbol="s",
            symbolSize=5,
            name="OpenSees 2D BNWF",
        )
        master.addWidget(self.moment_plot, stretch=2)

        # Right side: Quantitative Discrepancy Card
        card = QFrame()
        card.setMinimumWidth(255)
        card.setMaximumWidth(310)
        card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {THEME['surface_elevated']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 8px;
            }}
            QLabel {{
                color: {THEME['text_primary']};
                font-size: 11px;
            }}
            """
        )
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(10, 8, 10, 8)
        card_lay.setSpacing(6)

        hdr = QLabel("<b>MULTI-SOLVER DISCREPANCY</b>")
        hdr.setStyleSheet(f"color: {THEME['accent_orange']}; font-size: 11px;")
        card_lay.addWidget(hdr)

        self.lbl_metrics = QLabel("Awaiting analytical update...")
        self.lbl_metrics.setWordWrap(True)
        card_lay.addWidget(self.lbl_metrics)
        card_lay.addStretch()
        master.addWidget(card, stretch=1)

    def set_bnwf_result(self, result: Optional[BNWFSimulationResult]) -> None:
        """Stores latest OpenSees 2D BNWF simulation result."""
        self._bnwf_result = result

    def set_fea_result(self, result: Optional[ContinuumFEAResult]) -> None:
        """Stores latest OpenSees 3D / Kratos Continuum FEA result."""
        self._fea_result = result

    def set_unit_system(self, unit_system: UnitSystem | str) -> None:
        """Updates comparison plot axes and summary metrics to SI or Imperial display units."""
        self.unit_system = UnitSystem(unit_system)
        self._apply_display()

    def _apply_display(self) -> None:
        """Renders cached `self._last_metrics` into plots & summary labels using active units."""
        m = self._last_metrics
        u_len = unit_label("length", self.unit_system)
        u_press = unit_label("pressure", self.unit_system)
        u_mom = unit_label("moment_per_m", self.unit_system)
        u_thrust = unit_label("force_per_m", self.unit_system)

        self.pressure_plot.setLabel("bottom", "Lateral Pressure sigma_h", units=u_press)
        self.pressure_plot.setLabel("left", "Depth z below Crest", units=u_len)
        self.moment_plot.setLabel("bottom", "Bending Moment M", units=u_mom)
        self.moment_plot.setLabel("left", "Stem Elevation y", units=u_len)

        if m is None:
            return

        fl = from_si_value(1.0, "length", self.unit_system)
        fp = from_si_value(1.0, "pressure", self.unit_system)
        fm = from_si_value(1.0, "moment_per_m", self.unit_system)
        ft = from_si_value(1.0, "force_per_m", self.unit_system)

        self.curve_rankine.setData(m.rankine_pressure_kpa * fp, m.depths_m * fl)
        self.curve_mo.setData(m.mo_dynamic_pressure_kpa * fp, m.depths_m * fl)
        self.curve_arching.setData(m.arching_pressure_kpa * fp, m.depths_m * fl)

        if len(m.fea_mid_depths_m) > 0:
            self.curve_fea_mid.setData(m.fea_mid_pressure_kpa * fp, m.fea_mid_depths_m * fl)
        else:
            self.curve_fea_mid.setData([], [])

        if len(m.fea_corner_depths_m) > 0:
            self.curve_fea_corner.setData(m.fea_corner_pressure_kpa * fp, m.fea_corner_depths_m * fl)
        else:
            self.curve_fea_corner.setData([], [])

        self.curve_stem_moment.setData(m.stem_moment_knm_m * fm, m.stem_elevations_m * fl)
        if len(m.bnwf_elevations_m) > 0:
            self.curve_bnwf_moment.setData(m.bnwf_moment_knm_m * fm, m.bnwf_elevations_m * fl)
        else:
            self.curve_bnwf_moment.setData([], [])

        fea_line = (
            f"3D FEA Peak Thrust: <b>{m.fea_peak_thrust_kn_m * ft:.2f} {u_thrust}</b> "
            f"({m.fea_thrust_diff_pct:+.1f}% vs M-O)<br>"
            f"3D Resultant Height: <b>{m.fea_h_res_over_H:.2f} H</b><br>"
            f"3D Corner Concentration: <b>{m.fea_corner_ratio:.2f}x</b>"
            if m.fea_peak_thrust_kn_m is not None
            else "3D FEA: <i>Click 'Run 3D FEA' to overlay sigma_xx(z)</i>"
        )
        bnwf_line = (
            f"2D BNWF Max Moment: <b>{m.bnwf_max_moment_knm * fm:.2f} {u_mom}</b> "
            f"({m.bnwf_moment_diff_pct:+.1f}% vs Stem Theory)"
            if m.bnwf_max_moment_knm is not None
            else "2D BNWF: <i>Click 'Run 2D BNWF' to overlay M(y)</i>"
        )

        self.lbl_metrics.setText(
            f"M-O Thrust P<sub>ae</sub>: <b>{m.mo_total_thrust_kn_m * ft:.2f} {u_thrust}</b><br>"
            f"Classical h<sub>res</sub> / H: <b>{m.mo_h_res_over_H:.3f}</b><br>"
            f"Shell Arching Transfer: <b>{m.arching_reduction_pct:.1f}%</b><br>"
            f"Stem M<sub>max</sub>: <b>{float(np.max(m.stem_moment_knm_m)) * fm:.2f} {u_mom}</b>"
            f"<hr>{fea_line}<hr>{bnwf_line}"
        )

    def update_comparison(
        self,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        results: Optional[AnalysisResults] = None,
        shell_geom: Optional[CurvedShellGeometry] = None,
        arching_result: Optional[ShellArchingResult] = None,
        stem_profile: Optional[StemStructuralProfile] = None,
    ) -> SolverComparisonMetrics:
        """Recomputes comparison curves and refreshes both plots and summary metrics."""
        m = compute_theory_vs_solver_comparison(
            geom=geom,
            soil=soil,
            seismic=seismic,
            results=results,
            shell_geom=shell_geom,
            arching_result=arching_result,
            stem_profile=stem_profile,
            bnwf_result=self._bnwf_result,
            fea_result=self._fea_result,
        )
        self._last_metrics = m
        self._apply_display()
        return m

    def last_metrics(self) -> Optional[SolverComparisonMetrics]:
        """Returns the most recently computed `SolverComparisonMetrics`."""
        return self._last_metrics

