"""
palette — centralised colour & font definitions for FTH Trade Copier themes.

Every UI colour and font tuple used by the application is defined here as
a field on a frozen dataclass.  The rest of the code reads the *current*
palette/fonts either through:

  * ``palette_proxy`` / ``fonts_proxy`` — lazy proxies whose attribute
    access forwards to the *currently active* theme.  This is what
    ``gui.py`` binds to ``p`` / ``f`` so widgets built later transparently
    pick up the active theme.
  * ``get_palette()`` / ``get_fonts()`` — return the current dataclass
    instance (use this when you need to enumerate fields).

Switching themes
----------------
``set_theme(name)`` activates a theme.  After it returns, every future
``p.X`` access yields the new value, but widgets already on screen still
carry the OLD colours.  To repaint them, call::

    old = get_palette()
    set_theme(new_name)
    apply_ttk_styles(scale_fn=...)
    remap_widget_colors(root, build_remap(old, get_palette()))

Adding a builtin theme
----------------------
Declare a ``Palette(...)`` instance, then ``register_theme("my_name",
my_palette, label="My Name", appearance="dark" or "light")``.

Custom (user-defined) themes
----------------------------
``register_theme`` is also the entry point for runtime/user-defined
themes.  Persisted custom themes are stored as JSON via
``save_custom_themes(path)`` / ``load_custom_themes(path)``.  Only
non-builtin themes are persisted; builtins live in code.
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


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

    # ── Soft-design tokens ──────────────────────────────────────────
    # Optional with sensible defaults so existing builtin themes
    # (NEON_CYAN, LIGHT_PRO) keep working without changes. The
    # ``Light Soft`` redesign theme overrides these for tinted icon
    # circles, P&L row tints and rounded-corner widgets.

    # Tinted backgrounds for icon circles / row stripes (BUY/SELL etc.)
    TINT_BLUE: str = "#EFF6FF"
    TINT_PURPLE: str = "#F5F3FF"
    TINT_GREEN: str = "#ECFDF5"
    TINT_ORANGE: str = "#FFF7ED"
    TINT_RED: str = "#FEF2F2"

    # Foreground colours for chips/badges over the tinted backgrounds.
    TINT_BLUE_FG: str = "#2563EB"
    TINT_PURPLE_FG: str = "#7C3AED"
    TINT_GREEN_FG: str = "#16A34A"
    TINT_ORANGE_FG: str = "#EA580C"
    TINT_RED_FG: str = "#DC2626"

    # Corner radii used by CTk widgets in the redesigned UI. Existing
    # themes keep a small default radius for compatibility; the soft
    # redesign theme bumps these to 8/12/16 for a softer look.
    RADIUS_SM: int = 4
    RADIUS_MD: int = 6
    RADIUS_LG: int = 8
    RADIUS_PILL: int = 999


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
    # Dark counterpart of the soft card-based design.  Same card / radii
    # rhythm as LIGHT_SOFT but inverted for night use: deep slate page,
    # near-black cards with a soft border, cyan accent, saturated semantic
    # colours.  Icon-circle tints are dark-theme variants — saturated hue
    # at ~10% lightness so the icon sits on top of a low-contrast disc
    # that reads as "tinted" without blowing out the dark surface.

    # Backgrounds: page bg slightly lighter than cards so the cards float.
    BG_DEEP="#0A0A14",       # page background (slate-950-ish)
    BG="#0A0A14",            # frames / panels (flat page)
    BG_ROW="#13131F",        # cards, table rows (slate-900)
    BG_ROW_HOVER="#1B1B2A",  # subtle hover on row
    BG_INPUT="#191924",      # entry / combobox
    BG_HEADER="#13131F",     # section header card (same as row card)

    # Foregrounds: high-contrast primary, slate-toned secondary/labels.
    FG="#E8E8F4",            # primary text (slate-100-ish)
    FG_DIM="#7A7A92",        # tertiary text (slate-500)
    FG_LABEL="#9090A8",      # secondary text / labels (slate-400)
    FG_MUTED="#4A4A60",      # muted / disabled

    # Cyan accent stays the brand colour.
    ACCENT="#00B4D8",
    ACCENT_H="#00D0F0",
    ACCENT_DIM="#006E88",
    ACCENT_FG="#FFFFFF",
    CYAN_GLOW="#002933",

    # Saturated semantic colours (unchanged — they're already night-ready).
    GREEN="#00E676",
    GREEN_DIM="#00B85E",
    GREEN_GLOW="#0A2A1A",     # row tint (profit) — deep green wash
    RED="#FF3D57",
    RED_DIM="#CC3044",
    RED_GLOW="#2A0A14",       # row tint (loss) — deep red wash
    YELLOW="#FFB020",
    YELLOW_DIM="#CC8D1A",

    # Borders: thin slate divider visible on both the page and row bg.
    BORDER="#1E1E2E",         # card border
    BORDER_LIGHT="#2A2A3D",   # divider (lighter)
    DIVIDER="#1A1A28",

    # ── Tinted backgrounds for icon circles ────────────────────
    # Dark, saturated hues so the 28 px KPI disc reads as a coloured
    # token against the near-black card.  FG pair is the bright semantic
    # colour so the icon glyph (or its tinted Lucide PNG) pops on top.
    TINT_BLUE="#0B2A3A",       # deep teal-blue, pairs with cyan accent
    TINT_PURPLE="#1F1530",     # deep purple
    TINT_GREEN="#0E2A1F",      # deep green
    TINT_ORANGE="#2E1F0A",     # deep amber
    TINT_RED="#2E0E14",        # deep red

    TINT_BLUE_FG="#00B4D8",    # ACCENT cyan
    TINT_PURPLE_FG="#A78BFA",  # violet-400
    TINT_GREEN_FG="#00E676",   # GREEN
    TINT_ORANGE_FG="#FFB020",  # YELLOW
    TINT_RED_FG="#FF3D57",     # RED

    # ── Radii ──────────────────────────────────────────────
    # Match LIGHT_SOFT so the soft / modern card aesthetic stays
    # consistent when the user toggles between dark and light themes.
    RADIUS_SM=8,
    RADIUS_MD=12,
    RADIUS_LG=16,
    RADIUS_PILL=999,
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

LIGHT_SOFT = Palette(
    # Soft light theme — modern card-based redesign.
    # Reference: ChatGPT-generated mock (see PR description).
    # Page is a soft gray (#F2F4F7), content lives in white rounded
    # cards (#FFFFFF) with thin neutral borders (#E5E7EB) instead of
    # drop shadows. Saturated blue accent, Tailwind-style semantic
    # colours, tinted icon circles for KPI cards (blue/purple/green/
    # orange) and tinted row backgrounds for the trade log.
    BG_DEEP="#F2F4F7",       # page background
    BG="#F2F4F7",            # frames / panels (flat page bg)
    BG_ROW="#FFFFFF",        # cards, table rows
    BG_ROW_HOVER="#F8FAFC",  # subtle hover on row
    BG_INPUT="#FFFFFF",      # entry / combobox (with border)
    BG_HEADER="#FFFFFF",     # section header card
    FG="#0F172A",            # primary text (slate-900)
    FG_DIM="#94A3B8",        # tertiary text (slate-400)
    FG_LABEL="#64748B",      # secondary text / labels (slate-500)
    FG_MUTED="#94A3B8",      # muted / disabled
    ACCENT="#3B82F6",        # primary blue (Tailwind blue-500)
    ACCENT_H="#2563EB",      # blue-600 hover
    ACCENT_DIM="#93C5FD",    # blue-300 disabled
    ACCENT_FG="#FFFFFF",     # text on blue
    CYAN_GLOW="#EFF6FF",     # blue-50 badge background
    GREEN="#22C55E",         # green-500
    GREEN_DIM="#16A34A",     # green-600
    GREEN_GLOW="#ECFDF5",    # green-50 row tint (profit)
    RED="#EF4444",           # red-500
    RED_DIM="#DC2626",       # red-600
    RED_GLOW="#FEF2F2",      # red-50 row tint (loss)
    YELLOW="#F59E0B",        # amber-500
    YELLOW_DIM="#D97706",    # amber-600
    BORDER="#E5E7EB",        # card border (slate-200)
    BORDER_LIGHT="#F1F5F9",  # divider (slate-100)
    DIVIDER="#F1F5F9",
    # Tints — used for KPI icon circles and chips.
    TINT_BLUE="#EFF6FF",
    TINT_PURPLE="#F5F3FF",
    TINT_GREEN="#ECFDF5",
    TINT_ORANGE="#FFF7ED",
    TINT_RED="#FEF2F2",
    TINT_BLUE_FG="#2563EB",
    TINT_PURPLE_FG="#7C3AED",
    TINT_GREEN_FG="#16A34A",
    TINT_ORANGE_FG="#EA580C",
    TINT_RED_FG="#DC2626",
    # Larger radii for the soft / modern look.
    RADIUS_SM=8,
    RADIUS_MD=12,
    RADIUS_LG=16,
    RADIUS_PILL=999,
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
    appearance: str = "dark"  # "dark" or "light" — drives ctk.set_appearance_mode
    hidden: bool = False  # if True, skipped by available_themes()/UI pickers


THEMES: Dict[str, Theme] = {
    "neon_cyan": Theme(palette=NEON_CYAN, fonts=DEFAULT_FONTS, appearance="dark"),
    # light_pro is kept registered so saved configs that still point at it
    # resolve correctly, but hidden=True keeps it out of the UI picker.
    "light_pro": Theme(palette=LIGHT_PRO, fonts=DEFAULT_FONTS, appearance="light", hidden=True),
    "light_soft": Theme(palette=LIGHT_SOFT, fonts=DEFAULT_FONTS, appearance="light"),
}

# Human-readable names for the theme picker UI.
THEME_LABELS: Dict[str, str] = {
    "neon_cyan": "Neon Cyan (тёмная)",
    "light_pro": "Light Pro (MetaTrader 5)",
    "light_soft": "Light Soft (светлая)",
}

DEFAULT_THEME = "light_soft"

# Built-ins cannot be unregistered or overwritten via custom-themes JSON.
_BUILTIN_THEMES = frozenset({"neon_cyan", "light_pro", "light_soft"})

# ── Global state ────────────────────────────────────────────────────

_current_theme_name: str = DEFAULT_THEME
_listeners: List[Callable[[], None]] = []


# ── Listener / pub-sub ──────────────────────────────────────────────

def add_listener(callback: Callable[[], None]) -> None:
    """Register a no-arg callback fired after every theme change or
    register/unregister event. Idempotent for the same callable."""
    if callable(callback) and callback not in _listeners:
        _listeners.append(callback)


def remove_listener(callback: Callable[[], None]) -> None:
    if callback in _listeners:
        _listeners.remove(callback)


def _notify_listeners() -> None:
    for cb in list(_listeners):
        try:
            cb()
        except Exception:
            pass  # never let a bad listener break theme changes


# ── Active theme accessors ──────────────────────────────────────────

def set_theme(name: str) -> None:
    """Select the active theme by name.

    Note: switching at runtime updates the value returned by future
    ``get_palette()`` / ``palette_proxy`` accesses, but does NOT repaint
    already-built widgets.  Use ``remap_widget_colors(...)`` plus
    ``apply_ttk_styles(...)`` after this call to live-refresh the UI.
    """
    global _current_theme_name
    if name not in THEMES:
        raise ValueError(
            f"Unknown theme '{name}'. Available: {', '.join(sorted(THEMES))}"
        )
    _current_theme_name = name
    _notify_listeners()


def get_theme_name() -> str:
    return _current_theme_name


def get_palette() -> Palette:
    return THEMES[_current_theme_name].palette


def get_fonts() -> Fonts:
    return THEMES[_current_theme_name].fonts


def get_theme_appearance() -> str:
    """Return ``"dark"`` or ``"light"`` for the active theme."""
    return THEMES[_current_theme_name].appearance


def available_themes(*, include_hidden: bool = False) -> List[str]:
    """Return a sorted list of registered theme names (builtins + custom).

    Hidden themes (``Theme.hidden=True``, e.g. deprecated ones kept only
    for backwards compatibility with saved configs) are skipped unless
    ``include_hidden=True``.  The UI theme picker uses the default
    filtered list; theme-resolution code that needs ALL themes should
    pass ``include_hidden=True``.
    """
    if include_hidden:
        return sorted(THEMES.keys())
    return sorted(n for n, th in THEMES.items() if not th.hidden)


def is_builtin_theme(name: str) -> bool:
    return name in _BUILTIN_THEMES


# ── Lazy proxies ────────────────────────────────────────────────────
#
# Bind these to ``p`` and ``f`` in the UI code instead of caching the
# result of ``get_palette()`` / ``get_fonts()``.  Every attribute access
# is resolved against the *current* theme, so newly built widgets after
# a ``set_theme()`` call use the new colours/fonts automatically.

class _PaletteProxy:
    __slots__ = ()

    def __getattr__(self, name: str):
        return getattr(get_palette(), name)

    def __dir__(self):
        return list(super().__dir__()) + [f.name for f in dataclasses.fields(Palette)]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PaletteProxy theme={_current_theme_name}>"


class _FontsProxy:
    __slots__ = ()

    def __getattr__(self, name: str):
        return getattr(get_fonts(), name)

    def __dir__(self):
        return list(super().__dir__()) + [f.name for f in dataclasses.fields(Fonts)]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FontsProxy theme={_current_theme_name}>"


palette_proxy = _PaletteProxy()
fonts_proxy = _FontsProxy()


# ── Theme registration ──────────────────────────────────────────────

def register_theme(
    name: str,
    palette: Palette,
    *,
    fonts: Optional[Fonts] = None,
    label: Optional[str] = None,
    appearance: str = "dark",
    hidden: bool = False,
) -> None:
    """Register or override a theme by name.

    Built-ins cannot be overwritten — pass a different *name*.
    ``hidden=True`` keeps the theme registered (so saved configs still
    resolve) but hides it from the UI picker via ``available_themes()``.
    Notifies listeners so any open theme picker can refresh.
    """
    if name in _BUILTIN_THEMES and name in THEMES:
        raise ValueError(f"'{name}' is a built-in theme and cannot be overridden")
    if appearance not in ("dark", "light"):
        raise ValueError("appearance must be 'dark' or 'light'")
    THEMES[name] = Theme(
        palette=palette, fonts=fonts or DEFAULT_FONTS,
        appearance=appearance, hidden=hidden,
    )
    if label is not None:
        THEME_LABELS[name] = label
    elif name not in THEME_LABELS:
        THEME_LABELS[name] = name
    _notify_listeners()


def unregister_theme(name: str) -> bool:
    """Remove a user-defined theme.

    Returns True if the theme was removed, False if it was a built-in
    or didn't exist.  If the active theme is removed, falls back to
    ``DEFAULT_THEME``.
    """
    if name in _BUILTIN_THEMES or name not in THEMES:
        return False
    THEMES.pop(name, None)
    THEME_LABELS.pop(name, None)
    global _current_theme_name
    if _current_theme_name == name:
        _current_theme_name = DEFAULT_THEME
    _notify_listeners()
    return True


def custom_themes() -> Dict[str, dict]:
    """Return all non-builtin themes as ``{name: {label, appearance, colors}}``."""
    out: Dict[str, dict] = {}
    for n, th in THEMES.items():
        if n in _BUILTIN_THEMES:
            continue
        out[n] = {
            "label": THEME_LABELS.get(n, n),
            "appearance": th.appearance,
            "colors": palette_to_dict(th.palette),
        }
    return out


# ── Palette ↔ dict ──────────────────────────────────────────────────

def palette_to_dict(p: Palette) -> Dict[str, str]:
    """Serialize a ``Palette`` to a plain dict suitable for JSON."""
    return {f.name: getattr(p, f.name) for f in dataclasses.fields(Palette)}


def palette_from_dict(d: Dict[str, str], *, base: Optional[Palette] = None) -> Palette:
    """Build a ``Palette`` from a dict.  Missing fields fall back to *base*
    (defaults to ``NEON_CYAN``)."""
    base = base or NEON_CYAN
    kwargs: Dict[str, str] = {}
    for f in dataclasses.fields(Palette):
        v = d.get(f.name)
        kwargs[f.name] = v if isinstance(v, str) and v else getattr(base, f.name)
    return Palette(**kwargs)


# ── Persistence for custom themes ───────────────────────────────────

def load_custom_themes(path: str) -> int:
    """Load user-defined themes from a JSON file. Returns # loaded.

    Robust to malformed files / missing path — returns 0 silently.
    Built-in theme names in the file are skipped.
    """
    if not path or not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0
    items = data.get("themes", data)
    if not isinstance(items, dict):
        return 0
    n = 0
    for name, entry in items.items():
        if not isinstance(name, str) or name in _BUILTIN_THEMES:
            continue
        if not isinstance(entry, dict):
            continue
        try:
            colors = entry.get("colors") or {}
            label = entry.get("label") or name
            appearance = entry.get("appearance") or "dark"
            if appearance not in ("dark", "light"):
                appearance = "dark"
            pal = palette_from_dict(colors)
            register_theme(name, pal, label=label, appearance=appearance)
            n += 1
        except Exception:
            continue
    return n


def save_custom_themes(path: str) -> bool:
    """Persist user-defined themes to a JSON file.  Built-ins are not saved."""
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"themes": custom_themes()}, fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ── Widget-tree colour remap (hot reload) ───────────────────────────

# CTk widget colour keys — passed through ``configure(...)`` and read via
# ``cget(...)``.  Not every widget supports every key; missing keys raise
# and are caught in the walker.
_CTK_COLOR_KEYS = (
    "fg_color", "bg_color", "hover_color",
    "text_color", "text_color_disabled",
    "border_color",
    "button_color", "button_hover_color",
    "checkmark_color", "progress_color",
    "placeholder_text_color",
    "scrollbar_button_color", "scrollbar_button_hover_color",
    "selected_color", "selected_hover_color",
    "label_text_color",
    "dropdown_fg_color", "dropdown_hover_color", "dropdown_text_color",
    "argument_text_color",
)

# Standard tk widget colour keys.
_TK_COLOR_KEYS = (
    "bg", "background", "fg", "foreground",
    "activebackground", "activeforeground",
    "selectbackground", "selectforeground",
    "highlightbackground", "highlightcolor",
    "insertbackground", "readonlybackground",
    "disabledforeground", "disabledbackground",
    "troughcolor",
)


def build_remap(old: Palette, new: Palette) -> Dict[str, str]:
    """Map every hex string in *old* palette → corresponding hex in *new* palette."""
    out: Dict[str, str] = {}
    for f in dataclasses.fields(Palette):
        ov = getattr(old, f.name)
        nv = getattr(new, f.name)
        if isinstance(ov, str) and ov.startswith("#"):
            out[ov.lower()] = nv
    return out


def _normalize_color(v) -> Optional[str]:
    """Return a lowercase ``#rrggbb`` if *v* looks like a hex colour, else None.
    Accepts CTk-style ``(light, dark)`` tuples — uses the first element."""
    if isinstance(v, (tuple, list)):
        if not v:
            return None
        v = v[0]
    if not isinstance(v, str):
        return None
    if not v.startswith("#"):
        return None
    return v.lower()


def remap_widget_colors(root, remap: Dict[str, str]) -> int:
    """Walk a widget tree starting at *root* and replace any colour
    attribute whose current value appears in *remap*.

    Works for both classic tk widgets (bg/fg/etc.) and CustomTkinter
    widgets (fg_color/text_color/etc.).  Returns the number of attribute
    writes performed.
    """
    keys = _CTK_COLOR_KEYS + _TK_COLOR_KEYS
    count = 0

    def visit(w) -> None:
        nonlocal count
        for k in keys:
            try:
                cur = w.cget(k)
            except Exception:
                continue
            n = _normalize_color(cur)
            if n is None or n not in remap:
                continue
            new = remap[n]
            if new.lower() == n:
                continue
            try:
                w.configure(**{k: new})
                count += 1
            except Exception:
                continue

    def walk(w) -> None:
        visit(w)
        try:
            kids = w.winfo_children()
        except Exception:
            kids = []
        for c in kids:
            walk(c)

    # Also visit any orphan toplevels (e.g. tooltip overlays) that share
    # the tk interpreter but aren't in *root*.winfo_children().
    visited = set()
    walk(root)
    visited.add(str(root))
    try:
        for name in root.tk.eval("winfo children .").split():
            try:
                w = root.nametowidget(name)
            except Exception:
                continue
            if str(w) in visited:
                continue
            walk(w)
            visited.add(str(w))
    except Exception:
        pass

    return count


# ── ttk style helper ─────────────────────────────────────────────────

def apply_ttk_styles(
    scale_fn=None,
    *,
    palette: Optional[Palette] = None,
    fonts: Optional[Fonts] = None,
) -> None:
    """Configure ttk Treeview and Notebook styles from the active palette.

    Safe to re-call after a theme change — ttk styles are replaced in
    place and refresh open Treeview/Notebook widgets automatically.
    """
    from tkinter import ttk

    pal = palette or get_palette()
    fnt = fonts or get_fonts()
    s = scale_fn or (lambda x: x)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Treeview (trades table) — 32px rows with 10pt body text.  The
    # ealier 36/11 combo made the trade log feel oversized vs the rest
    # of the UI.
    style.configure(
        "T.Treeview",
        background=pal.BG_ROW,
        foreground=pal.FG,
        fieldbackground=pal.BG_ROW,
        font=("Segoe UI", 10),
        rowheight=s(32),
        borderwidth=0,
        relief="flat",
    )
    # Heading: light slate band, 9pt bold label colour, 12/10 padding.
    style.configure(
        "T.Treeview.Heading",
        background=pal.BG_ROW_HOVER,
        foreground=pal.FG_LABEL,
        font=("Segoe UI", 9, "bold"),
        borderwidth=0,
        relief="flat",
        padding=(12, 10),
    )
    style.map(
        "T.Treeview",
        background=[("selected", pal.ACCENT)],
        foreground=[("selected", pal.ACCENT_FG)],
    )
    style.map("T.Treeview.Heading", background=[("active", pal.BG_ROW_HOVER)])

    # Notebook (bottom tabs: Сделки / Лог)
    style.configure("TNotebook", background=pal.BG_ROW, borderwidth=0, relief="flat")
    # Tabs (Сделки / Лог): 9pt bold + 16/8 padding so they read as a
    # secondary navigation strip, not chunky primary buttons.
    style.configure(
        "TNotebook.Tab",
        background=pal.BG_INPUT,
        foreground=pal.FG_DIM,
        padding=[16, 8],
        font=("Segoe UI", 9, "bold"),
        borderwidth=0,
        relief="flat",
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", pal.BG_ROW)],
        foreground=[("selected", pal.FG)],
    )


__all__ = [
    "Palette", "Fonts", "Theme",
    # accessors
    "get_palette", "get_fonts", "get_theme_name", "get_theme_appearance",
    "set_theme", "available_themes", "is_builtin_theme",
    # proxies
    "palette_proxy", "fonts_proxy",
    # theme management
    "register_theme", "unregister_theme", "custom_themes",
    "palette_to_dict", "palette_from_dict",
    "load_custom_themes", "save_custom_themes",
    # listeners
    "add_listener", "remove_listener",
    # ttk + hot-reload
    "apply_ttk_styles", "build_remap", "remap_widget_colors",
    # builtins
    "NEON_CYAN", "LIGHT_PRO", "DEFAULT_FONTS",
    "THEMES", "THEME_LABELS", "DEFAULT_THEME",
]
