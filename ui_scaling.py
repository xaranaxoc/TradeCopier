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


def get_window_dpi(root) -> int:
    """Return the DPI of the monitor the given Tk window is currently on.

    Uses Win10 1607+ ``GetDpiForWindow``; falls back to the cached primary
    DPI if the API is unavailable or the hwnd can't be resolved.
    """
    if sys.platform.startswith("win"):
        try:
            hwnd = ctypes.windll.user32.GetParent(int(root.winfo_id()))
            if not hwnd:
                hwnd = int(root.winfo_id())
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            if dpi and dpi > 0:
                return int(dpi)
        except (AttributeError, OSError, Exception):
            pass
    return _DPI


def update_scale_for_dpi(dpi: int, root) -> float:
    """Re-cache ``_SCALE``/``_DPI`` and re-apply ``tk scaling`` for *dpi*.

    Called by the DPI-change handler when the window moves to a monitor
    with a different DPI.  Returns the new effective scale.
    """
    global _SCALE, _DPI
    _DPI = max(96, int(dpi))
    _SCALE = max(0.75, _DPI / 96.0)
    try:
        root.tk.call("tk", "scaling", _DPI / 72.0)
    except Exception:
        pass
    return _SCALE


def get_cursor_work_area(root=None):
    """Return ``(left, top, right, bottom)`` work area (excluding taskbar) of
    the monitor under the mouse cursor.

    Falls back to the primary screen size reported by Tk if Windows APIs are
    unavailable. ``root`` is only used for the Tk fallback.
    """
    if sys.platform.startswith("win"):
        try:
            user32 = ctypes.windll.user32

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            pt = POINT()
            if user32.GetCursorPos(ctypes.byref(pt)):
                MONITOR_DEFAULTTONEAREST = 2
                hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                    r = mi.rcWork
                    return (r.left, r.top, r.right, r.bottom)
        except (AttributeError, OSError):
            pass
    # Fallback to Tk's primary-screen size (no taskbar info).
    if root is not None:
        try:
            return (0, 0, int(root.winfo_screenwidth()), int(root.winfo_screenheight()))
        except Exception:
            pass
    return (0, 0, 1024, 768)


def get_work_area_for_window(hwnd_or_root):
    """Return work area for the monitor the given window is on.

    Accepts a Tk widget (uses ``winfo_id``) or a raw HWND. Falls back to the
    cursor monitor or primary screen.
    """
    hwnd = None
    root = None
    if isinstance(hwnd_or_root, int):
        hwnd = hwnd_or_root
    else:
        root = hwnd_or_root
        try:
            hwnd = int(hwnd_or_root.winfo_id())
        except Exception:
            hwnd = None
    if sys.platform.startswith("win") and hwnd:
        try:
            user32 = ctypes.windll.user32

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            MONITOR_DEFAULTTONEAREST = 2
            hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcWork
                return (r.left, r.top, r.right, r.bottom)
        except (AttributeError, OSError):
            pass
    return get_cursor_work_area(root)


def clamp_to_work_area(x, y, w, h, work_area):
    """Clamp a window rect into a work area so it cannot fall off-screen."""
    wl, wt, wr, wb = work_area
    ww = max(1, wr - wl)
    wh = max(1, wb - wt)
    w = min(int(w), ww)
    h = min(int(h), wh)
    x = max(wl, min(int(x), wr - w))
    y = max(wt, min(int(y), wb - h))
    return x, y, w, h


def compute_initial_geometry(work_area, frac=0.78, min_w=960, min_h=640,
                             max_w=1400, max_h=900):
    """Return ``(w, h, x, y)`` for an adaptive initial window centered in ``work_area``.

    ``min_*``/``max_*`` are unscaled logical sizes; they get DPI-scaled here.
    """
    wl, wt, wr, wb = work_area
    aw = max(1, wr - wl)
    ah = max(1, wb - wt)
    # Limit logical bounds by physical work area too.
    mn_w = min(scale(min_w), aw - scale(16))
    mn_h = min(scale(min_h), ah - scale(16))
    mx_w = min(scale(max_w), aw - scale(16))
    mx_h = min(scale(max_h), ah - scale(16))
    w = int(aw * frac)
    h = int(ah * frac)
    w = max(mn_w, min(w, mx_w))
    h = max(mn_h, min(h, mx_h))
    x = wl + (aw - w) // 2
    y = wt + (ah - h) // 2
    return w, h, x, y


__all__ = [
    "enable_dpi_awareness",
    "init_root_scaling",
    "scale",
    "fpt",
    "current_scale",
    "current_dpi",
    "get_window_dpi",
    "update_scale_for_dpi",
    "get_cursor_work_area",
    "get_work_area_for_window",
    "clamp_to_work_area",
    "compute_initial_geometry",
]
