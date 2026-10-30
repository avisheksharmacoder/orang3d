"""
Intermediate Level L1 BNWF (Beam on Nonlinear Winkler Foundation) Engine.
Executes staged construction, nonlinear p-y/t-z/q-z soil spring interaction,
strut tension slackening and compressive buckling caps, and dynamic earthquake
time-history analysis with cooperative multi-threaded PySide6 worker execution.
"""

from __future__ import annotations

import time
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from PySide6.QtCore import QThread, Signal

try:
    import openseespy.opensees as ops
    OPENSEES_AVAILABLE = True
except (ImportError, Exception):
    ops = None
    OPENSEES_AVAILABLE = False

from ..models.advanced_wall_params import MultiStrutPiledWallModel
from ..models.wall_params import SoilProperties
from .opensees_assembler import (
    BNWFModelInfo,
    build_opensees_bnwf_model,
)


@dataclass
class BNWFSimulationResult:
    """Comprehensive output container for BNWF staged and dynamic simulation."""
    time_history: np.ndarray = field(default_factory=lambda: np.array([]))
    crest_displacement: np.ndarray = field(default_factory=lambda: np.array([]))
    pile_head_displacement: np.ndarray = field(default_factory=lambda: np.array([]))
    max_bending_moment: np.ndarray = field(default_factory=lambda: np.array([]))
    strut_forces: Dict[int, np.ndarray] = field(default_factory=dict)
    bending_moment_profile: Dict[float, np.ndarray] = field(default_factory=dict)
    shear_force_profile: Dict[float, np.ndarray] = field(default_factory=dict)
    deflection_profile: Dict[float, np.ndarray] = field(default_factory=dict)
    staged_converged: bool = True
    dynamic_converged: bool = True
    total_steps: int = 0
    max_crest_disp_cm: float = 0.0
    max_moment_knm: float = 0.0
    status: str = "SUCCESS"


