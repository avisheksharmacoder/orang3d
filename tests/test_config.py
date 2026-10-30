"""
Unit tests for configuration, theme registry, regional standards, and immutability (Phase 1).
"""

import pytest
from orang3d.config import (
    APP_NAME,
    APP_VERSION,
    THEME,
    VIEWPORT_COLORS,
    SAFETY_THRESHOLDS,
    ThemeMode,
    get_theme,
    RegionalStandard,
    get_safety_thresholds,
)


def test_theme_mode_retrieval():
    dark_theme = get_theme(ThemeMode.DARK)
    assert dark_theme["background_dark"] == "#121417"
    assert "accent_orange" in dark_theme

    light_theme = get_theme(ThemeMode.LIGHT)
    assert light_theme["background_dark"] != dark_theme["background_dark"]
    assert "accent_orange" in light_theme

    # String input support
    assert get_theme("dark")["background_dark"] == dark_theme["background_dark"]
    assert get_theme("light")["background_dark"] == light_theme["background_dark"]

    with pytest.raises(ValueError, match="Unknown theme mode"):
        get_theme("cyberpunk_neon")


def test_regional_standards_thresholds():
    # Eurocode 7
    ec7 = get_safety_thresholds(RegionalStandard.EUROCODE_7)
    assert ec7["sliding_static"] == pytest.approx(1.1)
    assert ec7["sliding_seismic"] == pytest.approx(1.0)
    assert ec7["overturning_static"] == pytest.approx(1.3)
    assert ec7["overturning_seismic"] == pytest.approx(1.0)

    # AASHTO LRFD
    aashto = get_safety_thresholds(RegionalStandard.AASHTO_LRFD)
    assert aashto["sliding_static"] == pytest.approx(1.5)
    assert aashto["sliding_seismic"] == pytest.approx(1.1)

    # IS 14458 (Indian Standards)
    is_code = get_safety_thresholds(RegionalStandard.IS_14458)
    assert is_code["sliding_static"] == pytest.approx(1.5)
    assert is_code["sliding_seismic"] == pytest.approx(1.2)
    assert is_code["overturning_static"] == pytest.approx(2.0)
    assert is_code["overturning_seismic"] == pytest.approx(1.5)

    # String lookup
    assert get_safety_thresholds("eurocode_7") == ec7
    assert get_safety_thresholds("aashto_lrfd") == aashto
    assert get_safety_thresholds("is_14458") == is_code

    with pytest.raises(ValueError, match="Unknown regional standard"):
        get_safety_thresholds("mars_standard")


def test_config_immutability_and_protection():
    # Mutating returned dictionary from get_theme must not alter default registry
    theme = get_theme(ThemeMode.DARK)
    original_bg = theme["background_dark"]
    theme["background_dark"] = "#ffffff"
    fresh_theme = get_theme(ThemeMode.DARK)
    assert fresh_theme["background_dark"] == original_bg

    # Mutating returned thresholds must not mutate default registry
    thresholds = get_safety_thresholds(RegionalStandard.AASHTO_LRFD)
    original_sliding = thresholds["sliding_static"]
    thresholds["sliding_static"] = 99.0
    fresh_thresholds = get_safety_thresholds(RegionalStandard.AASHTO_LRFD)
    assert fresh_thresholds["sliding_static"] == original_sliding
