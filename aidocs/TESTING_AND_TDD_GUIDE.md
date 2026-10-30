# Testing Architecture & Test-Driven Development (TDD) Guide

This guide details the testing principles, taxonomy, commands, and best practices for developing in **orang3D**.

---

## 1. Testing Philosophy & TDD Workflow

`orang3D` enforces a strict **Test-Driven Development (TDD)** lifecycle for all scientific, geometric, and numerical features:

```mermaid
flowchart LR
    A[1. Write Failing Test in tests/] -->|RED Phase| B[2. Run pytest: Verify Failure]
    B --> C[3. Implement Code in src/orang3d/]
    C -->|GREEN Phase| D[4. Run pytest: Verify Passing]
    D --> E[5. Refactor & Check 100% Coverage]
    E --> F[6. Update Docs & Completion Report]
```

### The 3 Rules of TDD in orang3D:
1. **Never write implementation code without a failing test first.**
2. **Never commit code if any existing test fails.**
3. **Always verify physical invariants** (e.g. conservation of energy, statics equilibrium $\sum F = 0$, non-decreasing plastic slip).

---

## 2. The 6 Testing Categories

To guarantee engineering reliability, tests are organized into six distinct categories:

| Category | Objective | Example in orang3D |
| :--- | :--- | :--- |
| **1. Unit & Contract Tests** | Verify dataclass attributes, boundary conditions, defaults, and schema validators. | Testing `RetainingWallGeometry` raises `ValueError` if stem top $>$ stem base. |
| **2. Physics Invariants** | Check that physical laws hold unconditionally. | Verifying $dM/dy = -V(y)$, $M(\text{crest}) = 0$, and Newmark slip is non-decreasing. |
| **3. Golden Benchmarks** | Compare against published peer-reviewed textbook problems and analytical solutions. | Validating safety factors against Das (*Principles of Foundation Engineering*) and Kramer (*Geotechnical Earthquake Engineering*). |
| **4. Performance Benchmarks** | Enforce strict execution time thresholds to ensure 60 FPS slider interactivity. | Asserting that the pure NumPy hex mesher rebuilds the wall in $< 5.0\text{ ms}$ over 20 consecutive runs. |
| **5. Robustness & Fuzzing** | Test extreme disaster conditions and malformed inputs. | Testing $100\%$ liquefaction ($r_u \to 1.0$), water table at crest, $1.5g$ earthquake, and truncated `.AT2` files. |
| **6. GUI & Threading Tests** | Test PySide6 widgets, signal/slot wiring, and background `QThread` execution. | Testing `KratosSimulationWorker` cooperative cancellation without UI freezing. |

---

## 3. How to Run Tests

### Standard Test Commands

All test executions must use `.venv/bin/pytest` and set `QT_QPA_PLATFORM=offscreen` to allow headless execution of PySide6 and PyVista VTK widgets without an X11 display:

```bash
# 1. Run the entire test suite (89 tests)
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v

# 2. Run the test suite with terminal coverage report
QT_QPA_PLATFORM=offscreen .venv/bin/pytest --cov=orang3d --cov-report=term-missing

# 3. Run a specific test module
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_signals.py -v
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_kratos_solver.py -v
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_mesher.py -v

# 4. Run a single specific test by name
QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_structural.py -k "test_differential_equilibrium_invariant" -v
```

---

## 4. Test Suite Mapping Table

The test suite consists of 89 automated tests covering all modules:

| Test File | Target Source File | Test Count | Key Invariants Tested |
| :--- | :--- | :---: | :--- |
| [`tests/test_models.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_models.py) | [`wall_params.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/models/wall_params.py) | 18 | Dataclass bounds, physical geometry constraints, soil friction angles, seismic PGA bounds. |
| [`tests/test_units.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_units.py) | [`units.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/units.py) | 8 | Exact bidirectional unit conversion (length, force, stress, unit weight, rebar area). |
| [`tests/test_config.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_config.py) | [`config.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/config.py) | 3 | Dark/light theme colors, Eurocode 7, AASHTO LRFD, and IS 14458 required safety factors. |
| [`tests/test_mesher.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_mesher.py) | [`hex_mesher.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/mesher/hex_mesher.py) | 11 | Hex cell topology (`VTK_HEXAHEDRON`), Jacobian positivity ($\det(J) > 0$), closed-form volume conservation, $< 5\text{ ms}$ latency benchmark. |
| [`tests/test_physics_stability.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_physics_stability.py) | [`mononobe_okabe.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/mononobe_okabe.py), [`stability.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/stability.py) | 16 | Mononobe-Okabe static limit ($K_{ae} \to K_a$), Seed & Whitman thrust height, sliding, overturning, Meyerhof/Hansen bearing capacity, Das & Kramer golden benchmarks. |
| [`tests/test_structural.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_structural.py) | [`structural.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/structural.py) | 7 | Crest boundary conditions $M(H)=0$, $V(H)=0$, base peak, differential equilibrium $dM/dy = -V(y)$, cracking prediction ($f_r = 0.62\sqrt{f'_c}$), ACI 318 rebar area. |
| [`tests/test_signals.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_signals.py) | [`synthetic.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/synthetic.py), [`at2_parser.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/signals/at2_parser.py) | 10 | Ricker wavelets zero DC velocity offset, linear/log chirps, Arias Intensity & CAV monotonicity, limit-equilibrium $k_y$, Newmark sliding block sub-yield vs post-yield, PEER `.AT2` parser. |
| [`tests/test_kratos_solver.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_kratos_solver.py) | [`kratos_solver.py`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/physics/kratos_solver.py) | 11 | Kratos kernel & OpenMP threads, 5 SubModelParts, Lysmer absorbing boundaries ($C_p, C_s$), coupled $u-p$ dynamic step, `QThread` signals, cooperative cancellation, HDF5 binary caching. |
| [`tests/test_gui_events.py`](file:///home/avisheks/Documents/dibs/orang3d/tests/test_gui_events.py) | [`gui/`](file:///home/avisheks/Documents/dibs/orang3d/src/orang3d/gui/) | 5 | Headless PySide6 window creation, slider change event emission, safety badge updates, offscreen 3D viewport rendering. |

---

## 5. Critical Gotchas & Troubleshooting

### 1. Missing X11 Display in Headless CI
- **Symptom:** `qt.qpa.xcb: could not connect to display` or instant abort.
- **Remedy:** Always prepend `QT_QPA_PLATFORM=offscreen`:
  ```bash
  QT_QPA_PLATFORM=offscreen .venv/bin/pytest
  ```

### 2. NumPy 2.0 Compatibility (`np.trapz` removal)
- **Symptom:** `AttributeError: module 'numpy' has no attribute 'trapz'`.
- **Remedy:** In NumPy 2.0+, `np.trapz` was removed and replaced with `np.trapezoid`. Use the dual-compatibility idiom:
  ```python
  _trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
  ```

### 3. PyVista `cast_to_unstructured_grid()`
- **Symptom:** `AttributeError: 'PolyData' object has no attribute 'cells'`.
- **Remedy:** When passing geometric meshes to cell/Jacobian evaluators, check and cast:
  ```python
  if not isinstance(mesh, pv.UnstructuredGrid):
      mesh = mesh.cast_to_unstructured_grid()
  ```

### 4. Kratos OpenMP Deprecations
- **Symptom:** `[WARNING] OpenMPUtils: "GetNumThreads" is deprecated, please use ParallelUtilities.GetNumThreads instead`.
- **Remedy:** Check for `KM.ParallelUtilities` first, falling back to `KM.OpenMPUtils`.
