"""
ctk_compat — tk-flavoured wrappers around customtkinter widgets so the
rest of `gui.py` can keep using `bg=`/`fg=`/`width=N`/etc. without a
full kwargs rewrite at every call site.

Subclass strategy is intentional:
  * Each wrapper translates tk-style kwargs to CTk-style **only** when the
    caller passes them. CTk's internal `configure(require_redraw=True, ...)`
    calls keep working untouched.
  * `corner_radius=0` and `border_width=0` are the defaults — we preserve
    the existing flat / square FTH look (no pill buttons, no cards).
  * `tk.Button`/`tk.Entry` accept `width=N` in *characters*; CTk uses
    pixels. We treat any `width` ≤ 24 as characters and convert to pixels
    via an 8 px/char heuristic. Anything larger is passed through as pixels.

What is *not* wrapped here (intentionally):
  * `tk.Tk` / `tk.Toplevel` window roots — gui.py uses `ctk.CTk` /
    `ctk.CTkToplevel` directly (see below for a thin Toplevel helper that
    injects an icon-safe protocol_handler default).
  * `tk.Listbox`, `tk.Canvas`, `tk.PanedWindow`, `tk.Menu`, `tk.Text`,
    `ttk.Treeview` / `ttk.Notebook` / `ttk.Scrollbar` — CTk has no
    equivalents, those stay tk/ttk and are themed via ttk.Style.
  * `_Tip` tooltip overlay — stays raw `tk.Toplevel` + `tk.Label`,
    because it uses `wm_overrideredirect` and we don't want CTk's
    canvas-based painting for a transient tooltip.

The translation maps are intentionally minimal — we don't try to emulate
every tk option, only the ones actually used inside `gui.py`.
"""

from __future__ import annotations

from typing import Any, Mapping, Set
import tkinter as tk

import customtkinter as ctk


# ── kwargs translation tables ───────────────────────────────────────

_LABEL_MAP: Mapping[str, str] = {
    "bg": "fg_color", "background": "fg_color",
    "fg": "text_color", "foreground": "text_color",
}

# Options tk supports but CTk widgets don't — silently dropped.
# NOTE: padx/pady are *kept* for Label — CTkLabel forwards them to its
# inner tk.Label and they're what we need to restore the tk.Label
# natural padding (~2 px) that CTkLabel removes (padx=0, pady=0 default).
# Without that pad the rows look "broken / fonts too small" because the
# text-only height is ~25 % shorter than tk.Label of the same font.
_LABEL_DROP: Set[str] = {
    "relief", "bd", "borderwidth", "cursor",
    "highlightthickness", "highlightbackground", "highlightcolor",
    "activebackground", "activeforeground", "insertbackground",
    "selectbackground", "selectforeground",
}

_BUTTON_MAP: Mapping[str, str] = {
    "bg": "fg_color", "background": "fg_color",
    "fg": "text_color", "foreground": "text_color",
    "activebackground": "hover_color",
    "highlightbackground": "border_color",
}

_BUTTON_DROP: Set[str] = {
    "padx", "pady", "relief", "bd", "borderwidth", "cursor", "justify",
    "highlightthickness", "highlightcolor",
    "activeforeground", "insertbackground",
    "selectbackground", "selectforeground",
}

_ENTRY_MAP: Mapping[str, str] = {
    "bg": "fg_color", "background": "fg_color",
    "fg": "text_color", "foreground": "text_color",
    "highlightbackground": "border_color",
    "highlightcolor": "border_color",
}

_ENTRY_DROP: Set[str] = {
    "padx", "pady", "relief", "bd", "borderwidth", "cursor", "justify",
    "highlightthickness",
    "activebackground", "activeforeground", "insertbackground",
    "selectbackground", "selectforeground",
}

_FRAME_MAP: Mapping[str, str] = {
    "bg": "fg_color", "background": "fg_color",
    "highlightbackground": "border_color",
}

_FRAME_DROP: Set[str] = {
    "padx", "pady", "relief", "bd", "borderwidth", "cursor",
    "highlightcolor",
}


# ── helpers ──────────────────────────────────────────────────────────


