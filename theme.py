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

# Phase 6: accent-пресеты для пользовательских настроек. Cyan — дефолт.
ACCENT_PRESETS = {
    "cyan": {
        "ACCENT": "#00B4D8", "ACCENT_HOVER": "#00D0F0",
        "ACCENT_DIM": "#006E88", "ACCENT_GLOW": "#002933",
    },
    "teal": {
        "ACCENT": "#14B8A6", "ACCENT_HOVER": "#2DD4BF",
        "ACCENT_DIM": "#0F7E72", "ACCENT_GLOW": "#0B2A26",
    },
    "violet": {
        "ACCENT": "#8B5CF6", "ACCENT_HOVER": "#A78BFA",
        "ACCENT_DIM": "#5B3FA0", "ACCENT_GLOW": "#1E1339",
    },
    "amber": {
        "ACCENT": "#F59E0B", "ACCENT_HOVER": "#FBBF24",
        "ACCENT_DIM": "#A56708", "ACCENT_GLOW": "#3A2502",
    },
}

# Status colors
STATUS_OK = "#00E676"
STATUS_OK_DIM = "#00B85E"
STATUS_OK_GLOW = "#003318"

STATUS_ERR = "#FF3D57"
STATUS_ERR_DIM = "#CC3044"
STATUS_ERR_GLOW = "#330D14"

STATUS_WARN = "#FFB020"
STATUS_WARN_DIM = "#CC8D1A"
STATUS_WARN_GLOW = "#3B2A07"

STATUS_INFO = ACCENT
STATUS_INFO_GLOW = ACCENT_GLOW


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


# ── CONTROL SIZE SYSTEM ────────────────────────────────────
# Use a single height for inputs and buttons that sit next to each
# other in a toolbar/header row. Mixing 28/30/32/34 px controls in
# the same row looks broken (Vitaliy, 2026-06-15).
CTRL_H_LG = 36     # primary buttons, header actions, master entry
CTRL_H_MD = 32     # secondary controls in tighter rows
CTRL_H_SM = 28     # chips, micro-toolbar

# Default min width for primary text buttons. Linear/Notion-style.
BTN_PRIMARY_MIN_W = 108


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
# Phosphor Icons v2.1 (Tobias Fried & Helena Zhang, IcoMoon build).
# Codepoints VERIFIED against @phosphor-icons/web@2.1.1 CSS mapping
# AND against the bundled `img/fonts/Phosphor-Regular.ttf` cmap.
# DO NOT GUESS — verify any new icon with:
#     from fontTools.ttLib import TTFont
#     0xXXXX in TTFont('img/fonts/Phosphor-Regular.ttf').getBestCmap()
ICON_GEAR        = "\ue270"  # gear
ICON_INFO        = "\ue2ce"  # info  (⚠ \ue450 is speaker-simple-high!)
ICON_PLAY        = "\ue3d0"  # play
ICON_STOP        = "\ue46c"  # stop
ICON_PLUS        = "\ue3d4"  # plus
ICON_X           = "\ue4f6"  # x
ICON_TRASH       = "\ue4a6"  # trash
ICON_CHART       = "\ue156"  # chart-line-up
ICON_WARNING     = "\ue4e0"  # warning
ICON_PENCIL      = "\ue3ae"  # pencil
ICON_FOLDER      = "\ue256"  # folder-open
ICON_DOWNLOAD    = "\ue20a"  # download
ICON_REFRESH     = "\ue094"  # arrows-clockwise
ICON_SEARCH      = "\ue30c"  # magnifying-glass
ICON_FILTER      = "\ue266"  # funnel
ICON_DOTS        = "\ue208"  # dots-three-vertical
ICON_CHEVRON_DN  = "\ue136"  # caret-down
ICON_CHEVRON_RT  = "\ue13a"  # caret-right
ICON_COPY        = "\ue1ca"  # copy
ICON_HOUSE       = "\ue2c2"  # house
ICON_QUESTION    = "\ue3e8"  # question
ICON_POWER       = "\ue3da"  # power
ICON_SLIDERS     = "\ue434"  # sliders-horizontal
ICON_SPARKLE     = "\ue6a2"  # sparkle
ICON_TARGET      = "\ue47c"  # target
ICON_LIGHTNING   = "\ue2de"  # lightning
ICON_SIGN_OUT    = "\ue42a"  # sign-out


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


# ── PREFERENCES ────────────────────────────────────────────
# Phase 6: чтение/применение пользовательских предпочтений.
def apply_accent_preset(name: str) -> None:
    """Изменяет ACCENT/ACCENT_HOVER/ACCENT_DIM/ACCENT_GLOW под выбранный пресет.

    Допустимые имена: cyan (default), teal, violet, amber.
    Неизвестные имена игнорируются.
    """
    global ACCENT, ACCENT_HOVER, ACCENT_DIM, ACCENT_GLOW
    preset = ACCENT_PRESETS.get((name or "").lower())
    if not preset:
        return
    ACCENT = preset["ACCENT"]
    ACCENT_HOVER = preset["ACCENT_HOVER"]
    ACCENT_DIM = preset["ACCENT_DIM"]
    ACCENT_GLOW = preset["ACCENT_GLOW"]


def apply_preferences_from_file(config_path: str) -> dict:
    """Считывает блок ``preferences`` из config.json (если есть) и применяет.

    Безопасно к отсутствию файла / битому JSON / отсутствию блока.
    Возвращает словарь применённых настроек или пустой dict.
    """
    import json
    import os

    prefs: dict = {}
    try:
        if not config_path or not os.path.exists(config_path):
            return {}
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        prefs = data.get("preferences") or {}
        if not isinstance(prefs, dict):
            return {}
    except Exception:
        return {}
    accent = prefs.get("accent")
    if isinstance(accent, str):
        apply_accent_preset(accent)
    return prefs


def get_user_scale_factor(prefs: dict) -> float:
    """Возвращает множитель из ``preferences.font_scale`` (clamp 0.8..1.3)."""
    try:
        v = float(prefs.get("font_scale", 1.0))
    except Exception:
        v = 1.0
    if v < 0.8:
        v = 0.8
    if v > 1.3:
        v = 1.3
    return v
