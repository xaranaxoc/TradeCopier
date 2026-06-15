"""
theme.py — design tokens for FTH Trade Copier.

Single source of truth for colors, spacing, radii and typography.
Imported by gui.py; gui.py keeps the old constant names as aliases
so existing code keeps working unchanged.

Phase 1 of the UI polish series (feat/ui-polish).
"""

import os
import sys
import ctypes
import tkinter.font as tkfont


# ── COLORS ─────────────────────────────────────────────────
# Semantic surfaces (background layers, from darkest to lightest)
SURFACE_0 = "#080810"   # window root (BG_DEEP)
SURFACE_1 = "#0C0C14"   # base body (BG)
SURFACE_2 = "#11111C"   # cards (CARD_BG)
SURFACE_3 = "#181826"   # hover / nested elevation (CARD_BG_HOVER)
SURFACE_INPUT = "#191924"  # input fields (BG_INPUT)
SURFACE_ROW = "#111119"    # table row idle (BG_ROW)
SURFACE_ROW_HOVER = "#171722"  # table row hover (BG_ROW_HOVER)
SURFACE_HEADER = "#0E0E18"  # header strip (BG_HEADER)

# Borders / dividers
BORDER_SOFT = "#1F1F30"     # cards (SOFT_BORDER)
BORDER_DEFAULT = "#1C1C2C"  # default (BORDER)
BORDER_STRONG = "#252538"   # accented (BORDER_LIGHT)
DIVIDER = "#111120"

# Text
TEXT_PRIMARY = "#E4E4EE"     # FG
TEXT_SECONDARY = "#8888A0"   # FG_LABEL
TEXT_TERTIARY = "#6A6A80"    # FG_DIM
TEXT_DISABLED = "#3A3A50"    # FG_MUTED

# Accent (cyan family — locked, per user)
ACCENT = "#00B4D8"
ACCENT_HOVER = "#00D0F0"
ACCENT_DIM = "#006E88"
ACCENT_GLOW = "#002933"

# Status colors
STATUS_OK = "#00E676"
STATUS_OK_DIM = "#00B85E"
STATUS_OK_GLOW = "#003318"

STATUS_ERR = "#FF3D57"
STATUS_ERR_DIM = "#CC3044"
STATUS_ERR_GLOW = "#330D14"

STATUS_WARN = "#FFB020"
STATUS_WARN_DIM = "#CC8D1A"

STATUS_INFO = ACCENT


# ── SPACING SCALE ──────────────────────────────────────────
# Use these everywhere instead of magic numbers.
SP_XS = 4
SP_SM = 8
SP_MD = 12
SP_LG = 16
SP_XL = 20
SP_XXL = 24
SP_XXXL = 32


# ── RADII ──────────────────────────────────────────────────
RADIUS_CARD = 14   # large cards
RADIUS_CTRL = 10   # buttons, inputs, dropdowns
RADIUS_CHIP = 6    # chips, badges, tags


# ── TYPOGRAPHY ─────────────────────────────────────────────
# Logical sizes (px @ 96dpi); actual scaling is handled by
# ctk.set_widget_scaling() applied at app startup.

# Font family preferences. Inter is bundled in img/fonts/ and registered at
# startup; on Windows that makes "Inter" available to Tk. Segoe UI is the
# fallback for systems where registration didn't take.
SANS_PREFS = ["Inter", "Inter Variable", "Segoe UI Variable",
              "Segoe UI", "Roboto", "DejaVu Sans"]
SANS_BOLD_PREFS = ["Inter", "Inter Variable", "Segoe UI Variable",
                   "Segoe UI Semibold", "Segoe UI", "Roboto Medium",
                   "DejaVu Sans", "Arial"]
SANS_BLACK_PREFS = ["Inter", "Inter Variable", "Segoe UI Black",
                    "Arial Black", "DejaVu Sans"]
MONO_PREFS = ["Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono"]
ICON_PREFS = ["Phosphor", "Phosphor-Regular"]


# Typography ramp — (logical_size, weight_token).
# weight_token: "normal" / "bold" — Tk only honours those two reliably,
# so 600/700 collapse to "bold" and 400/500 collapse to "normal".
T_DISPLAY  = (28, "bold")    # KPI values, big numbers
T_TITLE    = (17, "bold")    # app title in header
T_HEADING  = (13, "bold")    # section headings (MASTER, SLAVE ACCOUNTS)
T_BODY     = (12, "normal")  # default body text
T_LABEL    = (10, "bold")    # ALL-CAPS micro-labels (LOGIN, БАЛАНС)
T_MICRO    = (9,  "normal")  # hints, super-fine print
T_MONO     = (11, "normal")  # numbers and log


