"""
3D Architectural Graphics (glTF 2.0 Binary .glb) & BIM (IFC 4 .ifc) Exporters (Phase 9).

Provides:
  - Binary glTF 2.0 (.glb) export directly from PyVista 3D meshes (zero OpenGL dependency).
  - IFC 4 STEP (.ifc) BIM export emitting IfcProject / IfcSite / IfcBuilding / IfcWall
    (predefined RETAININGWALL), IfcPile, and IfcMember entities with Pset metadata,
    using `ifcopenshell` when installed or a clean ISO-10303-21 IFC4 writer fallback.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import struct
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union
import uuid

import numpy as np
import pyvista as pv

try:
    import ifcopenshell  # type: ignore

    IFCOPENSHELL_AVAILABLE = True
except (ImportError, Exception):
    ifcopenshell = None
    IFCOPENSHELL_AVAILABLE = False

from ..mesher.arch_wall_mesher import build_architectural_wall_mesh
from ..mesher.hex_mesher import build_3d_wall_mesh
from ..models.advanced_wall_params import MultiStrutPiledWallModel
from ..models.architectural_wall_params import ArchitecturalWallSpec
from ..models.wall_params import AnalysisResults, RetainingWallGeometry


def _dataset_to_tri_arrays(grid: pv.DataSet) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extracts float32 (N,3) positions, (N,3) normals, and uint32 (M*3,) triangle indices."""
    surf = grid.extract_surface(algorithm="dataset_surface").triangulate()
    if surf.n_points == 0 or surf.n_cells == 0:
        raise ValueError("Cannot export empty PyVista surface to GLB.")

    surf = surf.compute_normals(point_normals=True, cell_normals=False, auto_orient_normals=False)
    pts = np.asarray(surf.points, dtype=np.float32)
    if "Normals" in surf.point_data:
        normals = np.asarray(surf.point_data["Normals"], dtype=np.float32)
    else:
        normals = np.tile(np.array([[0.0, 1.0, 0.0]], dtype=np.float32), (len(pts), 1))

    # Normalize safely to unit vectors for valid glTF 2.0 normals
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.where(norms > 1e-8, normals / np.maximum(norms, 1e-8), np.array([0.0, 1.0, 0.0], dtype=np.float32))

    faces = np.asarray(surf.faces, dtype=np.int64).reshape(-1, 4)
    if faces.shape[1] != 4 or not np.all(faces[:, 0] == 3):
        raise ValueError("Triangulated surface contains non-triangle cells.")
    indices = np.ascontiguousarray(faces[:, 1:4].ravel(), dtype=np.uint32)
    return np.ascontiguousarray(pts, dtype=np.float32), np.ascontiguousarray(normals, dtype=np.float32), indices


