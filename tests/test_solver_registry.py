"""
Tests for Phase 1 Solver Capability & Provenance Registry.
"""

from orang3d.physics import (
    KRATOS_AVAILABLE,
    OPENSEES_AVAILABLE,
    SolverCapability,
    SolverProvenance,
    SolverTier,
    build_provenance,
    detect_solver_capabilities,
    get_available_solvers,
)


def test_detect_solver_capabilities_returns_all_tiers():
    caps = detect_solver_capabilities()

    assert set(caps.keys()) == set(SolverTier)
    for tier, cap in caps.items():
        assert isinstance(cap, SolverCapability)
        assert cap.tier == tier
        assert isinstance(cap.to_dict(), dict)
        assert cap.to_dict()["tier"] == tier.value


def test_analytical_and_pinn_always_available():
    caps = detect_solver_capabilities()
    assert caps[SolverTier.L0_ANALYTICAL].available is True
    assert caps[SolverTier.L0_PINN].available is True
    assert caps[SolverTier.L1_OPENSEES_2D_BNWF].available is OPENSEES_AVAILABLE
    assert caps[SolverTier.L2_KRATOS_FEA].available is KRATOS_AVAILABLE
    assert caps[SolverTier.L2_OPENSEES_3D_FEA].available is OPENSEES_AVAILABLE
    assert caps[SolverTier.L2_KRATOS_FEA].is_continuum_fea is True

    available_tiers = {cap.tier for cap in get_available_solvers()}
    assert SolverTier.L0_ANALYTICAL in available_tiers
    assert SolverTier.L0_PINN in available_tiers


def test_build_provenance_populates_metadata():
    prov = build_provenance(
        SolverTier.L0_PINN,
        element_types=["MLP_64_64"],
        constitutive_model="Equilibrium-Projected Surrogate",
        damping_model="Rayleigh 5%",
        runtime_ms=0.18,
        converged=True,
        random_seed=42,
        extra={"equilibrium_imbalance_pct": 0.0},
    )

    assert isinstance(prov, SolverProvenance)
    assert prov.tier == SolverTier.L0_PINN
    assert prov.is_surrogate is True
    assert prov.random_seed == 42
    assert prov.runtime_ms == 0.18

    payload = prov.to_dict()
    assert payload["tier"] == "l0_pinn"
    assert payload["element_types"] == ["MLP_64_64"]
    assert payload["extra"]["equilibrium_imbalance_pct"] == 0.0

