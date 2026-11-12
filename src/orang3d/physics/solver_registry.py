"""
Solver Capability & Provenance Registry for orang3D.
Tracks available analytical, surrogate, 2D BNWF, and continuum FEA backends
and records reproducible metadata for every engineering simulation run.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from importlib.metadata import PackageNotFoundError, version as pkg_version
from typing import Any, Dict, List, Optional

from .kratos_solver import KRATOS_AVAILABLE
from .opensees_assembler import OPENSEES_AVAILABLE
from .surrogate_engine import TORCH_AVAILABLE


class SolverTier(str, Enum):
    """Supported physics fidelity tiers in orang3D."""

    L0_ANALYTICAL = "l0_analytical"
    L0_PINN = "l0_pinn"
    L1_OPENSEES_2D_BNWF = "l1_opensees_2d_bnwf"
    L2_OPENSEES_3D_FEA = "l2_opensees_3d_fea"
    L2_KRATOS_FEA = "l2_kratos_fea"


@dataclass(frozen=True)
class SolverCapability:
    """Availability and engineering scope metadata for a solver tier."""

    tier: SolverTier
    name: str
    available: bool
    dimensionality: str
    platform_support: str
    backend_version: str
    is_continuum_fea: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "name": self.name,
            "available": self.available,
            "dimensionality": self.dimensionality,
            "platform_support": self.platform_support,
            "backend_version": self.backend_version,
            "is_continuum_fea": self.is_continuum_fea,
            "notes": self.notes,
        }


@dataclass
class SolverProvenance:
    """Reproducible execution record attached to a simulation output."""

    tier: SolverTier
    solver_name: str
    backend_version: str
    dimensionality: str
    element_types: List[str] = field(default_factory=list)
    constitutive_model: str = "Analytical Limit Equilibrium"
    damping_model: str = "None"
    runtime_ms: float = 0.0
    converged: bool = True
    is_surrogate: bool = False
    random_seed: Optional[int] = None
    platform_os: str = field(default_factory=platform.system)
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "solver_name": self.solver_name,
            "backend_version": self.backend_version,
            "dimensionality": self.dimensionality,
            "element_types": list(self.element_types),
            "constitutive_model": self.constitutive_model,
            "damping_model": self.damping_model,
            "runtime_ms": self.runtime_ms,
            "converged": self.converged,
            "is_surrogate": self.is_surrogate,
            "random_seed": self.random_seed,
            "platform_os": self.platform_os,
            "timestamp_utc": self.timestamp_utc,
            "extra": dict(self.extra),
        }


def _safe_pkg_version(package_name: str, fallback: str = "unknown") -> str:
    """Safely queries an installed Python distribution version."""
    try:
        return pkg_version(package_name)
    except PackageNotFoundError:
        return fallback


def detect_solver_capabilities() -> Dict[SolverTier, SolverCapability]:
    """
    Detects installed simulation backends and reports their current fidelity scope.
    """
    numpy_ver = _safe_pkg_version("numpy")
    opensees_ver = _safe_pkg_version("openseespy") if OPENSEES_AVAILABLE else "not_installed"
    kratos_ver = _safe_pkg_version("KratosMultiphysics") if KRATOS_AVAILABLE else "not_installed"
    pinn_backend = (
        f"PyTorch {_safe_pkg_version('torch')} + NumPy {numpy_ver}"
        if TORCH_AVAILABLE
        else f"Pure NumPy {numpy_ver}"
    )

    return {
        SolverTier.L0_ANALYTICAL: SolverCapability(
            tier=SolverTier.L0_ANALYTICAL,
            name="Mononobe-Okabe & Limit Equilibrium",
            available=True,
            dimensionality="2D Unit-Width Analytical",
            platform_support="Linux, Windows, macOS",
            backend_version=f"NumPy {numpy_ver}",
            is_continuum_fea=False,
            notes="Sub-millisecond Rankine, Coulomb, Mononobe-Okabe, Seed-Whitman, arching, and Newmark slip.",
        ),
        SolverTier.L0_PINN: SolverCapability(
            tier=SolverTier.L0_PINN,
            name="PINN Fast Surrogate",
            available=True,
            dimensionality="2D Parametric Surrogate",
            platform_support="Linux, Windows, macOS",
            backend_version=pinn_backend,
            is_continuum_fea=False,
            notes="Equilibrium-projected MLP surrogate (< 1 ms) with pure NumPy fallback when PyTorch is absent.",
        ),
        SolverTier.L1_OPENSEES_2D_BNWF: SolverCapability(
            tier=SolverTier.L1_OPENSEES_2D_BNWF,
            name="OpenSeesPy 2D BNWF",
            available=OPENSEES_AVAILABLE,
            dimensionality="2D Frame + Winkler Springs",
            platform_support="Linux, Windows",
            backend_version=opensees_ver,
            is_continuum_fea=False,
            notes="Beam on Nonlinear Winkler Foundation (PySimple1/TzSimple1/QzSimple1) with raking struts.",
        ),
        SolverTier.L2_OPENSEES_3D_FEA: SolverCapability(
            tier=SolverTier.L2_OPENSEES_3D_FEA,
            name="OpenSeesPy 3D Continuum SSI",
            available=OPENSEES_AVAILABLE,
            dimensionality="3D Continuum Solid + Interface",
            platform_support="Linux, Windows",
            backend_version=opensees_ver,
            is_continuum_fea=True,
            notes="OpenSeesPy 3D stdBrick/brickUP continuum soil-wall-foundation FEA with zeroLength interfaces & Lysmer dashpots.",
        ),
        SolverTier.L2_KRATOS_FEA: SolverCapability(
            tier=SolverTier.L2_KRATOS_FEA,
            name="KratosMultiphysics GeoMechanics",
            available=KRATOS_AVAILABLE,
            dimensionality="2D U-Pw Plane-Strain Continuum FEA",
            platform_support="Linux x86_64",
            backend_version=kratos_ver,
            is_continuum_fea=True,
            notes="Kratos GeoMechanics UPwSmallStrainElement2D4N + UPwLysmerAbsorbingCondition2D2N solved via NewmarkDynamicUPwScheme.",
        ),
    }


def get_available_solvers() -> List[SolverCapability]:
    """Returns only the solver tiers currently runnable on this host."""
    return [cap for cap in detect_solver_capabilities().values() if cap.available]


def build_provenance(
    tier: SolverTier,
    *,
    element_types: Optional[List[str]] = None,
    constitutive_model: str = "Analytical Limit Equilibrium",
    damping_model: str = "None",
    runtime_ms: float = 0.0,
    converged: bool = True,
    is_surrogate: bool = False,
    random_seed: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> SolverProvenance:
    """Creates a populated SolverProvenance record using detected backend metadata."""
    caps = detect_solver_capabilities()
    cap = caps[tier]
    return SolverProvenance(
        tier=tier,
        solver_name=cap.name,
        backend_version=cap.backend_version,
        dimensionality=cap.dimensionality,
        element_types=list(element_types or []),
        constitutive_model=constitutive_model,
        damping_model=damping_model,
        runtime_ms=float(runtime_ms),
        converged=converged,
        is_surrogate=is_surrogate or (tier == SolverTier.L0_PINN),
        random_seed=random_seed,
        extra=dict(extra or {}),
    )

