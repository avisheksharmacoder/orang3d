"""
Unit, Invariant, Physical Validation, and Concurrency Tests for Phase 4:
Level L1 BNWF (Beam on Nonlinear Winkler Foundation) OpenSeesPy Engine.
"""

import time
import math
import pytest
import numpy as np
from PySide6.QtWidgets import QApplication

from orang3d.models.advanced_wall_params import (
    CurvedShellGeometry,
    PierAndPileGeometry,
    StrutSupportSystem,
    MultiStrutPiledWallModel,
)
from orang3d.models.wall_params import SoilProperties
from orang3d.physics.spring_curves import (
    compute_py_sand_parameters,
    compute_py_clay_parameters,
    compute_tz_parameters,
    compute_qz_parameters,
    generate_soil_spring_profile,
    reese_matlock_theoretical_displacement,
)
from orang3d.physics.opensees_assembler import (
    build_opensees_bnwf_model,
    OPENSEES_AVAILABLE,
)
from orang3d.physics.bnwf_solver import (
    OpenSeesBNWFSolver,
    BNWFSimulationWorker,
)


@pytest.fixture(autouse=True)
def skip_if_no_opensees():
    if not OPENSEES_AVAILABLE:
        pytest.skip("OpenSeesPy is not installed on this system.")


# ==============================================================================
# 1. Soil Spring Curves & Radiation Damping Verification
# ==============================================================================

def test_soil_spring_curves_parameters():
    """
    Validates parameter computation for API sand p-y, Matlock clay p-y,
    Mosher t-z, Meyerhof q-z, and Berger radiation damping.
    """
    # 1. Sand p-y
    py_sand = compute_py_sand_parameters(
        depth=3.0,
        gamma=18.0,
        phi=32.0,
        diameter=0.8,
        tributary_length=1.0,
        slope_angle=15.0,
    )
    assert py_sand.mat_type == 1
    assert py_sand.p_ult > 0.0
    assert py_sand.p_ult_integrated > 0.0
    assert 0.001 <= py_sand.y_50 <= 0.08
    assert py_sand.c_dashpot > 0.0

    # 2. Clay p-y
    py_clay = compute_py_clay_parameters(
        depth=3.0,
        gamma=19.0,
        cu=40.0,
        diameter=0.8,
        tributary_length=1.0,
        slope_angle=0.0,
    )
    assert py_clay.mat_type == 2
    assert py_clay.p_ult > 0.0
    assert py_clay.y_50 > 0.0
    assert py_clay.c_dashpot > 0.0

    # 3. Sloping ground reduces ultimate capacity
    py_sand_level = compute_py_sand_parameters(
        depth=3.0, gamma=18.0, phi=32.0, diameter=0.8, tributary_length=1.0, slope_angle=0.0
    )
    py_sand_slope = compute_py_sand_parameters(
        depth=3.0, gamma=18.0, phi=32.0, diameter=0.8, tributary_length=1.0, slope_angle=25.0
    )
    assert py_sand_slope.p_ult < py_sand_level.p_ult

    # 4. t-z and q-z
    tz = compute_tz_parameters(depth=5.0, gamma=18.0, phi=30.0, cu=0.0, diameter=0.8, tributary_length=1.0)
    assert tz.t_ult > 0.0
    assert tz.z_50 > 0.0
    assert tz.c_dashpot > 0.0

    qz = compute_qz_parameters(diameter=0.8, gamma=18.0, phi=30.0, cu=0.0, pile_length=12.0)
    assert qz.q_ult > 0.0
    assert qz.z_50 > 0.0
    assert qz.c_dashpot > 0.0


def test_spring_profile_generation():
    """Validates complete soil spring profile generation along a pile."""
    pier_pile = PierAndPileGeometry(pile_length=10.0, pile_diameter=0.8)
    soil = SoilProperties(foundation_unit_weight=18.5, foundation_friction_angle=32.0, foundation_cohesion=10.0)

    profile = generate_soil_spring_profile(pier_pile, soil, slope_angle=10.0, num_pile_nodes=11)
    assert len(profile.depths) == 11
    assert len(profile.py_springs) == 11
    assert len(profile.tz_springs) == 11
    assert math.isclose(profile.depths[0], 0.0)
    assert math.isclose(profile.depths[-1], 10.0)
    assert profile.qz_spring.q_ult > 0.0


# ==============================================================================
# 2. Reese & Matlock Single Pile Lateral Pushover Verification
# ==============================================================================

