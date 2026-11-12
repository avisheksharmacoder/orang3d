"""
Project Session Serialization & Migration Engine for orang3D (Phase 9 - Schema v2.0.0).
Manages saving and loading complete project sessions as single compressed .o3d packages
(JSON metadata and schemas + HDF5 simulation & FEA caches) with backward-compatibility
for v0.1 / v1.0 .o3d files.
"""

from __future__ import annotations

import os
import json
import zipfile
import tempfile
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict, Any
import numpy as np
import h5py

from ..config import APP_NAME, APP_VERSION, RegionalStandard, ThemeMode
from ..models.advanced_wall_params import (
    CurvedShellGeometry,
    PierAndPileGeometry,
    StrutSupportSystem,
    WallSystemMode,
)
from ..models.architectural_wall_params import ArchitecturalWallSpec
from ..models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
)
from ..physics.surcharge import AdjacentSurchargeParams, SurchargeLoadType
from ..units import UnitSystem


CURRENT_SCHEMA_VERSION = "2.0.0"


class CorruptProjectError(Exception):
    """Raised when an .o3d file is truncated, unreadable, or missing required manifest schemas."""
    pass


@dataclass
class ProjectSession:
    """Complete serialized representation of an orang3D v1/v2 project session."""

    geom: RetainingWallGeometry
    soil: SoilProperties
    seismic: SeismicParams
    results: AnalysisResults
    time_arr: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    accel_arr: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    slip_arr: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    pore_arr: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    notes: str = ""
    schema_version: str = CURRENT_SCHEMA_VERSION
    created_at: str = ""
    app_version: str = APP_VERSION
    # Schema v2.0.0 extensions
    wall_mode: WallSystemMode = WallSystemMode.CANTILEVER
    shell_geom: CurvedShellGeometry = field(default_factory=CurvedShellGeometry)
    pier_pile_geom: PierAndPileGeometry = field(default_factory=PierAndPileGeometry)
    strut_sys: StrutSupportSystem = field(default_factory=StrutSupportSystem)
    arch_spec: ArchitecturalWallSpec = field(default_factory=ArchitecturalWallSpec)
    surcharge_params: AdjacentSurchargeParams = field(default_factory=AdjacentSurchargeParams)
    num_bays: int = 3
    regional_standard: RegionalStandard = RegionalStandard.STANDARD
    unit_system: UnitSystem = UnitSystem.SI
    theme_mode: ThemeMode = ThemeMode.DARK
    terrain_metadata: Dict[str, Any] = field(default_factory=dict)
    uq_results: Dict[str, Any] = field(default_factory=dict)
    fea_cache: Dict[str, np.ndarray] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)


def _json_safe(obj: Any) -> Any:
    """Converts numpy arrays, scalars, and Enums recursively for JSON serialization."""
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if hasattr(obj, "value"):
        return obj.value
    return obj


def _migrate_schema_dict(data: Dict[str, Any], from_version: str) -> Dict[str, Any]:
    """
    Handles schema migrations across v0.1 -> v1.0 -> v2.0 to guarantee
    full backward compatibility for legacy `.o3d` sessions.
    """
    migrated = dict(data)

    # v0.1 -> v1.0 migrations
    geom_data = migrated.setdefault("geometry", {})
    geom_data.setdefault("shear_key_depth", 0.0)
    geom_data.setdefault("shear_key_width", 0.0)
    geom_data.setdefault("wall_length", 5.0)

    soil_data = migrated.setdefault("soil", {})
    if "subgrade_friction_angle" in soil_data:
        soil_data.setdefault("foundation_friction_angle", soil_data.pop("subgrade_friction_angle"))
    if "subgrade_cohesion" in soil_data:
        soil_data.setdefault("foundation_cohesion", soil_data.pop("subgrade_cohesion"))
    soil_data.setdefault("foundation_friction_angle", soil_data.get("friction_angle", 30.0))
    soil_data.setdefault("foundation_cohesion", 25.0)
    soil_data.setdefault("foundation_unit_weight", 19.0)
    soil_data.setdefault("allowable_bearing_capacity", 300.0)

    seismic_data = migrated.setdefault("seismic", {})
    if "vertical_pga_ratio" in seismic_data:
        v_ratio = seismic_data.pop("vertical_pga_ratio")
        seismic_data.setdefault("vertical_pga", round(seismic_data.get("horizontal_pga", 0.25) * v_ratio, 4))
    seismic_data.setdefault("vertical_pga", 0.125)
    seismic_data.setdefault("pore_pressure_ratio_ru", 0.0)
    seismic_data.setdefault("backfill_slope", 0.0)

    # v1.0 -> v2.0 migrations
    migrated.setdefault("wall_mode", WallSystemMode.CANTILEVER.value)
    migrated.setdefault("shell_geom", CurvedShellGeometry().to_dict())
    migrated.setdefault("pier_pile_geom", PierAndPileGeometry().to_dict())
    migrated.setdefault("strut_sys", StrutSupportSystem().to_dict())
    migrated.setdefault("arch_spec", ArchitecturalWallSpec().to_dict())
    sur_default = asdict(AdjacentSurchargeParams())
    sur_default["load_type"] = AdjacentSurchargeParams().load_type.value
    migrated.setdefault("surcharge_params", sur_default)
    migrated.setdefault("num_bays", 3)
    migrated.setdefault("regional_standard", RegionalStandard.STANDARD.value)
    migrated.setdefault("unit_system", UnitSystem.SI.value)
    migrated.setdefault("theme_mode", ThemeMode.DARK.value)
    migrated.setdefault("terrain_metadata", {})
    migrated.setdefault("uq_results", {})
    migrated.setdefault("provenance", {})

    migrated["schema_version"] = CURRENT_SCHEMA_VERSION
    return migrated


