"""
widgets — reusable CTk primitives for the *Light Soft* redesign.

These are the small building blocks used by the new card-based UI:

  * ``Card``         — white rounded container (frame).
  * ``IconCircle``   — tinted circular badge that hosts an icon.
  * ``KPICard``      — big-number tile (icon circle + label + value + sub).
  * ``StatusPill``   — rounded pill with a dot + label (e.g. *● Running*).
  * ``Chip``         — coloured rounded badge (BUY/SELL/symbol chips).
  * ``IconButton``   — square icon-only button (variants: ghost / primary /
                       danger / warn / success).
  * ``SectionHeader``— title + optional counter row.
  * ``RiskBar``      — slim progress bar + numeric label.

All widgets read colours and radii from ``palette.palette_proxy`` so they
follow the active theme automatically.  When the theme is switched at
runtime, the host application is expected to call ``apply_theme()`` which
already triggers ``_apply_runtime_theme`` in ``gui.py`` — that path
rebuilds widgets, so the new colours pick up on first paint.

Designed to render correctly even when no PIL ``CTkImage`` is provided
for an icon: the icon slot simply stays empty, which is useful for early
phases of the redesign before the Lucide icon set is wired in.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Tuple, Union

import customtkinter as ctk

from palette import palette_proxy as p, fonts_proxy as f


# ── Helpers ──────────────────────────────────────────────────────────


def _normalise_tint(name: Optional[str]) -> Tuple[str, str]:
    """Map a tint *name* to ``(bg, fg)`` colour pair from the palette.

    Accepts: ``blue``, ``purple``, ``green``, ``orange``, ``red`` (case
    insensitive) or a literal ``"#RRGGBB"`` hex string for *bg* with the
    accent foreground.  Returns ``(BG, FG)``.
    """
    if not name:
        return p.TINT_BLUE, p.TINT_BLUE_FG
    n = name.lower()
    table = {
        "blue":   (p.TINT_BLUE,   p.TINT_BLUE_FG),
        "purple": (p.TINT_PURPLE, p.TINT_PURPLE_FG),
        "green":  (p.TINT_GREEN,  p.TINT_GREEN_FG),
        "orange": (p.TINT_ORANGE, p.TINT_ORANGE_FG),
        "red":    (p.TINT_RED,    p.TINT_RED_FG),
        # Semantic aliases reused by status pills.
        "success": (p.TINT_GREEN,  p.TINT_GREEN_FG),
        "danger":  (p.TINT_RED,    p.TINT_RED_FG),
        "warn":    (p.TINT_ORANGE, p.TINT_ORANGE_FG),
        "info":    (p.TINT_BLUE,   p.TINT_BLUE_FG),
        "neutral": (p.BORDER_LIGHT, p.FG_LABEL),
    }
    if n in table:
        return table[n]
    if isinstance(name, str) and name.startswith("#"):
        return name, p.ACCENT_FG
    return p.TINT_BLUE, p.TINT_BLUE_FG


# ── Card — generic white rounded container ──────────────────────────


class Card(ctk.CTkFrame):
    """White rounded card with thin border. Drop-shadow-less by design
    (Tk has no shadows; we lean on the border + soft page background).
    """

    def __init__(self, master: Any, *, padding: int = 16, **kw: Any) -> None:
        super().__init__(
            master,
            fg_color=kw.pop("fg_color", p.BG_ROW),
            corner_radius=kw.pop("corner_radius", p.RADIUS_LG),
            border_width=kw.pop("border_width", 1),
            border_color=kw.pop("border_color", p.BORDER),
            **kw,
        )
        self._padding = padding


# ── IconCircle — tinted circular badge ──────────────────────────────


class IconCircle(ctk.CTkFrame):
    """A circular tinted badge that hosts a single icon or short text.

    The circle is faked with ``corner_radius=RADIUS_PILL`` on a fixed
    square frame (CTk's rounded rectangle approximates a circle when w==h
    and radius is very large).
    """

    def __init__(
        self,
        master: Any,
        *,
        size: int = 44,
        tint: Optional[str] = "blue",
        icon: Optional[Any] = None,
        glyph: Optional[str] = None,
        glyph_size: int = 18,
        **kw: Any,
    ) -> None:
        bg, fg = _normalise_tint(tint)
        super().__init__(
            master,
            width=size,
            height=size,
            fg_color=bg,
            corner_radius=p.RADIUS_PILL,
            border_width=0,
            **kw,
        )
        # Lock size so the frame stays square (otherwise child packing
        # would let it collapse vertically and look like a pill).
        self.grid_propagate(False)
        self.pack_propagate(False)
        self._tint_bg = bg
        self._tint_fg = fg
        if icon is not None:
            lbl = ctk.CTkLabel(self, image=icon, text="")
            lbl.place(relx=0.5, rely=0.5, anchor="center")
        elif glyph:
            lbl = ctk.CTkLabel(
                self,
                text=glyph,
                text_color=fg,
                font=("Segoe UI Symbol", glyph_size, "bold"),
            )
            lbl.place(relx=0.5, rely=0.5, anchor="center")


# ── KPICard — big number tile ───────────────────────────────────────


class KPICard(Card):
    """Card with: tinted icon circle + uppercase label + big number +
    sub-text (e.g. *+3.24% today*).

    Use ``set_value()`` to update the displayed number after construction.
    """

    def __init__(
        self,
        master: Any,
        *,
        label: str = "",
        value: str = "—",
        sub_text: str = "",
        sub_color: Optional[str] = None,
        tint: str = "blue",
        icon: Optional[Any] = None,
        glyph: Optional[str] = None,
        **kw: Any,
    ) -> None:
        super().__init__(master, **kw)

        self.columnconfigure(1, weight=1)

        # Typography rhythm:
        #   - LABEL  10 bold uppercase (eyebrow)
        #   - VALUE  24 bold (hero number — sized so $125,893.45 fits a
        #     KPI column at 4-up on a 1280-wide window)
        #   - SUB    10 normal (caption)
        # 24px internal padding + 20px gap between icon and text.
        self._icon = IconCircle(self, size=40, tint=tint, icon=icon, glyph=glyph)
        self._icon.grid(row=0, column=0, rowspan=3, padx=(20, 20), pady=20, sticky="n")

        self._lbl = ctk.CTkLabel(
            self,
            text=label.upper(),
            text_color=p.FG_LABEL,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )
        self._lbl.grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=(20, 0))

        self._val = ctk.CTkLabel(
            self,
            text=value,
            text_color=p.FG,
            font=("Segoe UI", 24, "bold"),
            anchor="w",
        )
        self._val.grid(row=1, column=1, sticky="ew", padx=(0, 20), pady=(4, 0))

        self._sub = ctk.CTkLabel(
            self,
            text=sub_text,
            text_color=sub_color or p.GREEN_DIM,
            font=("Segoe UI", 10, "normal"),
            anchor="w",
        )
        self._sub.grid(row=2, column=1, sticky="ew", padx=(0, 20), pady=(2, 20))

    def set_value(
        self,
        value: str,
        *,
        sub_text: Optional[str] = None,
        sub_color: Optional[str] = None,
    ) -> None:
        self._val.configure(text=value)
        if sub_text is not None:
            self._sub.configure(text=sub_text)
        if sub_color is not None:
            self._sub.configure(text_color=sub_color)


# ── StatusPill — rounded pill with dot + text ───────────────────────


class StatusPill(ctk.CTkFrame):
    """Rounded pill: coloured dot + label, e.g. ``● Running``.

    ``state`` accepts the same colour aliases as ``tint``: ``success`` /
    ``danger`` / ``warn`` / ``info`` / ``neutral``.
    """

    _DOT_COLOR = {
        "success": "GREEN",
        "danger":  "RED",
        "warn":    "YELLOW",
        "info":    "ACCENT",
        "neutral": "FG_DIM",
    }

    def __init__(
        self,
        master: Any,
        *,
        text: str = "",
        state: str = "success",
        **kw: Any,
    ) -> None:
        bg, _fg = _normalise_tint(state)
        super().__init__(
            master,
            fg_color=bg,
            corner_radius=p.RADIUS_PILL,
            border_width=0,
            **kw,
        )
        # Pill geometry: 6 vertical / 12 horizontal padding — smaller
        # than the previous 8/14 since the larger version read as a
        # button.  Dot 10pt, label 10pt bold so the pill stays in the
        # supporting-element scale.
        self._dot = ctk.CTkLabel(
            self,
            text="●",
            text_color=getattr(p, self._DOT_COLOR.get(state, "GREEN")),
            font=("Segoe UI", 10, "bold"),
        )
        self._dot.pack(side="left", padx=(12, 5), pady=6)
        self._lbl = ctk.CTkLabel(
            self,
            text=text,
            text_color=getattr(p, self._DOT_COLOR.get(state, "GREEN")),
            font=("Segoe UI", 10, "bold"),
        )
        self._lbl.pack(side="left", padx=(0, 12), pady=6)

    def set(self, text: str, *, state: Optional[str] = None) -> None:
        self._lbl.configure(text=text)
        if state is not None:
            bg, _ = _normalise_tint(state)
            colour = getattr(p, self._DOT_COLOR.get(state, "GREEN"))
            self.configure(fg_color=bg)
            self._dot.configure(text_color=colour)
            self._lbl.configure(text_color=colour)


# ── Chip — coloured rounded badge (BUY / SELL / symbol) ─────────────


class Chip(ctk.CTkLabel):
    """Coloured rounded badge with no icon. Used for BUY/SELL chips,
    symbol-pairs, status markers in the trade log."""

    def __init__(
        self,
        master: Any,
        *,
        text: str = "",
        tint: str = "blue",
        bold: bool = True,
        **kw: Any,
    ) -> None:
        bg, fg = _normalise_tint(tint)
        super().__init__(
            master,
            text=text,
            fg_color=bg,
            text_color=fg,
            corner_radius=p.RADIUS_PILL,
            # 9pt is the standard chip size — bigger reads as a button.
            # 3px vertical pad still gives the chip a pill shape but keeps
            # it visually small next to 18pt headings (so it sits as a
            # tag, not as a sibling element).
            font=("Segoe UI", 9, "bold" if bold else "normal"),
            padx=10,
            pady=3,
            **kw,
        )


# ── IconButton — square icon-only button ────────────────────────────


class IconButton(ctk.CTkButton):
    """Square icon-only button. Variants:

      * ``ghost``    — transparent bg, neutral icon, used in row actions.
      * ``primary``  — accent-blue filled, white icon.
      * ``success``  — green filled.
      * ``danger``   — red filled.
      * ``warn``     — amber filled.
      * ``soft``     — tinted bg matching the icon meaning (subtle).
    """

    _VARIANTS = {
        "ghost":   ("transparent", "FG_LABEL",  "BG_ROW_HOVER"),
        "primary": ("ACCENT",      "ACCENT_FG", "ACCENT_H"),
        "success": ("GREEN",       "ACCENT_FG", "GREEN_DIM"),
        "danger":  ("RED",         "ACCENT_FG", "RED_DIM"),
        "warn":    ("YELLOW",      "ACCENT_FG", "YELLOW_DIM"),
    }

    def __init__(
        self,
        master: Any,
        *,
        icon: Optional[Any] = None,
        text: str = "",
        variant: str = "ghost",
        size: int = 32,
        command: Optional[Callable[[], None]] = None,
        **kw: Any,
    ) -> None:
        bg_tok, fg_tok, hover_tok = self._VARIANTS.get(variant, self._VARIANTS["ghost"])
        bg = bg_tok if bg_tok == "transparent" else getattr(p, bg_tok)
        fg = getattr(p, fg_tok)
        hover = getattr(p, hover_tok) if hover_tok != "transparent" else None
        super().__init__(
            master,
            width=size,
            height=size,
            text=text,
            image=icon,
            fg_color=bg,
            hover_color=hover or bg,
            text_color=fg,
            corner_radius=p.RADIUS_MD,
            border_width=0,
            command=command,
            **kw,
        )


# ── SectionHeader — section title + optional counter ────────────────


class SectionHeader(ctk.CTkFrame):
    """One-line header row: ``TITLE  2/10  …actions…``.

    Use ``add_action(widget)`` to append a button to the right side.
    """

    def __init__(
        self,
        master: Any,
        *,
        title: str = "",
        counter: Optional[str] = None,
        **kw: Any,
    ) -> None:
        super().__init__(
            master,
            fg_color=kw.pop("fg_color", "transparent"),
            **kw,
        )
        self.columnconfigure(2, weight=1)

        # Section title reads as a heading: 12pt bold uppercase, neutral
        # FG colour.  Counter pill sits 12px after the title and uses the
        # accent colour so it can be parsed as metadata, not text body.
        self._title = ctk.CTkLabel(
            self,
            text=title.upper(),
            text_color=p.FG,
            font=("Segoe UI", 12, "bold"),
        )
        self._title.grid(row=0, column=0, padx=(0, 12), sticky="w")

        self._counter = ctk.CTkLabel(
            self,
            text=counter or "",
            text_color=p.ACCENT,
            font=("Segoe UI", 11, "bold"),
        )
        self._counter.grid(row=0, column=1, sticky="w")

        # Right-side actions live in a sub-frame for easy ``pack``.
        self._actions = ctk.CTkFrame(self, fg_color="transparent")
        self._actions.grid(row=0, column=3, sticky="e")

    def set_counter(self, text: str) -> None:
        self._counter.configure(text=text)

    def add_action(self, widget: Any, *, padx: Tuple[int, int] = (6, 0)) -> None:
        widget.pack(in_=self._actions, side="left", padx=padx)


# ── RiskBar — slim progress bar + numeric label ─────────────────────


class RiskBar(ctk.CTkFrame):
    """Slim progress bar with a numeric label (e.g. ``1.0%``).

    ``value`` is in ``[0, 1]``. Colour shifts from accent → warn → danger
    as the value crosses ``warn_at`` / ``danger_at`` thresholds.
    """

    def __init__(
        self,
        master: Any,
        *,
        value: float = 0.0,
        label: Optional[str] = None,
        width: int = 110,
        warn_at: float = 0.6,
        danger_at: float = 0.85,
        **kw: Any,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kw)
        self._warn_at = warn_at
        self._danger_at = danger_at

        self._label = ctk.CTkLabel(
            self,
            text=label if label is not None else f"{value * 100:.1f}%",
            text_color=p.FG,
            font=("Segoe UI", 9, "bold"),
            anchor="e",
        )
        self._label.pack(side="top", anchor="e", pady=(0, 2))

        self._bar = ctk.CTkProgressBar(
            self,
            width=width,
            height=6,
            corner_radius=p.RADIUS_PILL,
            fg_color=p.BORDER,
            progress_color=p.ACCENT,
        )
        self._bar.set(max(0.0, min(1.0, value)))
        self._bar.pack(side="top", fill="x")
        self.set(value, label=label)

    def _colour_for(self, value: float) -> str:
        if value >= self._danger_at:
            return p.RED
        if value >= self._warn_at:
            return p.YELLOW
        return p.ACCENT

    def set(self, value: float, *, label: Optional[str] = None) -> None:
        v = max(0.0, min(1.0, value))
        self._bar.set(v)
        self._bar.configure(progress_color=self._colour_for(v))
        self._label.configure(
            text=label if label is not None else f"{v * 100:.1f}%"
        )


__all__ = [
    "Card",
    "IconCircle",
    "KPICard",
    "StatusPill",
    "Chip",
    "IconButton",
    "SectionHeader",
    "RiskBar",
]