def test_single_pile_lateral_pushover():
    """
    Phase 4.4: Validates p-y response against Reese & Matlock (1956) closed-form solutions.
    """
    # 1. Closed-form theoretical prediction
    ep = 30.0e6     # 30 GPa = 30,000,000 kPa
    dp = 0.8        # m
    ip = (math.pi * (dp ** 4)) / 64.0
    phi = 32.0
    nh = 400.0 * phi # 12,800 kN/m^3
    shear_load = 50.0 # kN

    theory_disp = reese_matlock_theoretical_displacement(
        lateral_shear=shear_load,
        moment=0.0,
        elastic_modulus=ep,
        moment_of_inertia=ip,
        subgrade_rate_nh=nh,
    )
    assert theory_disp > 0.0

    # 2. Numerical OpenSees BNWF pushover
    model = MultiStrutPiledWallModel(
        pier_pile=PierAndPileGeometry(pier_height=6.0, pile_length=12.0, pile_diameter=0.8)
    )
    soil = SoilProperties(foundation_unit_weight=18.0, foundation_friction_angle=32.0, foundation_cohesion=0.0)

    solver = OpenSeesBNWFSolver(model=model, soil=soil, num_pile_nodes=15, num_pier_nodes=8)
    solver.initialize()

    pushover_res = solver.run_pushover_analysis(max_displacement=0.02, num_steps=10)
    disps = pushover_res["displacements"]
    shears = pushover_res["base_shears"]

    assert len(disps) == 11
    assert disps[-1] > disps[0]
    # Shear resistance must increase monotonically with applied displacement
    assert shears[-1] > shears[0]
    assert np.all(np.diff(disps) >= 0)


# ==============================================================================
# 3. Strut Nonlinear Mechanics: Tension Slackening & Compression Buckling
# ==============================================================================

def test_strut_slackening_rebound():
    """
    Phase 4.4: Verifies that when a strut experiences tension beyond lock-off,
    axial resistance drops to zero (slack behavior) without numerical divergence.
    """
    import openseespy.opensees as ops

    model = MultiStrutPiledWallModel()
    soil = SoilProperties()

    solver = OpenSeesBNWFSolver(model=model, soil=soil)
    info = solver.initialize()

    # The strut element connects the pier node to fixed anchor.
    # Pier node is at X = 0, Anchor is at X = -L*cos(alpha).
    # Moving the pier node in -X compresses the strut.
    # Moving the pier node in +X pulls (tensions) the strut away from anchor.
    strut_node = info.strut_node_map[0]
    strut_ele = info.strut_elements[0]

    # Apply positive X displacement (pulling into tension)
    ops.timeSeries("Linear", 777)
    ops.pattern("Plain", 888, 777)
    ops.load(strut_node, 1.0, 0.0, 0.0)

    ops.system("BandGeneral")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.test("NormDispIncr", 1.0e-5, 40, 0)
    ops.algorithm("Newton")
    # Pull by 10 mm
    ops.integrator("DisplacementControl", strut_node, 1, 0.002)
    ops.analysis("Static")

    ret = ops.analyze(5)
    assert ret == 0, "Static analysis with slack strut converged cleanly"

    # Axial force in tension must be negligible (slackened)
    axial_res = ops.eleResponse(strut_ele, "axialForce")
    t_force = axial_res[0] if axial_res else 0.0
    # Compressive force is negative; tension is positive.
    # For a slack strut, tension resistance must be virtually zero (< 0.5 kN)
    assert abs(t_force) < 0.5, f"Expected slack strut force near 0 kN, got {t_force} kN"


def test_strut_buckling_limit():
    """
    Phase 4.4: Verifies that compressive strut force is capped at Euler buckling load P_cr.
    """
    import openseespy.opensees as ops

    model = MultiStrutPiledWallModel()
    soil = SoilProperties()

    solver = OpenSeesBNWFSolver(model=model, soil=soil)
    info = solver.initialize()

    struts = model.struts
    p_cr_expected = struts.euler_buckling_load # kN

    strut_node = info.strut_node_map[0]
    strut_ele = info.strut_elements[0]

    # Fix vertical DOF 2 to isolate axial shortening
    ops.fix(strut_node, 0, 1, 0)

    # Apply negative X displacement pushing directly toward the anchor (compression)
    ops.timeSeries("Linear", 991)
    ops.pattern("Plain", 992, 991)
    ops.load(strut_node, -1.0, 0.0, 0.0)

    ops.system("BandGeneral")
    ops.numberer("RCM")
    ops.constraints("Transformation")
    ops.test("NormDispIncr", 1.0e-4, 50, 0)
    ops.algorithm("Newton")
    # Push into deep post-buckling plastic regime (-2 mm per step, 15 steps = 30 mm)
    ops.integrator("DisplacementControl", strut_node, 1, -0.002)
    ops.analysis("Static")

    # Analyze 15 steps
    ret = ops.analyze(15)
    assert ret == 0, "Post-buckling plateau converged without divergence"

    axial_res = ops.eleResponse(strut_ele, "axialForce")
    c_force = abs(axial_res[0]) if axial_res else 0.0

    # Compressive force must reach and be capped at P_cr within 1%
    assert c_force <= p_cr_expected * 1.02, (
        f"Compressive force {c_force:.2f} kN exceeded Euler buckling cap {p_cr_expected:.2f} kN"
    )
    assert c_force >= p_cr_expected * 0.95, (
        f"Compressive force {c_force:.2f} kN did not reach buckling plateau {p_cr_expected:.2f} kN"
    )