# ── PHOSPHOR ICON GLYPHS ───────────────────────────────────
# Useful subset; codepoints from Phosphor Icons 2.x.
# Use as IconButton(parent, glyph=ICON_GEAR).
ICON_GEAR        = "\ue3a4"  # gear (settings)
ICON_INFO        = "\ue450"  # info circle
ICON_PLAY        = "\ue5b0"  # play
ICON_STOP        = "\ue65c"  # stop (square)
ICON_PLUS        = "\ue5bc"  # plus
ICON_X           = "\ue19c"  # x
ICON_TRASH       = "\ue6c4"  # trash
ICON_CHART       = "\ue160"  # chart-line-up
ICON_WARNING     = "\ue730"  # warning
ICON_PENCIL      = "\ue598"  # pencil
ICON_FOLDER      = "\ue3b8"  # folder-open
ICON_DOWNLOAD    = "\ue2dc"  # download
ICON_REFRESH     = "\ue05c"  # arrows-clockwise
ICON_SEARCH      = "\ue608"  # magnifying-glass
ICON_FILTER      = "\ue394"  # funnel
ICON_DOTS        = "\ue2c4"  # dots-three-vertical
ICON_CHEVRON_DN  = "\ue1c0"  # caret-down
ICON_CHEVRON_RT  = "\ue1cc"  # caret-right


# ── FONT REGISTRATION ──────────────────────────────────────
_FONT_DIR = None
_FONTS_REGISTERED = False


def _font_dir():
    """Return absolute path to img/fonts directory (bundled or dev)."""
    global _FONT_DIR
    if _FONT_DIR is not None:
        return _FONT_DIR
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        bundle = os.path.dirname(os.path.abspath(__file__))
    _FONT_DIR = os.path.join(bundle, "img", "fonts")
    return _FONT_DIR


def register_bundled_fonts():
    """Register bundled .ttf fonts with the OS so Tk can use them by name.

    Windows: uses AddFontResourceEx with FR_PRIVATE so the install is
    process-scoped (no admin, no permanent install). Other platforms get
    a best-effort no-op — they should already have Segoe UI/Inter via
    fallbacks.
    """
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    _FONTS_REGISTERED = True

    fdir = _font_dir()
    if not os.path.isdir(fdir):
        return

    if sys.platform.startswith("win"):
        try:
            FR_PRIVATE = 0x10
            gdi32 = ctypes.windll.gdi32
            for name in os.listdir(fdir):
                if name.lower().endswith(".ttf"):
                    path = os.path.join(fdir, name)
                    try:
                        gdi32.AddFontResourceExW(path, FR_PRIVATE, 0)
                    except Exception:
                        pass
        except Exception:
            # Non-fatal — fallbacks still work.
            pass


def pick_font(prefs, fallback="TkDefaultFont"):
    """First available font family from prefs, or fallback."""
    try:
        available = set(tkfont.families())
    except Exception:
        return prefs[0] if prefs else fallback
    for name in prefs:
        if name in available:
            return name
    return fallback


def resolve_font_families():
    """Pick sans-regular, sans-bold, sans-black, mono, icon families."""
    return (
        pick_font(SANS_PREFS),
        pick_font(SANS_BOLD_PREFS),
        pick_font(SANS_BLACK_PREFS),
        pick_font(MONO_PREFS),
        pick_font(ICON_PREFS),
    )


# ── DPI SCALING ────────────────────────────────────────────
def compute_dpi_scale(tk_root):
    """Compute a CustomTkinter scale factor based on screen DPI.

    Clamped to [0.85, 2.0]. CTk applies it to widget sizes, fonts and
    window geometry via set_widget_scaling/set_window_scaling.
    """
    try:
        dpi = float(tk_root.winfo_fpixels("1i"))
    except Exception:
        dpi = 96.0
    scale = dpi / 96.0
    if scale < 0.85:
        scale = 0.85
    elif scale > 2.0:
        scale = 2.0
    return scale


def apply_dpi_scaling(tk_root, ctk_module):
    """Compute and apply DPI scaling to a CustomTkinter app."""
    scale = compute_dpi_scale(tk_root)
    try:
        ctk_module.set_widget_scaling(scale)
        ctk_module.set_window_scaling(scale)
    except Exception:
        pass
    return scale


# ── TABULAR NUMERALS ───────────────────────────────────────
def configure_tabular_numerals(family, size, weight="normal"):
    """Return a tkfont.Font configured for tabular (monospaced) digits.

    Inter exposes `tnum` via the OpenType `tnum` feature; we can't toggle
    that from Tk directly, but Inter Display defaults to proportional
    digits and Inter has tnum off by default. As a robust fallback we
    just hand back a Font tuple — caller can opt into the mono family
    for KPI values by using MONO_PREFS instead.
    """
    return tkfont.Font(family=family, size=size, weight=weight)
