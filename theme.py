"""
theme — global CustomTkinter appearance setup for the FTH Trade Copier.

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


def apply_theme() -> None:
    """Install the FTH dark theme: dark appearance, dark-blue accents.

    Must be called **after** a Tk root exists. Calling this multiple
    times is safe — CTk's setters are idempotent.
    """
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    # We don't ship a custom .json theme — the colour mapping in gui.py
    # (BG, FG, ACCENT, etc.) is applied per-widget through `ctk_compat`,
    # so the default dark-blue theme just provides reasonable fallbacks
    # for any widget we forgot to colour explicitly.


__all__ = ["apply_theme"]