def _translate(kwargs: dict, mapping: Mapping[str, str], drop: Set[str]) -> dict:
    out: dict = {}
    for k, v in kwargs.items():
        if k in drop:
            continue
        out[mapping.get(k, k)] = v
    return out


def _chars_to_px(width: Any, px_per_char: int = 8, pad: int = 10) -> Any:
    """Convert tk-style char width to CTk-style pixel width.

    Heuristic: any integer 1..48 is treated as a tk character count
    (matches the original `tk.Button(... width=2)` / `tk.Entry(width=36)`
    call sites). Larger values are assumed to already be in pixels and
    are passed through unchanged. Non-int values pass through.
    """
    if isinstance(width, int) and 1 <= width <= 48:
        return width * px_per_char + pad
    return width


# ── Wrappers ─────────────────────────────────────────────────────────


class Label(ctk.CTkLabel):
    """CTkLabel that accepts ``bg=``/``fg=``/``padx=``-style tk kwargs.

    Defaults: transparent background, square corners, no border. Internal
    text padding (tk's ``padx``/``pady``) is dropped — use the parent's
    ``pack``/``grid`` paddings instead.
    """

    def __init__(self, master, **kwargs):
        kwargs.setdefault("corner_radius", 0)
        # CTkLabel defaults to height=28 px which is ~2x taller than a
        # tk.Label rendering the same font. Setting height=0 makes the
        # CTkLabel shrink to its natural text height; pady=2/padx=1
        # restores the natural tk.Label internal padding (CTkLabel sets
        # padx=0, pady=0 on its inner tk.Label which gives a 13 px box
        # for a 11pt font — tk.Label is 17 px).
        kwargs.setdefault("height", 0)
        kwargs.setdefault("width", 0)
        kwargs.setdefault("pady", 2)
        kwargs.setdefault("padx", 1)
        # CTkLabel default fg_color is theme-aware (gray). Keep labels
        # transparent unless an explicit bg/fg_color was passed — that
        # matches tk.Label's default of inheriting the parent's bg.
        if "bg" not in kwargs and "background" not in kwargs and "fg_color" not in kwargs:
            kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **_translate(kwargs, _LABEL_MAP, _LABEL_DROP))

    def configure(self, require_redraw: bool = False, **kwargs):
        return super().configure(
            require_redraw=require_redraw,
            **_translate(kwargs, _LABEL_MAP, _LABEL_DROP),
        )

    def config(self, **kwargs):
        return self.configure(**kwargs)


class Button(ctk.CTkButton):
    """CTkButton with tk-friendly defaults.

    Converts ``width=N`` (chars) → pixels, drops ``padx``/``pady``/``relief``.
    Uses ``corner_radius=0``/``border_width=0`` so the visual matches the
    flat tk.Button look in the existing FTH UI.
    """

    def __init__(self, master, **kwargs):
        kwargs.setdefault("corner_radius", 0)
        kwargs.setdefault("border_width", 0)
        # Default CTkButton width is 140 px which is far too wide for the
        # small icon buttons (text="⚙" / "..." / "×"). Convert tk-style
        # char widths to pixels; if the caller didn't pass any width,
        # use a tight default that auto-grows with the text.
        # tk.Button width=N renders as ~6*N + 30 px wide for Segoe UI 8-9pt
        # (measured under Xvfb on this sandbox, matches Windows default tk
        # rendering for those fonts). Matches the icon-button look from the
        # original tk UI: width=2 → 42 px, width=10 → 90 px.
        if "width" in kwargs:
            kwargs["width"] = _chars_to_px(kwargs["width"], px_per_char=6, pad=30)
        else:
            kwargs.setdefault("width", 0)
        # tk.Button with a 8-9pt font renders ~27 px tall. CTkButton
        # defaults to 28 — 27 keeps the slave-row buttons identical to tk.
        kwargs.setdefault("height", 27)
        super().__init__(master, **_translate(kwargs, _BUTTON_MAP, _BUTTON_DROP))

    def configure(self, require_redraw: bool = False, **kwargs):
        if "width" in kwargs:
            kwargs["width"] = _chars_to_px(kwargs["width"], px_per_char=6, pad=30)
        return super().configure(
            require_redraw=require_redraw,
            **_translate(kwargs, _BUTTON_MAP, _BUTTON_DROP),
        )

    def config(self, **kwargs):
        return self.configure(**kwargs)