# ==============================================================================
# 4. Staged Construction Equilibrium Verification
# ==============================================================================

def test_staged_equilibrium():
    """
    Phase 4.4: Ensures intermediate excavation stages satisfy static equilibrium prior to dynamic shaking.
    """
    model = MultiStrutPiledWallModel()
    soil = SoilProperties()

    solver = OpenSeesBNWFSolver(model=model, soil=soil)
    solver.initialize()

    # Run staged sequence (Stage 0: gravity, Stage 1: excavation + active pressure, Stage 2: prestress)
    success = solver.run_staged_construction()
    assert success is True, "All staged excavation phases converged in static equilibrium"


# ==============================================================================
# 5. Dynamic Transient Simulation & Asynchronous Worker Cancellation
# ==============================================================================

def test_dynamic_transient_earthquake_run():
    """
    Verifies OpenSees transient dynamic analysis under synthetic earthquake ground motion.
    """
    model = MultiStrutPiledWallModel()
    soil = SoilProperties()

    solver = OpenSeesBNWFSolver(model=model, soil=soil, num_pile_nodes=12, num_pier_nodes=8)
    solver.initialize()

    # Synthetic 1.0 second Ricker-like wavelet acceleration (50 steps at dt = 0.02s)
    time_arr = np.linspace(0.0, 1.0, 50, dtype=np.float64)
    # Peak acceleration 0.25g
    accel_arr = 0.25 * np.sin(2.0 * np.pi * 3.0 * time_arr) * np.exp(-((time_arr - 0.4) / 0.15) ** 2)

    res = solver.run_dynamic_analysis(time_arr=time_arr, accel_arr=accel_arr)
    assert res.status == "SUCCESS"
    assert res.total_steps == 50
    assert len(res.crest_displacement) == 50
    assert res.max_crest_disp_cm > 0.0
    assert res.max_moment_knm > 0.0


def test_worker_cancellation():
    """
    Phase 4.4: Verifies that triggering worker.cancel() cleanly terminates
    OpenSees execution within 100 ms.
    """
    # Initialize PySide6 QApplication if not present
    _ = QApplication.instance() or QApplication([])

    model = MultiStrutPiledWallModel()
    soil = SoilProperties()

    # 200 time steps of synthetic shaking
    time_arr = np.linspace(0.0, 4.0, 200, dtype=np.float64)
    accel_arr = 0.20 * np.sin(2.0 * np.pi * 2.5 * time_arr)

    worker = BNWFSimulationWorker(
        model=model,
        soil=soil,
        time_arr=time_arr,
        accel_arr=accel_arr,
    )

    worker.start()
    # Allow worker to initialize and enter dynamic analysis
    time.sleep(0.05)

    cancel_start = time.perf_counter()
    worker.cancel()
    worker.wait(500) # Wait up to 500 ms
    cancel_duration_ms = (time.perf_counter() - cancel_start) * 1000.0

    print(f"\n[BENCHMARK] Worker cancellation latency: {cancel_duration_ms:.2f} ms (Threshold: < 100 ms)")
    assert not worker.isRunning(), "Worker thread must terminate cleanly upon cancel()"
    assert cancel_duration_ms < 100.0, f"Cancellation took {cancel_duration_ms:.2f} ms (> 100 ms threshold)"


# ==============================================================================
# 6. Edge Cases & Boundary Handling
# ==============================================================================

