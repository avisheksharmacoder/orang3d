"""
Project Session Serialization & Migration Engine for orang3D (Phase 9).
Manages saving and loading complete project sessions as single compressed .o3d packages
(JSON metadata and schemas + HDF5 simulation caches) with schema backward-compatibility.
"""

import os
import json
import zipfile
import tempfile
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict, Any
import numpy as np
import h5py

from ..models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
    AnalysisResults,
)
from ..config import APP_NAME, APP_VERSION


CURRENT_SCHEMA_VERSION = "1.0.0"


class CorruptProjectError(Exception):
    """Raised when an .o3d file is truncated, unreadable, or missing required manifest schemas."""
    pass


@dataclass
class ProjectSession:
    """Complete serialized representation of an orang3D project session."""
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


def _migrate_schema_dict(data: Dict[str, Any], from_version: str) -> Dict[str, Any]:
    """
    Handles schema migrations across versions to guarantee backward compatibility.
    """
    migrated = dict(data)
    # Add default migration handlers if fields were added in newer versions
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
) -> str:
    """
    Saves a complete project session into a single .o3d package archive
    containing project.json schema and simulation.h5 dynamic caches.
    """
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

    manifest = {
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

        # Bundle into single .o3d archive
        with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(json_path, arcname="project.json")
            zf.write(h5_path, arcname="simulation.h5")

    return filepath


def load_project_session(filepath: str) -> ProjectSession:
    """
    Loads and validates a complete .o3d project session package.
    Raises FileNotFoundError if file is missing, or CorruptProjectError if file is invalid.
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

            time_arr = np.array([], dtype=np.float64)
            accel_arr = np.array([], dtype=np.float64)
            slip_arr = np.array([], dtype=np.float64)
            pore_arr = np.array([], dtype=np.float64)

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
            )

    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, TypeError, ValueError) as err:
        raise CorruptProjectError(f"Corrupt or invalid .o3d project file content: {err}") from err
