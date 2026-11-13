"""
Unit and Integration Tests for Window Maximize Availability and 16:9 Screen & UI Ratio.
Verifies:
1. Window flags explicitly include Qt.WindowMaximizeButtonHint, WindowMinimizeButtonHint, and WindowCloseButtonHint.
2. Initial desktop window size defaults to exact 16:9 widescreen ratio (1440x810).
3. Window minimum size is bounded to 16:9 ratio (1152x648) with layout minimumSizeHint <= 1152x648.
4. Window maximize action (F11 / menu) toggles between normal and maximized states.
5. Window aspect ratio presets (1280x720, 1440x810, 1600x900) preserve exact 16:9 ratio.
6. Toolbars are organized in responsive 2-row layout without overflowing 16:9 displays.
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from orang3d.gui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_flags_and_maximize_button(qapp):
    """Verifies that window flags explicitly declare Maximize, Minimize, and Close buttons."""
    win = MainWindow()
    flags = win.windowFlags()

    assert bool(flags & Qt.WindowMaximizeButtonHint) is True
    assert bool(flags & Qt.WindowMinimizeButtonHint) is True
    assert bool(flags & Qt.WindowCloseButtonHint) is True

    # Verify Maximize menu action exists and is bound to shortcut
    assert hasattr(win, "act_maximize")
    assert win.act_maximize.shortcut().toString() == "F11"

    # Test programmatically triggering maximize
    win.show()
    win.act_maximize.trigger()
    assert win.isMaximized() is True

    # Test toggling back to normal
    win.act_maximize.trigger()
    assert win.isMaximized() is False

    win.close()


def test_main_window_16_9_aspect_ratio_sizing(qapp):
    """Verifies that default size and minimum size conform strictly to 16:9 widescreen ratio."""
    win = MainWindow()

    # Initial default size must be 1440x810 (exact 16:9)
    assert win.width() == 1440
    assert win.height() == 810
    ratio_initial = win.width() / win.height()
    assert ratio_initial == pytest.approx(16.0 / 9.0, rel=1e-3)

    # Minimum size must be 1152x648 (exact 16:9)
    min_w = win.minimumWidth()
    min_h = win.minimumHeight()
    assert min_w == 1152
    assert min_h == 648
    ratio_min = min_w / min_h
    assert ratio_min == pytest.approx(16.0 / 9.0, rel=1e-3)

    # Layout minimumSizeHint must fit within 1152x648 so standard 16:9 monitors don't clip
    hint_w = win.minimumSizeHint().width()
    hint_h = win.minimumSizeHint().height()
    assert hint_w <= 1152
    assert hint_h <= 648

    win.close()


def test_reset_to_16_9_ratio_presets(qapp):
    """Verifies aspect ratio preset resets (1280x720, 1440x810, 1600x900) preserve exact 16:9 geometry."""
    win = MainWindow()

    # Compact 16:9 (720p HD)
    win.reset_to_16_9_ratio(1280)
    assert win.width() == 1280
    assert win.height() == 720
    assert (win.width() / win.height()) == pytest.approx(16.0 / 9.0, rel=1e-3)

    # Large 16:9 (900p HD+)
    win.reset_to_16_9_ratio(1600)
    assert win.width() == 1600
    assert win.height() == 900
    assert (win.width() / win.height()) == pytest.approx(16.0 / 9.0, rel=1e-3)

    # Standard 16:9 (1440x810)
    win.reset_to_16_9_ratio(1440)
    assert win.width() == 1440
    assert win.height() == 810
    assert (win.width() / win.height()) == pytest.approx(16.0 / 9.0, rel=1e-3)

    win.close()


def test_toolbar_and_viewport_responsive_layout(qapp):
    """Verifies that toolbars and viewport inspection bar fit cleanly on 16:9 screens."""
    win = MainWindow()

    # Verify 2-row toolbar architecture exists
    assert hasattr(win, "toolbar")
    assert hasattr(win, "sim_toolbar")
    assert win.toolbar is not None
    assert win.sim_toolbar is not None

    # Both toolbars must have sizeHint widths under 1150px
    assert win.toolbar.sizeHint().width() < 1150
    assert win.sim_toolbar.sizeHint().width() < 1150

    # Viewport inspection bar must be hosted inside a QScrollArea
    assert hasattr(win.viewport_3d, "control_scroll")
    assert win.viewport_3d.control_scroll is not None
    assert win.viewport_3d.control_scroll.height() <= 42

    win.close()