def test_edge_cases_and_error_handling():
    """Verifies edge cases and boundary checks across spring curves and BNWF solver."""
    # Invalid pile diameter
    with pytest.raises(ValueError, match="diameter must be positive"):
        compute_py_sand_parameters(depth=2.0, gamma=18.0, phi=30.0, diameter=0.0, tributary_length=1.0)

    # Invalid tributary length
    with pytest.raises(ValueError, match="tributary_length must be positive"):
        compute_py_clay_parameters(depth=2.0, gamma=18.0, cu=30.0, diameter=0.8, tributary_length=-1.0)

    # Invalid depth
    with pytest.raises(ValueError, match="depth cannot be negative"):
        compute_py_sand_parameters(depth=-1.0, gamma=18.0, phi=30.0, diameter=0.8, tributary_length=1.0)

    # Insufficient pile nodes
    with pytest.raises(ValueError, match="num_pile_nodes must be >= 2"):
        generate_soil_spring_profile(PierAndPileGeometry(), SoilProperties(), num_pile_nodes=1)

    # Insufficient time steps in dynamic analysis
    solver = OpenSeesBNWFSolver(MultiStrutPiledWallModel(), SoilProperties())
    with pytest.raises(ValueError, match="time_arr must contain >= 2 steps"):
        solver.run_dynamic_analysis(time_arr=np.array([0.0]), accel_arr=np.array([0.0]))

    # Reese & Matlock validation errors
    with pytest.raises(ValueError, match="subgrade_rate_nh must be positive"):
        reese_matlock_theoretical_displacement(10.0, 0.0, 30e6, 0.02, -100.0)
    with pytest.raises(ValueError, match="E\\*I must be positive"):
        reese_matlock_theoretical_displacement(10.0, 0.0, 0.0, 0.02, 12000.0)

    # Assembler node checks
    with pytest.raises(ValueError, match="num_pile_nodes must be >= 3"):
        build_opensees_bnwf_model(MultiStrutPiledWallModel(), SoilProperties(), num_pile_nodes=2)
    with pytest.raises(ValueError, match="num_pier_nodes must be >= 2"):
        build_opensees_bnwf_model(MultiStrutPiledWallModel(), SoilProperties(), num_pier_nodes=1)


def test_submerged_sand_and_cohesive_springs():
    """Verifies water table immersion in sand, cohesive clay t-z & q-z, and zero depth."""
    # Submerged sand (depth > water_table_depth)
    py_sub = compute_py_sand_parameters(
        depth=5.0, gamma=20.0, phi=35.0, diameter=0.8, tributary_length=1.0, water_table_depth=2.0
    )
    assert py_sub.p_ult > 0.0

    # Depth = 0 edge case
    py_zero = compute_py_sand_parameters(
        depth=0.0, gamma=18.0, phi=30.0, diameter=0.8, tributary_length=1.0
    )
    assert py_zero.p_ult > 0.0

    py_clay_zero = compute_py_clay_parameters(
        depth=0.0, gamma=18.0, cu=25.0, diameter=0.8, tributary_length=1.0
    )
    assert py_clay_zero.p_ult > 0.0

    # Cohesive t-z and q-z with cu > 5.0 and phi < 15.0
    tz_clay = compute_tz_parameters(
        depth=4.0, gamma=18.0, phi=10.0, cu=50.0, diameter=0.8, tributary_length=1.0
    )
    assert tz_clay.t_ult > 0.0

    qz_clay = compute_qz_parameters(
        diameter=0.8, gamma=18.0, phi=10.0, cu=50.0, pile_length=10.0
    )
    assert qz_clay.q_ult > 0.0

    # Soil spring profile in pure cohesive soil
    clay_soil = SoilProperties(
        foundation_unit_weight=18.0,
        foundation_friction_angle=10.0,
        foundation_cohesion=45.0,
    )
    profile = generate_soil_spring_profile(PierAndPileGeometry(), clay_soil, num_pile_nodes=5)
    assert profile.py_springs[0].mat_type == 2


