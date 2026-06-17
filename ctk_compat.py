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
        #
        # tk.Button(padx=N, pady=N) means N px of *internal* padding on each
        # side; CTkButton has no padx/pady, so we pop them and turn them into
        # extra width/height. Without this the text of accent/danger buttons
        # (Старт/Стоп/+ Аккаунт/× Закрыть сделки …) sits flush against the
        # button edges.
        padx_arg = kwargs.pop("padx", None)
        pady_arg = kwargs.pop("pady", None)
        if "width" in kwargs:
            kwargs["width"] = _chars_to_px(kwargs["width"], px_per_char=6, pad=30)
            # If padx is also given (e.g. header info/settings: width=2 + padx=8),
            # add it on top — tk.Button stacks padx on top of the char width.
            if padx_arg is not None:
                kwargs["width"] = int(kwargs["width"]) + 2 * int(padx_arg)
        else:
            kwargs.setdefault("width", 0)
            if padx_arg is not None:
                # When no explicit width was given, the button auto-sizes to
                # its text. tk would have added 2*padx on top of that; CTk
                # doesn't, so set an explicit width = measured_text + 2*padx.
                text = kwargs.get("text", "") or ""
                if text:
                    try:
                        import tkinter.font as _tkfont
                        font_spec = kwargs.get("font") or ("Segoe UI", 9)
                        family = font_spec[0] if len(font_spec) > 0 else "Segoe UI"
                        size = font_spec[1] if len(font_spec) > 1 else 9
                        weight = font_spec[2] if len(font_spec) > 2 else "normal"
                        f = _tkfont.Font(root=master, family=family,
                                         size=size, weight=weight)
                        text_w = f.measure(text)
                    except Exception:
                        # Fallback: rough char-width estimate.
                        text_w = max(1, len(text)) * 7
                    kwargs["width"] = text_w + 2 * int(padx_arg) + 4
        # tk.Button height ≈ font_linespace + 2*pady + 6 (bd + internals).
        # For Segoe UI 8-9pt on Windows that's ~26-27 px at pady=0. CTkButton
        # defaults to 28; we want to track tk's height + pady.
        if "height" not in kwargs:
            # Width=2 icon buttons (no padx/pady) → 27 to match tk.Button(pady=0)
            # for Segoe UI 8-9pt.
            base_h = 27
            if pady_arg is not None:
                # tk doubles pady internally; the icon-button default is ~21
                # at pady=0, so base + 2*pady tracks tk closely without
                # overshooting (e.g. pady=3 → 27, matches tk reqh=25-27).
                base_h = 21 + 2 * int(pady_arg)
            kwargs["height"] = base_h
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
