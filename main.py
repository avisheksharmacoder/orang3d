#!/usr/bin/env python3
"""
orang3D - Real-time 3D Seismic and Disaster Analysis of Retaining Walls
Launch script.
"""

import os
import sys
import ctypes
from pathlib import Path

# Preload libxcb-cursor if present in user local lib to guarantee Qt 6.5+ XCB loads cleanly
_local_xcb = Path.home() / ".local" / "lib" / "libxcb-cursor.so.0"
if _local_xcb.is_file():
    try:
        ctypes.CDLL(str(_local_xcb), mode=ctypes.RTLD_GLOBAL)
    except Exception:
        pass

# Ensure src/ is on Python module search path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from orang3d.main import main

if __name__ == "__main__":
    main()