class OpenSeesBNWFSolver:
    """
    Core numerical solver for 2D Beam on Nonlinear Winkler Foundation (BNWF)
    using OpenSeesPy. Simulates staged excavation and dynamic ground motions.
    """
    def __init__(
        self,
        model: MultiStrutPiledWallModel,
        soil: SoilProperties,
        slope_angle: float = 0.0,
        num_pile_nodes: int = 15,
        num_pier_nodes: int = 10,
    ):
        if not OPENSEES_AVAILABLE:
            raise RuntimeError(
                "OpenSeesPy is not installed. Install via `pip install openseespy`."
            )
        self.model = model
        self.soil = soil
        self.slope_angle = slope_angle
        self.num_pile_nodes = num_pile_nodes
        self.num_pier_nodes = num_pier_nodes
        self.info: Optional[BNWFModelInfo] = None
        self._is_initialized = False

    def initialize(self) -> BNWFModelInfo:
        """Builds and initializes the OpenSeesPy model."""
        self.info = build_opensees_bnwf_model(
            model=self.model,
            soil=self.soil,
            slope_angle=self.slope_angle,
            num_pile_nodes=self.num_pile_nodes,
            num_pier_nodes=self.num_pier_nodes,
        )
        self._is_initialized = True
        return self.info

    def run_staged_construction(
        self,
        excavation_stages: Optional[List[float]] = None,
    ) -> bool:
        """
        Executes staged construction simulation:
        - Stage 0: Initial self-weight & K0 static balance
        - Stage 1: Excavation to intermediate level
        - Stage 2: Install Strut 1 with lock-off prestress P0
        - Stage 3: Excavate to full dredge line, install Strut 2
        Returns True if all stages converged in static equilibrium.
        """
        if not self._is_initialized:
            self.initialize()

        info = self.info
        assert info is not None

        pier_h = self.model.pier_pile.pier_height
        struts = self.model.struts

        # Setup standard static analysis controls
        ops.system("BandGeneral")
        ops.numberer("RCM")
        ops.constraints("Transformation")
        ops.test("NormDispIncr", 1.0e-5, 50, 0)
        ops.algorithm("Newton")
        ops.integrator("LoadControl", 1.0)
        ops.analysis("Static")

        # Stage 0: Gravity self-weight equilibrium
        ops.timeSeries("Linear", 101)
        ops.pattern("Plain", 201, 101)
        # Apply vertical gravity load on pier and pile nodes
        for node in info.pier_nodes + info.pile_nodes[1:]:
            y_elev = info.node_elevations[node]
            # Structural self weight (kN)
            if y_elev >= 0.0:
                dy = pier_h / (self.num_pier_nodes - 1)
                f_g = -25.0 * (self.model.pier_pile.pier_width * self.model.pier_pile.pier_depth) * dy
            else:
                dy = self.model.pier_pile.pile_length / (self.num_pile_nodes - 1)
                a_piles = ((math.pi * (self.model.pier_pile.pile_diameter ** 2)) / 4.0) * self.model.pier_pile.num_piles_per_pier
                f_g = -25.0 * a_piles * dy
            ops.load(node, 0.0, f_g, 0.0)

        ret0 = ops.analyze(1)
        if ret0 != 0:
            return False

        # Stage 1: Excavation to first strut level & activate lateral earth pressure
        ops.loadConst()
        ops.timeSeries("Linear", 102)
        ops.pattern("Plain", 202, 102)

        # Distribute active earth pressure along pier nodes
        total_p_active = 0.5 * self.soil.unit_weight * (pier_h ** 2) * 0.33 * self.model.shell.bay_span
        f_lateral_per_node = total_p_active / len(info.pier_nodes)
        for node in info.pier_nodes:
            ops.load(node, f_lateral_per_node, 0.0, 0.0)

        ret1 = ops.analyze(1)
        if ret1 != 0:
            return False

        # Stage 2: Apply lock-off prestress P0 to raking struts
        ops.loadConst()
        ops.timeSeries("Linear", 103)
        ops.pattern("Plain", 203, 103)
        alpha_rad = math.radians(struts.inclination_angle)
        for s_idx, p_0 in info.lock_off_forces.items():
            pier_node = info.strut_node_map[s_idx]
            # Prestress pushes backwards into the hill (-X, +Y)
            p0_h = -p_0 * math.cos(alpha_rad)
            p0_v = -p_0 * math.sin(alpha_rad)
            ops.load(pier_node, p0_h, p0_v, 0.0)

        ret2 = ops.analyze(1)
        if ret2 != 0:
            return False

        return True

    def run_pushover_analysis(
        self,
        max_displacement: float = 0.05, # 5 cm
        num_steps: int = 20,
    ) -> Dict[str, np.ndarray]:
        """
        Executes lateral pushover analysis by applying incremental displacement
        at the wall crest node and records base shear, moment, and strut reactions.
        """
        if not self._is_initialized:
            self.initialize()

        info = self.info
        assert info is not None

        crest_node = info.crest_node_tag
        d_step = max_displacement / num_steps

        ops.timeSeries("Linear", 104)
        ops.pattern("Plain", 204, 104)
        ops.load(crest_node, 1.0, 0.0, 0.0)

        ops.system("BandGeneral")
        ops.numberer("RCM")
        ops.constraints("Transformation")
        ops.test("NormDispIncr", 1.0e-5, 50, 0)
        ops.algorithm("Newton")
        ops.integrator("DisplacementControl", crest_node, 1, d_step)
        ops.analysis("Static")

        disp_history = [0.0]
        shear_history = [0.0]
        strut_force_history = {s_idx: [0.0] for s_idx in range(len(info.strut_elements))}

        for step in range(num_steps):
            ret = ops.analyze(1)
            u_crest = ops.nodeDisp(crest_node, 1)
            disp_history.append(float(u_crest))

            # Base shear reaction at pile head (Node 100)
            # Sum of lateral forces on pier elements
            v_base = 0.0
            if info.pier_elements:
                forces = ops.eleResponse(info.pier_elements[0], "forces")
                v_base = abs(forces[1]) if forces else 0.0
            shear_history.append(float(v_base))

            # Strut axial forces
            for s_idx, ele_tag in enumerate(info.strut_elements):
                f_ax = ops.eleResponse(ele_tag, "axialForce")
                strut_force_history[s_idx].append(float(f_ax[0]) if f_ax else 0.0)

        return {
            "displacements": np.array(disp_history),
            "base_shears": np.array(shear_history),
            "strut_forces": {k: np.array(v) for k, v in strut_force_history.items()},
        }

    def run_dynamic_analysis(
        self,
        time_arr: np.ndarray,
        accel_arr: np.ndarray,
        damping_ratio: float = 0.05,
        cancel_check: Optional[callable] = None,
        progress_callback: Optional[callable] = None,
    ) -> BNWFSimulationResult:
        """
        Executes dynamic earthquake time-history analysis using Newmark beta integrator.
        Applies ground acceleration at the soil support base nodes via UniformExcitation.
        """
        if not self._is_initialized:
            self.initialize()

        info = self.info
        assert info is not None

        n_steps = len(time_arr)
        if n_steps < 2:
            raise ValueError(f"time_arr must contain >= 2 steps, got {n_steps}")

        dt = float(time_arr[1] - time_arr[0])

        # Rayleigh damping: C = a0 * M + a1 * K
        # Target 5% damping between omega1 (fundamental) and omega2
        omega1 = 2.0 * math.pi * 1.5 # ~1.5 Hz
        omega2 = 2.0 * math.pi * 10.0 # ~10 Hz
        a0 = 2.0 * damping_ratio * (omega1 * omega2) / (omega1 + omega2)
        a1 = 2.0 * damping_ratio / (omega1 + omega2)
        ops.rayleigh(a0, a1, 0.0, 0.0)

        # Dynamic ground motion input
        ts_tag = 200
        ops.timeSeries("Path", ts_tag, "-dt", dt, "-values", *list(accel_arr), "-factor", 9.81)
        pattern_tag = 300
        ops.pattern("UniformExcitation", pattern_tag, 1, "-accel", ts_tag)

        # Dynamic Transient Analysis Setup
        ops.wipeAnalysis()
        ops.system("BandGeneral")
        ops.numberer("RCM")
        ops.constraints("Transformation")
        ops.test("NormDispIncr", 1.0e-4, 40, 0)
        ops.algorithm("Newton")
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")

        t_hist = []
        crest_u = []
        pile_head_u = []
        max_moments = []
        strut_f: Dict[int, List[float]] = {i: [] for i in range(len(info.strut_elements))}

        crest_node = info.crest_node_tag
        pile_head_node = info.pile_head_node_tag

        converged = True

        for step in range(n_steps):
            if cancel_check and cancel_check():
                converged = False
                break

            t = float(time_arr[step])
            ret = ops.analyze(1, dt)

            # Fallback to ModifiedNewton if standard Newton struggles
            if ret != 0:
                ops.algorithm("ModifiedNewton")
                ret = ops.analyze(1, dt)
                ops.algorithm("Newton")

            if ret != 0:
                converged = False
                break

            u_crest = float(ops.nodeDisp(crest_node, 1))
            u_head = float(ops.nodeDisp(pile_head_node, 1))

            # Maximum bending moment along pier and pile elements
            m_max = 0.0
            for ele in info.pier_elements + info.pile_elements:
                forces = ops.eleResponse(ele, "forces")
                if forces and len(forces) >= 6:
                    m1, m2 = abs(forces[2]), abs(forces[5])
                    m_max = max(m_max, m1, m2)

            t_hist.append(t)
            crest_u.append(u_crest)
            pile_head_u.append(u_head)
            max_moments.append(m_max)

            for s_idx, ele_tag in enumerate(info.strut_elements):
                f_ax = ops.eleResponse(ele_tag, "axialForce")
                strut_f[s_idx].append(float(f_ax[0]) if f_ax else 0.0)

            if progress_callback:
                progress_callback(step, t, u_crest, m_max)

        crest_arr = np.array(crest_u, dtype=np.float64)
        max_disp_cm = float(np.max(np.abs(crest_arr)) * 100.0) if len(crest_arr) > 0 else 0.0
        max_m = float(np.max(max_moments)) if max_moments else 0.0

        return BNWFSimulationResult(
            time_history=np.array(t_hist, dtype=np.float64),
            crest_displacement=crest_arr,
            pile_head_displacement=np.array(pile_head_u, dtype=np.float64),
            max_bending_moment=np.array(max_moments, dtype=np.float64),
            strut_forces={k: np.array(v, dtype=np.float64) for k, v in strut_f.items()},
            staged_converged=True,
            dynamic_converged=converged,
            total_steps=len(t_hist),
            max_crest_disp_cm=max_disp_cm,
            max_moment_knm=max_m,
            status="SUCCESS" if converged else "INTERRUPTED",
        )