def export_mesh_to_glb(
    meshes: Union[pv.DataSet, Mapping[str, pv.DataSet]],
    filepath: str | Path,
    *,
    base_color_rgba: Tuple[float, float, float, float] = (0.76, 0.78, 0.80, 1.0),
) -> str:
    """
    Exports one PyVista DataSet or a mapping `{part_name: DataSet}` to a valid
    binary glTF 2.0 (`.glb`) file for Rhino, Blender, Three.js, and web viewers.
    """
    out_path = Path(filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    mesh_map: Dict[str, pv.DataSet] = (
        {"RetainingWall": meshes} if isinstance(meshes, pv.DataSet) else dict(meshes)
    )
    if not mesh_map:
        raise ValueError("At least one PyVista mesh must be provided for GLB export.")

    bin_chunks: List[bytes] = []
    byte_offset = 0
    buffer_views: List[Dict[str, Any]] = []
    accessors: List[Dict[str, Any]] = []
    gltf_meshes: List[Dict[str, Any]] = []
    gltf_nodes: List[Dict[str, Any]] = []

    def _append_blob(raw: bytes, target: Optional[int] = None) -> int:
        nonlocal byte_offset
        pad = (4 - (len(raw) % 4)) % 4
        padded = raw + (b"\x00" * pad)
        bv: Dict[str, Any] = {
            "buffer": 0,
            "byteOffset": byte_offset,
            "byteLength": len(raw),
        }
        if target is not None:
            bv["target"] = target
        idx = len(buffer_views)
        buffer_views.append(bv)
        bin_chunks.append(padded)
        byte_offset += len(padded)
        return idx

    for part_name, dataset in mesh_map.items():
        pts, normals, indices = _dataset_to_tri_arrays(dataset)
        p_min = [float(v) for v in np.min(pts, axis=0)]
        p_max = [float(v) for v in np.max(pts, axis=0)]

        bv_pos = _append_blob(pts.tobytes(), target=34962)   # ARRAY_BUFFER
        bv_nrm = _append_blob(normals.tobytes(), target=34962)
        bv_idx = _append_blob(indices.tobytes(), target=34963)  # ELEMENT_ARRAY_BUFFER

        acc_pos = len(accessors)
        accessors.append(
            {
                "bufferView": bv_pos,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": int(len(pts)),
                "type": "VEC3",
                "min": p_min,
                "max": p_max,
            }
        )
        acc_nrm = len(accessors)
        accessors.append(
            {
                "bufferView": bv_nrm,
                "byteOffset": 0,
                "componentType": 5126,
                "count": int(len(normals)),
                "type": "VEC3",
            }
        )
        acc_idx = len(accessors)
        accessors.append(
            {
                "bufferView": bv_idx,
                "byteOffset": 0,
                "componentType": 5125,  # UNSIGNED_INT
                "count": int(len(indices)),
                "type": "SCALAR",
            }
        )

        mesh_idx = len(gltf_meshes)
        gltf_meshes.append(
            {
                "name": str(part_name),
                "primitives": [
                    {
                        "attributes": {"POSITION": acc_pos, "NORMAL": acc_nrm},
                        "indices": acc_idx,
                        "material": 0,
                        "mode": 4,  # TRIANGLES
                    }
                ],
            }
        )
        gltf_nodes.append({"name": str(part_name), "mesh": mesh_idx})

    bin_payload = b"".join(bin_chunks)
    gltf_doc = {
        "asset": {
            "version": "2.0",
            "generator": "orang3D Phase 9 BIM/CAD Exporter",
        },
        "scene": 0,
        "scenes": [{"name": "orang3D_Scene", "nodes": list(range(len(gltf_nodes)))}],
        "nodes": gltf_nodes,
        "meshes": gltf_meshes,
        "materials": [
            {
                "name": "StructuralConcrete",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [float(c) for c in base_color_rgba],
                    "metallicFactor": 0.05,
                    "roughnessFactor": 0.82,
                },
                "doubleSided": True,
            }
        ],
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(bin_payload)}],
    }

    json_bytes = json.dumps(gltf_doc, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_chunk = json_bytes + (b" " * json_pad)

    total_length = 12 + 8 + len(json_chunk) + 8 + len(bin_payload)
    header = struct.pack("<4sII", b"glTF", 2, total_length)
    chunk0_hdr = struct.pack("<II", len(json_chunk), 0x4E4F534A)  # JSON
    chunk1_hdr = struct.pack("<II", len(bin_payload), 0x004E4942)  # BIN

    out_path.write_bytes(header + chunk0_hdr + json_chunk + chunk1_hdr + bin_payload)
    return str(out_path)


def read_glb_summary(filepath: str | Path) -> Dict[str, Any]:
    """Reads and validates a GLB 2.0 header and parses its embedded JSON asset manifest."""
    data = Path(filepath).read_bytes()
    if len(data) < 20:
        raise ValueError("File too small to be a valid GLB 2.0 archive.")
    magic, version, total_len = struct.unpack("<4sII", data[:12])
    if magic != b"glTF" or version != 2:
        raise ValueError(f"Invalid GLB header: magic={magic!r}, version={version}")
    if total_len != len(data):
        raise ValueError(f"GLB length mismatch: header={total_len}, actual={len(data)}")

    json_len, json_type = struct.unpack("<II", data[12:20])
    if json_type != 0x4E4F534A:
        raise ValueError("First GLB chunk is not JSON.")
    manifest = json.loads(data[20 : 20 + json_len].decode("utf-8"))
    return {
        "magic": magic.decode("ascii"),
        "version": version,
        "total_length": total_len,
        "manifest": manifest,
    }


def export_wall_to_glb(
    filepath: str | Path,
    geom: RetainingWallGeometry,
    results: Optional[AnalysisResults] = None,
    *,
    arch_spec: Optional[ArchitecturalWallSpec] = None,
    active_mesh: Optional[pv.DataSet] = None,
) -> str:
    """Exports the active retaining wall (cantilever, architectural, or cached mesh) to `.glb`."""
    if active_mesh is not None:
        grid = active_mesh
    elif arch_spec is not None:
        grid = build_architectural_wall_mesh(arch_spec)
    else:
        grid = build_3d_wall_mesh(geom, results)
    return export_mesh_to_glb({"RetainingWall": grid}, filepath)


def _ifc_guid() -> str:
    """Generates a 22-character IFC compressed GUID string."""
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
    num = uuid.uuid4().int
    out = []
    for _ in range(22):
        out.append(chars[num % 64])
        num //= 64
    return "".join(reversed(out))


def export_wall_to_ifc(
    filepath: str | Path,
    geom: RetainingWallGeometry,
    results: Optional[AnalysisResults] = None,
    *,
    multi_strut_model: Optional[MultiStrutPiledWallModel] = None,
    num_bays: int = 3,
    project_name: str = "orang3D Retaining Wall BIM",
    standard_name: str = "IS_14458",
) -> str:
    """
    Exports an IFC 4 (`.ifc`) structural/BIM model containing IfcProject, IfcSite,
    IfcBuilding, IfcBuildingStorey, IfcWall (RETAININGWALL), optional IfcPile &
    IfcMember elements, and an engineering IfcPropertySet (`Pset_orang3D_Design`).
    """
    out_path = Path(filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if IFCOPENSHELL_AVAILABLE and ifcopenshell is not None:
        return _export_with_ifcopenshell(
            out_path=out_path,
            geom=geom,
            results=results,
            multi_strut_model=multi_strut_model,
            num_bays=num_bays,
            project_name=project_name,
            standard_name=standard_name,
        )

    return _export_ifc4_step_fallback(
        out_path=out_path,
        geom=geom,
        results=results,
        multi_strut_model=multi_strut_model,
        num_bays=num_bays,
        project_name=project_name,
        standard_name=standard_name,
    )


def _export_with_ifcopenshell(
    *,
    out_path: Path,
    geom: RetainingWallGeometry,
    results: Optional[AnalysisResults],
    multi_strut_model: Optional[MultiStrutPiledWallModel],
    num_bays: int,
    project_name: str,
    standard_name: str,
) -> str:
    """Native ifcopenshell IFC4 exporter when the optional package is installed."""
    model = ifcopenshell.file(schema="IFC4")
    owner = model.create_entity("IfcPerson", GivenName="orang3D", FamilyName="Engineer")
    org = model.create_entity("IfcOrganization", Name="orang3D")
    p_org = model.create_entity("IfcPersonAndOrganization", ThePerson=owner, TheOrganization=org)
    app = model.create_entity(
        "IfcApplication",
        ApplicationDeveloper=org,
        Version="3.0",
        ApplicationFullName="orang3D",
        ApplicationIdentifier="orang3D",
    )
    oh = model.create_entity(
        "IfcOwnerHistory",
        OwningUser=p_org,
        OwningApplication=app,
        ChangeAction="ADDED",
        CreationDate=int(datetime.now(timezone.utc).timestamp()),
    )
    unit_m = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    unit_assignment = model.create_entity("IfcUnitAssignment", Units=[unit_m])
    origin = model.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
    ctx = model.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=model.create_entity("IfcAxis2Placement3D", Location=origin),
    )
    project = model.create_entity(
        "IfcProject",
        GlobalId=_ifc_guid(),
        OwnerHistory=oh,
        Name=project_name,
        RepresentationContexts=[ctx],
        UnitsInContext=unit_assignment,
    )
    site = model.create_entity("IfcSite", GlobalId=_ifc_guid(), OwnerHistory=oh, Name="RetainingSite")
    bldg = model.create_entity("IfcBuilding", GlobalId=_ifc_guid(), OwnerHistory=oh, Name="RetainingStructure")
    storey = model.create_entity("IfcBuildingStorey", GlobalId=_ifc_guid(), OwnerHistory=oh, Name="GradeLevel", Elevation=0.0)
    model.create_entity("IfcRelAggregates", GlobalId=_ifc_guid(), OwnerHistory=oh, RelatingObject=project, RelatedObjects=[site])
    model.create_entity("IfcRelAggregates", GlobalId=_ifc_guid(), OwnerHistory=oh, RelatingObject=site, RelatedObjects=[bldg])
    model.create_entity("IfcRelAggregates", GlobalId=_ifc_guid(), OwnerHistory=oh, RelatingObject=bldg, RelatedObjects=[storey])

    wall = model.create_entity(
        "IfcWall",
        GlobalId=_ifc_guid(),
        OwnerHistory=oh,
        Name="CantileverRetainingWall",
        Description=f"H={geom.total_height:.2f}m, Base={geom.footing_width:.2f}m, Std={standard_name}",
        PredefinedType="RETAININGWALL",
    )
    contained: List[Any] = [wall]
    if multi_strut_model is not None:
        for idx in range(num_bays + 1):
            contained.append(
                model.create_entity(
                    "IfcPile",
                    GlobalId=_ifc_guid(),
                    OwnerHistory=oh,
                    Name=f"BoredPile_{idx + 1}",
                    PredefinedType="BORED",
                )
            )
            for s_idx, _lvl in enumerate(multi_strut_model.struts.strut_levels):
                contained.append(
                    model.create_entity(
                        "IfcMember",
                        GlobalId=_ifc_guid(),
                        OwnerHistory=oh,
                        Name=f"RakingStrut_P{idx + 1}_S{s_idx + 1}",
                        PredefinedType="STRUT",
                    )
                )

    model.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=_ifc_guid(),
        OwnerHistory=oh,
        RelatingStructure=storey,
        RelatedElements=contained,
    )
    if results is not None:
        props = [
            model.create_entity("IfcPropertySingleValue", Name="FS_Sliding", NominalValue=model.create_entity("IfcReal", float(results.fs_sliding))),
            model.create_entity("IfcPropertySingleValue", Name="FS_Overturning", NominalValue=model.create_entity("IfcReal", float(results.fs_overturning))),
            model.create_entity("IfcPropertySingleValue", Name="FS_Bearing", NominalValue=model.create_entity("IfcReal", float(results.fs_bearing))),
        ]
        pset = model.create_entity("IfcPropertySet", GlobalId=_ifc_guid(), OwnerHistory=oh, Name="Pset_orang3D_GeotechnicalDesign", HasProperties=props)
        model.create_entity("IfcRelDefinesByProperties", GlobalId=_ifc_guid(), OwnerHistory=oh, RelatedObjects=[wall], RelatingPropertyDefinition=pset)

    model.write(str(out_path))
    return str(out_path)


