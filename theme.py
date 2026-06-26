"""
theme — global CustomTkinter appearance setup for Trade Copier.

Includes a runtime patch of customtkinter's `_apply_font_scaling` so that
positive font sizes in tuples (e.g. `("Segoe UI", 9)`) keep their tk
"points" semantics instead of being silently converted to negative
"pixels" — that conversion is what made every CTk widget render with a
~25% smaller font than the equivalent tk widget on 96 DPI displays, and
is the root cause of the "слишком маленькие шрифты" report from
2026-06-17. We also lock widget/window scaling to 1.0 so the layout
matches the original tk UI 1-to-1 regardless of system DPI.

Centralising the appearance + colour scheme call here keeps gui.py free
of CTk boilerplate and makes it easy to switch palettes later (e.g. a
light mode toggle) without hunting through dialogs.

Call ``apply_theme()`` **once, right after** the root ``ctk.CTk()`` /
top-level Toplevel is created. Doing it before any Tk root exists, or
before the App's ``super().__init__()`` finishes, raises a TclError
inside customtkinter (see the regression notes in the user skill —
this was rollback pitfall #2 during the previous CTk attempt).
"""

from __future__ import annotations

import customtkinter as ctk
from customtkinter import CTkFont
from customtkinter.windows.widgets.scaling.scaling_base_class import (
    CTkScalingBaseClass,
)

from palette import get_theme_appearance


def _patched_apply_font_scaling(self, font):
    """Drop CTk's automatic point→pixel font conversion.

    The stock implementation does ``return font[0], -abs(round(size *
    widget_scaling))`` which forces the inner ``tk.Label`` to interpret
    the size as pixels. tk's natural reading of ``("Segoe UI", 9)`` is
    9 *points* (≈12 px at 96 DPI), so the stock conversion makes every
    label render ~25 % smaller than the tk.Label it replaces. We keep
    the size positive and skip widget scaling (we lock that to 1.0
    below), so CTk widgets render exactly as the original tk widgets.
    """
    if isinstance(font, tuple):
        if len(font) == 1:
            return font
        if len(font) == 2:
            return font[0], round(font[1])
        return (font[0], round(font[1])) + tuple(font[2:])
    if isinstance(font, CTkFont):
        return font.create_scaled_tuple(1.0)
    raise ValueError(
        f"Can not scale font '{font}' of type {type(font)}. "
        f"font needs to be tuple or instance of CTkFont"
    )


_PATCH_APPLIED = False
_SCALING_LOCKED = False


def init_scaling() -> None:
    """Lock CTk widget/window scaling to 1.0 and install the font
    scaling patch.

    **Must be called BEFORE the root ``ctk.CTk()`` window exists.** If
    called after, ``ScalingTracker.update_scaling_callbacks_all()`` will
    fire ``CTk._set_scaling`` on the already-registered root, and that
    callback does:

        super().minsize(_current_w, _current_h)   # 600x500 at init
        super().maxsize(_current_w, _current_h)   # 600x500 at init
        super().geometry("600x500")
        after(1000, _set_scaled_min_max)          # restores real max

    i.e. it forcibly clamps wm geometry to CTk's internal default
    600x500 for one full second before restoring the user's intended
    min/max. That 1-second clamp is exactly the "small window flash"
    users see on startup — the window maps at clamped size, then a
    second later un-clamps to the saved geometry.

    By doing the scaling lock here (before super().__init__()), no
    window is registered with the ScalingTracker yet, so the callback
    is a no-op and our root is born with the correct scaling baked in.

    Idempotent: subsequent calls do nothing.
    """
    global _PATCH_APPLIED, _SCALING_LOCKED
    if _SCALING_LOCKED:
        return
    try:
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)
    except Exception:
        pass
    if not _PATCH_APPLIED:
        CTkScalingBaseClass._apply_font_scaling = _patched_apply_font_scaling
        _PATCH_APPLIED = True
    _SCALING_LOCKED = True


def apply_theme() -> None:
    """Install the theme.

    Reads ``get_theme_appearance()`` from ``palette`` so the CTk
    appearance mode follows the active theme — switching to LIGHT_PRO
    flips CTk's internal light/dark switch so the few widgets we don't
    override per-colour (dropdown panels, etc.) follow suit.

    Must be called **after** a Tk root exists. Safe to call multiple
    times — used both at startup and after every hot theme switch.

    Note: this function intentionally does NOT touch CTk's scaling —
    that's a one-shot startup concern handled by ``init_scaling()``
    before the root window is created (see that docstring for the
    1-second flash explanation).
    """
    appearance = get_theme_appearance()
    if appearance not in ("dark", "light"):
        appearance = "dark"
    ctk.set_appearance_mode(appearance)
    ctk.set_default_color_theme("dark-blue")
    # We don't ship a custom .json theme — the colour mapping in gui.py
    # (BG, FG, ACCENT, etc.) is applied per-widget through `ctk_compat`,
    # so the default dark-blue theme just provides reasonable fallbacks
    # for any widget we forgot to colour explicitly.


__all__ = ["init_scaling", "apply_theme"]
