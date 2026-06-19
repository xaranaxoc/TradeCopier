"""
lucide — loader for the bundled Lucide icon set.

Lucide icons live in ``assets/lucide/{name}.png`` as black-stroke PNGs on
a transparent background, rendered at 48×48 (2× the typical 24-pixel
display size for crisp HiDPI rendering).

This module hands callers a ``CTkImage`` tinted to the requested colour
on demand.  Results are cached by ``(name, size, color)`` so repeat
lookups (a thousand trade-log rows asking for the same chevron) don't
hammer Pillow.

The tinting trick:

    The source PNG has the icon shape encoded in the *alpha* channel
    (anti-aliased) and the RGB channels filled with black.  To recolour
    we throw the RGB away and re-paint it with the requested hex while
    keeping the original alpha channel.  This preserves the stroke's
    sub-pixel antialiasing exactly.

Public API
~~~~~~~~~~
    icon(name, size=18, color=None)          → CTkImage | None
    raw(name)                                → PIL.Image | None  (debug)
    available()                              → list[str]
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

try:
    import customtkinter as ctk  # type: ignore
except ImportError:  # pragma: no cover - CTk is installed in the running app
    ctk = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:  # pragma: no cover - PIL is already a runtime dep via CTk
    Image = None  # type: ignore[assignment]

from palette import palette_proxy as p


# Resolve the assets directory relative to this file so PyInstaller /
# Nuitka one-folder builds also find the icons after _MEIPASS extraction.
_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "assets", "lucide")

# Cache: (name, size, color_hex) → CTkImage
_cache: Dict[Tuple[str, int, str], "ctk.CTkImage"] = {}
_raw_cache: Dict[str, "Image.Image"] = {}


def available() -> list:
    """Return the list of available icon names (no extension)."""
    if not os.path.isdir(_ASSETS_DIR):
        return []
    return sorted(
        f[:-4] for f in os.listdir(_ASSETS_DIR)
        if f.endswith(".png")
    )


def raw(name: str) -> Optional["Image.Image"]:
    """Return the raw PIL Image for *name* (black on transparent), or
    ``None`` if the asset is missing.  Useful for debugging."""
    if Image is None:
        return None
    if name in _raw_cache:
        return _raw_cache[name]
    path = os.path.join(_ASSETS_DIR, f"{name}.png")
    if not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        return None
    _raw_cache[name] = img
    return img


def _tint(img: "Image.Image", color_hex: str) -> "Image.Image":
    """Recolour *img* to *color_hex* while preserving its alpha channel."""
    rgba = img.convert("RGBA")
    alpha = rgba.split()[-1]
    coloured = Image.new("RGBA", rgba.size, color_hex)
    coloured.putalpha(alpha)
    return coloured


def icon(name: str, size: int = 18, color: Optional[str] = None) -> Optional["ctk.CTkImage"]:
    """Return a tinted ``CTkImage`` for *name* at the given display *size*.

    Parameters
    ----------
    name :
        File-name stem under ``assets/lucide/`` (e.g. ``"play"``).
    size :
        Logical pixel size at which the icon should *render*.  CTk will
        scale our 48 px source down for crisp results.
    color :
        Hex colour string (``"#3B82F6"``).  Defaults to ``palette.FG``
        for the active theme so icons read on top of the page bg.
        Pass ``"accent"`` for ``palette.ACCENT``.
    """
    if Image is None or ctk is None:
        return None

    if color is None:
        color = p.FG
    elif color == "accent":
        color = p.ACCENT
    elif color == "label":
        color = p.FG_LABEL
    elif color == "dim":
        color = p.FG_DIM
    elif color == "danger":
        color = p.RED
    elif color == "warn":
        color = p.YELLOW
    elif color == "success":
        color = p.GREEN
    elif color == "white" or color == "on_accent":
        color = p.ACCENT_FG

    key = (name, int(size), color)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    src = raw(name)
    if src is None:
        return None

    tinted = _tint(src, color)
    try:
        ctk_img = ctk.CTkImage(light_image=tinted, dark_image=tinted,
                               size=(int(size), int(size)))
    except Exception:
        return None
    _cache[key] = ctk_img
    return ctk_img


def clear_cache() -> None:
    """Drop cached images. Call after a theme switch so colour aliases
    (``"accent"``, ``"label"`` …) pick up the new palette."""
    _cache.clear()


__all__ = ["icon", "raw", "available", "clear_cache"]
