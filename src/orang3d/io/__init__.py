"""
orang3d.io: Session serialization, CAD/BIM/GLB/IFC mesh exports, runnable solver decks,
research archives, and PDF report generation.
"""

from .serialization import (
    CURRENT_SCHEMA_VERSION,
    save_project_session,
    load_project_session,
    ProjectSession,
    CorruptProjectError,
)
from .mesh_export import (
    export_grid_mesh,
    export_mesh_to_vtk,
    export_mesh_to_stl,
    export_mesh_to_obj,
    export_signals_to_csv,
)
from .report_generator import generate_engineering_pdf_report
from .dxf_export import (
    RetainingWallDXFExporter,
    export_retaining_wall_dxf,
    export_grid_to_3d_dxf,
    EZDXF_AVAILABLE,
    DXF_LAYERS,
    DXF_3D_LAYERS,
)
from .deck_export import (
    export_opensees_bnwf_deck,
    export_kratos_deck,
    export_research_archive,
)
from .bim_export import (
    IFCOPENSHELL_AVAILABLE,
    export_mesh_to_glb,
    export_wall_to_glb,
    export_wall_to_ifc,
    read_glb_summary,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "save_project_session",
    "load_project_session",
    "ProjectSession",
    "CorruptProjectError",
    "export_grid_mesh",
    "export_mesh_to_vtk",
    "export_mesh_to_stl",
    "export_mesh_to_obj",
    "export_signals_to_csv",
    "generate_engineering_pdf_report",
    "RetainingWallDXFExporter",
    "export_retaining_wall_dxf",
    "export_grid_to_3d_dxf",
    "EZDXF_AVAILABLE",
    "DXF_LAYERS",
    "DXF_3D_LAYERS",
    "export_opensees_bnwf_deck",
    "export_kratos_deck",
    "export_research_archive",
    "IFCOPENSHELL_AVAILABLE",
    "export_mesh_to_glb",
    "export_wall_to_glb",
    "export_wall_to_ifc",
    "read_glb_summary",
]
