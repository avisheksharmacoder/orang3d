"""
Step-by-Step "Show the Math" Equation Inspector Tab (v3 Phase 5).

Renders live HTML/Unicode derivations with color-coded numerical substitutions
into a native `QTextBrowser` so students and engineers can trace every formula:
  1. Active Earth Pressure Coefficients (Rankine, Coulomb, Mononobe-Okabe K_ae, theta_e)
  2. Thrust Breakdown (P_a at H/3, delta_P_ae at 0.6H, hydrostatic P_w) & h_res
  3. Sliding, Overturning, Eccentricity & Meyerhof Bearing Capacity (Nc, Nq, Ngamma)
  4. Curved Shell Horizontal Arching Partition (eta_arch) & Stem Structural Checks
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtWidgets import QHBoxLayout, QLabel, QTextBrowser, QVBoxLayout, QWidget

from ...config import THEME
from ...models.advanced_wall_params import CurvedShellGeometry, WallSystemMode
from ...models.wall_params import (
    AnalysisResults,
    RetainingWallGeometry,
    SeismicParams,
    SoilProperties,
)
from ...physics.mononobe_okabe import (
    compute_coulomb_earth_pressures,
    compute_lateral_thrusts,
    compute_liquefaction_degradation,
    compute_mononobe_okabe,
    compute_rankine_earth_pressures,
)
from ...physics.shell_arching import ShellArchingResult, compute_shell_arching_partition
from ...physics.stability import compute_bearing_capacity_factors, compute_ultimate_bearing_capacity
from ...physics.structural import StemStructuralProfile, compute_stem_internal_profiles


def _fmt_num(val: float, decimals: int = 3) -> str:
    """Formats numbers uniformly with accent color span for substituted terms."""
    return (
        f"<span style='color:{THEME['accent_orange']}; font-weight:600;'>"
        f"{val:.{decimals}f}</span>"
    )


def _fmt_res(val: float, decimals: int = 3, color_key: str = "accent_blue") -> str:
    """Formats evaluated outputs with highlighted result span."""
    return (
        f"<span style='color:{THEME[color_key]}; font-weight:700;'>"
        f"{val:.{decimals}f}</span>"
    )


def _build_equation_html(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    results: AnalysisResults,
    shell_geom: Optional[CurvedShellGeometry] = None,
    arching: Optional[ShellArchingResult] = None,
    stem: Optional[StemStructuralProfile] = None,
    wall_mode: WallSystemMode = WallSystemMode.CANTILEVER,
    preset_note: str = "",
) -> str:
    """Builds the step-by-step pedagogical HTML derivation for the current wall state."""
    phi_eff, c_eff = compute_liquefaction_degradation(
        soil.friction_angle, soil.cohesion, seismic.liquefaction_factor
    )
    delta_eff = min(soil.wall_friction_angle, max(0.0, phi_eff - 0.1))
    beta_eff = min(seismic.backfill_slope, max(0.0, phi_eff - 0.5))

    ka_rankine, kp_rankine = compute_rankine_earth_pressures(phi_eff, c=c_eff)
    ka_coulomb, _ = compute_coulomb_earth_pressures(phi_eff, delta_eff, beta_deg=beta_eff)
    k_ae, k_a_static, delta_k_ae = compute_mononobe_okabe(
        phi_deg=phi_eff,
        delta_deg=delta_eff,
        kh=seismic.horizontal_pga,
        kv=seismic.vertical_pga,
        beta_deg=beta_eff,
        liquefaction_factor=0.0,  # phi_eff already reflects degradation
    )

    kv_factor = max(0.01, 1.0 - seismic.vertical_pga)
    theta_e_rad = math.atan2(seismic.horizontal_pga, kv_factor)
    theta_e_deg = math.degrees(theta_e_rad)

    H = geom.total_height
    B = geom.base_width
    h_w_depth = max(0.0, min(seismic.water_table_depth, H))
    h_sub = H - h_w_depth
    gamma_w = 9.81
    gamma_eff = (
        soil.unit_weight
        if h_sub <= 0.0
        else (
            soil.unit_weight * (h_w_depth / H)
            + (soil.saturated_unit_weight - gamma_w) * (h_sub / H)
        )
    )

    p_a_static = 0.5 * gamma_eff * (H ** 2) * k_a_static
    delta_p_ae = 0.5 * gamma_eff * (H ** 2) * max(0.0, k_ae - k_a_static) * kv_factor
    total_combined, overall_h, p_water, h_water = compute_lateral_thrusts(
        wall_height=H,
        gamma=soil.unit_weight,
        gamma_sat=soil.saturated_unit_weight,
        k_ae=k_ae,
        k_a=k_a_static,
        water_table_depth=seismic.water_table_depth,
        kv=seismic.vertical_pga,
    )

    # Bearing / Meyerhof detail
    nc, nq, ng = compute_bearing_capacity_factors(soil.foundation_friction_angle)
    b_eff = max(0.2, B - 2.0 * abs(results.eccentricity))
    fs_color = "accent_green" if results.fs_sliding >= 1.1 else "accent_red"
    ot_color = "accent_green" if results.fs_overturning >= 1.5 else "accent_red"
    br_color = "accent_green" if results.fs_bearing >= 2.0 else "accent_red"

    if stem is None:
        stem = compute_stem_internal_profiles(geom, soil, seismic)
    if shell_geom is not None and arching is None:
        arching = compute_shell_arching_partition(shell_geom, soil)

    arching_html = ""
    if shell_geom is not None and arching is not None:
        eta_pct = arching.arching_ratio * 100.0
        arching_html = f"""
        <div class='card'>
          <h3>4. Curved Shell Horizontal Arching Partition &amp; Stem Checks ({wall_mode.value})</h3>
          <p class='eq'>
            &eta;<sub>arch</sub> = P<sub>pier,transfer</sub> / P<sub>free-field</sub> =
            {_fmt_num(arching.total_pier_thrust, 2)} / {_fmt_num(arching.total_free_field_thrust, 2)} =
            {_fmt_res(arching.arching_ratio, 4)} ({_fmt_res(eta_pct, 1, 'accent_green')}% transfer to piers)
          </p>
          <p class='eq'>
            Shell geometry: R = {_fmt_num(shell_geom.radius, 2)} m,
            2&theta; = {_fmt_num(shell_geom.subtended_angle, 1)}&deg;,
            L<sub>bay</sub> = {_fmt_num(shell_geom.bay_span, 2)} m,
            f<sub>sagitta</sub> = {_fmt_num(shell_geom.crown_sagitta, 3)} m &rarr;
            N<sub>hoop,max</sub> = {_fmt_res(arching.max_hoop_thrust, 2)} kN/m
          </p>
          <p class='eq'>
            Cantilever stem junction: V<sub>max</sub> = {_fmt_res(stem.max_shear_force, 2)} kN/m,
            M<sub>max</sub> = {_fmt_res(stem.max_bending_moment, 2)} kN&middot;m/m,
            &sigma;<sub>t</sub> = {_fmt_res(stem.max_tensile_stress, 2)} MPa vs.
            f<sub>r</sub> = 0.7&radic;f<sub>ck</sub> = {_fmt_num(stem.modulus_of_rupture, 2)} MPa
          </p>
        </div>
        """

    note_banner = (
        f"<div class='banner'>{preset_note}</div>"
        if preset_note
        else ""
    )

    return f"""
    <html>
    <head>
    <style>
      body {{
        background-color: {THEME['surface_dark']};
        color: {THEME['text_primary']};
        font-family: 'Segoe UI', 'DejaVu Sans', sans-serif;
        font-size: 12px;
        margin: 8px;
      }}
      .banner {{
        background-color: {THEME['surface_elevated']};
        border-left: 3px solid {THEME['accent_blue']};
        padding: 6px 10px;
        margin-bottom: 8px;
        color: {THEME['text_secondary']};
      }}
      .grid {{
        width: 100%;
      }}
      .card {{
        background-color: {THEME['background_dark']};
        border: 1px solid {THEME['border']};
        border-radius: 5px;
        padding: 8px 10px;
        margin-bottom: 8px;
      }}
      h3 {{
        margin: 0 0 6px 0;
        color: {THEME['accent_orange']};
        font-size: 13px;
      }}
      p.eq {{
        margin: 3px 0;
        line-height: 1.45;
      }}
      .muted {{
        color: {THEME['text_secondary']};
        font-size: 11px;
      }}
    </style>
    </head>
    <body>
      {note_banner}
      <div class='card'>
        <h3>1. Active Earth Pressure Coefficients (Rankine, Coulomb &amp; Mononobe-Okabe)</h3>
        <p class='eq'>
          <b>Rankine Active/Passive:</b>
          K<sub>a,Rank</sub> = tan&sup2;(45&deg; &minus; &phi;'/2) = tan&sup2;(45&deg; &minus; {_fmt_num(phi_eff, 1)}&deg;/2)
          = {_fmt_res(ka_rankine, 4)} &nbsp;|&nbsp;
          K<sub>p,Rank</sub> = tan&sup2;(45&deg; + &phi;'/2) = {_fmt_res(kp_rankine, 3)}
        </p>
        <p class='eq'>
          <b>Coulomb Static (&delta; = {_fmt_num(delta_eff, 1)}&deg;, &beta; = {_fmt_num(beta_eff, 1)}&deg;):</b>
          K<sub>a,Coul</sub> = {_fmt_res(ka_coulomb, 4)}
        </p>
        <p class='eq'>
          <b>Seismic Inertia Angle:</b>
          &theta;<sub>e</sub> = arctan[ k<sub>h</sub> / (1 &minus; k<sub>v</sub>) ]
          = arctan[ {_fmt_num(seismic.horizontal_pga, 3)} / (1 &minus; {_fmt_num(seismic.vertical_pga, 3)}) ]
          = {_fmt_res(theta_e_deg, 2)}&deg;
        </p>
        <p class='eq'>
          <b>Mononobe-Okabe Dynamic Coefficient:</b>
          K<sub>ae</sub> = {_fmt_res(k_ae, 4)} &nbsp;|&nbsp;
          &Delta;K<sub>ae</sub> = K<sub>ae</sub> &minus; K<sub>a</sub> = {_fmt_res(delta_k_ae, 4)}
          <span class='muted'>(liquefaction r<sub>u</sub> = {seismic.liquefaction_factor:.2f})</span>
        </p>
      </div>

      <div class='card'>
        <h3>2. Lateral Thrust Breakdown &amp; Resultant Elevations (Seed-Whitman 1970)</h3>
        <p class='eq'>
          <b>Effective Unit Weight:</b>
          H = {_fmt_num(H, 2)} m, H<sub>w</sub> = {_fmt_num(h_w_depth, 2)} m &rarr;
          &gamma;<sub>eff</sub> = {_fmt_res(gamma_eff, 2)} kN/m&sup3;
        </p>
        <p class='eq'>
          <b>Static Active Thrust:</b>
          P<sub>a</sub> = &frac12;&gamma;<sub>eff</sub>H&sup2;K<sub>a</sub>
          = 0.5 &times; {_fmt_num(gamma_eff, 2)} &times; {_fmt_num(H, 2)}&sup2; &times; {_fmt_num(k_a_static, 4)}
          = {_fmt_res(p_a_static, 2)} kN/m @ <b>H/3 = {_fmt_num(H / 3.0, 2)} m</b>
        </p>
        <p class='eq'>
          <b>Dynamic Seismic Increment:</b>
          &Delta;P<sub>ae</sub> = &frac12;&gamma;<sub>eff</sub>H&sup2;(K<sub>ae</sub> &minus; K<sub>a</sub>)(1 &minus; k<sub>v</sub>)
          = {_fmt_res(delta_p_ae, 2)} kN/m @ <b>0.6H = {_fmt_num(0.6 * H, 2)} m</b>
        </p>
        <p class='eq'>
          <b>Hydrostatic Thrust &amp; Combined Resultant:</b>
          P<sub>w</sub> = &frac12;&gamma;<sub>w</sub>h<sub>sub</sub>&sup2; = {_fmt_res(p_water, 2)} kN/m @ {_fmt_num(h_water, 2)} m
          &nbsp;&rarr;&nbsp;
          <b>P<sub>total</sub> = {_fmt_res(total_combined, 2)} kN/m @ h<sub>res</sub> = {_fmt_res(overall_h, 2)} m</b>
        </p>
      </div>

      <div class='card'>
        <h3>3. Global Stability, Eccentricity &amp; Meyerhof Bearing Capacity</h3>
        <p class='eq'>
          <b>Overturning Check:</b>
          FS<sub>OT</sub> = &Sigma;M<sub>stab</sub> / &Sigma;M<sub>ot</sub>
          = {_fmt_res(results.fs_overturning, 3, ot_color)}
          &nbsp;|&nbsp;
          <b>Sliding Check:</b>
          FS<sub>slide</sub> = (V<sub>eff</sub>tan&phi;<sub>b</sub> + c<sub>a</sub>B + P<sub>p</sub>) / D<sub>slide</sub>
          = {_fmt_res(results.fs_sliding, 3, fs_color)}
        </p>
        <p class='eq'>
          <b>Eccentricity &amp; Effective Width:</b>
          e = B/2 &minus; (&Sigma;M<sub>stab</sub> &minus; &Sigma;M<sub>ot</sub>)/V<sub>eff</sub>
          = {_fmt_res(results.eccentricity, 3)} m
          (B/6 = {_fmt_num(B / 6.0, 3)} m, Meyerhof B' = B &minus; 2|e| = {_fmt_num(b_eff, 3)} m)
        </p>
        <p class='eq'>
          <b>Meyerhof Bearing Factors (&phi;<sub>f</sub> = {_fmt_num(soil.foundation_friction_angle, 1)}&deg;):</b>
          N<sub>c</sub> = {_fmt_num(nc, 2)}, N<sub>q</sub> = {_fmt_num(nq, 2)}, N<sub>&gamma;</sub> = {_fmt_num(ng, 2)}
          &nbsp;&rarr;&nbsp;
          q<sub>max</sub> = {_fmt_res(results.max_bearing_pressure, 1)} kPa,
          q<sub>min</sub> = {_fmt_res(results.min_bearing_pressure, 1)} kPa,
          <b>FS<sub>bearing</sub> = {_fmt_res(results.fs_bearing, 3, br_color)}</b>
        </p>
      </div>

      {arching_html}
    </body>
    </html>
    """


class EquationInspectorTab(QWidget):
    """Live HTML/Unicode Equation Inspector showing substituted geotechnical formulas."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("Show the Math — Live Step-by-Step Geotechnical Derivations")
        title.setStyleSheet(
            f"color: {THEME['accent_orange']}; font-weight: bold; font-size: 12px;"
        )
        header.addWidget(title)
        header.addStretch()
        self.lbl_summary = QLabel("Active equations updated live")
        self.lbl_summary.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        header.addWidget(self.lbl_summary)
        layout.addLayout(header)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setStyleSheet(
            f"background-color: {THEME['surface_dark']}; border: 1px solid {THEME['border']};"
        )
        layout.addWidget(self.browser)

        self._last_html: str = ""

    def update_equations(
        self,
        geom: RetainingWallGeometry,
        soil: SoilProperties,
        seismic: SeismicParams,
        results: AnalysisResults,
        shell_geom: Optional[CurvedShellGeometry] = None,
        arching_result: Optional[ShellArchingResult] = None,
        stem_profile: Optional[StemStructuralProfile] = None,
        wall_mode: WallSystemMode = WallSystemMode.CANTILEVER,
        preset_note: str = "",
    ) -> None:
        """Rebuilds and displays substituted HTML equations for the active design state."""
        html = _build_equation_html(
            geom=geom,
            soil=soil,
            seismic=seismic,
            results=results,
            shell_geom=shell_geom,
            arching=arching_result,
            stem=stem_profile,
            wall_mode=wall_mode,
            preset_note=preset_note,
        )
        self._last_html = html
        self.browser.setHtml(html)
        self.lbl_summary.setText(
            f"K_a={results.k_a_static:.3f} | K_ae={results.k_ae:.3f} | "
            f"P_total={results.total_thrust:.1f} kN/m @ h={results.thrust_height:.2f} m"
        )

    def current_html(self) -> str:
        """Returns the last rendered HTML string (convenient for inspection and testing)."""
        return self._last_html