def save_project_session(
    filepath: str,
    geom: RetainingWallGeometry,
    soil: SoilProperties,
    seismic: SeismicParams,
    results: AnalysisResults,
    time_arr: Optional[np.ndarray] = None,
    accel_arr: Optional[np.ndarray] = None,
    slip_arr: Optional[np.ndarray] = None,
    pore_arr: Optional[np.ndarray] = None,
    notes: str = "",
    schema_version: str = CURRENT_SCHEMA_VERSION,
    *,
    wall_mode: WallSystemMode = WallSystemMode.CANTILEVER,
    shell_geom: Optional[CurvedShellGeometry] = None,
    pier_pile_geom: Optional[PierAndPileGeometry] = None,
    strut_sys: Optional[StrutSupportSystem] = None,
    arch_spec: Optional[ArchitecturalWallSpec] = None,
    surcharge_params: Optional[AdjacentSurchargeParams] = None,
    num_bays: int = 3,
    regional_standard: RegionalStandard = RegionalStandard.STANDARD,
    unit_system: UnitSystem = UnitSystem.SI,
    theme_mode: ThemeMode = ThemeMode.DARK,
    terrain_metadata: Optional[Dict[str, Any]] = None,
    uq_results: Optional[Dict[str, Any]] = None,
    fea_cache: Optional[Dict[str, np.ndarray]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Saves a complete v2.0 project session into a single `.o3d` package archive
    containing `project.json` schema and `simulation.h5` dynamic + FEA caches.
    """
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

    s_geom = shell_geom or CurvedShellGeometry()
    p_geom = pier_pile_geom or PierAndPileGeometry()
    st_sys = strut_sys or StrutSupportSystem()
    a_spec = arch_spec or ArchitecturalWallSpec()
    sur_p = surcharge_params or AdjacentSurchargeParams()
    sur_dict = asdict(sur_p)
    sur_dict["load_type"] = sur_p.load_type.value

    manifest: Dict[str, Any] = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "schema_version": schema_version,
        "created_at": datetime.now().isoformat(),
        "notes": notes,
        "geometry": asdict(geom),
        "soil": asdict(soil),
        "seismic": asdict(seismic),
        "results": asdict(results),
    }
    if not str(schema_version).startswith(("0.", "1.")):
        manifest.update({
            "wall_mode": WallSystemMode(wall_mode).value,
            "shell_geom": s_geom.to_dict(),
            "pier_pile_geom": p_geom.to_dict(),
            "strut_sys": st_sys.to_dict(),
            "arch_spec": a_spec.to_dict(),
            "surcharge_params": sur_dict,
            "num_bays": int(num_bays),
            "regional_standard": RegionalStandard(regional_standard).value,
            "unit_system": UnitSystem(unit_system).value,
            "theme_mode": ThemeMode(theme_mode).value,
            "terrain_metadata": _json_safe(terrain_metadata or {}),
            "uq_results": _json_safe(uq_results or {}),
            "provenance": _json_safe(provenance or {}),
        })

    with tempfile.TemporaryDirectory() as tmp_dir:
        json_path = os.path.join(tmp_dir, "project.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        h5_path = os.path.join(tmp_dir, "simulation.h5")
        with h5py.File(h5_path, "w") as hf:
            hf.attrs["schema_version"] = schema_version
            t_data = time_arr if time_arr is not None else np.array([], dtype=np.float64)
            a_data = accel_arr if accel_arr is not None else np.array([], dtype=np.float64)
            s_data = slip_arr if slip_arr is not None else np.array([], dtype=np.float64)
            p_data = pore_arr if pore_arr is not None else np.array([], dtype=np.float64)

            hf.create_dataset("time", data=t_data, compression="gzip")
            hf.create_dataset("acceleration", data=a_data, compression="gzip")
            hf.create_dataset("displacement", data=s_data, compression="gzip")
            hf.create_dataset("pore_pressure", data=p_data, compression="gzip")

            if fea_cache:
                grp = hf.create_group("fea_cache")
                for key, arr in fea_cache.items():
                    np_arr = np.asarray(arr, dtype=np.float64)
                    if np_arr.size > 0:
                        grp.create_dataset(str(key), data=np_arr, compression="gzip")
                    else:
                        grp.create_dataset(str(key), data=np_arr)

        with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(json_path, arcname="project.json")
            zf.write(h5_path, arcname="simulation.h5")

    return filepath


def load_project_session(filepath: str) -> ProjectSession:
    """
    Loads and validates a complete `.o3d` project session package (v0.1, v1.0, or v2.0).
    Raises `FileNotFoundError` if file is missing, or `CorruptProjectError` if invalid.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Project session file not found: {filepath}")

    if not zipfile.is_zipfile(filepath):
        raise CorruptProjectError(f"Corrupt or invalid .o3d project file: {filepath}")

    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            if "project.json" not in zf.namelist():
                raise CorruptProjectError(f"Missing project.json in .o3d package: {filepath}")

            with zf.open("project.json") as jf:
                raw_json = json.load(jf)

            file_schema = raw_json.get("schema_version", "0.1.0")
            data = _migrate_schema_dict(raw_json, from_version=file_schema)

            geom = RetainingWallGeometry(**data["geometry"])
            soil = SoilProperties(**data["soil"])
            seismic = SeismicParams(**data["seismic"])
            results = AnalysisResults(**data["results"])

            wall_mode = WallSystemMode(data["wall_mode"])
            shell_geom = CurvedShellGeometry.from_dict(data["shell_geom"])
            pier_pile_geom = PierAndPileGeometry.from_dict(data["pier_pile_geom"])
            strut_sys = StrutSupportSystem.from_dict(data["strut_sys"])
            arch_spec = ArchitecturalWallSpec.from_dict(data["arch_spec"])

            sur_raw = dict(data["surcharge_params"])
            sur_raw["load_type"] = SurchargeLoadType(sur_raw.get("load_type", SurchargeLoadType.NONE))
            surcharge_params = AdjacentSurchargeParams(**sur_raw)

            regional_standard = RegionalStandard(data["regional_standard"])
            unit_system = UnitSystem(data["unit_system"])
            theme_mode = ThemeMode(data["theme_mode"])

            time_arr = np.array([], dtype=np.float64)
            accel_arr = np.array([], dtype=np.float64)
            slip_arr = np.array([], dtype=np.float64)
            pore_arr = np.array([], dtype=np.float64)
            fea_cache: Dict[str, np.ndarray] = {}

            if "simulation.h5" in zf.namelist():
                with tempfile.TemporaryDirectory() as tmp_dir:
                    extracted_h5 = zf.extract("simulation.h5", path=tmp_dir)
                    with h5py.File(extracted_h5, "r") as hf:
                        if "time" in hf:
                            time_arr = np.array(hf["time"][:], dtype=np.float64)
                        if "acceleration" in hf:
                            accel_arr = np.array(hf["acceleration"][:], dtype=np.float64)
                        if "displacement" in hf:
                            slip_arr = np.array(hf["displacement"][:], dtype=np.float64)
                        if "pore_pressure" in hf:
                            pore_arr = np.array(hf["pore_pressure"][:], dtype=np.float64)
                        if "fea_cache" in hf:
                            for key in hf["fea_cache"].keys():
                                fea_cache[str(key)] = np.array(hf["fea_cache"][key][:], dtype=np.float64)

            return ProjectSession(
                geom=geom,
                soil=soil,
                seismic=seismic,
                results=results,
                time_arr=time_arr,
                accel_arr=accel_arr,
                slip_arr=slip_arr,
                pore_arr=pore_arr,
                notes=data.get("notes", ""),
                schema_version=CURRENT_SCHEMA_VERSION,
                created_at=data.get("created_at", ""),
                app_version=data.get("app_version", APP_VERSION),
                wall_mode=wall_mode,
                shell_geom=shell_geom,
                pier_pile_geom=pier_pile_geom,
                strut_sys=strut_sys,
                arch_spec=arch_spec,
                surcharge_params=surcharge_params,
                num_bays=int(data.get("num_bays", 3)),
                regional_standard=regional_standard,
                unit_system=unit_system,
                theme_mode=theme_mode,
                terrain_metadata=dict(data.get("terrain_metadata", {})),
                uq_results=dict(data.get("uq_results", {})),
                fea_cache=fea_cache,
                provenance=dict(data.get("provenance", {})),
            )

    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, TypeError, ValueError) as err:
        raise CorruptProjectError(f"Corrupt or invalid .o3d project file content: {err}") from err
