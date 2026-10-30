"""
orang3d.io: Session serialization, CAD/FEA mesh exports, and PDF report generation.
"""

from .serialization import (
    save_project_session,
    load_project_session,
    ProjectSession,
    CorruptProjectError,
)
from .mesh_export import (
    export_mesh_to_vtk,
    export_mesh_to_stl,
    export_mesh_to_obj,
    export_signals_to_csv,
)
from .report_generator import generate_engineering_pdf_report
from .dxf_export import (
    RetainingWallDXFExporter,
    export_retaining_wall_dxf,
    EZDXF_AVAILABLE,
    DXF_LAYERS,
)

__all__ = [
    "save_project_session",
    "load_project_session",
    "ProjectSession",
    "CorruptProjectError",
    "export_mesh_to_vtk",
    "export_mesh_to_stl",
    "export_mesh_to_obj",
    "export_signals_to_csv",
    "generate_engineering_pdf_report",
    "RetainingWallDXFExporter",
    "export_retaining_wall_dxf",
    "EZDXF_AVAILABLE",
    "DXF_LAYERS",
]
