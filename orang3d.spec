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
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

is_windows = sys.platform.startswith('win')
is_linux = sys.platform.startswith('linux')
onefile_mode = os.environ.get('ORANG3D_ONEFILE', '0') == '1'

block_cipher = None

# 1. Collect Application Data Files
datas = []
if os.path.isdir('resources'):
    datas.append(('resources', 'resources'))

datas += collect_data_files('pyvista')
datas += collect_data_files('pyvistaqt')
datas += collect_data_files('pyqtgraph')
datas += collect_data_files('matplotlib')

# 2. Collect Dynamic Libraries & Binaries
binaries = []
if is_windows:
    binaries += collect_dynamic_libs('vtkmodules')

# 3. Explicit Hidden Imports
hidden_imports = [
    'orang3d',
    'orang3d.config',
    'orang3d.units',
    'orang3d.models',
    'orang3d.models.wall_params',
    'orang3d.physics',
    'orang3d.physics.mononobe_okabe',
    'orang3d.physics.stability',
    'orang3d.physics.structural',
    'orang3d.physics.kratos_solver',
    'orang3d.mesher',
    'orang3d.mesher.hex_mesher',
    'orang3d.signals',
    'orang3d.signals.synthetic',
    'orang3d.signals.at2_parser',
    'orang3d.gui',
    'orang3d.gui.main_window',
    'orang3d.gui.viewport_3d',
    'orang3d.gui.charts_2d',
    'orang3d.gui.panels',
    'orang3d.gui.panels.geometry_panel',
    'orang3d.gui.panels.soil_panel',
    'orang3d.gui.panels.seismic_panel',
    'orang3d.io',
    'orang3d.io.serialization',
    'orang3d.io.mesh_export',
    'orang3d.io.report_generator',
    'pyvista',
    'pyvistaqt',
    'pyqtgraph',
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
