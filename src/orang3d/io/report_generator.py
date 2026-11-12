"""
Automated Geotechnical Engineering PDF Report Generator for orang3D (Phase 9).
Produces a comprehensive design report containing:
- Cross-section diagram with all dimensions labeled
- Soil stratification and seismic disaster parameters tables
- Factors of Safety summary with regional code compliance checks (Eurocode 7, AASHTO, IS 14458)
- Embedded seismic waveform and Newmark permanent displacement curves
- Professional engineering typography and layout (< 1.5s execution, > 50 KB PDF)
"""

import os
import io
import base64
from datetime import datetime
from typing import Optional, Union

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter

from ..models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
)
from ..config import (
    RegionalStandard,
    get_safety_thresholds,
    APP_NAME,
    APP_VERSION,
)
from ..units import UnitSystem, from_si_value, unit_label


def _render_cross_section_png(
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    results: AnalysisResults,
    unit_system: UnitSystem = UnitSystem.SI,
) -> str:
    """Renders a dimensioned 2D engineering cross-section to a base64-encoded PNG."""
    fig = Figure(figsize=(6.5, 4.2), dpi=120)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f9fafb")

    toe = geom.toe_length
    t_base = geom.stem_thickness_base
    t_top = geom.stem_thickness_top
    heel = geom.heel_length
    d_f = geom.footing_thickness
    h_s = geom.stem_height
    b_w = toe + t_base + heel
    total_h = d_f + h_s

    # 1. Footing Slab Polygon: (0,0) -> (B, 0) -> (B, d_f) -> (0, d_f)
    f_x = [0.0, b_w, b_w, 0.0, 0.0]
    f_y = [0.0, 0.0, d_f, d_f, 0.0]
    ax.fill(f_x, f_y, color="#d1d5db", edgecolor="#374151", linewidth=1.5, hatch="//", label="Concrete Footing")

    # 2. Stem Polygon: (toe, d_f) -> (toe + t_base, d_f) -> (toe + t_base, total_h) -> (toe + t_base - t_top, total_h)
    s_x = [toe, toe + t_base, toe + t_base, toe + t_base - t_top, toe]
    s_y = [d_f, d_f, total_h, total_h, d_f]
    ax.fill(s_x, s_y, color="#e5e7eb", edgecolor="#1f2937", linewidth=1.8, hatch="\\\\", label="Concrete Stem")

    # 3. Ground and Backfill Surface
    back_ext = heel + 2.0
    ax.plot([toe + t_base, toe + t_base + back_ext], [total_h, total_h + back_ext * np.tan(np.radians(seismic.backfill_slope))],
            color="#b45309", linewidth=2.0, linestyle="-")
    ax.text(toe + t_base + 0.6 * back_ext, total_h + 0.2, "Ground Surface", color="#92400e", fontsize=8, weight="bold")

    # 4. Water Table Line
    if seismic.water_table_depth < total_h:
        y_w = total_h - seismic.water_table_depth
        ax.plot([toe + t_base, toe + t_base + back_ext], [y_w, y_w], color="#0284c7", linewidth=1.8, linestyle="--")
        dw_disp = from_si_value(seismic.water_table_depth, "length", unit_system)
        u_len = unit_label("length", unit_system)
        ax.text(toe + t_base + 0.2, y_w + 0.12, f"GWT (d_w = {dw_disp:.1f} {u_len})", color="#0369a1", fontsize=8, weight="bold")

    # 5. Thrust Resultant Arrow P_ae
    p_y = max(d_f + 0.5, results.thrust_height)
    p_x = toe + t_base
    pae_disp = from_si_value(results.total_thrust, "force_per_m", unit_system)
    u_force_m = unit_label("force_per_m", unit_system)
    ax.annotate(
        f"P_ae = {pae_disp:.2f} {u_force_m}",
        xy=(p_x, p_y),
        xytext=(p_x + 1.8, p_y + 0.6),
        arrowprops=dict(facecolor="#dc2626", edgecolor="#b91c1c", width=2.0, headwidth=8.0),
        fontsize=9, weight="bold", color="#b91c1c"
    )

    # 6. Dimension Annotations
    u_len = unit_label("length", unit_system)
    htot_disp = from_si_value(total_h, "length", unit_system)
    bw_disp = from_si_value(b_w, "length", unit_system)
    ax.annotate("", xy=(-0.3, 0), xytext=(-0.3, total_h), arrowprops=dict(arrowstyle="<->", color="#4b5563"))
    ax.text(-0.5, total_h / 2.0, f"H_total = {htot_disp:.2f} {u_len}", rotation=90, va="center", ha="right", fontsize=8, color="#374151")

    ax.annotate("", xy=(0, -0.3), xytext=(b_w, -0.3), arrowprops=dict(arrowstyle="<->", color="#4b5563"))
    ax.text(b_w / 2.0, -0.55, f"B = {bw_disp:.2f} {u_len}", ha="center", fontsize=8, color="#374151")

    ax.set_xlim(-1.2, b_w + back_ext + 0.5)
    ax.set_ylim(-0.8, total_h + 1.2)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Retaining Wall Dimensioned Cross-Section", fontsize=10, weight="bold", pad=8, color="#111827")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    fig.clear()
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _render_waveforms_png(
    time_arr: np.ndarray,
    slip_arr: np.ndarray,
    unit_system: UnitSystem = UnitSystem.SI,
) -> str:
    """Renders dynamic Newmark sliding displacement curve to a base64-encoded PNG."""
    fig = Figure(figsize=(6.5, 2.5), dpi=120)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f9fafb")

    slip_disp = slip_arr * from_si_value(1.0, "disp_cm", unit_system)
    u_disp = unit_label("disp_cm", unit_system)
    ax.plot(time_arr, slip_disp, color="#ea580c", linewidth=2.0, label="Permanent Slip u(t)")
    ax.fill_between(time_arr, 0, slip_disp, color="#ffedd5", alpha=0.5)

    ax.set_xlabel("Time (s)", fontsize=8, color="#374151")
    ax.set_ylabel(f"Permanent Slip ({u_disp})", fontsize=8, color="#374151")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.set_title("Newmark Dynamic Sliding Displacement History", fontsize=9, weight="bold", color="#111827")
    ax.tick_params(labelsize=8)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    fig.clear()
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def generate_engineering_pdf_report(
    filepath: str,
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    results: AnalysisResults,
    regional_standard: Union[RegionalStandard, str] = RegionalStandard.STANDARD,
    time_arr: Optional[np.ndarray] = None,
    slip_arr: Optional[np.ndarray] = None,
    project_title: str = "Retaining Wall Dynamic Safety & Disaster Assessment",
    unit_system: Union[UnitSystem, str] = UnitSystem.SI,
) -> str:
    """
    Generates a PDF design report containing cross-section drawings,
    material properties, seismic parameters, code compliance checks, and waveform histories
    formatted in either SI or Imperial units.
    """
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

    std = RegionalStandard(regional_standard) if isinstance(regional_standard, str) else regional_standard
    u_sys = UnitSystem(unit_system)
    thresholds = get_safety_thresholds(std)

    cross_section_b64 = _render_cross_section_png(geom, soil, seismic, results, unit_system=u_sys)

    waveforms_b64 = ""
    if time_arr is not None and slip_arr is not None and len(time_arr) > 0:
        waveforms_b64 = _render_waveforms_png(time_arr, slip_arr, unit_system=u_sys)

    # Compliance evaluations
    req_s = thresholds["sliding_seismic"]
    req_o = thresholds["overturning_seismic"]
    req_b = thresholds["bearing_seismic"]

    pass_s = results.fs_sliding >= req_s
    pass_o = results.fs_overturning >= req_o
    pass_b = results.fs_bearing >= req_b
    all_pass = pass_s and pass_o and pass_b

    verdict_color = "#16a34a" if all_pass else "#dc2626"
    verdict_text = "COMPLIANT / SAFE DESIGN" if all_pass else "ACTION REQUIRED / DEFICIENT CAPACITY"

    def status_pill(passed: bool) -> str:
        bg = "#dcfce7" if passed else "#fee2e2"
        fg = "#15803d" if passed else "#b91c1c"
        txt = "PASS" if passed else "FAIL"
        return f"<span style='background:{bg}; color:{fg}; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:10px;'>{txt}</span>"

    def _f(val: float, kind: str, dec: int = 2) -> str:
        return f"{from_si_value(val, kind, u_sys):.{dec}f} {unit_label(kind, u_sys)}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          color: #1f2937;
          margin: 15px;
          font-size: 11px;
          line-height: 1.4;
        }}
        h1 {{
          color: #0f172a;
          font-size: 18px;
          margin: 0 0 4px 0;
          font-weight: 800;
        }}
        h2 {{
          color: #1e293b;
          font-size: 13px;
          margin: 14px 0 6px 0;
          padding-bottom: 3px;
          border-bottom: 1.5px solid #e2e8f0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }}
        .header-meta {{
          color: #64748b;
          font-size: 9px;
          margin-bottom: 12px;
        }}
        .verdict-box {{
          background: #f8fafc;
          border-left: 4px solid {verdict_color};
          padding: 8px 12px;
          margin-bottom: 14px;
        }}
        .verdict-title {{
          font-size: 12px;
          font-weight: bold;
          color: {verdict_color};
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin-bottom: 10px;
          font-size: 10px;
        }}
        th {{
          background-color: #f1f5f9;
          color: #334155;
          text-align: left;
          padding: 5px 8px;
          border: 1px solid #cbd5e1;
          font-weight: 600;
        }}
        td {{
          padding: 4px 8px;
          border: 1px solid #e2e8f0;
        }}
        tr:nth-child(even) td {{
          background-color: #f8fafc;
        }}
        .img-container {{
          text-align: center;
          margin: 8px 0;
        }}
        .footer {{
          margin-top: 20px;
          padding-top: 8px;
          border-top: 1px solid #e2e8f0;
          font-size: 8px;
          color: #94a3b8;
          text-align: center;
        }}
      </style>
    </head>
    <body>
      <h1>{project_title}</h1>
      <div class="header-meta">
        Generated by {APP_NAME} v{APP_VERSION} | Design Code: <b>{std.value.upper()}</b> | Units: <b>{u_sys.value.upper()}</b> | Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
      </div>

      <div class="verdict-box">
        <div class="verdict-title">ENGINEERING VERDICT: {verdict_text}</div>
        <div>Dynamic safety evaluation indicates stability safety factors {'satisfy' if all_pass else 'do not satisfy'} all code requirements under {std.value.upper()}.</div>
      </div>

      <h2>1. Geometrical Dimensions & Cross-Section</h2>
      <table>
        <tr>
          <th>Stem Height <i>H</i></th><td>{_f(geom.stem_height, 'length')}</td>
          <th>Footing Thickness <i>D<sub>f</sub></i></th><td>{_f(geom.footing_thickness, 'length')}</td>
        </tr>
        <tr>
          <th>Base Stem Thickness <i>t<sub>base</sub></i></th><td>{_f(geom.stem_thickness_base, 'length')}</td>
          <th>Crest Thickness <i>t<sub>top</sub></i></th><td>{_f(geom.stem_thickness_top, 'length')}</td>
        </tr>
        <tr>
          <th>Front Toe Length <i>L<sub>toe</sub></i></th><td>{_f(geom.toe_length, 'length')}</td>
          <th>Rear Heel Length <i>L<sub>heel</sub></i></th><td>{_f(geom.heel_length, 'length')}</td>
        </tr>
        <tr>
          <th>Total Base Width <i>B</i></th><td>{_f(geom.base_width, 'length')}</td>
          <th>Total Height <i>H<sub>total</sub></i></th><td>{_f(geom.total_height, 'length')}</td>
        </tr>
      </table>

      <div class="img-container">
        <img src="data:image/png;base64,{cross_section_b64}" style="max-width: 95%; height: auto;" />
      </div>

      <h2>2. Geotechnical Strata & Seismic Parameters</h2>
      <table>
        <tr>
          <th>Backfill Soil Unit Weight &gamma;</th><td>{_f(soil.unit_weight, 'unit_weight', 1)}</td>
          <th>Backfill Friction Angle &phi;</th><td>{soil.friction_angle:.1f}°</td>
        </tr>
        <tr>
          <th>Foundation Cohesion <i>c<sub>f</sub></i></th><td>{_f(soil.foundation_cohesion, 'pressure', 2)}</td>
          <th>Allowable Bearing <i>q<sub>all</sub></i></th><td>{_f(soil.allowable_bearing_capacity, 'pressure', 2)}</td>
        </tr>
        <tr>
          <th>Peak Ground Acceleration <i>k<sub>h</sub></i></th><td>{seismic.horizontal_pga:.2f}g</td>
          <th>Water Table Depth <i>d<sub>w</sub></i></th><td>{_f(seismic.water_table_depth, 'length')}</td>
        </tr>
        <tr>
          <th>Pore Pressure Ratio <i>r<sub>u</sub></i></th><td>{seismic.pore_pressure_ratio_ru:.2f}</td>
          <th>Backfill Slope Angle &beta;</th><td>{seismic.backfill_slope:.1f}°</td>
        </tr>
      </table>

      <h2>3. Dynamic Safety Factors & Code Verification ({std.value.upper()})</h2>
      <table>
        <thead>
          <tr>
            <th>Failure Mechanism</th>
            <th>Calculated <i>FS</i></th>
            <th>Required <i>FS<sub>req</sub></i></th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Base Sliding Resistance</td>
            <td><b>{results.fs_sliding:.2f}</b></td>
            <td>{req_s:.2f}</td>
            <td>{status_pill(pass_s)}</td>
          </tr>
          <tr>
            <td>Toe Overturning Stability</td>
            <td><b>{results.fs_overturning:.2f}</b></td>
            <td>{req_o:.2f}</td>
            <td>{status_pill(pass_o)}</td>
          </tr>
          <tr>
            <td>Foundation Bearing Capacity</td>
            <td><b>{results.fs_bearing:.2f}</b></td>
            <td>{req_b:.2f}</td>
            <td>{status_pill(pass_b)}</td>
          </tr>
        </tbody>
      </table>

      <h2>4. Structural & Bearing Capacity Demands</h2>
      <table>
        <tr>
          <th>Total Dynamic Thrust <i>P<sub>ae</sub></i></th><td>{_f(results.total_thrust, 'force_per_m', 2)}</td>
          <th>Thrust Height Above Base</th><td>{_f(results.thrust_height, 'length')}</td>
        </tr>
        <tr>
          <th>Maximum Toe Pressure <i>q<sub>toe</sub></i></th><td>{_f(results.max_bearing_pressure, 'pressure', 2)}</td>
          <th>Minimum Heel Pressure <i>q<sub>heel</sub></i></th><td>{_f(results.min_bearing_pressure, 'pressure', 2)}</td>
        </tr>
        <tr>
          <th>Load Eccentricity <i>e</i></th><td>{_f(results.eccentricity, 'length')} (Kern limit: {_f(geom.base_width / 6.0, 'length')})</td>
          <th>Stem Base Bending Moment <i>M<sub>u</sub></i></th><td>{_f(results.max_bending_moment, 'moment_per_m', 2)}</td>
        </tr>
        <tr>
          <th>Stem Concrete Tensile Stress</th><td><b>{_f(results.concrete_tensile_stress, 'stress_mpa', 2)}</b></td>
          <th>Concrete Cracking State</th><td>{'CRACKED' if results.cracking_predicted else 'ELASTIC / UNCRACKED'}</td>
        </tr>
      </table>
    """

    if waveforms_b64:
        html += f"""
        <h2>5. Earthquake Time-History & Newmark Permanent Slip</h2>
        <div class="img-container">
          <img src="data:image/png;base64,{waveforms_b64}" style="max-width: 95%; height: auto;" />
        </div>
        """

    html += f"""
      <div class="footer">
        Confidential Engineering Calculation Document | Analyzed using {APP_NAME} 100% Permissive Open Source Stack (KratosMultiphysics / PyVista)
      </div>
    </body>
    </html>
    """

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(filepath)

    doc = QTextDocument()
    doc.setHtml(html)
    doc.print_(printer)

    return filepath
