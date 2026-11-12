# -*- mode: python ; coding: utf-8 -*-
"""
Cross-Platform PyInstaller Specification for orang3D.
Builds standalone, portable distribution bundles for Windows and Linux.
Bundles PySide6, PyVista/VTK, pyqtgraph, NumPy, SciPy, Matplotlib, and h5py.

Usage:
  pyinstaller --clean orang3d.spec
  ORANG3D_ONEFILE=1 pyinstaller --clean orang3d.spec
"""

import os
import sys
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)


def _safe_collect_data(pkg: str):
    try:
        return collect_data_files(pkg)
    except Exception:
        return []


def _safe_collect_libs(pkg: str):
    try:
        return collect_dynamic_libs(pkg)
    except Exception:
        return []


def _safe_collect_submodules(pkg: str):
    try:
        return collect_submodules(pkg)
    except Exception:
        return []


is_windows = sys.platform.startswith('win')
is_linux = sys.platform.startswith('linux')
onefile_mode = os.environ.get('ORANG3D_ONEFILE', '0') == '1'

block_cipher = None

# 1. Collect Application Data Files (Icons, Desktop Entry, Templates, Scientific Libraries)
datas = []
if os.path.isdir('resources'):
    datas.append(('resources', 'resources'))
if os.path.isdir(os.path.join('src', 'orang3d', 'resources')):
    datas.append((os.path.join('src', 'orang3d', 'resources'), os.path.join('orang3d', 'resources')))

for _data_pkg in (
    'pyvista',
    'pyvistaqt',
    'pyqtgraph',
    'matplotlib',
    'ezdxf',
    'openseespy',
    'orang3d',
):
    datas += _safe_collect_data(_data_pkg)

# 2. Collect Dynamic Libraries & Binaries (.so / .dll for VTK, OpenSeesPy, etc.)
binaries = []
binaries += _safe_collect_libs('openseespy')
if is_windows:
    binaries += _safe_collect_libs('vtkmodules')
elif is_linux:
    binaries += _safe_collect_libs('vtkmodules')

# Explicitly ensure openseespy native extension modules (.so / .pyd / .dll) are bundled
try:
    import openseespy as _ops_pkg

    _ops_root = os.path.dirname(os.path.abspath(_ops_pkg.__file__))
    for _root, _, _files in os.walk(_ops_root):
        for _fname in _files:
            if _fname.endswith(('.so', '.dll', '.pyd', '.dylib')) or '.so.' in _fname:
                _src = os.path.join(_root, _fname)
                _rel = os.path.relpath(_root, os.path.dirname(_ops_root))
                binaries.append((_src, _rel))
except Exception:
    pass