class Entry(ctk.CTkEntry):
    """CTkEntry with tk-friendly defaults.

    Converts ``width=N`` (chars) → pixels, maps ``highlightbackground``→
    ``border_color`` so the existing focus/blur ring colours survive.
    Drops ``insertbackground`` — CTk derives the caret color from
    ``text_color``.
    """

    def __init__(self, master, **kwargs):
        kwargs.setdefault("corner_radius", 0)
        kwargs.setdefault("border_width", 1)
        # tk.Entry width=N renders as ~6*N + 6 px for Segoe UI 9pt
        # (measured: width=10→66, width=28→174, width=36→222).
        if "width" in kwargs:
            kwargs["width"] = _chars_to_px(kwargs["width"], px_per_char=6, pad=6)
        # tk.Entry with a 9pt font renders ~22 px tall (incl. 1px border).
        # CTkEntry defaults to 28. 22 matches tk.
        kwargs.setdefault("height", 22)
        super().__init__(master, **_translate(kwargs, _ENTRY_MAP, _ENTRY_DROP))

    def configure(self, require_redraw: bool = False, **kwargs):
        if "width" in kwargs:
            kwargs["width"] = _chars_to_px(kwargs["width"], px_per_char=6, pad=6)
        return super().configure(
            require_redraw=require_redraw,
            **_translate(kwargs, _ENTRY_MAP, _ENTRY_DROP),
        )

    def config(self, **kwargs):
        return self.configure(**kwargs)


class Frame(ctk.CTkFrame):
    """CTkFrame with tk-friendly defaults.

    ``corner_radius=0``, ``border_width=0`` by default. ``highlightthickness=N``
    on a tk.Frame is mapped to ``border_width=N`` so the existing
    "bordered card" frames (master panel, KPI cards, slave rows) keep
    their 1 px outlines.
    """

    def __init__(self, master, **kwargs):
        kwargs.setdefault("corner_radius", 0)
        # CTkFrame defaults to width=200, height=200. tk.Frame defaults to
        # 0/0 (size propagates from children). Without this override every
        # bg_frame / KPI card / slave-row background forces a 200x200
        # minimum into its grid cell, which made the slave table rows
        # explode vertically (one account taking ~200 px instead of ~29).
        kwargs.setdefault("width", 0)
        kwargs.setdefault("height", 0)
        # tk.Frame(highlightthickness=1, highlightbackground=BORDER) is the
        # idiom used for the bordered cards in the FTH UI. Translate to
        # CTk's border_width / border_color so we keep the same look.
        if "highlightthickness" in kwargs:
            kwargs["border_width"] = kwargs.pop("highlightthickness")
        else:
            kwargs.setdefault("border_width", 0)
        super().__init__(master, **_translate(kwargs, _FRAME_MAP, _FRAME_DROP))

    def configure(self, require_redraw: bool = False, **kwargs):
        if "highlightthickness" in kwargs:
            kwargs["border_width"] = kwargs.pop("highlightthickness")
        return super().configure(
            require_redraw=require_redraw,
            **_translate(kwargs, _FRAME_MAP, _FRAME_DROP),
        )

    def config(self, **kwargs):
        return self.configure(**kwargs)


class Toplevel(ctk.CTkToplevel):
    """CTkToplevel that accepts ``bg=`` and sets it as ``fg_color``.

    Most of the dialog code does ``self.configure(bg=BG)`` right after
    ``super().__init__``. Translate that single kwarg here so call sites
    don't need to change.
    """

    def configure(self, **kwargs):
        # CTkToplevel.configure forwards to tk.Toplevel.configure which
        # does not know about fg_color; CTkToplevel maps fg_color via its
        # own setter. So we translate before calling.
        if "bg" in kwargs:
            kwargs["fg_color"] = kwargs.pop("bg")
        elif "background" in kwargs:
            kwargs["fg_color"] = kwargs.pop("background")
        return super().configure(**kwargs)

    def config(self, **kwargs):
        return self.configure(**kwargs)


__all__ = ["Label", "Button", "Entry", "Frame", "Toplevel"]
