"""
DPI awareness and UI scaling helpers (Windows-first).

Tkinter on Windows does not opt into Per-Monitor DPI by default, so on a 125/150/200%
display the OS bitmap-scales the window and everything looks blurry. This module:

1. Asks Windows to make the process Per-Monitor v2 DPI-aware (with sane fallbacks
   for older Win10 / Win7). Must be called BEFORE creating the root Tk window.
2. After the root exists, sets ``tk scaling`` and caches the effective DPI scale
   so other modules can size things consistently via ``scale(px)``.

Non-Windows imports are tolerated so the file can at least be imported in tests.
"""

from __future__ import annotations

import ctypes
import sys
from typing import Optional

# Cached effective scale (1.0 == 96 DPI / 100%).
_SCALE: float = 1.0
_DPI: int = 96


def enable_dpi_awareness() -> None:
    """Best-effort: make the process Per-Monitor v2 DPI-aware.

    Must be called BEFORE ``tk.Tk()``. Safe to call multiple times — Windows
    silently ignores duplicate calls and we swallow errors.
    """
    if not sys.platform.startswith("win"):
        return
    # 1) Win10 1703+: SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2 = -4)
    try:
        ctx = ctypes.c_void_p(-4)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctx):
            return
    except (AttributeError, OSError):
        pass
    # 2) Win8.1+: SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE = 2)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    # 3) Vista+: SetProcessDPIAware (system-DPI only, still better than bitmap-scaling)
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def _detect_primary_dpi() -> int:
    """Return the primary monitor DPI (defaults to 96)."""
    if not sys.platform.startswith("win"):
        return 96
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        # LOGPIXELSX = 88
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        ctypes.windll.user32.ReleaseDC(0, hdc)
        if dpi and dpi > 0:
            return int(dpi)
    except (AttributeError, OSError):
        pass
    return 96


def init_root_scaling(root, override_dpi: Optional[int] = None) -> float:
    """Configure Tk scaling on ``root`` and cache the effective UI scale.

    Returns the effective scale (1.0 == 100%).
    """
    global _SCALE, _DPI
    dpi = override_dpi or _detect_primary_dpi()
    _DPI = dpi
    _SCALE = max(0.75, dpi / 96.0)
    # Tk's "scaling" is points-per-pixel; 1.0 == 72 DPI. Setting dpi/72 makes
    # font sizes in points map 1:1 to the user's chosen DPI.
    try:
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:
        pass
    return _SCALE


def scale(px: float) -> int:
    """Scale a pixel value by the current DPI factor (rounded, min 1)."""
    if px <= 0:
        return 0
    v = int(round(px * _SCALE))
    return max(1, v)


def fpt(pt: int) -> int:
    """Pass-through for font point sizes.

    Because we configure ``tk scaling = dpi/72``, Tk already renders point
    sizes at the correct physical size on Hi-DPI. We keep this helper so
    callers can opt into a future explicit scale (e.g. user zoom).
    """
    return max(1, int(pt))


def current_scale() -> float:
    return _SCALE


def current_dpi() -> int:
    return _DPI


__all__ = [
    "enable_dpi_awareness",
    "init_root_scaling",
    "scale",
    "fpt",
    "current_scale",
    "current_dpi",
]
