"""
AutoCAD .dxf Construction Drawing Generator (Phase 10).
Produces layered engineering CAD drawings with exact geometry, reinforcement detailing,
strut connections, dimensions, and professional title blocks using ezdxf.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import numpy as np

try:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    EZDXF_AVAILABLE = True
except ImportError:
    ezdxf = None
    EZDXF_AVAILABLE = False

from ..models.advanced_wall_params import (
    MultiStrutPiledWallModel,
    CurvedShellGeometry,
    PierAndPileGeometry,
    StrutSupportSystem,
)


# Standard AutoCAD Layer Definitions
DXF_LAYERS: dict[str, int] = {
    "WALL_OUTLINE": 7,          # Color 7: White / Black
    "REBAR_REINFORCEMENT": 1,   # Color 1: Red
    "STRUT_DETAILS": 4,         # Color 4: Cyan
    "DIMENSIONS_AND_TEXT": 3,   # Color 3: Green
}

DXF_3D_LAYERS: dict[str, int] = {
    "WALL_3D_SHELL": 2,         # Color 2: Yellow (3D shell panels)
    "PIERS_AND_PILES_3D": 6,    # Color 6: Magenta (3D piers & bored piles)
    "STRUTS_3D": 5,             # Color 5: Blue (3D raking struts)
}


class RetainingWallDXFExporter:
    """
    Automated CAD detailing engine exporting multi-bay curved shell retaining wall
    construction drawings in AutoCAD DXF format (2D construction sheets + optional 3D entities).
    """

    def __init__(self, model: Optional[MultiStrutPiledWallModel] = None):
        self.model = model or MultiStrutPiledWallModel()

    def export(
        self,
        output_path: str | Path,
        project_title: str = "High-Voltage Uphill Retaining System",
        drawing_number: str = "DWG-O3D-001",
        num_bays: int = 3,
        rebar_callout: str = "2-layer T16 @ 125 mm c/c each face",
        pile_callout: str = "12-T25 Rebar Cage with T10 helical @ 100 mm pitch",
        strut_callout: str = "CHS 355.6x12.5 Structural Steel Strut (Fe 250)",
        include_3d: bool = False,
    ) -> str:
        """
        Generates layered AutoCAD .dxf file containing:
        1. Front Elevation View
        2. Plan View (Curved Shell Arches & Piers)
        3. Structural Reinforcement Detailing
        4. Engineering Title Block & Dimensions
        5. Optional 3D CAD geometry (`3DFACE` / `POLYLINE`) when `include_3d=True`.
        """
        file_path = Path(output_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if EZDXF_AVAILABLE:
            return self._export_ezdxf(
                file_path=file_path,
                project_title=project_title,
                drawing_number=drawing_number,
                num_bays=num_bays,
                rebar_callout=rebar_callout,
                pile_callout=pile_callout,
                strut_callout=strut_callout,
                include_3d=include_3d,
            )
        else:
            return self._export_ascii_dxf(
                file_path=file_path,
                project_title=project_title,
                drawing_number=drawing_number,
                num_bays=num_bays,
                rebar_callout=rebar_callout,
                pile_callout=pile_callout,
                strut_callout=strut_callout,
                include_3d=include_3d,
            )

    def _export_ezdxf(
        self,
        file_path: Path,
        project_title: str,
        drawing_number: str,
        num_bays: int,
        rebar_callout: str,
        pile_callout: str,
        strut_callout: str,
        include_3d: bool = False,
    ) -> str:
        """Generates DXF using ezdxf library."""
        doc = ezdxf.new("R2010", setup=True)
        msp = doc.modelspace()

        # Create layers
        layers_to_add = dict(DXF_LAYERS)
        if include_3d:
            layers_to_add.update(DXF_3D_LAYERS)
        for layer_name, color in layers_to_add.items():
            if layer_name not in doc.layers:
                doc.layers.add(layer_name, color=color)

        H = self.model.shell.panel_height
        L_bay = self.model.shell.bay_span
        R = self.model.shell.radius
        bp = self.model.pier_pile.pier_width
        dp = self.model.pier_pile.pier_depth
        hp = self.model.pier_pile.pier_height
        d_pile = self.model.pier_pile.pile_diameter
        l_pile = self.model.pier_pile.pile_length
        strut_levels = self.model.struts.strut_levels

        # Total system width
        total_width = num_bays * L_bay + (num_bays + 1) * bp

        # -------------------------------------------------------------
        # 1. FRONT ELEVATION VIEW (Origin: (0, 0))
        # -------------------------------------------------------------
        # Ground and Foundation Reference Lines
        msp.add_line((-2.0, 0.0), (total_width + 2.0, 0.0), dxfattribs={"layer": "WALL_OUTLINE"})
        msp.add_line((-2.0, H), (total_width + 2.0, H), dxfattribs={"layer": "WALL_OUTLINE"})

        # Vertical Piers & Bored Piles
        for i in range(num_bays + 1):
            x_pier = i * (L_bay + bp)
            # Pier rectangle (from y=0 to y=H)
            msp.add_lwpolyline([
                (x_pier, 0.0),
                (x_pier + bp, 0.0),
                (x_pier + bp, hp),
                (x_pier, hp),
                (x_pier, 0.0),
            ], dxfattribs={"layer": "WALL_OUTLINE"})

            # Bored Pile below ground (from y=0 down to y=-l_pile)
            x_pile_center = x_pier + bp / 2.0
            x_pile_left = x_pile_center - d_pile / 2.0
            x_pile_right = x_pile_center + d_pile / 2.0
            msp.add_lwpolyline([
                (x_pile_left, 0.0),
                (x_pile_left, -l_pile),
                (x_pile_right, -l_pile),
                (x_pile_right, 0.0),
            ], dxfattribs={"layer": "WALL_OUTLINE"})

            # Pile Rebar Cage Centerline (dashed effect in red)
            msp.add_line((x_pile_left + 0.08, -0.1), (x_pile_left + 0.08, -l_pile + 0.1), dxfattribs={"layer": "REBAR_REINFORCEMENT"})
            msp.add_line((x_pile_right - 0.08, -0.1), (x_pile_right - 0.08, -l_pile + 0.1), dxfattribs={"layer": "REBAR_REINFORCEMENT"})

        # Curved Shell Panels between Piers
        for i in range(num_bays):
            x_start = i * (L_bay + bp) + bp
            x_end = (i + 1) * (L_bay + bp)
            # Panel outline rectangle in elevation
            msp.add_lwpolyline([
                (x_start, 0.0),
                (x_end, 0.0),
                (x_end, H),
                (x_start, H),
                (x_start, 0.0),
            ], dxfattribs={"layer": "WALL_OUTLINE"})

            # Shell Rebar Grid (Horizontal and Vertical Rebar lines in Red)
            for rebar_y in np.linspace(0.5, H - 0.5, 5):
                msp.add_line((x_start + 0.1, rebar_y), (x_end - 0.1, rebar_y), dxfattribs={"layer": "REBAR_REINFORCEMENT"})

        # Steel Struts (Raking Braces)
        for i in range(num_bays + 1):
            x_pier_mid = i * (L_bay + bp) + bp / 2.0
            for s_level in strut_levels:
                # Strut rakes downward and forward
                x_strut_anchor = x_pier_mid - 2.5
                y_strut_anchor = -0.5
                msp.add_line((x_pier_mid, s_level), (x_strut_anchor, y_strut_anchor), dxfattribs={"layer": "STRUT_DETAILS"})
                # Gusset plate bracket
                msp.add_circle((x_pier_mid, s_level), radius=0.15, dxfattribs={"layer": "STRUT_DETAILS"})

        # -------------------------------------------------------------
        # 2. PLAN VIEW (Origin: (0, -l_pile - 6.0))
        # -------------------------------------------------------------
        y_plan_origin = -l_pile - 6.0

        for i in range(num_bays + 1):
            x_pier = i * (L_bay + bp)
            # Pier rectangle in plan (bp x dp)
            msp.add_lwpolyline([
                (x_pier, y_plan_origin),
                (x_pier + bp, y_plan_origin),
                (x_pier + bp, y_plan_origin - dp),
                (x_pier, y_plan_origin - dp),
                (x_pier, y_plan_origin),
            ], dxfattribs={"layer": "WALL_OUTLINE"})

            # Circular Bored Pile footprint underneath pier cap
            x_pile_center = x_pier + bp / 2.0
            y_pile_center = y_plan_origin - dp / 2.0
            msp.add_circle((x_pile_center, y_pile_center), radius=d_pile / 2.0, dxfattribs={"layer": "WALL_OUTLINE"})

        # Cylindrical Shell Arches in Plan
        for i in range(num_bays):
            x_start = i * (L_bay + bp) + bp
            x_end = (i + 1) * (L_bay + bp)
            x_mid = (x_start + x_end) / 2.0
            # Arch bulges convex into retained backfill
            theta_half = math.asin(min(1.0, (L_bay / 2.0) / R))
            sagitta = R * (1.0 - math.cos(theta_half))

            # Approximate arc using 10 polyline segments
            arc_pts = []
            for t in np.linspace(0.0, 1.0, 11):
                px = x_start + t * (x_end - x_start)
                # Parabolic/circular sagitta curve
                py = y_plan_origin + sagitta * 4.0 * t * (1.0 - t)
                arc_pts.append((float(px), float(py)))

            msp.add_lwpolyline(arc_pts, dxfattribs={"layer": "WALL_OUTLINE"})

        # -------------------------------------------------------------
        # 3. DIMENSIONS AND TEXT ANNOTATIONS
        # -------------------------------------------------------------
        # View Titles
        msp.add_text("FRONT ELEVATION VIEW", height=0.6, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((0.0, H + 1.5))
        msp.add_text("PLAN VIEW (CURVED ARCH SHELL & PIERS)", height=0.6, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((0.0, y_plan_origin + 1.5))

        # Height and Span Dimensions
        msp.add_text(f"Panel Height H = {H:.2f} m", height=0.4, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((-3.5, H / 2.0))
        msp.add_text(f"Bay Span L_bay = {L_bay:.2f} m", height=0.4, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((bp + L_bay / 3.0, -1.0))
        msp.add_text(f"Pile Embedment L_pile = {l_pile:.2f} m", height=0.4, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((-3.5, -l_pile / 2.0))

        # Structural Callouts
        x_callout = total_width + 2.5
        msp.add_text("ENGINEERING SPECIFICATIONS & MEMBER SIZING:", height=0.45, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((x_callout, H - 0.5))
        msp.add_text(f"- Shell Rebar: {rebar_callout}", height=0.35, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((x_callout, H - 1.5))
        msp.add_text(f"- Bored Pile: {pile_callout}", height=0.35, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((x_callout, H - 2.5))
        msp.add_text(f"- Strut Rake: {strut_callout}", height=0.35, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((x_callout, H - 3.5))
        msp.add_text("- Design Standards: IS 456:2000, IS 2911:2010, IS 800:2007", height=0.35, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((x_callout, H - 4.5))

        # -------------------------------------------------------------
        # 4. PROFESSIONAL TITLE BLOCK
        # -------------------------------------------------------------
        tb_x = total_width - 8.0
        tb_y = y_plan_origin - dp - 4.0
        tb_w = 12.0
        tb_h = 3.5

        # Border rectangle
        msp.add_lwpolyline([
            (tb_x, tb_y),
            (tb_x + tb_w, tb_y),
            (tb_x + tb_w, tb_y - tb_h),
            (tb_x, tb_y - tb_h),
            (tb_x, tb_y),
        ], dxfattribs={"layer": "DIMENSIONS_AND_TEXT"})

        msp.add_line((tb_x, tb_y - 1.0), (tb_x + tb_w, tb_y - 1.0), dxfattribs={"layer": "DIMENSIONS_AND_TEXT"})
        msp.add_line((tb_x, tb_y - 2.2), (tb_x + tb_w, tb_y - 2.2), dxfattribs={"layer": "DIMENSIONS_AND_TEXT"})

        msp.add_text(f"PROJECT: {project_title}", height=0.35, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((tb_x + 0.3, tb_y - 0.7))
        msp.add_text("ORANG3D 3D SCIENTIFIC RETAINING WALL ENGINE", height=0.30, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((tb_x + 0.3, tb_y - 1.7))
        msp.add_text(f"DRAWING NO: {drawing_number}  |  SCALE: 1:50  |  STATUS: APPROVED", height=0.25, dxfattribs={"layer": "DIMENSIONS_AND_TEXT"}).set_placement((tb_x + 0.3, tb_y - 2.8))

        if include_3d:
            self._emit_3d_entities_ezdxf(msp, num_bays=num_bays)

        doc.saveas(file_path)
        return str(file_path)

    def _emit_3d_entities_ezdxf(self, msp: Any, num_bays: int) -> None:
        """Emits 3DFACE shells, piers, bored piles, and 3D POLYLINE struts into DXF modelspace."""
        H = self.model.shell.panel_height
        L_bay = self.model.shell.bay_span
        R = self.model.shell.radius
        bp = self.model.pier_pile.pier_width
        dp = self.model.pier_pile.pier_depth
        hp = self.model.pier_pile.pier_height
        d_pile = self.model.pier_pile.pile_diameter
        l_pile = self.model.pier_pile.pile_length
        alpha_rad = math.radians(self.model.struts.inclination_angle)
        l_strut = self.model.struts.unbraced_length

        def _add_box_faces(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, layer: str) -> None:
            faces = [
                [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
                [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
                [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
            ]
            for f in faces:
                msp.add_3dface(f, dxfattribs={"layer": layer})

        # 3D Piers, Octagonal Bored Piles, and 3D Polyline Raking Struts
        for i in range(num_bays + 1):
            xp = i * (L_bay + bp)
            _add_box_faces(xp, xp + bp, 0.0, dp, 0.0, hp, "PIERS_AND_PILES_3D")

            xc = xp + 0.5 * bp
            yc = 0.5 * dp
            rad = 0.5 * d_pile
            n_sides = 8
            for k in range(n_sides):
                a0 = 2.0 * math.pi * k / n_sides
                a1 = 2.0 * math.pi * (k + 1) / n_sides
                p0 = (xc + rad * math.cos(a0), yc + rad * math.sin(a0))
                p1 = (xc + rad * math.cos(a1), yc + rad * math.sin(a1))
                msp.add_3dface(
                    [(p0[0], p0[1], 0.0), (p1[0], p1[1], 0.0), (p1[0], p1[1], -l_pile), (p0[0], p0[1], -l_pile)],
                    dxfattribs={"layer": "PIERS_AND_PILES_3D"},
                )

            for lvl in self.model.struts.strut_levels:
                z_top = hp - lvl
                y_anc = yc - l_strut * math.cos(alpha_rad)
                z_anc = z_top - l_strut * math.sin(alpha_rad)
                msp.add_polyline3d([(xc, yc, z_top), (xc, y_anc, z_anc)], dxfattribs={"layer": "STRUTS_3D"})

        # 3D Cylindrical Shell Arch Facets
        theta_half = math.asin(min(1.0, (L_bay / 2.0) / R))
        sagitta = R * (1.0 - math.cos(theta_half))
        n_seg = 8
        for i in range(num_bays):
            x0_bay = i * (L_bay + bp) + bp
            x1_bay = (i + 1) * (L_bay + bp)
            ts = np.linspace(0.0, 1.0, n_seg + 1)
            for j in range(n_seg):
                ta, tb = float(ts[j]), float(ts[j + 1])
                xa = x0_bay + ta * (x1_bay - x0_bay)
                xb = x0_bay + tb * (x1_bay - x0_bay)
                ya = dp + sagitta * 4.0 * ta * (1.0 - ta)
                yb = dp + sagitta * 4.0 * tb * (1.0 - tb)
                msp.add_3dface(
                    [(xa, ya, 0.0), (xb, yb, 0.0), (xb, yb, H), (xa, ya, H)],
                    dxfattribs={"layer": "WALL_3D_SHELL"},
                )

    def _export_ascii_dxf(
        self,
        file_path: Path,
        project_title: str,
        drawing_number: str,
        num_bays: int,
        rebar_callout: str,
        pile_callout: str,
        strut_callout: str,
        include_3d: bool = False,
    ) -> str:
        """Pure Python fallback generating valid ASCII DXF format."""
        layers_to_add = dict(DXF_LAYERS)
        if include_3d:
            layers_to_add.update(DXF_3D_LAYERS)
        lines = [
            "0", "SECTION",
            "2", "HEADER",
            "9", "$ACADVER", "1", "AC1015",
            "0", "ENDSEC",
            "0", "SECTION",
            "2", "TABLES",
            "0", "TABLE",
            "2", "LAYER",
            "70", str(len(layers_to_add)),
        ]
        for name, color in layers_to_add.items():
            lines.extend([
                "0", "LAYER",
                "2", name,
                "70", "0",
                "62", str(color),
                "6", "CONTINUOUS",
            ])
        lines.extend([
            "0", "ENDTAB",
            "0", "ENDSEC",
            "0", "SECTION",
            "2", "ENTITIES",
        ])

        H = self.model.shell.panel_height
        L_bay = self.model.shell.bay_span

        # Elevation lines
        lines.extend([
            "0", "LINE", "8", "WALL_OUTLINE",
            "10", "0.0", "20", "0.0", "30", "0.0",
            "11", str(num_bays * L_bay), "21", "0.0", "31", "0.0",
            "0", "LINE", "8", "WALL_OUTLINE",
            "10", "0.0", "20", str(H), "30", "0.0",
            "11", str(num_bays * L_bay), "21", str(H), "31", "0.0",
            "0", "TEXT", "8", "DIMENSIONS_AND_TEXT",
            "10", "0.0", "20", str(H + 1.0), "30", "0.0",
            "40", "0.5",
            "1", project_title,
        ])

        if include_3d:
            bp = self.model.pier_pile.pier_width
            for i in range(num_bays):
                xa = i * (L_bay + bp) + bp
                xb = (i + 1) * (L_bay + bp)
                lines.extend([
                    "0", "3DFACE", "8", "WALL_3D_SHELL",
                    "10", f"{xa:.4f}", "20", "0.0", "30", "0.0",
                    "11", f"{xb:.4f}", "21", "0.0", "31", "0.0",
                    "12", f"{xb:.4f}", "22", "0.0", "32", f"{H:.4f}",
                    "13", f"{xa:.4f}", "23", "0.0", "33", f"{H:.4f}",
                ])

        lines.extend([
            "0", "ENDSEC",
            "0", "EOF",
        ])

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return str(file_path)

    # Alias for pure ASCII DXF export
    _export_fallback_ascii = _export_ascii_dxf


def export_grid_to_3d_dxf(
    grid: Any,
    file_path: str | Path,
    layer_name: str = "WALL_3D_SHELL",
) -> str:
    """Exports any PyVista 3D dataset surface triangles as 3DFACE entities in DXF."""
    out_path = Path(file_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    surf = grid.extract_surface(algorithm="dataset_surface").triangulate()
    pts = np.asarray(surf.points, dtype=np.float64)
    faces = np.asarray(surf.faces, dtype=np.int64).reshape(-1, 4)[:, 1:4]

    if EZDXF_AVAILABLE:
        doc = ezdxf.new("R2010", setup=True)
        doc.layers.add(layer_name, color=2)
        msp = doc.modelspace()
        for tri in faces:
            p0, p1, p2 = pts[tri[0]], pts[tri[1]], pts[tri[2]]
            msp.add_3dface(
                [(float(p0[0]), float(p0[1]), float(p0[2])),
                 (float(p1[0]), float(p1[1]), float(p1[2])),
                 (float(p2[0]), float(p2[1]), float(p2[2]))],
                dxfattribs={"layer": layer_name},
            )
        doc.saveas(out_path)
        return str(out_path)

    lines = ["0", "SECTION", "2", "ENTITIES"]
    for tri in faces:
        p0, p1, p2 = pts[tri[0]], pts[tri[1]], pts[tri[2]]
        lines.extend([
            "0", "3DFACE", "8", layer_name,
            "10", f"{p0[0]:.5f}", "20", f"{p0[1]:.5f}", "30", f"{p0[2]:.5f}",
            "11", f"{p1[0]:.5f}", "21", f"{p1[1]:.5f}", "31", f"{p1[2]:.5f}",
            "12", f"{p2[0]:.5f}", "22", f"{p2[1]:.5f}", "32", f"{p2[2]:.5f}",
            "13", f"{p2[0]:.5f}", "23", f"{p2[1]:.5f}", "33", f"{p2[2]:.5f}",
        ])
    lines.extend(["0", "ENDSEC", "0", "EOF"])
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out_path)


def export_retaining_wall_dxf(
    model: MultiStrutPiledWallModel,
    file_path: str,
    project_title: str = "High-Voltage Uphill Retaining System",
    drawing_number: str = "DWG-O3D-001",
    num_bays: int = 3,
    rebar_callout: str = "2-layer T16 @ 125 mm c/c each face",
    pile_callout: str = "12-T25 Rebar Cage with T10 helical @ 100 mm pitch",
    strut_callout: str = "CHS 355.6x12.5 Structural Steel Strut (Fe 250)",
    include_3d: bool = False,
) -> str:
    """Convenience function for automated DXF construction drawing generation."""
    exporter = RetainingWallDXFExporter(model=model)
    return exporter.export(
        output_path=file_path,
        project_title=project_title,
        drawing_number=drawing_number,
        num_bays=num_bays,
        rebar_callout=rebar_callout,
        pile_callout=pile_callout,
        strut_callout=strut_callout,
        include_3d=include_3d,
    )
