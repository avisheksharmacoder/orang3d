"""
Entry point for orang3D desktop application.
"""

import os
import sys
import ctypes
from pathlib import Path

# Platform-specific initialization
if sys.platform.startswith("linux"):
    # Preload libxcb-cursor if present in user local lib to guarantee Qt 6.5+ XCB loads cleanly
    _local_xcb = Path.home() / ".local" / "lib" / "libxcb-cursor.so.0"
    if _local_xcb.is_file():
        try:
            mode = getattr(ctypes, "RTLD_GLOBAL", 0)
            ctypes.CDLL(str(_local_xcb), mode=mode)
        except Exception:
            pass
elif sys.platform == "win32":
    # Enable Windows AppUserModelID for proper taskbar icon and window grouping
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("orang3D.Geotechnical.CivilEngineering.1.0")
    except Exception:
        pass

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from .gui.main_window import MainWindow


def main():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("orang3D")
    app.setOrganizationName("orang3D")

    # Resolve application icon (source tree vs PyInstaller bundle)
    icon_candidates = [
        Path(__file__).resolve().parent.parent.parent / "resources" / "icons" / "orang3d.png",
    ]
    if hasattr(sys, "_MEIPASS"):
        icon_candidates.insert(0, Path(sys._MEIPASS) / "resources" / "icons" / "orang3d.png")

    for cand in icon_candidates:
        if cand.is_file():
            app.setWindowIcon(QIcon(str(cand)))
            break

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