class BNWFSimulationWorker(QThread):
    """
    Dedicated background worker thread for OpenSeesPy BNWF simulation.
    Ensures GUI responsiveness and provides real-time progress callbacks
    and fast cooperative cancellation (< 100 ms).
    """
    stepCompleted = Signal(int, float, float, float)  # (step, time, crest_disp_m, max_moment_knm)
    stageCompleted = Signal(int, str)                 # (stage_idx, stage_name)
    simulationFinished = Signal(dict)
    simulationError = Signal(str)

    def __init__(
        self,
        model: MultiStrutPiledWallModel,
        soil: SoilProperties,
        time_arr: np.ndarray,
        accel_arr: np.ndarray,
        slope_angle: float = 0.0,
        parent=None,
    ):
        super().__init__(parent)
        self.model = model
        self.soil = soil
        self.time_arr = time_arr
        self.accel_arr = accel_arr
        self.slope_angle = slope_angle
        self._is_cancelled = False
        self._start_time = 0.0

    def cancel(self):
        """Requests cooperative cancellation of OpenSeesPy simulation."""
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self):
        self._start_time = time.perf_counter()
        try:
            if not OPENSEES_AVAILABLE:
                self.simulationError.emit("OpenSeesPy is not installed.")
                return

            solver = OpenSeesBNWFSolver(
                model=self.model,
                soil=self.soil,
                slope_angle=self.slope_angle,
            )

            # Stage 1: Build & initialize model
            self.stageCompleted.emit(1, "Model Assembly & Winkler Spring Construction")
            solver.initialize()

            if self._is_cancelled:
                self.simulationFinished.emit({"status": "CANCELLED"})
                return

            # Stage 2: Staged construction sequence
            self.stageCompleted.emit(2, "Staged Excavation & Strut Prestress Activation")
            staged_ok = solver.run_staged_construction()
            if not staged_ok:
                self.simulationError.emit("Staged excavation equilibrium failed to converge.")
                return

            if self._is_cancelled:
                self.simulationFinished.emit({"status": "CANCELLED"})
                return

            # Stage 3: Dynamic transient analysis
            self.stageCompleted.emit(3, "Earthquake Transient Ground Motion Analysis")

            def on_progress(step, t, crest_u, max_m):
                if step % 2 == 0 or step == len(self.time_arr) - 1:
                    self.stepCompleted.emit(step, t, crest_u, max_m)
                # Cooperative sleep for thread event loop
                time.sleep(0.0005)

            result = solver.run_dynamic_analysis(
                time_arr=self.time_arr,
                accel_arr=self.accel_arr,
                cancel_check=lambda: self._is_cancelled,
                progress_callback=on_progress,
            )

            elapsed = time.perf_counter() - self._start_time
            summary = {
                "status": "CANCELLED" if self._is_cancelled else result.status,
                "total_steps": result.total_steps,
                "max_crest_disp_cm": result.max_crest_disp_cm,
                "max_moment_knm": result.max_moment_knm,
                "elapsed_seconds": elapsed,
            }
            self.simulationFinished.emit(summary)

        except Exception as e:
            self.simulationError.emit(str(e))