def _export_ifc4_step_fallback(
    *,
    out_path: Path,
    geom: RetainingWallGeometry,
    results: Optional[AnalysisResults],
    multi_strut_model: Optional[MultiStrutPiledWallModel],
    num_bays: int,
    project_name: str,
    standard_name: str,
) -> str:
    """Pure-Python ISO-10303-21 IFC4 STEP generator emitting extruded retaining wall BIM entities."""
    ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    ts_int = int(datetime.now(timezone.utc).timestamp())
    fs_s = float(results.fs_sliding) if results is not None else 0.0
    fs_o = float(results.fs_overturning) if results is not None else 0.0
    fs_b = float(results.fs_bearing) if results is not None else 0.0
    moment = float(results.max_bending_moment) if results is not None else 0.0

    entities: List[str] = [
        f"#1=IFCPERSON($,'Engineer','orang3D',$,$,$,$,$);",
        f"#2=IFCORGANIZATION($,'orang3D','Geotechnical 3D Retaining Engine',$,$);",
        f"#3=IFCPERSONANDORGANIZATION(#1,#2,$);",
        f"#4=IFCAPPLICATION(#2,'3.0','orang3D','orang3D');",
        f"#5=IFCOWNERHISTORY(#3,#4,$,.ADDED.,$,$,$,{ts_int});",
        f"#6=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);",
        f"#7=IFCUNITASSIGNMENT((#6));",
        f"#8=IFCCARTESIANPOINT((0.,0.,0.));",
        f"#9=IFCDIRECTION((0.,0.,1.));",
        f"#10=IFCDIRECTION((1.,0.,0.));",
        f"#11=IFCAXIS2PLACEMENT3D(#8,#9,#10);",
        f"#12=IFCGEOMETRICREPRESENTATIONCONTEXT('Model','Model',3,1.E-05,#11,$);",
        f"#13=IFCPROJECT('{_ifc_guid()}',#5,'{project_name}',$,$,$,$,(#12),#7);",
        f"#14=IFCLOCALPLACEMENT($,#11);",
        f"#15=IFCSITE('{_ifc_guid()}',#5,'RetainingSite',$,$,#14,$,$,.ELEMENT.,$,$,$,$,$);",
        f"#16=IFCBUILDING('{_ifc_guid()}',#5,'RetainingStructure',$,$,#14,$,$,.ELEMENT.,$,$,$);",
        f"#17=IFCBUILDINGSTOREY('{_ifc_guid()}',#5,'GradeLevel',$,$,#14,$,$,.ELEMENT.,0.);",
        f"#18=IFCRELAGGREGATES('{_ifc_guid()}',#5,$,$,#13,(#15));",
        f"#19=IFCRELAGGREGATES('{_ifc_guid()}',#5,$,$,#15,(#16));",
        f"#20=IFCRELAGGREGATES('{_ifc_guid()}',#5,$,$,#16,(#17));",
        # Extruded stem wall solid (footing_width x stem_thickness_base x wall_length)
        f"#21=IFCRECTANGLEPROFILEDEF(.AREA.,'WallStemProfile',$,{geom.stem_thickness_base:.4f},{geom.wall_length:.4f});",
        f"#22=IFCCARTESIANPOINT(({geom.toe_length + 0.5 * geom.stem_thickness_base:.4f},{0.5 * geom.wall_length:.4f},{geom.footing_thickness:.4f}));",
        f"#23=IFCAXIS2PLACEMENT3D(#22,#9,#10);",
        f"#24=IFCEXTRUDEDAREASOLID(#21,#23,#9,{geom.stem_height:.4f});",
        f"#25=IFCSHAPEREPRESENTATION(#12,'Body','SweptSolid',(#24));",
        f"#26=IFCPRODUCTDEFINITIONSHAPE($,$,(#25));",
        f"#27=IFCWALL('{_ifc_guid()}',#5,'CantileverRetainingWall','H={geom.total_height:.2f}m;Std={standard_name}',$,#14,#26,'WALL-01',.RETAININGWALL.);",
    ]

    eid = 28
    contained_ids = ["#27"]

    if multi_strut_model is not None:
        bp = multi_strut_model.pier_pile.pier_width
        l_bay = multi_strut_model.shell.bay_span
        d_pile = multi_strut_model.pier_pile.pile_diameter
        l_pile = multi_strut_model.pier_pile.pile_length
        for i in range(num_bays + 1):
            x_c = i * (l_bay + bp) + 0.5 * bp
            pt_id = eid
            ax_id = eid + 1
            prof_id = eid + 2
            ext_id = eid + 3
            rep_id = eid + 4
            pds_id = eid + 5
            pile_id = eid + 6
            eid += 7
            entities.extend([
                f"#{pt_id}=IFCCARTESIANPOINT(({x_c:.4f},0.,{-l_pile:.4f}));",
                f"#{ax_id}=IFCAXIS2PLACEMENT3D(#{pt_id},#9,#10);",
                f"#{prof_id}=IFCCIRCLEPROFILEDEF(.AREA.,'BoredPile',$,{0.5 * d_pile:.4f});",
                f"#{ext_id}=IFCEXTRUDEDAREASOLID(#{prof_id},#{ax_id},#9,{l_pile:.4f});",
                f"#{rep_id}=IFCSHAPEREPRESENTATION(#12,'Body','SweptSolid',(#{ext_id}));",
                f"#{pds_id}=IFCPRODUCTDEFINITIONSHAPE($,$,(#{rep_id}));",
                f"#{pile_id}=IFCPILE('{_ifc_guid()}',#5,'BoredPile_{i + 1}',$,$,#14,#{pds_id},'PILE-{i + 1}',.BORED.,$);",
            ])
            contained_ids.append(f"#{pile_id}")

            for s_idx, _lvl in enumerate(multi_strut_model.struts.strut_levels):
                mem_id = eid
                eid += 1
                entities.append(
                    f"#{mem_id}=IFCMEMBER('{_ifc_guid()}',#5,'RakingStrut_P{i + 1}_S{s_idx + 1}',$,$,#14,$,'STRUT-{i + 1}-{s_idx + 1}',.STRUT.);"
                )
                contained_ids.append(f"#{mem_id}")

    rel_contain_id = eid
    eid += 1
    entities.append(
        f"#{rel_contain_id}=IFCRELCONTAINEDINSPATIALSTRUCTURE('{_ifc_guid()}',#5,$,$,({','.join(contained_ids)}),#17);"
    )

    p1, p2, p3, p4, pset_id, rel_prop_id = eid, eid + 1, eid + 2, eid + 3, eid + 4, eid + 5
    entities.extend([
        f"#{p1}=IFCPROPERTYSINGLEVALUE('FS_Sliding',$,IFCREAL({fs_s:.4f}),$);",
        f"#{p2}=IFCPROPERTYSINGLEVALUE('FS_Overturning',$,IFCREAL({fs_o:.4f}),$);",
        f"#{p3}=IFCPROPERTYSINGLEVALUE('FS_Bearing',$,IFCREAL({fs_b:.4f}),$);",
        f"#{p4}=IFCPROPERTYSINGLEVALUE('Max_Moment_kNm',$,IFCREAL({moment:.4f}),$);",
        f"#{pset_id}=IFCPROPERTYSET('{_ifc_guid()}',#5,'Pset_orang3D_GeotechnicalDesign',$,(#{p1},#{p2},#{p3},#{p4}));",
        f"#{rel_prop_id}=IFCRELDEFINESBYPROPERTIES('{_ifc_guid()}',#5,$,$,(#27),#{pset_id});",
    ])

    step_text = "\n".join([
        "ISO-10303-21;",
        "HEADER;",
        f"FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');",
        f"FILE_NAME('{out_path.name}','{ts_str}',('orang3D'),('orang3D'),'orang3D IFC4','orang3D','');",
        "FILE_SCHEMA(('IFC4'));",
        "ENDSEC;",
        "DATA;",
        *entities,
        "ENDSEC;",
        "END-ISO-10303-21;",
        "",
    ])
    out_path.write_text(step_text, encoding="utf-8")
    return str(out_path)