# 3. Explicit Hidden Imports (All Phase 1-10 Packages, Panels, Dialogs, Solvers, Exports)
hidden_imports = sorted(
    set(
        _safe_collect_submodules('orang3d')
        + _safe_collect_submodules('ezdxf')
        + _safe_collect_submodules('openseespy')
        + [
            'orang3d',
            'orang3d.main',
            'orang3d.config',
            'orang3d.units',
            'orang3d.models',
            'orang3d.models.wall_params',
            'orang3d.models.advanced_wall_params',
            'orang3d.models.architectural_wall_params',
            'orang3d.models.is_code_params',
            'orang3d.models.presets',
            'orang3d.models.tower_params',
            'orang3d.physics',
            'orang3d.physics.arch_wall_solver',
            'orang3d.physics.bnwf_solver',
            'orang3d.physics.calibration',
            'orang3d.physics.code_auditor',
            'orang3d.physics.cyclic_soil',
            'orang3d.physics.is_1893_engine',
            'orang3d.physics.is_codes',
            'orang3d.physics.is_codes.audit_engine',
            'orang3d.physics.is_codes.is_456',
            'orang3d.physics.is_codes.is_800',
            'orang3d.physics.is_codes.is_2911',
            'orang3d.physics.kratos_solver',
            'orang3d.physics.mononobe_okabe',
            'orang3d.physics.opensees_3d_solver',
            'orang3d.physics.opensees_assembler',
            'orang3d.physics.pile_statics',
            'orang3d.physics.pinn_trainer',
            'orang3d.physics.shell_arching',
            'orang3d.physics.sizing_advisor',
            'orang3d.physics.solver_registry',
            'orang3d.physics.spring_curves',
            'orang3d.physics.stability',
            'orang3d.physics.structural',
            'orang3d.physics.strut_statics',
            'orang3d.physics.surcharge',
            'orang3d.physics.surrogate_engine',
            'orang3d.physics.tower_coupling',
            'orang3d.physics.uncertainty',
            'orang3d.physics.unsaturated_soil',
            'orang3d.physics.wind_loads',
            'orang3d.mesher',
            'orang3d.mesher.arch_wall_mesher',
            'orang3d.mesher.continuum_fea_mesher',
            'orang3d.mesher.hex_mesher',
            'orang3d.mesher.hybrid_assembler',
            'orang3d.mesher.pile_strut_mesher',
            'orang3d.mesher.shell_mesher',
            'orang3d.mesher.terrain',
            'orang3d.signals',
            'orang3d.signals.at2_parser',
            'orang3d.signals.synthetic',
            'orang3d.signals.topography',
            'orang3d.gui',
            'orang3d.gui.main_window',
            'orang3d.gui.viewport_3d',
            'orang3d.gui.charts_2d',
            'orang3d.gui.dialogs',
            'orang3d.gui.dialogs.calibration_wizard',
            'orang3d.gui.dialogs.sensitivity_dialog',
            'orang3d.gui.panels',
            'orang3d.gui.panels.geometry_panel',
            'orang3d.gui.panels.soil_panel',
            'orang3d.gui.panels.seismic_panel',
            'orang3d.gui.panels.shell_panel',
            'orang3d.gui.panels.strut_pile_panel',
            'orang3d.gui.panels.advanced_soil_panel',
            'orang3d.gui.panels.arch_wall_panel',
            'orang3d.gui.panels.terrain_panel',
            'orang3d.gui.panels.audit_tab',
            'orang3d.gui.panels.bnwf_pinn_tab',
            'orang3d.gui.panels.comparison_tab',
            'orang3d.gui.panels.equation_inspector_tab',
            'orang3d.gui.panels.uq_fragility_tab',
            'orang3d.io',
            'orang3d.io.serialization',
            'orang3d.io.mesh_export',
            'orang3d.io.report_generator',
            'orang3d.io.dxf_export',
            'orang3d.io.deck_export',
            'orang3d.io.bim_export',
            'pyvista',
            'pyvistaqt',
            'pyqtgraph',
            'ezdxf',
            'PIL',
            'PIL.Image',
            'openseespy',
            'openseespy.opensees',
            'vtkmodules',
            'vtkmodules.all',
            'vtkmodules.qt.QVTKRenderWindowInteractor',
            'vtkmodules.util',
            'vtkmodules.numpy_interface',
            'vtkmodules.numpy_interface.dataset_adapter',
            'meshio',
            'h5py',
            'scipy',
            'scipy.signal',
            'scipy.spatial',
            'scipy.interpolate',
            'matplotlib',
            'matplotlib.backends.backend_agg',
            'PySide6.QtPrintSupport',
            'PySide6.QtSvg',
            'PySide6.QtOpenGL',
            'PySide6.QtOpenGLWidgets',
        ]
    )
)

# 4. Icon Resolution
icon_file = 'resources/icons/orang3d.ico' if is_windows else 'resources/icons/orang3d.png'
if not os.path.exists(icon_file):
    icon_file = None

a = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib.tests', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if onefile_mode:
    # Single-file standalone executable
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='orang3d',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_file,
    )
else:
    # Onedir distribution folder (recommended for large scientific Qt/VTK apps)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='orang3d',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_file,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='orang3d',
    )
