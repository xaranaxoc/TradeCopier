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

LIGHT_PRO = Palette(
    # MetaTrader 5 styled light theme.
    # Mirrors MT5's default look: Windows-gray chrome, white tables with
    # black text, classic blue accent/selection, saturated green/red for
    # bull/bear (profit/loss).
    BG_DEEP="#F0F0F0",      # window chrome (Windows control gray)
    BG="#F0F0F0",           # frames / panels
    BG_ROW="#FFFFFF",       # market-watch / trade tables
    BG_ROW_HOVER="#CCE4F7", # classic Windows light-blue selection
    BG_INPUT="#FFFFFF",     # entry / combobox
    BG_HEADER="#E5E5E5",    # column header bar
    FG="#000000",           # primary text — black like MT5
    FG_DIM="#555555",       # secondary text
    FG_LABEL="#404040",     # field labels
    FG_MUTED="#808080",     # disabled / muted
    ACCENT="#2A5DB0",       # MT5 brand blue (toolbar / links)
    ACCENT_H="#1E4A8F",     # darker blue on hover
    ACCENT_DIM="#A8C5E8",   # disabled blue
    ACCENT_FG="#FFFFFF",    # text on blue buttons
    CYAN_GLOW="#DEECF9",    # light-blue badge background
    GREEN="#008000",        # MT5 bull / profit (saturated green)
    GREEN_DIM="#006400",    # darker green
    GREEN_GLOW="#E6F5E6",   # profit badge background
    RED="#C00000",          # MT5 bear / loss (saturated red)
    RED_DIM="#A00000",      # darker red
    RED_GLOW="#FCE6E6",     # loss badge background
    YELLOW="#C08000",       # amber / warning (MT5-style)
    YELLOW_DIM="#A06800",
    BORDER="#CCCCCC",       # standard Windows border
    BORDER_LIGHT="#DDDDDD",
    DIVIDER="#E5E5E5",
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
    "light_pro": Theme(palette=LIGHT_PRO, fonts=DEFAULT_FONTS),
}

# Human-readable names for the theme picker UI.
THEME_LABELS: Dict[str, str] = {
    "neon_cyan": "Neon Cyan (тёмная)",
    "light_pro": "Light Pro (MetaTrader 5)",
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


# ── ttk style helper ─────────────────────────────────────────────────

def apply_ttk_styles(
    scale_fn=None,
    *,
    palette: Palette | None = None,
    fonts: Fonts | None = None,
) -> None:
    """Configure ttk Treeview and Notebook styles from the active palette.

    Call once after the Tk root exists.

    Parameters
    ----------
    scale_fn : callable, optional
        DPI-scaling function (e.g. ``ui_scaling.scale``).  If *None*,
        raw pixel values are used.
    palette / fonts : override the current theme (mainly for tests).
    """
    from tkinter import ttk

    pal = palette or get_palette()
    fnt = fonts or get_fonts()
    s = scale_fn or (lambda x: x)

    style = ttk.Style()
    style.theme_use("clam")

    # Treeview (trades table)
    style.configure(
        "T.Treeview",
        background=pal.BG_ROW,
        foreground=pal.FG,
        fieldbackground=pal.BG_ROW,
        font=fnt.MONO_SM,
        rowheight=s(17),
        borderwidth=0,
    )
    style.configure(
        "T.Treeview.Heading",
        background=pal.BG_INPUT,
        foreground=pal.FG_DIM,
        font=fnt.XS,
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "T.Treeview",
        background=[("selected", pal.ACCENT)],
        foreground=[("selected", pal.ACCENT_FG)],
    )
    style.map("T.Treeview.Heading", background=[("active", pal.BG_ROW_HOVER)])

    # Notebook (bottom tabs: Сделки / Лог)
    style.configure("TNotebook", background=pal.BG_DEEP, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=pal.BG_INPUT,
        foreground=pal.FG_DIM,
        padding=[12, 3],
        font=fnt.SM,
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", pal.BG_ROW)],
        foreground=[("selected", pal.FG)],
    )


__all__ = [
    "Palette", "Fonts", "Theme",
    "get_palette", "get_fonts", "set_theme",
    "get_theme_name", "available_themes",
    "apply_ttk_styles",
    "NEON_CYAN", "LIGHT_PRO", "DEFAULT_FONTS",
    "THEME_LABELS",
]
