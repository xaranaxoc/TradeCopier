"""
FTH Trade Copier — фабрики стилизованных CustomTkinter-виджетов.

Здесь собирается ВНЕШНИЙ ВИД. Экраны (gui / prototype) только зовут эти фабрики
и навешивают обработчики. Логика приложения сюда не попадает.

Все цвета/шрифты/радиусы берутся из theme.py — единого источника правды.
"""

import customtkinter as ctk

import theme as T


# ── Кнопки ──────────────────────────────────────────────────

def make_button(parent, text, command=None, kind="neutral", width=0, **kw):
    """kind: accent | danger | neutral | ghost."""
    if kind == "accent":
        fg, hover, txt = T.ACCENT, T.ACCENT_H, "#04141A"
    elif kind == "danger":
        fg, hover, txt = T.RED_DIM, T.RED, "#FFFFFF"
    elif kind == "ghost":
        fg, hover, txt = "transparent", T.BG_ROW_HOVER, T.FG_LABEL
    else:  # neutral
        fg, hover, txt = T.BG_INPUT, T.BG_ROW_HOVER, T.FG_LABEL
    return ctk.CTkButton(
        parent, text=text, command=command,
        fg_color=fg, hover_color=hover, text_color=txt,
        corner_radius=T.RADIUS_BTN, height=T.BTN_HEIGHT,
        width=width or 0, font=ctk.CTkFont(T.FONT_FAMILY, 12, "bold"),
        border_width=0, **kw,
    )


def make_icon_button(parent, glyph, command=None, color=None, hover=None, tip=None):
    """Маленькая квадратная иконка-кнопка (⚙ / ✖ / 📈 / ⚠)."""
    btn = ctk.CTkButton(
        parent, text=glyph, command=command, width=T.ICON_BTN_SIZE,
        height=T.ICON_BTN_SIZE, corner_radius=T.RADIUS_BTN,
        fg_color="transparent", hover_color=T.BG_ROW_HOVER,
        text_color=color or T.FG_DIM,
        font=ctk.CTkFont(T.FONT_FAMILY, 13),
    )
    return btn


# ── Карточки / панели ───────────────────────────────────────

def make_card(parent, **kw):
    return ctk.CTkFrame(
        parent, corner_radius=T.RADIUS_CARD, fg_color=T.BG_ROW,
        border_width=1, border_color=T.BORDER, **kw,
    )


def make_accent_panel(parent, accent=None, **kw):
    """Панель с цветной полоской слева (как блок 'МАСТЕР')."""
    wrap = ctk.CTkFrame(parent, corner_radius=T.RADIUS_CARD, fg_color=T.BG_ROW,
                        border_width=1, border_color=T.BORDER, **kw)
    strip = ctk.CTkFrame(wrap, width=T.ACCENT_STRIP_W, corner_radius=2,
                         fg_color=accent or T.ACCENT)
    strip.place(x=3, y=8, relheight=0.78)
    body = ctk.CTkFrame(wrap, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=(T.PAD_CARD, T.PAD_CARD),
              pady=T.PAD_GAP)
    return wrap, body


def make_kpi(parent, title, value="—", value_color=None):
    """KPI-карточка: подпись сверху, крупное значение снизу."""
    card = make_card(parent)
    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=T.PAD_CARD, pady=(10, 10))
    ctk.CTkLabel(inner, text=title.upper(), text_color=T.FG_DIM,
                 font=ctk.CTkFont(T.FONT_FAMILY, 10),
                 anchor="w").pack(anchor="w")
    val = ctk.CTkLabel(inner, text=value, text_color=value_color or T.FG,
                       font=ctk.CTkFont(T.FONT_FAMILY, 20, "bold"), anchor="w")
    val.pack(anchor="w", pady=(2, 0))
    return card, val


# ── Поля / подписи ──────────────────────────────────────────

def make_entry(parent, placeholder="", width=200, **kw):
    return ctk.CTkEntry(
        parent, placeholder_text=placeholder, width=width,
        corner_radius=T.RADIUS_INPUT, height=T.BTN_HEIGHT,
        fg_color=T.BG_INPUT, border_color=T.BORDER, text_color=T.FG,
        font=ctk.CTkFont(T.FONT_FAMILY, 11), **kw,
    )


def make_label(parent, text, kind="body"):
    """kind: title | h2 | body | dim | label | accent."""
    spec = {
        "title":  (ctk.CTkFont(T.FONT_FAMILY, 16, "bold"), T.FG),
        "h2":     (ctk.CTkFont(T.FONT_FAMILY, 13, "bold"), T.FG),
        "body":   (ctk.CTkFont(T.FONT_FAMILY, 11), T.FG),
        "dim":    (ctk.CTkFont(T.FONT_FAMILY, 10), T.FG_DIM),
        "label":  (ctk.CTkFont(T.FONT_FAMILY, 10, "bold"), T.FG_LABEL),
        "accent": (ctk.CTkFont(T.FONT_FAMILY, 11, "bold"), T.ACCENT),
    }[kind]
    return ctk.CTkLabel(parent, text=text, font=spec[0], text_color=spec[1])


def make_pill(parent, text, color):
    """Статус-чип со скруглением (зелёный / красный / cyan)."""
    return ctk.CTkLabel(
        parent, text=text, fg_color=T.BG_INPUT, text_color=color,
        corner_radius=T.RADIUS_PILL, font=ctk.CTkFont(T.FONT_FAMILY, 10, "bold"),
        padx=10, pady=2,
    )


def make_divider(parent):
    return ctk.CTkFrame(parent, height=1, fg_color=T.DIVIDER, corner_radius=0)


def apply_theme():
    """Применить тёмную тему + JSON-палитру FTH. Звать один раз при старте."""
    import os
    ctk.set_appearance_mode("dark")
    here = os.path.dirname(os.path.abspath(__file__))
    theme_path = os.path.join(here, "fth_theme.json")
    if os.path.exists(theme_path):
        ctk.set_default_color_theme(theme_path)