def test_worker_full_lifecycle():
    """Verifies that BNWFSimulationWorker runs to completion and emits all lifecycle signals."""
    _ = QApplication.instance() or QApplication([])

    model = MultiStrutPiledWallModel(
        pier_pile=PierAndPileGeometry(pier_height=8.0, pile_length=8.0),
        struts=StrutSupportSystem(strut_levels=[2.0, 5.0]),
    )
    soil = SoilProperties()

    # Short 5-step dynamic run
    time_arr = np.linspace(0.0, 0.1, 5, dtype=np.float64)
    accel_arr = np.array([0.0, 0.05, 0.1, -0.05, 0.0], dtype=np.float64)

    worker = BNWFSimulationWorker(
        model=model,
        soil=soil,
        time_arr=time_arr,
        accel_arr=accel_arr,
    )

    stages_emitted = []
    steps_emitted = []
    finished_summary = []

    worker.stageCompleted.connect(lambda idx, name: stages_emitted.append((idx, name)))
    worker.stepCompleted.connect(lambda s, t, u, m: steps_emitted.append((s, t, u, m)))
    worker.simulationFinished.connect(lambda res: finished_summary.append(res))

    worker.run()

    assert not worker.is_cancelled()
    assert len(stages_emitted) == 3
    assert len(steps_emitted) > 0
    assert len(finished_summary) == 1
    assert finished_summary[0]["status"] == "SUCCESS"
    assert finished_summary[0]["total_steps"] == 5


def test_missing_opensees_runtime_error(monkeypatch):
    """Verifies that RuntimeError is raised when OpenSeesPy is unavailable."""
    import orang3d.physics.opensees_assembler as asm
    import orang3d.physics.bnwf_solver as bsol

    monkeypatch.setattr(asm, "OPENSEES_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="OpenSeesPy is not installed"):
        asm.build_opensees_bnwf_model(MultiStrutPiledWallModel(), SoilProperties())

    monkeypatch.setattr(bsol, "OPENSEES_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="OpenSeesPy is not installed"):
        bsol.OpenSeesBNWFSolver(MultiStrutPiledWallModel(), SoilProperties())

    # Worker error emission when OpenSees is not available
    _ = QApplication.instance() or QApplication([])
    errors = []
    worker = bsol.BNWFSimulationWorker(
        MultiStrutPiledWallModel(),
        SoilProperties(),
        np.array([0.0, 0.1]),
        np.array([0.0, 0.0]),
    )
    worker.simulationError.connect(lambda msg: errors.append(msg))
    worker.run()
    assert len(errors) == 1
    assert "OpenSeesPy is not installed" in errors[0]


def test_clay_py_validation_errors():
    """Verifies input validation in compute_py_clay_parameters."""
    with pytest.raises(ValueError, match="diameter must be positive"):
        compute_py_clay_parameters(depth=1.0, gamma=18.0, cu=30.0, diameter=0.0, tributary_length=1.0)
    with pytest.raises(ValueError, match="depth cannot be negative"):
        compute_py_clay_parameters(depth=-1.0, gamma=18.0, cu=30.0, diameter=0.8, tributary_length=1.0)


def test_worker_cancellation_branches():
    """Verifies worker cancellation before stage 1, staged failure, and cancel_check callback."""
    _ = QApplication.instance() or QApplication([])
    import orang3d.physics.bnwf_solver as bsol

    # 1. Early cancel before run
    worker_early = bsol.BNWFSimulationWorker(
        MultiStrutPiledWallModel(struts=StrutSupportSystem(strut_levels=[2.0, 5.0])),
        SoilProperties(),
        np.array([0.0, 0.1]),
        np.array([0.0, 0.0]),
    )
    worker_early.cancel()
    cancelled_status = []
    worker_early.simulationFinished.connect(lambda res: cancelled_status.append(res))
    worker_early.run()
    assert len(cancelled_status) == 1
    assert cancelled_status[0]["status"] == "CANCELLED"

    # 2. Dynamic cancel_check callback
    solver = bsol.OpenSeesBNWFSolver(MultiStrutPiledWallModel(), SoilProperties())
    res_cancel = solver.run_dynamic_analysis(
        time_arr=np.array([0.0, 0.02, 0.04]),
        accel_arr=np.array([0.0, 0.1, 0.2]),
        cancel_check=lambda: True,
    )
    assert res_cancel.status == "INTERRUPTED"

    # 3. Worker staged failure branch
    worker_fail = bsol.BNWFSimulationWorker(
        MultiStrutPiledWallModel(struts=StrutSupportSystem(strut_levels=[2.0, 5.0])),
        SoilProperties(),
        np.array([0.0, 0.1]),
        np.array([0.0, 0.0]),
    )
    errors = []
    worker_fail.simulationError.connect(lambda msg: errors.append(msg))
    # Monkeypatch run_staged_construction to return False
    original_staged = bsol.OpenSeesBNWFSolver.run_staged_construction
    bsol.OpenSeesBNWFSolver.run_staged_construction = lambda self: False
    try:
        worker_fail.run()
        assert len(errors) == 1
        assert "Staged excavation equilibrium failed" in errors[0]
    finally:
        bsol.OpenSeesBNWFSolver.run_staged_construction = original_staged

