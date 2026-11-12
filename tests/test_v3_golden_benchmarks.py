"""
Phase 10.2(1): 3D & Nonlinear Golden Benchmark Suite.

Validates orang3D solvers against closed-form analytical solutions and
published geotechnical / structural reference benchmarks:
  1. 2D/3D Geostatic K0 & Static Active Earth Pressure (< 3% error vs Rankine/Coulomb)
  2. 3D Corner & Finite-Length Effect Benchmark (rigid return boundary vs plane strain)
  3. Dynamic Centrifuge / Shake-Table Reference Trends (Seed-Whitman Delta P_ae,
     upward thrust centroid shift, dynamic phase lag, and permanent displacement)
  4. Curved Shell Arching Comparison (shell_arching.py eta_arch vs 3D continuum FEA)
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from orang3d.models.wall_params import (
    RetainingWallGeometry,
    SoilProperties,
    SeismicParams,
)
from orang3d.models.advanced_wall_params import (
    CurvedShellGeometry,
    MultiStrutPiledWallModel,
    PierAndPileGeometry,
    StrutSupportSystem,
    WallSystemMode,
)
from orang3d.physics import (
    KRATOS_AVAILABLE,
    OPENSEES_AVAILABLE,
    ConstitutiveModelType,
    OpenSees3DContinuumSolver,
)
from orang3d.physics.kratos_solver import KratosRetainingWallSolver
from orang3d.physics.mononobe_okabe import (
    compute_coulomb_earth_pressures,
    compute_lateral_thrusts,
    compute_mononobe_okabe,
    compute_rankine_earth_pressures,
)
from orang3d.physics.shell_arching import compute_shell_arching_partition
from orang3d.physics.stability import evaluate_wall_stability
from orang3d.signals.synthetic import (
    compute_newmark_sliding_displacement,
    compute_yield_acceleration_ky,
    generate_ricker_wavelet,
)

if OPENSEES_AVAILABLE:
    import openseespy.opensees as ops


def _benchmark_models():
    geom = RetainingWallGeometry(
        stem_height=4.5,
        stem_thickness_base=0.5,
        stem_thickness_top=0.35,
        toe_length=0.8,
        heel_length=1.9,
        footing_thickness=0.5,
        wall_length=8.0,
    )
    soil = SoilProperties(
        unit_weight=18.5,
        saturated_unit_weight=20.0,
        friction_angle=32.0,
        wall_friction_angle=20.0,
        cohesion=0.0,
        elastic_modulus=35000.0,
        poissons_ratio=0.30,
    )
    seismic = SeismicParams(
        horizontal_pga=0.25,
        vertical_pga=0.0,
        water_table_depth=10.0,
    )
    return geom, soil, seismic


def _run_3d_active_wall_column(
    solver: OpenSees3DContinuumSolver,
    interface_friction_deg: float,
    delta_x_m: float,
    nx: int = 8,
    ny: int = 6,
    nz: int = 1,
) -> dict:
    """
    Runs a conformal 3D PDMY02 soil column behind a rigid vertical wall on a
    smooth base roller (fx free on y=0 except far-field x=lx), integrating the
    full [0, H] wall normal reaction for exact Rankine/Coulomb comparison.
    """
    soil = solver.soil
    gamma = float(soil.unit_weight)
    h_wall = float(solver.geom.total_height)
    lx = 2.0 * h_wall
    lz = 1.0

    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 3)
    solver._register_soil_material(1, ConstitutiveModelType.PDMY02, cohesion_override=0.05)

    xs = np.linspace(0.0, lx, nx + 1)
    ys = np.linspace(0.0, h_wall, ny + 1)
    zs = np.linspace(0.0, lz, nz + 1)
    dy_vals, dz_vals = np.diff(ys), np.diff(zs)

    def nid(ix: int, iy: int, iz: int) -> int:
        return ix * (ny + 1) * (nz + 1) + iy * (nz + 1) + iz + 1

    for ix, x in enumerate(xs):
        for iy, y in enumerate(ys):
            for iz, z in enumerate(zs):
                tag = nid(ix, iy, iz)
                ops.node(tag, float(x), float(y), float(z))
                fx = 1 if ix == nx else 0
                fy = 1 if iy == 0 else 0
                fz = 1
                ops.fix(tag, fx, fy, fz)

    eid = 1
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                ops.element(
                    "stdBrick",
                    eid,
                    nid(ix, iy, iz),
                    nid(ix + 1, iy, iz),
                    nid(ix + 1, iy + 1, iz),
                    nid(ix, iy + 1, iz),
                    nid(ix, iy, iz + 1),
                    nid(ix + 1, iy, iz + 1),
                    nid(ix + 1, iy + 1, iz + 1),
                    nid(ix, iy + 1, iz + 1),
                    1,
                    0.0,
                    -gamma,
                    0.0,
                )
                eid += 1

    k_act = 1.0e8
    ops.uniaxialMaterial("Elastic", 2, k_act)
    ops.uniaxialMaterial("ENT", 3, 1.0e6)
    ops.uniaxialMaterial("Elastic", 4, 1.0)
    ops.uniaxialMaterial("Parallel", 5, 3, 4)

    mu = math.tan(math.radians(max(0.0, interface_friction_deg)))
    links = []
    act_nodes = []
    mat_id = 10

    for iy in range(ny + 1):
        dy_t = 0.5 * ((dy_vals[iy - 1] if iy > 0 else 0.0) + (dy_vals[iy] if iy < ny else 0.0))
        sig_est = max(2.0, 0.30 * gamma * (h_wall - ys[iy]))
        for iz in range(nz + 1):
            dz_t = 0.5 * ((dz_vals[iz - 1] if iz > 0 else 0.0) + (dz_vals[iz] if iz < nz else 0.0))
            area = max(1e-3, float(dy_t * dz_t))
            t = nid(0, iy, iz)
            d_free, d_fix = 10000 + t, 20000 + t
            ops.node(d_free, 0.0, float(ys[iy]), float(zs[iz]))
            ops.fix(d_free, 0, 1, 1)
            ops.node(d_fix, 0.0, float(ys[iy]), float(zs[iz]))
            ops.fix(d_fix, 1, 1, 1)
            act_nodes.append(d_free)
            ops.element("zeroLength", eid, d_fix, d_free, "-mat", 2, "-dir", 1)
            eid += 1

            if mu <= 1e-6:
                ops.uniaxialMaterial("Elastic", mat_id, 1.0)
            else:
                fy_s = max(0.05, sig_est * area * mu)
                kt_s = 1.0e4 * area
                ops.uniaxialMaterial("ElasticPP", mat_id, kt_s, fy_s / kt_s)
            ops.element("zeroLength", eid, d_free, t, "-mat", 5, mat_id, "-dir", 1, 2)
            links.append(eid)
            mat_id += 1
            eid += 1

    # Stage 0: Elastic K0 gravity turn-on
    ops.updateMaterialStage("-material", 1, "-stage", 0)
    ops.timeSeries("Constant", 1)
    ops.pattern("Plain", 1, 1)
    ops.constraints("Transformation")
    ops.test("NormDispIncr", 1e-4, 30, 0)
    ops.algorithm("Newton")
    ops.numberer("RCM")
    ops.system("BandGeneral")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")
    ok0 = ops.analyze(1)
    p_k0 = sum(max(0.0, float(ops.eleResponse(e, "force")[0])) for e in links) / lz

    # Stage 1: Elastoplastic PDMY02 settling + outward wall translation to active state
    ops.updateMaterialStage("-material", 1, "-stage", 1)
    ok1 = ops.analyze(1)
    ops.loadConst("-time", 0.0)
    ops.timeSeries("Linear", 2)
    ops.pattern("Plain", 2, 2)
    for d_free in act_nodes:
        ops.load(d_free, k_act * delta_x_m, 0.0, 0.0)
    ops.integrator("LoadControl", 0.05)
    ops.algorithm("KrylovNewton")
    ok2 = 0
    for _ in range(20):
        step_ok = ops.analyze(1)
        if step_ok != 0:
            ok2 = step_ok
            break
    p_active = sum(max(0.0, float(ops.eleResponse(e, "force")[0])) for e in links) / lz

    return {
        "converged": (ok0 == 0 and ok1 == 0 and ok2 == 0),
        "p_k0_kn_m": p_k0,
        "p_active_kn_m": p_active,
    }


# ==============================================================================
# BENCHMARK 1: 2D/3D Geostatic K0 & Static Active Earth Pressure (< 3% Error)
# ==============================================================================
@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_golden_1_geostatic_and_static_active_earth_pressure():
    """
    Validates 3D OpenSeesPy and 2D Kratos continuum FEA against closed-form
    geostatic K0 and Rankine (delta=0) / Coulomb (delta=20 deg) active states.
    Requires < 1% geostatic error and < 3% static active thrust error.
    """
    geom, soil, seismic = _benchmark_models()
    solver = OpenSees3DContinuumSolver(geom, soil, seismic)

    # 1A. 3D Geostatic K0 Patch Test
    patch = solver.run_geostatic_patch_test(nx=3, ny=4, nz=2, use_k0_poisson=True)
    assert patch["converged"] is True
    assert patch["max_sigma_yy_rel_error"] < 0.01
    assert patch["max_sigma_xx_rel_error"] < 0.01
    assert patch["max_lateral_drift_m"] < 1e-6

    # 1B. K0 thrust & Active Smooth Wall (< 3% vs Rankine) & Rough Wall (< 3% vs Coulomb)
    h_wall = geom.total_height
    k0_theory = soil.poissons_ratio / (1.0 - soil.poissons_ratio)
    p_k0_theory = 0.5 * soil.unit_weight * (h_wall ** 2) * k0_theory

    ka_rankine, _ = compute_rankine_earth_pressures(soil.friction_angle)
    p_rankine = 0.5 * soil.unit_weight * (h_wall ** 2) * ka_rankine

    ka_coulomb, _ = compute_coulomb_earth_pressures(soil.friction_angle, soil.wall_friction_angle)
    p_coulomb = 0.5 * soil.unit_weight * (h_wall ** 2) * ka_coulomb

    res_smooth = _run_3d_active_wall_column(solver, interface_friction_deg=0.0, delta_x_m=-0.010)
    res_rough = _run_3d_active_wall_column(
        solver, interface_friction_deg=soil.wall_friction_angle, delta_x_m=-0.013
    )

    assert res_smooth["converged"] is True
    assert res_rough["converged"] is True

    # Geostatic total thrust matches K0 solution within 1%
    k0_err = abs(res_smooth["p_k0_kn_m"] - p_k0_theory) / p_k0_theory
    assert k0_err < 0.01, f"3D Geostatic K0 thrust error {k0_err:.4f} exceeded 1%"

    # Active earth pressure thrust within < 3% of Rankine (smooth) and Coulomb (rough)
    smooth_err = abs(res_smooth["p_active_kn_m"] - p_rankine) / p_rankine
    rough_err = abs(res_rough["p_active_kn_m"] - p_coulomb) / p_coulomb
    assert smooth_err < 0.03, (
        f"Smooth wall active thrust {res_smooth['p_active_kn_m']:.2f} vs "
        f"Rankine {p_rankine:.2f} (err={smooth_err*100:.2f}%)"
    )
    assert rough_err < 0.03, (
        f"Rough wall active thrust {res_rough['p_active_kn_m']:.2f} vs "
        f"Coulomb {p_coulomb:.2f} (err={rough_err*100:.2f}%)"
    )
    assert res_rough["p_active_kn_m"] < res_smooth["p_active_kn_m"]

    # 1C. Kratos 2D GeoMechanics static / low-inertia equilibrium verification
    if KRATOS_AVAILABLE:
        kratos_solver = KratosRetainingWallSolver(geom, soil, SeismicParams(horizontal_pga=0.0, water_table_depth=10.0))
        mp = kratos_solver.initialize_model()
        assert mp.NumberOfElements() > 0
        assert mp.NumberOfConditions() > 0
        static_step = kratos_solver.run_dynamic_step(t=0.01, dt=0.01, accel_g=0.0)
        assert static_step["status"] == "CONVERGED"
        assert static_step["base_shear_kn"] >= 0.0
        assert abs(static_step["stress_tensor"]["sigma_yy"]) > 0.0


# ==============================================================================
# BENCHMARK 2: 3D Corner & Finite-Length Restraint Effect
# ==============================================================================
@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_golden_2_3d_corner_and_finite_length_effect():
    """
    Verifies 3D corner restraint and finite wall length arching:
    a short retaining wall bounded by stiff return corners exhibits significantly
    lower midspan lateral earth pressure than a long unrestrained plane-strain wall.
    """
    geom, soil, seismic = _benchmark_models()
    solver = OpenSees3DContinuumSolver(geom, soil, seismic)

    study = solver.run_3d_corner_effect_study(short_length_m=3.5, long_length_m=18.0)

    assert study["short_midspan_pressure_kpa"] > 0.0
    assert study["long_midspan_pressure_kpa"] > 0.0
    assert study["short_midspan_pressure_kpa"] < study["long_midspan_pressure_kpa"]
    assert 0.20 < study["corner_reduction_ratio"] < 0.90
    assert study["short_corner_concentration"] > 0.0


# ==============================================================================
# BENCHMARK 3: Dynamic Centrifuge / Seed-Whitman & Newmark Trends
# ==============================================================================
@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_golden_3_dynamic_centrifuge_seed_whitman_and_displacement_trends():
    """
    Cross-validates 3D dynamic continuum FEA against Seed & Whitman (1970) /
    Kramer (1996) / Newmark (1965) centrifuge trends:
      1. Seismic incremental thrust Delta P_ae > 0 and scales with input PGA.
      2. Dynamic resultant height elevates above static baseline (~0.33H -> 0.55-0.75H).
      3. Response exhibits physical inertial/wave-propagation phase lag (t_resp >= t_pga).
      4. Both continuum crest displacement and Newmark permanent sliding increase with PGA.
    """
    geom, soil, _ = _benchmark_models()
    t = np.arange(0.0, 0.08, 0.01)
    pulse = np.array([0.0, 0.0, 0.08, 0.22, 0.30, 0.20, 0.05, -0.05])

    ax_low = 0.5 * pulse    # PGA = 0.15g
    ax_high = 1.0 * pulse   # PGA = 0.30g

    solver_low = OpenSees3DContinuumSolver(
        geom, soil, SeismicParams(horizontal_pga=0.15, water_table_depth=10.0)
    )
    res_low = solver_low.run_dynamic_seismic(
        t,
        ax_low,
        constitutive_model=ConstitutiveModelType.ELASTIC_ISOTROPIC,
        nx_backfill=4,
        ny_wall=3,
        nz_wall=2,
    )

    solver_high = OpenSees3DContinuumSolver(
        geom, soil, SeismicParams(horizontal_pga=0.30, water_table_depth=10.0)
    )
    res_high = solver_high.run_dynamic_seismic(
        t,
        ax_high,
        constitutive_model=ConstitutiveModelType.ELASTIC_ISOTROPIC,
        nx_backfill=4,
        ny_wall=3,
        nz_wall=2,
    )

    # 1. Dynamic incremental thrust Delta P_ae > 0 & upward centroid shift in 3D OpenSees
    p_static_0 = float(res_high.total_thrust_kn_m[0])
    peak_idx_low = 2 + int(np.argmax(res_low.total_thrust_kn_m[2:]))
    peak_idx_high = 2 + int(np.argmax(res_high.total_thrust_kn_m[2:]))
    delta_p_ae_low = float(res_low.total_thrust_kn_m[peak_idx_low] - res_low.total_thrust_kn_m[0])
    delta_p_ae_high = float(res_high.total_thrust_kn_m[peak_idx_high] - p_static_0)

    assert delta_p_ae_low > 0.0
    assert delta_p_ae_high > 0.0
    assert res_high.thrust_elevation_m[peak_idx_high] > res_high.thrust_elevation_m[0]

    # 2. Continuum crest displacement scales strictly with shaking intensity
    assert res_high.max_crest_disp_cm > res_low.max_crest_disp_cm > 0.0

    # 3. Kratos GeoMechanics Ricker dynamic SSI: Delta P_ae, PGA scaling & phase lag
    if KRATOS_AVAILABLE:
        t_kr, a_kr = generate_ricker_wavelet(
            pga_g=0.30, central_freq_hz=2.5, duration_sec=0.6, sampling_rate_hz=50.0
        )
        dt_kr = float(t_kr[1] - t_kr[0])
        t_pga = float(t_kr[int(np.argmax(np.abs(a_kr)))])

        k_low = KratosRetainingWallSolver(
            geom, soil, SeismicParams(horizontal_pga=0.15, water_table_depth=10.0)
        )
        k_low.initialize_model()
        shears_low, disps_low = [], []
        for ti, ai in zip(t_kr, 0.5 * a_kr):
            sr = k_low.run_dynamic_step(float(ti), dt_kr, float(ai))
            shears_low.append(sr["base_shear_kn"])
            disps_low.append(abs(sr["crest_displacement_m"]) * 100.0)

        k_high = KratosRetainingWallSolver(
            geom, soil, SeismicParams(horizontal_pga=0.30, water_table_depth=10.0)
        )
        k_high.initialize_model()
        shears_high, disps_high = [], []
        for ti, ai in zip(t_kr, a_kr):
            sr = k_high.run_dynamic_step(float(ti), dt_kr, float(ai))
            shears_high.append(sr["base_shear_kn"])
            disps_high.append(abs(sr["crest_displacement_m"]) * 100.0)

        assert max(shears_high) > max(shears_low) > shears_low[0]
        assert max(disps_high) > max(disps_low) > 0.0
        t_max_shear = float(t_kr[int(np.argmax(shears_high))])
        assert t_max_shear >= t_pga

    # 4. Compare Seed & Whitman / Mononobe-Okabe analytical trend against PGA
    kae_low, ka, _ = compute_mononobe_okabe(soil.friction_angle, soil.wall_friction_angle, 0.15, 0.0)
    kae_high, _, _ = compute_mononobe_okabe(soil.friction_angle, soil.wall_friction_angle, 0.30, 0.0)
    p_mo_low, h_mo_low, _, _ = compute_lateral_thrusts(
        geom.total_height, soil.unit_weight, soil.saturated_unit_weight, kae_low, ka, 10.0
    )
    p_mo_high, h_mo_high, _, _ = compute_lateral_thrusts(
        geom.total_height, soil.unit_weight, soil.saturated_unit_weight, kae_high, ka, 10.0
    )
    assert p_mo_high > p_mo_low
    assert h_mo_high > h_mo_low

    k_y = compute_yield_acceleration_ky(geom, soil)
    t_ric, a_ric_04 = generate_ricker_wavelet(pga_g=max(k_y + 0.15, 0.35), central_freq_hz=2.5, duration_sec=4.0)
    a_ric_07 = a_ric_04 * 1.75
    _, dn_mod = compute_newmark_sliding_displacement(t_ric, a_ric_04, yield_acceleration_ky=min(0.15, k_y * 0.5))
    _, dn_sev = compute_newmark_sliding_displacement(t_ric, a_ric_07, yield_acceleration_ky=min(0.15, k_y * 0.5))
    assert dn_sev > dn_mod > 0.0


# ==============================================================================
# BENCHMARK 4: Curved Shell Arching (Analytical eta_arch vs 3D Continuum FEA)
# ==============================================================================
@pytest.mark.skipif(not OPENSEES_AVAILABLE, reason="OpenSeesPy is not installed")
def test_golden_4_curved_shell_arching_vs_3d_continuum_fea():
    """
    Compares horizontal soil arching load partition eta_arch from shell_arching.py
    against the spatial bay pressure distribution from OpenSees 3D continuum FEA.
    """
    geom, soil, seismic = _benchmark_models()
    shell = CurvedShellGeometry(panel_height=geom.total_height, bay_span=6.0, radius=3.5)
    ms_model = MultiStrutPiledWallModel(
        shell=shell,
        pier_pile=PierAndPileGeometry(),
        struts=StrutSupportSystem(),
    )

    arch_res = compute_shell_arching_partition(shell, soil)

    # Exact analytical equilibrium conservation P_free == P_shell + P_pier
    assert arch_res.total_free_field_thrust == pytest.approx(
        arch_res.total_shell_thrust + arch_res.total_pier_thrust, rel=1e-6
    )
    assert 0.0 < arch_res.arching_ratio < 0.60

    # Parametric trend: narrower pier bay increases soil arching efficiency
    arch_narrow = compute_shell_arching_partition(
        CurvedShellGeometry(panel_height=geom.total_height, bay_span=3.5, radius=2.5), soil
    )
    assert arch_narrow.arching_ratio > arch_res.arching_ratio

    # 3D Continuum FEA bay pressure partition
    solver_fea = OpenSees3DContinuumSolver(
        geom,
        soil,
        seismic,
        wall_mode=WallSystemMode.MULTI_STRUT_CURVED_SHELL,
        multi_strut_model=ms_model,
    )
    fea_res = solver_fea.run_dynamic_seismic(
        np.array([0.0, 0.02, 0.04]),
        np.array([0.0, 0.08, 0.0]),
        constitutive_model=ConstitutiveModelType.ELASTIC_ISOTROPIC,
        nx_backfill=4,
        ny_wall=3,
        nz_wall=4,
        corner_restraint=True,
        z_buffer_m=0.0,
    )
    assert fea_res.status == "CONVERGED"

    coords = fea_res.backface_coords
    z_mid = 0.5 * (coords[:, 2].min() + coords[:, 2].max())
    z_span = max(0.5, float(coords[:, 2].max() - coords[:, 2].min()))
    mid_mask = np.abs(coords[:, 2] - z_mid) < 0.25 * z_span
    pier_mask = np.abs(coords[:, 2] - z_mid) > 0.35 * z_span

    bf_final = fea_res.backface_normal_stress_kpa[-1]
    sigma_mid_bay = float(np.mean(bf_final[mid_mask]))
    sigma_pier = float(np.mean(bf_final[pier_mask]))

    assert sigma_pier > sigma_mid_bay > 0.0
    eta_fea = 1.0 - (sigma_mid_bay / sigma_pier)
    assert eta_fea > 0.0
    assert abs(eta_fea - arch_res.arching_ratio) < 0.15
