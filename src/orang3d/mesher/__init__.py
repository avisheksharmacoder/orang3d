from .hex_mesher import (
    WallTemplate,
    WallGeometricProperties,
    build_3d_wall_mesh,
    build_3d_soil_mesh,
    build_3d_wedge_mesh,
    build_contact_pressure_glyphs,
    build_bearing_pressure_glyphs,
    compute_wall_geometric_properties,
    compute_hex_jacobian_determinants as compute_baseline_hex_jacobian_determinants,
)
from .shell_mesher import (
    shell_crown_profile,
    compute_shell_surface_normals,
    compute_hex_jacobian_determinants,
    build_curved_shell_panel_mesh,
    build_multi_bay_shell_mesh,
)
from .pile_strut_mesher import (
    build_pier_mesh,
    build_pile_cap_mesh,
    build_conformal_pier_and_cap_mesh,
    build_bored_piles_mesh,
    build_raking_struts_mesh,
    build_transmission_tower_mesh,
)
from .hybrid_assembler import (
    assemble_multi_strut_piled_wall_mesh,
    verify_conformal_junctions,
    build_high_fidelity_gmsh_mesh,
)
from .terrain import (
    TerrainRaster,
    DrapedWallAlignment,
    read_geotiff_dem,
    write_geotiff_dem,
    read_ascii_grid,
    write_ascii_grid,
    read_xyz_point_cloud,
    generate_synthetic_slope,
    drape_wall_on_terrain,
    RASTERIO_AVAILABLE,
)

__all__ = [
    # Baseline Cantilever / Gravity Mesher (v0.1.0)
    "WallTemplate",
    "WallGeometricProperties",
    "build_3d_wall_mesh",
    "build_3d_soil_mesh",
    "build_3d_wedge_mesh",
    "build_contact_pressure_glyphs",
    "build_bearing_pressure_glyphs",
    "compute_wall_geometric_properties",
    "compute_baseline_hex_jacobian_determinants",
    # Advanced Multi-Strut Shell Wall Suite (v2 Phase 2)
    "shell_crown_profile",
    "compute_shell_surface_normals",
    "compute_hex_jacobian_determinants",
    "build_curved_shell_panel_mesh",
    "build_multi_bay_shell_mesh",
    "build_pier_mesh",
    "build_pile_cap_mesh",
    "build_conformal_pier_and_cap_mesh",
    "build_bored_piles_mesh",
    "build_raking_struts_mesh",
    "build_transmission_tower_mesh",
    "assemble_multi_strut_piled_wall_mesh",
    "verify_conformal_junctions",
    "build_high_fidelity_gmsh_mesh",
    # Hill-Slope Topography & DEM Raster Ingestion (v2 Phase 5)
    "TerrainRaster",
    "DrapedWallAlignment",
    "read_geotiff_dem",
    "write_geotiff_dem",
    "read_ascii_grid",
    "write_ascii_grid",
    "read_xyz_point_cloud",
    "generate_synthetic_slope",
    "drape_wall_on_terrain",
    "RASTERIO_AVAILABLE",
]
