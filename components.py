# -*- coding: utf-8 -*-
"""components.py — переиспользуемые UI-кирпичики для FTH Trade Copier.

Phase 3a в серии `feat/ui-polish`. Здесь живут:

  * StatusPill   — овальная плюшка "● TEXT" со состояниями.
  * Badge        — компактная метка (ok / warn / err / info / muted).
  * Toast        — всплывающее уведомление (Toplevel, авто-закрытие).
  * ToastManager — стек тостов в правом нижнем углу.
  * EmptyState   — большая пустая зона (иконка + заголовок + подсказка
                   + опц. кнопка).
  * Tooltip      — заменитель _Tip с CTk-look-и-feel.

Все компоненты не тащат бизнес-логику. Цвета/шрифты берём из theme.py.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

import theme


# ─── StatusPill ───────────────────────────────────────────────────────
class StatusPill(ctk.CTkFrame):
    """Маленькая овальная плюшка `● TEXT` для статусов в шапке.

    Состояния: idle / running / stopped / warn / error.
    Цвет точки и подписи меняется через set_state().
    """

    # (dot, text) для каждого состояния.
    _COLORS = {
        "idle":    (theme.TEXT_TERTIARY, theme.TEXT_SECONDARY),
        "running": (theme.STATUS_OK,     theme.TEXT_PRIMARY),
        "stopped": (theme.TEXT_TERTIARY, theme.TEXT_SECONDARY),
        "warn":    (theme.STATUS_WARN,   theme.TEXT_PRIMARY),
        "error":   (theme.STATUS_ERR,    theme.TEXT_PRIMARY),
    }

    def __init__(self, master, text: str = "—", state: str = "idle"):
        super().__init__(
            master,
            fg_color=theme.SURFACE_INPUT,
            corner_radius=12,
            border_width=1,
            border_color=theme.BORDER_SOFT,
            height=26,
        )
        dot, txt = self._COLORS.get(state, self._COLORS["idle"])
        self._dot = tk.Canvas(
            self, width=8, height=8, bg=theme.SURFACE_INPUT,
            highlightthickness=0, bd=0,
        )
        self._dot.pack(side="left", padx=(12, 6), pady=8)
        self._dot_id = self._dot.create_oval(0, 0, 8, 8, fill=dot, outline="")

        bold = theme.pick_font(theme.SANS_BOLD_PREFS)
        self._lbl = tk.Label(
            self, text=text, bg=theme.SURFACE_INPUT, fg=txt,
            font=(bold, 10, "bold"),
        )
        self._lbl.pack(side="left", padx=(0, 14))

    def set_state(self, state: str, text: Optional[str] = None) -> None:
        if state not in self._COLORS:
            state = "idle"
        dot, txt = self._COLORS[state]
        self._dot.itemconfig(self._dot_id, fill=dot)
        self._lbl.config(fg=txt)
        if text is not None:
            self._lbl.config(text=text)


# ─── Badge ────────────────────────────────────────────────────────────
class Badge(ctk.CTkFrame):
    """Компактная метка-чип. variant: ok / warn / err / info / muted / accent."""

    _VARIANTS = {
        "ok":     (theme.STATUS_OK_GLOW,   theme.STATUS_OK),
        "warn":   (theme.STATUS_WARN_GLOW, theme.STATUS_WARN),
        "err":    (theme.STATUS_ERR_GLOW,  theme.STATUS_ERR),
        "info":   (theme.STATUS_INFO_GLOW, theme.STATUS_INFO),
        "muted":  (theme.SURFACE_3,        theme.TEXT_TERTIARY),
        "accent": (theme.ACCENT_GLOW,      theme.ACCENT),
    }

    def __init__(self, master, text: str = "", variant: str = "muted"):
        bg, fg = self._VARIANTS.get(variant, self._VARIANTS["muted"])
        super().__init__(
            master, fg_color=bg, corner_radius=theme.RADIUS_CHIP,
            border_width=0, height=20,
        )
        self._lbl_fg = fg
        bold = theme.pick_font(theme.SANS_BOLD_PREFS)
        self._lbl = tk.Label(
            self, text=text, bg=bg, fg=fg, font=(bold, 9, "bold"),
            padx=8, pady=2,
        )
        self._lbl.pack()

    def set_text(self, text: str) -> None:
        self._lbl.config(text=text)

    def set_variant(self, variant: str) -> None:
        bg, fg = self._VARIANTS.get(variant, self._VARIANTS["muted"])
        self.configure(fg_color=bg)
        self._lbl.config(bg=bg, fg=fg)


# ─── Toast / ToastManager ─────────────────────────────────────────────
class Toast(tk.Toplevel):
    """Одиночный тост: rounded card + иконка + текст. Авто-закрытие."""

    _KIND_STYLE = {
        "info":    (theme.STATUS_INFO,  theme.ICON_INFO),
        "ok":      (theme.STATUS_OK,    "\u2713"),     # check mark
        "warn":    (theme.STATUS_WARN,  theme.ICON_WARNING),
        "err":     (theme.STATUS_ERR,   theme.ICON_X),
    }

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        kind: str = "info",
        timeout: int = 3200,
        on_dismiss: Optional[Callable[["Toast"], None]] = None,
    ):
        super().__init__(parent)
        self._on_dismiss = on_dismiss
        self._dismissed = False

        self.wm_overrideredirect(True)
        try:
            self.wm_attributes("-topmost", True)
        except Exception:
            pass
        self.configure(bg=theme.SURFACE_0)

        accent, glyph = self._KIND_STYLE.get(kind, self._KIND_STYLE["info"])

        card = ctk.CTkFrame(
            self,
            fg_color=theme.SURFACE_2,
            corner_radius=theme.RADIUS_CTRL,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
        )
        card.pack(padx=2, pady=2, fill="both", expand=True)

        # Вертикальная цветная полоска слева — индикатор kind.
        stripe = tk.Frame(card, bg=accent, width=3)
        stripe.pack(side="left", fill="y", padx=(0, 0))

        # Иконка (Phosphor glyph для warn/info/err, ✓ для ok).
        icon_font = theme.pick_font(theme.ICON_PREFS)
        sans = theme.pick_font(theme.SANS_PREFS)

        body = ctk.CTkFrame(card, fg_color=theme.SURFACE_2)
        body.pack(side="left", fill="both", expand=True,
                  padx=(12, 12), pady=10)

        tk.Label(
            body, text=glyph, bg=theme.SURFACE_2, fg=accent,
            font=(icon_font, 14),
        ).pack(side="left", padx=(0, 10))

        tk.Label(
            body, text=text, bg=theme.SURFACE_2, fg=theme.TEXT_PRIMARY,
            font=(sans, 11), justify="left", anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Закрытие по клику в любую область.
        for w in (self, card, body):
            w.bind("<Button-1>", lambda _e: self.dismiss())

        if timeout and timeout > 0:
            self.after(timeout, self.dismiss)

    def dismiss(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        cb = self._on_dismiss
        try:
            self.destroy()
        except Exception:
            pass
        if cb:
            try:
                cb(self)
            except Exception:
                pass


class ToastManager:
    """Менеджер стека тостов. Кладёт их в правый-нижний угол `root`."""

    GAP = 8
    MARGIN_X = 24
    MARGIN_Y = 24
    WIDTH = 360

    def __init__(self, root: tk.Misc):
        self._root = root
        self._stack: List[Toast] = []

    def show(self, text: str, kind: str = "info", timeout: int = 3200) -> Toast:
        toast = Toast(
            self._root, text=text, kind=kind, timeout=timeout,
            on_dismiss=self._on_dismissed,
        )
        # Дай тосту посчитать собственный req-размер до позиционирования.
        toast.update_idletasks()
        try:
            toast.geometry(f"{self.WIDTH}x{toast.winfo_reqheight()}")
        except Exception:
            pass
        self._stack.append(toast)
        self._restack()
        return toast

    def _on_dismissed(self, t: Toast) -> None:
        try:
            self._stack.remove(t)
        except ValueError:
            pass
        self._restack()

    def _restack(self) -> None:
        try:
            root_x = self._root.winfo_rootx()
            root_y = self._root.winfo_rooty()
            root_w = self._root.winfo_width()
            root_h = self._root.winfo_height()
        except Exception:
            return
        # снизу-вверх
        y = root_y + root_h - self.MARGIN_Y
        for t in reversed(self._stack):
            try:
                t.update_idletasks()
                h = t.winfo_reqheight()
                w = self.WIDTH
                y -= h
                x = root_x + root_w - self.MARGIN_X - w
                t.geometry(f"{w}x{h}+{x}+{y}")
                y -= self.GAP
            except Exception:
                pass


# ─── EmptyState ───────────────────────────────────────────────────────
class EmptyState(ctk.CTkFrame):
    """Большая пустая зона: иконка-глиф + заголовок + подсказка + CTA."""

    def __init__(
        self,
        master,
        title: str,
        subtitle: str = "",
        icon: str = theme.ICON_INFO,
        cta_text: Optional[str] = None,
        cta_command: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master, fg_color="transparent")

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        icon_font = theme.pick_font(theme.ICON_PREFS)
        sans = theme.pick_font(theme.SANS_PREFS)
        bold = theme.pick_font(theme.SANS_BOLD_PREFS)

        # Иконка в круге.
        icon_wrap = ctk.CTkFrame(
            inner, fg_color=theme.SURFACE_3, corner_radius=32,
            width=64, height=64,
        )
        icon_wrap.pack(pady=(0, 16))
        icon_wrap.pack_propagate(False)
        tk.Label(
            icon_wrap, text=icon, bg=theme.SURFACE_3,
            fg=theme.TEXT_SECONDARY, font=(icon_font, 28),
        ).place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            inner, text=title, bg=master.cget("fg_color") if False else theme.SURFACE_2,
            fg=theme.TEXT_PRIMARY, font=(bold, 14, "bold"),
        ).pack()
        if subtitle:
            tk.Label(
                inner, text=subtitle, bg=theme.SURFACE_2,
                fg=theme.TEXT_TERTIARY, font=(sans, 11),
                wraplength=420, justify="center",
            ).pack(pady=(6, 0))

        if cta_text and cta_command:
            btn = ctk.CTkButton(
                inner, text=cta_text, command=cta_command,
                fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                text_color=theme.SURFACE_0,
                corner_radius=theme.RADIUS_CTRL, height=34, width=180,
                font=(bold, 11, "bold"),
            )
            btn.pack(pady=(18, 0))


# ─── Tooltip ──────────────────────────────────────────────────────────
class Tooltip:
    """Лёгкий tooltip с CTk-look-и-feel.

    Внутри — overrideredirect Toplevel с rounded CTk-фреймом. Появляется
    с маленькой задержкой, прячется на <Leave>. Поведение поверх _Tip:
    можно включать/выключать через ``Tooltip.enabled = False``.
    """

    enabled: bool = True
    delay_ms: int = 350

    _active: Optional[tk.Toplevel] = None
    _pending_after: Optional[str] = None
    _pending_widget: Optional[tk.Misc] = None

    # ──────────────────────────────────────────────────────────────
    @classmethod
    def bind(cls, widget: tk.Misc, text: str) -> None:
        if not text:
            return
        widget.bind("<Enter>", lambda e, w=widget, t=text: cls._on_enter(w, t),
                    add="+")
        widget.bind("<Leave>", lambda e: cls._on_leave(), add="+")
        widget.bind("<ButtonPress>", lambda e: cls._on_leave(), add="+")

    @classmethod
    def _on_enter(cls, widget: tk.Misc, text: str) -> None:
        cls._cancel_pending()
        cls.hide()
        if not cls.enabled:
            return
        cls._pending_widget = widget
        try:
            cls._pending_after = widget.after(
                cls.delay_ms, lambda: cls._show(widget, text),
            )
        except Exception:
            cls._pending_after = None

    @classmethod
    def _on_leave(cls) -> None:
        cls._cancel_pending()
        cls.hide()

    @classmethod
    def _cancel_pending(cls) -> None:
        if cls._pending_after and cls._pending_widget is not None:
            try:
                cls._pending_widget.after_cancel(cls._pending_after)
            except Exception:
                pass
        cls._pending_after = None
        cls._pending_widget = None

    # ──────────────────────────────────────────────────────────────
    @classmethod
    def _show(cls, widget: tk.Misc, text: str) -> None:
        cls.hide()
        try:
            tw = tk.Toplevel(widget)
        except Exception:
            return
        tw.wm_overrideredirect(True)
        try:
            tw.wm_attributes("-topmost", True)
        except Exception:
            pass
        tw.configure(bg=theme.SURFACE_0)

        card = ctk.CTkFrame(
            tw,
            fg_color=theme.SURFACE_3,
            corner_radius=theme.RADIUS_CHIP,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
        )
        card.pack(padx=1, pady=1)
        sans = theme.pick_font(theme.SANS_PREFS)
        tk.Label(
            card, text=text, bg=theme.SURFACE_3,
            fg=theme.TEXT_PRIMARY, font=(sans, 9),
            padx=10, pady=5,
        ).pack()

        tw.update_idletasks()
        try:
            wx = widget.winfo_rootx() + widget.winfo_width() // 2 - tw.winfo_width() // 2
            wy = widget.winfo_rooty() + widget.winfo_height() + 4
            tw.wm_geometry(f"+{wx}+{wy}")
        except Exception:
            pass
        cls._active = tw

    @classmethod
    def hide(cls) -> None:
        if cls._active:
            try:
                cls._active.destroy()
            except Exception:
                pass
            cls._active = None


def bind_tooltip(widget: tk.Misc, text: str) -> None:
    """Удобный шорткат для tooltip.bind — совместим со старым _bind_tip."""
    Tooltip.bind(widget, text)


__all__ = [
    "StatusPill",
    "Badge",
    "Toast",
    "ToastManager",
    "EmptyState",
    "Tooltip",
    "bind_tooltip",
]
