"""
Global configuration, theme colors, regional geotechnical standards, and defaults for orang3D.
Phase 1: Architecture, Core Typing & Configuration Registry.
"""

from enum import Enum
from typing import Dict, Union
import copy

# App branding
APP_NAME = "orang3D"
APP_SUBTITLE = "Seismic & Disaster Retaining Wall Analyzer"
APP_VERSION = "0.1.0"


class ThemeMode(str, Enum):
    """Supported UI themes."""
    DARK = "dark"
    LIGHT = "light"


# Modern Dark Engineering Theme Palette
THEME_DARK: Dict[str, str] = {
    "background_dark": "#121417",
    "surface_dark": "#1a1d24",
    "surface_elevated": "#232833",
    "border": "#2e3442",
    "accent_orange": "#ff6b35",
    "accent_orange_hover": "#ff8354",
    "accent_blue": "#00a6fb",
    "accent_green": "#06d6a0",
    "accent_red": "#ef476f",
    "accent_yellow": "#ffd166",
    "text_primary": "#f1f3f5",
    "text_secondary": "#9ba3b4",
    "text_muted": "#5f687a",
}

# Clean High-Contrast Light Theme Palette
THEME_LIGHT: Dict[str, str] = {
    "background_dark": "#f8f9fa",
    "surface_dark": "#ffffff",
    "surface_elevated": "#e9ecef",
    "border": "#ced4da",
    "accent_orange": "#e8590c",
    "accent_orange_hover": "#d9480f",
    "accent_blue": "#1971c2",
    "accent_green": "#2f9e44",
    "accent_red": "#e03131",
    "accent_yellow": "#f59f00",
    "text_primary": "#212529",
    "text_secondary": "#495057",
    "text_muted": "#868e96",
}

THEMES = {
    ThemeMode.DARK: THEME_DARK,
    ThemeMode.LIGHT: THEME_LIGHT,
}

# 3D Viewport Material & Color Scheme
VIEWPORT_COLORS: Dict[str, str] = {
    "background": "#0b0f19",
    "wall_concrete": "#e2e8f0",      # Architectural cast-in-place reinforced concrete
    "rebar_highlight": "#ef4444",    # High-visibility reinforcement steel
    "backfill_soil": "#d4a373",      # Rich warm golden sand / compacted gravel fill
    "foundation_soil": "#475569",    # Deep cool slate bedrock / dense foundation till
    "water_plane": "#0284c7",        # Shimmering aquatic blue with wave caustics
    "failure_wedge": "#f43f5e",      # Vivid shear rupture slip zone
    "contact_vector": "#38bdf8",     # Cyan contact thrust
    "bearing_vector": "#34d399",     # Emerald foundation bearing
    "strut_steel": "#0284c7",        # High-tensile structural steel
    "bored_pile": "#64748b",         # Cast-in-situ reinforced concrete pile
    "grid": "#1e293b",
}


class RegionalStandard(str, Enum):
    """Regional geotechnical building codes and design specifications."""
    EUROCODE_7 = "eurocode_7"
    AASHTO_LRFD = "aashto_lrfd"
    IS_14458 = "is_14458"
    ACI_318 = "aci_318"
    STANDARD = "standard"


# Safety Factor Thresholds by Regional Standard
REGIONAL_SAFETY_STANDARDS: Dict[RegionalStandard, Dict[str, float]] = {
    RegionalStandard.STANDARD: {
        "sliding_static": 1.5,
        "sliding_seismic": 1.1,
        "overturning_static": 2.0,
        "overturning_seismic": 1.2,
        "bearing_static": 3.0,
        "bearing_seismic": 2.0,
    },
    RegionalStandard.EUROCODE_7: {
        "sliding_static": 1.1,
        "sliding_seismic": 1.0,
        "overturning_static": 1.3,
        "overturning_seismic": 1.0,
        "bearing_static": 1.4,
        "bearing_seismic": 1.0,
    },
    RegionalStandard.AASHTO_LRFD: {
        "sliding_static": 1.5,
        "sliding_seismic": 1.1,
        "overturning_static": 2.0,
        "overturning_seismic": 1.2,
        "bearing_static": 2.5,
        "bearing_seismic": 1.5,
    },
    RegionalStandard.IS_14458: {
        "sliding_static": 1.5,
        "sliding_seismic": 1.2,
        "overturning_static": 2.0,
        "overturning_seismic": 1.5,
        "bearing_static": 3.0,
        "bearing_seismic": 2.0,
    },
    RegionalStandard.ACI_318: {
        "sliding_static": 1.5,
        "sliding_seismic": 1.1,
        "overturning_static": 2.0,
        "overturning_seismic": 1.2,
        "bearing_static": 3.0,
        "bearing_seismic": 2.0,
    },
}


def get_theme(mode: Union[ThemeMode, str] = ThemeMode.DARK) -> Dict[str, str]:
    """
    Returns an isolated copy of the requested theme palette to prevent accidental runtime mutations.
    """
    try:
        theme_key = ThemeMode(mode)
    except ValueError:
        raise ValueError(f"Unknown theme mode: '{mode}'. Valid modes: {[m.value for m in ThemeMode]}")
    return copy.deepcopy(THEMES[theme_key])


def get_safety_thresholds(
    standard: Union[RegionalStandard, str] = RegionalStandard.STANDARD
) -> Dict[str, float]:
    """
    Returns an isolated copy of safety factor thresholds according to the specified regional standard.
    """
    try:
        std_key = RegionalStandard(standard)
    except ValueError:
        raise ValueError(
            f"Unknown regional standard: '{standard}'. Valid standards: {[s.value for s in RegionalStandard]}"
        )
    return copy.deepcopy(REGIONAL_SAFETY_STANDARDS[std_key])


# Backward-compatible global aliases
THEME = THEME_DARK
SAFETY_THRESHOLDS = REGIONAL_SAFETY_STANDARDS[RegionalStandard.STANDARD]
