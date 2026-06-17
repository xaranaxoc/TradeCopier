"""
palette — centralised colour & font definitions for FTH Trade Copier themes.

Every UI colour and font tuple used by the application is defined here as
a field on a frozen dataclass.  The rest of the code reads the *current*
palette/fonts through the module-level accessors ``get_palette()`` and
``get_fonts()``.  Switching to another theme is a single call to
``set_theme(name)`` (takes effect on next app startup — runtime
hot-switch is not yet supported).

Adding a new theme
------------------
1. Create a new ``Palette(...)`` instance in ``PALETTES``.
2. Optionally create a matching ``Fonts(...)`` in ``FONTS`` (or reuse the
   default).
3. Register both in ``THEMES``.

That's it — the rest of the app picks up the new colours automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

# ── Palette dataclass ────────────────────────────────────────────────

@dataclass(frozen=True)
class Palette:
    """Complete set of semantic colour tokens for one theme."""

    # Backgrounds
    BG_DEEP: str
    BG: str
    BG_ROW: str
    BG_ROW_HOVER: str
    BG_INPUT: str
    BG_HEADER: str

    # Foregrounds
    FG: str
    FG_DIM: str
    FG_LABEL: str
    FG_MUTED: str

    # Accent
    ACCENT: str
    ACCENT_H: str       # hover
    ACCENT_DIM: str
    ACCENT_FG: str      # text colour on accent-background buttons
    CYAN_GLOW: str

    # Semantic colours
    GREEN: str
    GREEN_DIM: str
    GREEN_GLOW: str
    RED: str
    RED_DIM: str
    RED_GLOW: str
    YELLOW: str
    YELLOW_DIM: str

    # Borders / dividers
    BORDER: str
    BORDER_LIGHT: str
    DIVIDER: str


# ── Fonts dataclass ──────────────────────────────────────────────────

FontTuple = Tuple  # e.g. ("Segoe UI", 9) or ("Segoe UI", 9, "bold")


@dataclass(frozen=True)
class Fonts:
    """Complete set of font tuples for one theme."""

    TITLE: FontTuple
    VAL: FontTuple
    VAL_BOLD: FontTuple
    MONO: FontTuple
    MONO_SM: FontTuple
    DEFAULT: FontTuple
    BOLD: FontTuple
    SM: FontTuple
    XS: FontTuple


# ── Built-in palettes ───────────────────────────────────────────────

NEON_CYAN = Palette(
    BG_DEEP="#080810",
    BG="#0C0C14",
    BG_ROW="#111119",
    BG_ROW_HOVER="#171722",
    BG_INPUT="#191924",
    BG_HEADER="#0E0E18",
    FG="#E4E4EE",
    FG_DIM="#6A6A80",
    FG_LABEL="#8888A0",
    FG_MUTED="#3A3A50",
    ACCENT="#00B4D8",
    ACCENT_H="#00D0F0",
    ACCENT_DIM="#006E88",
    ACCENT_FG="#FFFFFF",
    CYAN_GLOW="#002933",
    GREEN="#00E676",
    GREEN_DIM="#00B85E",
    GREEN_GLOW="#003318",
    RED="#FF3D57",
    RED_DIM="#CC3044",
    RED_GLOW="#330D14",
    YELLOW="#FFB020",
    YELLOW_DIM="#CC8D1A",
    BORDER="#1C1C2C",
    BORDER_LIGHT="#252538",
    DIVIDER="#111120",
)

WARM_DARK = Palette(
    BG_DEEP="#0D0A08",
    BG="#12100E",
    BG_ROW="#181614",
    BG_ROW_HOVER="#201E1A",
    BG_INPUT="#221F1B",
    BG_HEADER="#100E0C",
    FG="#E8E0D8",
    FG_DIM="#7A7068",
    FG_LABEL="#9A8E84",
    FG_MUTED="#4A4038",
    ACCENT="#E8963A",
    ACCENT_H="#F0AA52",
    ACCENT_DIM="#8A5A22",
    ACCENT_FG="#FFFFFF",
    CYAN_GLOW="#2A1A08",
    GREEN="#4ADE80",
    GREEN_DIM="#38B866",
    GREEN_GLOW="#0A2A12",
    RED="#F87171",
    RED_DIM="#C55050",
    RED_GLOW="#2A0E0E",
    YELLOW="#FBBF24",
    YELLOW_DIM="#C99A1C",
    BORDER="#2A2420",
    BORDER_LIGHT="#342E28",
    DIVIDER="#1A1614",
)

# ── Built-in font sets ──────────────────────────────────────────────

DEFAULT_FONTS = Fonts(
    TITLE=("Segoe UI", 15, "bold"),
    VAL=("Segoe UI", 11),
    VAL_BOLD=("Segoe UI", 11, "bold"),
    MONO=("Cascadia Mono", 9),
    MONO_SM=("Cascadia Mono", 8),
    DEFAULT=("Segoe UI", 9),
    BOLD=("Segoe UI", 9, "bold"),
    SM=("Segoe UI", 8),
    XS=("Segoe UI", 7),
)

# ── Theme registry ──────────────────────────────────────────────────

@dataclass(frozen=True)
class Theme:
    palette: Palette
    fonts: Fonts


THEMES: Dict[str, Theme] = {
    "neon_cyan": Theme(palette=NEON_CYAN, fonts=DEFAULT_FONTS),
    "warm_dark": Theme(palette=WARM_DARK, fonts=DEFAULT_FONTS),
}

DEFAULT_THEME = "neon_cyan"

# ── Global state & accessors ────────────────────────────────────────

_current_theme_name: str = DEFAULT_THEME


def set_theme(name: str) -> None:
    """Select the active theme by name.  Call before building the UI."""
    global _current_theme_name
    if name not in THEMES:
        raise ValueError(
            f"Unknown theme '{name}'. Available: {', '.join(THEMES)}"
        )
    _current_theme_name = name


def get_theme_name() -> str:
    """Return the name of the currently active theme."""
    return _current_theme_name


def get_palette() -> Palette:
    """Return the active colour palette."""
    return THEMES[_current_theme_name].palette


def get_fonts() -> Fonts:
    """Return the active font set."""
    return THEMES[_current_theme_name].fonts


def available_themes() -> list[str]:
    """Return a sorted list of registered theme names."""
    return sorted(THEMES.keys())


__all__ = [
    "Palette", "Fonts", "Theme",
    "get_palette", "get_fonts", "set_theme",
    "get_theme_name", "available_themes",
    "NEON_CYAN", "WARM_DARK", "DEFAULT_FONTS",
]
