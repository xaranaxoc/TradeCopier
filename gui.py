"""
MT5 Local Copy Trader — GUI (tkinter + CustomTkinter)
"""

import os
import sys
import json
import time
import uuid
import subprocess
import threading
import ctypes
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, filedialog, messagebox, font as tkfont
from typing import Dict, List, Optional

import customtkinter as ctk

import theme
import components

# ── CTk globals (тёмная тема + синий акцент) ─────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Регистрируем встроенные шрифты (Inter, Phosphor) до создания окон.
theme.register_bundled_fonts()

try:
    import MetaTrader5 as mt5
    _MT5_OK = True
except ImportError:
    _MT5_OK = False

try:
    import pystray
    from PIL import Image as PILImage
    _PYSTRAY_OK = True
except ImportError:
    _PYSTRAY_OK = False

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False

try:
    from copier import CopyTrader, is_terminal_running, activate_terminal
    _COPIER_OK = True
except ImportError:
    _COPIER_OK = False

try:
    import license as lic_mod
    _LIC_OK = True
except ImportError:
    _LIC_OK = False

try:
    import updater as upd_mod
    _UPD_OK = True
except ImportError:
    _UPD_OK = False

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    _BUNDLE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = BASE_DIR

APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MT5CopyTrader")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "config.json")
STATE_FILE = os.path.join(APP_DATA_DIR, "state.json")
LOGS_DIR = os.path.join(APP_DATA_DIR, "logs")
TRADES_FILE = os.path.join(APP_DATA_DIR, "trades.json")
TRADES_KEEP_DAYS = 7

IMG_DIR = os.path.join(_BUNDLE_DIR, "img")
ICON_DEFAULT = os.path.join(IMG_DIR, "convertico-fth.ico")
ICON_CYAN = os.path.join(IMG_DIR, "convertico-fth-cyan.ico")

# ── Цветовая палитра (neon cyan) ───────────────────────────
# Источник правды — theme.py. Имена ниже оставлены как алиасы,
# чтобы существующий код продолжал работать без правок.
BG_DEEP       = theme.SURFACE_0
BG            = theme.SURFACE_1
BG_ROW        = theme.SURFACE_ROW
BG_ROW_HOVER  = theme.SURFACE_ROW_HOVER
BG_INPUT      = theme.SURFACE_INPUT
BG_HEADER     = theme.SURFACE_HEADER
FG            = theme.TEXT_PRIMARY
FG_DIM        = theme.TEXT_TERTIARY
FG_LABEL      = theme.TEXT_SECONDARY
FG_MUTED      = theme.TEXT_DISABLED
ACCENT        = theme.ACCENT
ACCENT_H      = theme.ACCENT_HOVER
ACCENT_DIM    = theme.ACCENT_DIM
CYAN_GLOW     = theme.ACCENT_GLOW
GREEN         = theme.STATUS_OK
GREEN_DIM     = theme.STATUS_OK_DIM
GREEN_GLOW    = theme.STATUS_OK_GLOW
RED           = theme.STATUS_ERR
RED_DIM       = theme.STATUS_ERR_DIM
RED_GLOW      = theme.STATUS_ERR_GLOW
YELLOW        = theme.STATUS_WARN
YELLOW_DIM    = theme.STATUS_WARN_DIM
BORDER        = theme.BORDER_DEFAULT
BORDER_LIGHT  = theme.BORDER_STRONG
DIVIDER       = theme.DIVIDER

# ── Шрифты ──────────────────────────────────────────────────
# Конкретные семейства подбираются в App._build_ui через
# theme.resolve_font_families() — там уже учтены встроенные
# Inter / Segoe UI / fallbacks.
FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_VAL = ("Segoe UI", 11)
FONT_VAL_BOLD = ("Segoe UI", 11, "bold")
FONT_MONO = ("Cascadia Mono", 9)
FONT_MONO_SM = ("Cascadia Mono", 8)

FONT = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 9, "bold")
FONT_SM = ("Segoe UI", 8)
FONT_XS = ("Segoe UI", 7)


# ── CTk-стилистика: радиусы / карточки / pill-кнопки ────────────
CORNER_LG = theme.RADIUS_CARD
CORNER_MD = theme.RADIUS_CTRL
CORNER_SM = 8  # input fields — между chip и control

CARD_BG       = theme.SURFACE_2
CARD_BG_HOVER = theme.SURFACE_3
SOFT_BORDER   = theme.BORDER_SOFT


def _pick_font(prefs, fallback="TkDefaultFont"):
    """Совместимость со старым API — делегирует в theme.pick_font."""
    return theme.pick_font(prefs, fallback)


def _resolve_fonts():
    """Подбор sans-семейств. Inter (встроен) → Segoe UI → fallbacks.

    Возвращает (sans_reg, sans_bold, sans_black) — старая сигнатура,
    которой ждёт остальной gui.py.
    """
    sans_reg, sans_bold, sans_black, _mono, _icon = theme.resolve_font_families()
    return sans_reg, sans_bold, sans_black


class PillButton(ctk.CTkButton):
    """Скруглённая pill-кнопка с тремя вариантами (primary/danger/ghost).

    Имеет shim `.config(...)`, чтобы старый код вида
    `btn.config(state="disabled")` продолжал работать.
    """

    # Phase 3b: добавлены вариант `subtle`, focus-ring и loading-state.
    def __init__(self, master, text, command=None, variant="ghost",
                 icon=None, width=None, focus_ring=True, **kw):
        if variant == "primary":
            fg, hover, txt = ACCENT, ACCENT_H, "#FFFFFF"
        elif variant == "danger":
            fg, hover, txt = RED_DIM, RED, "#FFFFFF"
        elif variant == "subtle":
            fg, hover, txt = "transparent", BG_INPUT, FG_DIM
        else:
            fg, hover, txt = BG_INPUT, CARD_BG_HOVER, FG_LABEL
        label = f"{icon}  {text}" if icon else text
        self._variant = variant
        self._stored_text = label
        kwargs = dict(
            master=master, text=label, command=command,
            fg_color=fg, hover_color=hover, text_color=txt,
            corner_radius=CORNER_MD, height=32,
            border_width=0, border_color=ACCENT_DIM,
        )
        if width is not None:
            kwargs["width"] = width
        kwargs.update(kw)
        super().__init__(**kwargs)

        if focus_ring:
            self.bind("<FocusIn>",  lambda _e: self.configure(border_width=2),
                      add="+")
            self.bind("<FocusOut>", lambda _e: self.configure(border_width=0),
                      add="+")

    def set_loading(self, loading: bool, loading_text: str = "…"):
        """Включает «загружается»: блокирует кнопку и временно меняет текст."""
        if loading:
            try:
                self._stored_text = self.cget("text")
            except Exception:
                pass
            self.configure(text=loading_text, state="disabled")
        else:
            self.configure(text=self._stored_text, state="normal")

    def config(self, **kw):  # type: ignore[override]
        if "bg" in kw:
            kw["fg_color"] = kw.pop("bg")
        if "fg" in kw:
            kw["text_color"] = kw.pop("fg")
        self.configure(**kw)


class IconButton(ctk.CTkButton):
    """Квадратная иконочная кнопка.

    Phase 3b: если передан ``icon`` (Phosphor codepoint), кнопка рисует
    его шрифтом Phosphor — чёткие, единообразные иконки вместо случайных
    Unicode-символов. Параметр ``glyph`` оставлен для обратной
    совместимости (обычная Unicode-строка, текущий шрифт).
    """

    def __init__(self, master, glyph=None, command=None, color=FG_DIM,
                 hover_color=None, size=34, icon=None, **kw):
        sym = icon if icon is not None else (glyph or "")
        font = kw.pop("font", None)
        if font is None and icon is not None:
            icon_family = theme.pick_font(theme.ICON_PREFS)
            font = (icon_family, max(12, int(size * 0.5)))
        kwargs = dict(
            master=master, text=sym, command=command,
            width=size, height=size,
            fg_color=BG_INPUT,
            hover_color=hover_color or CARD_BG_HOVER,
            text_color=color,
            corner_radius=CORNER_MD,
            border_width=0, border_color=ACCENT_DIM,
        )
        if font is not None:
            kwargs["font"] = font
        kwargs.update(kw)
        super().__init__(**kwargs)

        self.bind("<FocusIn>",  lambda _e: self.configure(border_width=2),
                  add="+")
        self.bind("<FocusOut>", lambda _e: self.configure(border_width=0),
                  add="+")


def _make_card(parent, **kw):
    """Скруглённая карточка с тонкой границей — базовый «контейнер»."""
    defaults = dict(
        corner_radius=CORNER_LG,
        fg_color=CARD_BG,
        border_width=1,
        border_color=SOFT_BORDER,
    )
    defaults.update(kw)
    return ctk.CTkFrame(parent, **defaults)


# Phase 3a: StatusPill переехал в components.py.
StatusPill = components.StatusPill


# ── Persistence: trades ─────────────────────────────────────

def _save_trade(trade: Dict):
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        trades = []
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, "r", encoding="utf-8") as f:
                trades = json.load(f)
        trade["date"] = datetime.now().strftime("%Y-%m-%d")
        trades.append(trade)
        cutoff = (datetime.now() - timedelta(days=TRADES_KEEP_DAYS)).strftime("%Y-%m-%d")
        trades = [t for t in trades if t.get("date", "") >= cutoff]
        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(trades, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _load_trades() -> List[Dict]:
    if not os.path.exists(TRADES_FILE):
        return []
    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            trades = json.load(f)
        cutoff = (datetime.now() - timedelta(days=TRADES_KEEP_DAYS)).strftime("%Y-%m-%d")
        return [t for t in trades if t.get("date", "") >= cutoff]
    except Exception:
        return []

# ── Tooltip (info mode) ────────────────────────────────────

# Phase 3a: tooltip переехал в components.Tooltip с CTk-look-и-feel.
# Здесь оставлен тонкий alias, чтобы старый код (dialogs / dialogs_ctk и
# куча мест в gui.py) продолжал работать без правок.
_Tip = components.Tooltip


def _bind_tip(widget, text):
    components.Tooltip.bind(widget, text)

# ── Символы-алиасы ─────────────────────────────────────────

_SYMBOL_ALIASES = {
    "DE30": "DE40", "DE40": "DE30",
    "DE35": "DE40", "UK100": "UK100USD",
    "NAS100": "USTECH", "USTECH": "NAS100",
    "US500": "US30", "SPX500": "US500",
    "US30": "US30USD", "DJ30": "US30",
    "XAUUSD": "GOLD", "GOLD": "XAUUSD",
    "XAGUSD": "SILVER", "SILVER": "XAGUSD",
    "WTI": "USOIL", "USOIL": "WTI",
    "BRENT": "UKOIL", "UKOIL": "BRENT",
    "BTCUSD": "BTCUSDT", "BTCUSDT": "BTCUSD",
    "ETHUSD": "ETHUSDT", "ETHUSDT": "ETHUSD",
    "EURUSD": "EURUSD.", "GBPUSD": "GBPUSD.",
    "USDJPY": "USDJPY.", "AUDUSD": "AUDUSD.",
}

# ── COL_SPEC ────────────────────────────────────────────────
# (col_index, header, min_width, weight, anchor)
COL_SPEC = [
    (0, "ON", 36, 0, "center"),
    (1, "", 20, 0, "center"),
    (2, "ИМЯ", 72, 0, "w"),
    (3, "ЛОГИН", 72, 0, "w"),
    (4, "БАЛАНС", 88, 0, "e"),
    (5, "ЭКВИТИ", 88, 0, "e"),
    (6, "P&L", 72, 0, "e"),
    (7, "СИМВОЛЫ", 100, 1, "w"),
    (8, "РИСК", 60, 0, "e"),
    (9, "СДЕЛ/Д", 54, 0, "center"),
    (10, "УБЫТ/Д", 110, 0, "center"),
    (11, "", 110, 0, "e"),
]


# ── SymbolPickerDialog ──────────────────────────────────────

class SymbolPickerDialog(tk.Toplevel):
    def __init__(self, parent, symbols: List[str], title_text: str = "Выбор символа"):
        super().__init__(parent)
        self.selected: Optional[str] = None
        self._all_symbols = symbols
        self.title(title_text)
        self.configure(bg=BG)
        self.resizable(False, False)
        icon = ICON_CYAN if (hasattr(parent, '_parent_app') and
            getattr(parent._parent_app, '_trader', None) and
            parent._parent_app._trader.is_running()) else ICON_DEFAULT
        if os.path.exists(icon):
            self.iconbitmap(icon)
        self.grab_set()
        self._build()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        pw, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw2, py2 = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"{300}x{380}+{pw + (pw2 - 300) // 2}+{py + (py2 - 380) // 2}")

    def _build(self):
        frm = tk.Frame(self, bg=BG)
        frm.pack(fill="x", padx=10, pady=8)
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *_: self._filter())
        ent = tk.Entry(frm, textvariable=self.var_search, width=28,
                       bg=BG_INPUT, fg=FG, insertbackground=FG, relief="flat",
                       font=FONT, highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=ACCENT)
        ent.pack(fill="x")
        ent.focus_set()

        frm_list = tk.Frame(self, bg=BG)
        frm_list.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        self.listbox = tk.Listbox(frm_list, bg=BG_ROW, fg=FG, font=FONT,
                                   selectbackground=ACCENT, selectforeground="white",
                                   relief="flat", highlightthickness=0, activestyle="none")
        sb = ttk.Scrollbar(frm_list, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<Double-1>", lambda e: self._pick())
        self.listbox.bind("<Return>", lambda e: self._pick())
        for s in self._all_symbols:
            self.listbox.insert("end", s)

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=10, pady=(0, 8))
        self._btn(btn_frame, "Выбрать", self._pick, accent=True).pack(side="left", padx=(0, 6))
        self._btn(btn_frame, "Отмена", self.destroy).pack(side="left")

    def _btn(self, parent, text, cmd, accent=False):
        bg = ACCENT if accent else BG_INPUT
        fg = "white" if accent else FG_DIM
        abg = ACCENT_H if accent else BG_ROW_HOVER
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, relief="flat",
                         font=FONT_BOLD if accent else FONT,
                         activebackground=abg, activeforeground=fg,
                         cursor="hand2", padx=12, pady=2)

    def _filter(self):
        query = self.var_search.get().strip().upper()
        self.listbox.delete(0, "end")
        for s in self._all_symbols:
            if not query or query in s.upper():
                self.listbox.insert("end", s)

    def _pick(self):
        sel = self.listbox.curselection()
        if sel:
            self.selected = self.listbox.get(sel[0])
            self.destroy()


# ── SlaveDialog ─────────────────────────────────────────────

class SlaveDialog(tk.Toplevel):
    def __init__(self, parent, slave_data: Optional[Dict] = None):
        super().__init__(parent)
        self.result: Optional[Dict] = None
        self._symbol_rows: List[Dict] = []
        self._master_symbols: List[str] = []
        self._slave_symbols: List[str] = []
        self._parent_app = parent
        self._updating_risk = False
        self._skip_suggest = True
        self._edit_id = (slave_data or {}).get("id", "")
        self.title("Настройки аккаунта")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.withdraw()
        icon = ICON_CYAN if getattr(parent, '_trader', None) and parent._trader.is_running() else ICON_DEFAULT
        if os.path.exists(icon):
            self.iconbitmap(icon)
        data = slave_data or {}
        self._build(data)
        self._center(parent)
        self.deiconify()
        self.grab_set()
        self._load_symbols()
        self._skip_suggest = False

    def _center(self, parent):
        self.update_idletasks()
        pw, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw2, py2 = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw + (pw2 - w) // 2}+{py + (py2 - h) // 2}")

    def _lbl(self, parent, text, **kw):
        return tk.Label(parent, text=text, bg=BG, fg=FG_LABEL, font=FONT_SM, **kw)

    def _ent(self, parent, var=None, width=28, **kw):
        return tk.Entry(parent, textvariable=var, width=width,
                        bg=BG_INPUT, fg=FG, insertbackground=FG, relief="flat",
                        font=FONT, highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT, **kw)

    def _btn(self, parent, text, cmd, accent=False, small=False):
        bg = ACCENT if accent else BG_INPUT
        fg = "white" if accent else FG_DIM
        abg = ACCENT_H if accent else BG_ROW_HOVER
        f = (FONT_BOLD if accent else FONT_SM) if not small else FONT_XS
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, relief="flat",
                         font=f, activebackground=abg, activeforeground=fg,
                         cursor="hand2", padx=10, pady=2)

    def _build(self, data: Dict):
        pad = {"padx": 12, "pady": 3}
        frm_top = tk.Frame(self, bg=BG)
        frm_top.pack(fill="x", **pad)

        self._lbl(frm_top, "Имя").grid(row=0, column=0, sticky="w", pady=2)
        self.var_name = tk.StringVar(value=data.get("name", ""))
        self._ent(frm_top, self.var_name, 26).grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=2)

        self._lbl(frm_top, "terminal64.exe").grid(row=1, column=0, sticky="w", pady=2)
        self.var_path = tk.StringVar(value=data.get("path", ""))
        path_frame = tk.Frame(frm_top, bg=BG)
        path_frame.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=2)
        self._ent(path_frame, self.var_path, 20).pack(side="left", fill="x", expand=True)
        btn_browse_s = self._btn(path_frame, "...", self._browse, small=True)
        btn_browse_s.pack(side="left", padx=(4, 0))
        _bind_tip(btn_browse_s, "Выбрать путь к terminal64.exe слейва")

        tk.Frame(self, bg=DIVIDER, height=1).pack(fill="x", padx=12, pady=6)

        sym_header = tk.Frame(self, bg=BG)
        sym_header.pack(fill="x", padx=12, pady=(2, 0))
        self._lbl(sym_header, "Символы (мастер \u2192 слейв)").pack(side="left")
        btn_load = self._btn(sym_header, "\u21E9 Загрузить", self._load_symbols, small=True)
        btn_load.pack(side="right")
        _bind_tip(btn_load, "Загрузить символы из запущенных терминалов")

        self.lbl_sym_status = tk.Label(self, text="", bg=BG, fg=FG_DIM, font=FONT_XS)
        self.lbl_sym_status.pack(anchor="w", padx=12)

        self.sym_frame = tk.Frame(self, bg=BG)
        self.sym_frame.pack(fill="x", padx=12, pady=2)

        symbol_map = data.get("symbol_map", {})
        for master_sym, slave_sym in symbol_map.items():
            self._add_symbol_row(master_sym, slave_sym)

        btn_add_sym = self._btn(self, "+ Символ", self._add_symbol_row, small=True)
        btn_add_sym.pack(anchor="w", padx=12, pady=(0, 2))
        _bind_tip(btn_add_sym, "Добавить строку маппинга символов")

        tk.Frame(self, bg=DIVIDER, height=1).pack(fill="x", padx=12, pady=6)

        # ── Риск ─────────────────────────────────────────────
        frm_risk = tk.Frame(self, bg=BG)
        frm_risk.pack(fill="x", padx=12, pady=2)

        self.var_risk_type = tk.StringVar(value=data.get("risk_type", "percent"))

        risk_value = data.get("risk_value", 1.0)
        risk_type = data.get("risk_type", "percent")

        self._lbl(frm_risk, "Риск %").grid(row=0, column=0, sticky="w", pady=2)
        pct_frame = tk.Frame(frm_risk, bg=BG)
        pct_frame.grid(row=0, column=1, sticky="w", padx=(6, 0), pady=2)
        self.var_risk_pct = tk.StringVar(
            value=str(risk_value) if risk_type == "percent" else "")
        self._ent(pct_frame, self.var_risk_pct, 8).pack(side="left")

        self._lbl(frm_risk, "Риск $").grid(row=1, column=0, sticky="w", pady=2)
        doll_frame = tk.Frame(frm_risk, bg=BG)
        doll_frame.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=2)
        self.var_risk_doll = tk.StringVar(
            value=str(risk_value) if risk_type == "fixed" else "")
        self._ent(doll_frame, self.var_risk_doll, 8).pack(side="left")

        self.lbl_risk_hint = tk.Label(frm_risk, text="", bg=BG, fg=FG_DIM, font=FONT_XS)
        self.lbl_risk_hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        self.var_risk_pct.trace_add("write", lambda *_: self._sync_risk("percent"))
        self.var_risk_doll.trace_add("write", lambda *_: self._sync_risk("fixed"))

        self._lbl(frm_risk, "Лот без SL").grid(row=3, column=0, sticky="w", pady=2)
        self.var_default_lot = tk.StringVar(value=str(data.get("default_lot", "0.01")))
        self._ent(frm_risk, self.var_default_lot, 8).grid(row=3, column=1, sticky="w", padx=(6, 0), pady=2)

        self._lbl(frm_risk, "Макс. просадка %").grid(row=4, column=0, sticky="w", pady=2)
        self.var_max_drawdown = tk.StringVar(value=str(data.get("max_drawdown", 0)))
        self._ent(frm_risk, self.var_max_drawdown, 8).grid(row=4, column=1, sticky="w", padx=(6, 0), pady=2)
        tk.Label(frm_risk, text="0 = выкл", bg=BG, fg=FG_DIM, font=FONT_XS).grid(
            row=5, column=1, sticky="w", padx=(6, 0))

        self._lbl(frm_risk, "Макс. сделок/день").grid(row=6, column=0, sticky="w", pady=2)
        self.var_max_trades = tk.StringVar(value=str(data.get("max_trades_per_day", 0)))
        self._ent(frm_risk, self.var_max_trades, 8).grid(row=6, column=1, sticky="w", padx=(6, 0), pady=2)
        tk.Label(frm_risk, text="0 = выкл", bg=BG, fg=FG_DIM, font=FONT_XS).grid(
            row=7, column=1, sticky="w", padx=(6, 0))

        self._lbl(frm_risk, "Макс. убыт/день $").grid(row=8, column=0, sticky="w", pady=2)
        self.var_daily_loss = tk.StringVar(value=str(data.get("daily_loss_limit", 0)))
        self._ent(frm_risk, self.var_daily_loss, 8).grid(row=8, column=1, sticky="w", padx=(6, 0), pady=2)
        tk.Label(frm_risk, text="0 = выкл", bg=BG, fg=FG_DIM, font=FONT_XS).grid(
            row=9, column=1, sticky="w", padx=(6, 0))

        tk.Frame(self, bg=DIVIDER, height=1).pack(fill="x", padx=12, pady=6)

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=(0, 10))
        btn_save = self._btn(btn_frame, "Сохранить", self._save, accent=True)
        btn_save.pack(side="left", padx=6)
        _bind_tip(btn_save, "Сохранить настройки аккаунта")
        btn_cancel = self._btn(btn_frame, "Отмена", self.destroy)
        btn_cancel.pack(side="left", padx=6)
        _bind_tip(btn_cancel, "Закрыть без сохранения")

    def _get_ref_balance(self) -> float:
        if hasattr(self._parent_app, '_rows') and self._parent_app._rows:
            for row, slave in zip(self._parent_app._rows, self._parent_app._slaves):
                if slave.get("name") == self.var_name.get().strip():
                    try:
                        return float(row.lbl_balance.cget("text").replace("$", "").replace(",", ""))
                    except Exception:
                        pass
        return 0.0

    def _sync_risk(self, source: str):
        if self._updating_risk:
            return
        self._updating_risk = True
        try:
            if source == "percent":
                try:
                    pct_val = float(self.var_risk_pct.get())
                    self.var_risk_type.set("percent")
                    bal = self._get_ref_balance()
                    if bal > 0:
                        self.var_risk_doll.set(f"{bal * pct_val / 100.0:.2f}")
                    self.lbl_risk_hint.config(text=f"{pct_val}% от баланса", fg=ACCENT)
                except (ValueError, tk.TclError):
                    pass
            elif source == "fixed":
                try:
                    doll_val = float(self.var_risk_doll.get())
                    self.var_risk_type.set("fixed")
                    bal = self._get_ref_balance()
                    if bal > 0:
                        self.var_risk_pct.set(f"{doll_val / bal * 100.0:.2f}")
                    self.lbl_risk_hint.config(text=f"${doll_val:.2f} фиксированный", fg=ACCENT)
                except (ValueError, tk.TclError):
                    pass
        finally:
            self._updating_risk = False

    def _browse(self):
        path = filedialog.askopenfilename(
            title="terminal64.exe", filetypes=[("MT5", "terminal64.exe"), ("EXE", "*.exe")],
            initialdir="C:\\")
        if path:
            self.var_path.set(path.replace("/", "\\"))

    def _load_symbols(self):
        if not _MT5_OK:
            self.lbl_sym_status.config(text="MT5 не установлен", fg=RED)
            return
        master_path = self._get_master_path()
        slave_path = self.var_path.get().strip()
        if master_path:
            self._master_symbols = self._fetch_symbols(master_path, "мастер")
        if slave_path:
            self._slave_symbols = self._fetch_symbols(slave_path, "слейв")
        parts = []
        if self._master_symbols:
            parts.append(f"мастер: {len(self._master_symbols)}")
        if self._slave_symbols:
            parts.append(f"слейв: {len(self._slave_symbols)}")
        if parts:
            self.lbl_sym_status.config(text="Загружено: " + ", ".join(parts), fg=GREEN_DIM)
        else:
            self.lbl_sym_status.config(text="Символы не загружены — запустите терминалы", fg=FG_DIM)

    def _get_master_path(self) -> str:
        parent = self.master
        if hasattr(parent, "var_master_path"):
            return parent.var_master_path.get().strip()
        return ""

    def _fetch_symbols(self, path: str, label: str) -> List[str]:
        if not path or not is_terminal_running(path):
            self.lbl_sym_status.config(text=f"Терминал {label} не запущен", fg=YELLOW)
            return []
        if not mt5.initialize(path=path):
            self.lbl_sym_status.config(text=f"Ошибка подключения к {label}", fg=YELLOW)
            return []
        try:
            symbols = mt5.symbols_get()
            return sorted([s.name for s in symbols if s.name]) if symbols else []
        finally:
            mt5.shutdown()

    def _auto_suggest(self, var_master: tk.StringVar, var_slave: tk.StringVar):
        if self._skip_suggest:
            return
        m = var_master.get().strip().upper()
        if not m:
            return
        s = var_slave.get().strip()
        if s:
            return
        match = self._auto_match(m)
        if match:
            var_slave.set(match)

    def _auto_match(self, master_sym: str) -> str:
        master_upper = master_sym.upper().rstrip(".")
        # 1. Точное совпадение (с точкой или без)
        for s in self._slave_symbols:
            if s.upper().rstrip(".") == master_upper:
                return s
        # 2. Алиас (XAUUSD → GOLD и т.д.)
        alias = _SYMBOL_ALIASES.get(master_upper)
        if alias:
            alias_upper = alias.upper().rstrip(".")
            for s in self._slave_symbols:
                if s.upper().rstrip(".") == alias_upper:
                    return s
        # 3. Совпадение с суффиксом брокера (GBPUSD → GBPUSD., XAUUSD → XAUUSDb)
        for s in self._slave_symbols:
            s_base = s.upper().rstrip(".")
            if s_base.startswith(master_upper) and len(s_base) - len(master_upper) <= 2:
                tail = s_base[len(master_upper):]
                if tail in ("B", "M", "E", "X", "I"):
                    return s
        return ""

    def _add_symbol_row(self, master_sym: str = "", slave_sym: str = ""):
        row_frame = tk.Frame(self.sym_frame, bg=BG)
        row_frame.pack(fill="x", pady=1)
        var_master = tk.StringVar(value=master_sym)
        var_slave = tk.StringVar(value=slave_sym)
        self._ent(row_frame, var_master, 8).pack(side="left")

        var_master.trace_add("write", lambda *_: self._auto_suggest(var_master, var_slave))

        def pick_m():
            dlg = SymbolPickerDialog(self, self._master_symbols, "Мастер")
            self.wait_window(dlg)
            if dlg.selected:
                var_master.set(dlg.selected)

        btn_pick_m = self._btn(row_frame, "...", pick_m, small=True)
        btn_pick_m.pack(side="left", padx=1)
        _bind_tip(btn_pick_m, "Выбрать символ мастера из списка")
        tk.Label(row_frame, text="\u2192", bg=BG, fg=FG_DIM, font=FONT_SM).pack(side="left", padx=3)
        self._ent(row_frame, var_slave, 8).pack(side="left")

        def pick_s():
            dlg = SymbolPickerDialog(self, self._slave_symbols, "Слейв")
            self.wait_window(dlg)
            if dlg.selected:
                var_slave.set(dlg.selected)

        btn_pick_s = self._btn(row_frame, "...", pick_s, small=True)
        btn_pick_s.pack(side="left", padx=1)
        _bind_tip(btn_pick_s, "Выбрать символ слейва из списка")

        def remove():
            row_frame.destroy()
            self._symbol_rows = [r for r in self._symbol_rows if r["frame"] != row_frame]

        btn_rm = self._btn(row_frame, "\u00D7", remove, small=True)
        btn_rm.pack(side="left", padx=(2, 0))
        _bind_tip(btn_rm, "Удалить строку маппинга")
        self._symbol_rows.append({"frame": row_frame, "master": var_master, "slave": var_slave})

    def _save(self):
        name = self.var_name.get().strip()
        path = self.var_path.get().strip()
        if not name:
            messagebox.showwarning("Ошибка", "Введите имя", parent=self)
            return
        if not path:
            messagebox.showwarning("Ошибка", "Укажите путь", parent=self)
            return
        norm_path = os.path.normcase(os.path.abspath(path))
        for slave in self._parent_app._slaves:
            existing = slave.get("path", "")
            if existing and os.path.normcase(os.path.abspath(existing)) == norm_path:
                if slave.get("id", "") != self._edit_id:
                    messagebox.showwarning("Ошибка", "Этот терминал уже добавлен", parent=self)
                    return

        symbol_map = {}
        for row in self._symbol_rows:
            m = row["master"].get().strip().upper()
            s = row["slave"].get().strip()
            if m and s:
                symbol_map[m] = s

        risk_type = self.var_risk_type.get()
        try:
            if risk_type == "percent":
                risk_value = float(self.var_risk_pct.get())
            else:
                risk_value = float(self.var_risk_doll.get())
        except (ValueError, tk.TclError):
            messagebox.showwarning("Ошибка", "Неверное значение риска", parent=self)
            return
        try:
            default_lot = float(self.var_default_lot.get())
        except ValueError:
            messagebox.showwarning("Ошибка", "Неверный лот", parent=self)
            return
        try:
            max_drawdown = float(self.var_max_drawdown.get())
        except ValueError:
            max_drawdown = 0.0
        try:
            max_trades_per_day = int(self.var_max_trades.get())
        except ValueError:
            max_trades_per_day = 0
        try:
            daily_loss_limit = float(self.var_daily_loss.get())
        except ValueError:
            daily_loss_limit = 0

        self.result = {
            "name": name, "path": path, "symbol_map": symbol_map,
            "risk_type": risk_type, "risk_value": risk_value,
            "default_lot": default_lot, "max_drawdown": max_drawdown,
            "max_trades_per_day": max_trades_per_day,
            "daily_loss_limit": daily_loss_limit,
        }
        self.destroy()


# ── AccountRow ──────────────────────────────────────────────

class AccountRow:
    def __init__(self, parent, row_index, slave_data, on_edit, on_delete, on_toggle, on_test, on_open, on_close_all):
        self._parent = parent
        self._row = row_index
        self.slave_data = slave_data
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_toggle = on_toggle
        self._on_test = on_test
        self._on_open = on_open
        self._on_close_all = on_close_all
        self._hover = False
        self._leave_timer = None
        self._widgets = []
        self._build()

    @property
    def row_index(self):
        return self._row

    @row_index.setter
    def row_index(self, value):
        self._row = value
        if hasattr(self, '_bg_frame') and self._bg_frame:
            self._bg_frame.grid(row=value)
        for w in self._widgets:
            w.grid(row=value)

    def _cur_bg(self):
        return BG_ROW_HOVER if self._hover else BG_ROW

    def _build(self):
        d = self.slave_data
        bg = BG_ROW
        r = self._row

        self._bg_frame = tk.Frame(self._parent, bg=bg, highlightbackground=BORDER,
                                   highlightthickness=1 if not self._hover else 1)
        self._bg_frame.grid(row=r, column=0, columnspan=12, sticky="nsew", pady=(1, 1))
        self._bg_frame.lower()

        self._accent_strip = tk.Frame(self._bg_frame, bg=FG_DIM, width=3)
        self._accent_strip.place(x=0, y=0, relheight=1.0)

        enabled = d.get("enabled", True)
        self.var_enabled = tk.BooleanVar(value=enabled)
        self.lbl_check = tk.Label(self._parent, text="\u2611" if enabled else "\u2610",
                                   bg=bg, fg=GREEN if enabled else FG_DIM,
                                   font=FONT_BOLD, cursor="hand2")
        self.lbl_check.grid(row=r, column=0, padx=(8, 2), pady=6, sticky="ew")
        self.lbl_check.bind("<Button-1>", lambda e: self._toggle())
        _bind_tip(self.lbl_check, "Включить / выключить аккаунт")
        self._widgets.append(self.lbl_check)

        dot_frame = tk.Frame(self._parent, bg=bg, width=20, height=20)
        dot_frame.grid(row=r, column=1, padx=2, pady=6, sticky="")
        self._dot_canvas = tk.Canvas(dot_frame, width=14, height=14, bg=bg,
                                      highlightthickness=0, bd=0)
        self._dot_canvas.pack(padx=2, pady=2)
        self._dot_oval = self._dot_canvas.create_oval(3, 3, 11, 11, fill=FG_DIM, outline="")
        self._widgets.append(dot_frame)

        self.lbl_name = tk.Label(self._parent, text=d.get("name", "\u2014"), bg=bg, fg=FG,
                                  font=FONT_BOLD, anchor="w")
        self.lbl_name.grid(row=r, column=2, padx=(4, 4), pady=6, sticky="ew")
        self._widgets.append(self.lbl_name)

        self.lbl_login = tk.Label(self._parent, text="\u2014", bg=bg, fg=FG_DIM,
                                   font=FONT_MONO_SM, anchor="w")
        self.lbl_login.grid(row=r, column=3, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_login)

        self.lbl_balance = tk.Label(self._parent, text="\u2014", bg=bg, fg=FG,
                                     font=FONT_VAL_BOLD, anchor="e")
        self.lbl_balance.grid(row=r, column=4, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_balance)

        self.lbl_equity = tk.Label(self._parent, text="\u2014", bg=bg, fg=FG_DIM,
                                    font=FONT_MONO_SM, anchor="e")
        self.lbl_equity.grid(row=r, column=5, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_equity)

        self.lbl_pnl = tk.Label(self._parent, text="\u2014", bg=bg, fg=FG_DIM,
                                 font=FONT_VAL, anchor="e")
        self.lbl_pnl.grid(row=r, column=6, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_pnl)

        sym_map = d.get("symbol_map", {})
        sym_text = "  ".join(f"{k}\u2192{v}" for k, v in list(sym_map.items())[:3])
        if len(sym_map) > 3:
            sym_text += f" +{len(sym_map) - 3}"
        self.lbl_symbols = tk.Label(self._parent, text=sym_text or "\u2014", bg=bg, fg=FG_DIM,
                                     font=FONT_XS, anchor="w")
        self.lbl_symbols.grid(row=r, column=7, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_symbols)

        rt = d.get("risk_type", "percent")
        rv = d.get("risk_value", 1.0)
        risk_text = f"{rv}{'%' if rt == 'percent' else '$'}"
        self.lbl_risk = tk.Label(self._parent, text=risk_text, bg=bg, fg=YELLOW,
                                  font=FONT_SM, anchor="e")
        self.lbl_risk.grid(row=r, column=8, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_risk)

        mtd = d.get("max_trades_per_day", 0)
        self.lbl_trades_day = tk.Label(self._parent, text=str(mtd) if mtd else "\u2014",
                                        bg=bg, fg=FG_DIM, font=FONT_SM, anchor="center")
        self.lbl_trades_day.grid(row=r, column=9, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_trades_day)

        dll = d.get("daily_loss_limit", 0)
        bar_w = 100
        self._loss_canvas = tk.Canvas(self._parent, width=bar_w, height=16,
                                       bg=BG_INPUT, highlightthickness=0, bd=0)
        self._loss_canvas.grid(row=r, column=10, padx=4, pady=6, sticky="ew")
        self._loss_fill = self._loss_canvas.create_rectangle(0, 0, 0, 16, fill="", outline="")
        self._loss_text = self._loss_canvas.create_text(bar_w // 2, 8, text="\u2014",
                                                         fill=FG_DIM, font=FONT_XS)
        if dll > 0:
            self._loss_canvas.itemconfigure(self._loss_text, text=f"${dll:.0f}",
                                             fill=FG_DIM)
        self._widgets.append(self._loss_canvas)

        bf = tk.Frame(self._parent, bg=bg)
        bf.grid(row=r, column=11, padx=(2, 6), pady=6, sticky="e")

        btn_open = tk.Button(bf, text="\U0001F4C8", command=self._open_terminal,
                  bg=bg, fg=FG_DIM, relief="flat", font=FONT_SM,
                  activebackground=BG_ROW_HOVER, activeforeground=ACCENT,
                  cursor="hand2", width=2, highlightthickness=0)
        btn_open.pack(side="left", padx=1)
        _bind_tip(btn_open, "Открыть терминал")

        btn_close = tk.Button(bf, text="\u2716", command=self._close_all,
                  bg=bg, fg=RED_DIM, relief="flat", font=FONT_SM,
                  activebackground=BG_ROW_HOVER, activeforeground=RED,
                  cursor="hand2", width=2, highlightthickness=0)
        btn_close.pack(side="left", padx=1)
        _bind_tip(btn_close, "Закрыть все позиции")

        btn_test = tk.Button(bf, text="\u26A0", command=self._test,
                  bg=bg, fg=YELLOW, relief="flat", font=FONT_SM,
                  activebackground=BG_ROW_HOVER, activeforeground=YELLOW,
                  cursor="hand2", width=2, highlightthickness=0)
        btn_test.pack(side="left", padx=1)
        _bind_tip(btn_test, "Тест: BUY 0.01 лот")

        btn_edit = tk.Button(bf, text="\u2699", command=self._edit,
                  bg=bg, fg=FG_DIM, relief="flat", font=FONT_SM,
                  activebackground=BG_ROW_HOVER, activeforeground=ACCENT,
                  cursor="hand2", width=2, highlightthickness=0)
        btn_edit.pack(side="left", padx=1)
        _bind_tip(btn_edit, "Настройки")

        btn_del = tk.Button(bf, text="\u2715", command=self._delete,
                  bg=bg, fg=FG_DIM, relief="flat", font=FONT_SM,
                  activebackground=BG_ROW_HOVER, activeforeground=RED,
                  cursor="hand2", width=2, highlightthickness=0)
        btn_del.pack(side="left", padx=1)
        _bind_tip(btn_del, "Удалить аккаунт")

        self._widgets.append(bf)

        for w in self._widgets:
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _on_enter(self, event=None):
        if self._leave_timer:
            self._parent.after_cancel(self._leave_timer)
            self._leave_timer = None
        if not self._hover:
            self._set_hover(True)

    def _on_leave(self, event=None):
        self._leave_timer = self._parent.after(80, self._do_leave)

    def _do_leave(self):
        self._leave_timer = None
        self._set_hover(False)

    def _dot_color(self):
        try:
            return self._dot_canvas.itemcget(self._dot_oval, "fill")
        except Exception:
            return FG_DIM

    def _set_hover(self, hover: bool):
        if self._hover == hover:
            return
        self._hover = hover
        if hasattr(self, '_bg_frame') and self._bg_frame:
            if hover:
                self._bg_frame.configure(highlightbackground=ACCENT_DIM)
            else:
                self._bg_frame.configure(highlightbackground=BORDER)


    def update_info(self, balance: float, equity: float, login: int = 0,
                    status: str = ""):
        bg = BG_ROW
        self.lbl_balance.config(text=f"${balance:,.2f}", bg=bg)
        self.lbl_equity.config(text=f"${equity:,.2f}", bg=bg)
        if login:
            self.lbl_login.config(text=f"#{login}", bg=bg)

        pnl = equity - balance
        pnl_color = GREEN if pnl >= 0 else RED
        pnl_sign = "+" if pnl >= 0 else ""
        self.lbl_pnl.config(text=f"{pnl_sign}${pnl:,.2f}", fg=pnl_color, bg=bg)

        if status:
            dot_color = GREEN if "\U0001F7E2" in status else RED if "\U0001F534" in status else YELLOW if "\U0001F7E1" in status else FG_DIM
            self._dot_canvas.itemconfigure(self._dot_oval, fill=dot_color)
            self._dot_canvas.configure(bg=bg)

    def update_status_only(self, status: str, balance: float = 0, equity: float = 0):
        bg = BG_ROW
        dot_color = GREEN if "\U0001F7E2" in status else RED if "\U0001F534" in status else YELLOW if "\U0001F7E1" in status else FG_DIM
        self._dot_canvas.itemconfigure(self._dot_oval, fill=dot_color)
        self._dot_canvas.configure(bg=bg)
        if balance > 0:
            self.lbl_balance.config(text=f"${balance:,.2f}", bg=bg)
        if equity > 0:
            self.lbl_equity.config(text=f"${equity:,.2f}", bg=bg)
            pnl = equity - balance
            pnl_color = GREEN if pnl >= 0 else RED
            pnl_sign = "+" if pnl >= 0 else ""
            self.lbl_pnl.config(text=f"{pnl_sign}${pnl:,.2f}", fg=pnl_color, bg=bg)

    def update_daily_loss(self, daily_loss: float, daily_loss_limit: float):
        if daily_loss_limit <= 0:
            self._loss_canvas.coords(self._loss_fill, 0, 0, 0, 16)
            self._loss_canvas.itemconfigure(self._loss_fill, fill="")
            self._loss_canvas.itemconfigure(self._loss_text, text="\u2014", fill=FG_DIM)
            return
        bar_w = 100
        pct = min(daily_loss / daily_loss_limit, 1.0) if daily_loss_limit > 0 else 0
        fill_w = int(bar_w * pct)
        exceeded = daily_loss >= daily_loss_limit
        fill_color = RED if exceeded else ACCENT
        text_color = "white" if pct > 0.5 else FG
        self._loss_canvas.coords(self._loss_fill, 0, 0, fill_w, 16)
        self._loss_canvas.itemconfigure(self._loss_fill, fill=fill_color)
        self._loss_canvas.itemconfigure(self._loss_text,
                                          text=f"${daily_loss:.0f}/${daily_loss_limit:.0f}",
                                          fill=text_color)

    def _toggle(self):
        new_val = not self.var_enabled.get()
        self.var_enabled.set(new_val)
        bg = self._cur_bg()
        self.lbl_check.config(text="\u2611" if new_val else "\u2610",
                               fg=GREEN if new_val else FG_DIM, bg=bg)
        self.slave_data["enabled"] = new_val
        if self._on_toggle:
            self._on_toggle(self.slave_data)

    def _edit(self):
        if self._on_edit:
            self._on_edit(self.slave_data, self)

    def _delete(self):
        if self._on_delete:
            self._on_delete(self.slave_data, self)

    def _test(self):
        if self._on_test:
            self._on_test(self.slave_data)

    def _open_terminal(self):
        if self._on_open:
            self._on_open(self.slave_data)

    def _close_all(self):
        if self._on_close_all:
            self._on_close_all(self.slave_data)

    def destroy(self):
        if self._leave_timer:
            try:
                self._parent.after_cancel(self._leave_timer)
            except Exception:
                pass
            self._leave_timer = None
        for w in self._widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self._widgets.clear()
        if hasattr(self, '_bg_frame') and self._bg_frame:
            try:
                self._bg_frame.destroy()
            except Exception:
                pass

    def refresh(self, data: Dict):
        self.slave_data = data
        self.destroy()
        self._build()


# ── TradesTable ─────────────────────────────────────────────

class TradesTable(tk.Frame):
    COLS = ["time", "slave", "symbol", "dir", "lot", "master", "slave_tk", "status"]
    HEADERS = ["Время", "Слейв", "Символ", "\u2191\u2193", "Лот", "Мастер #", "Слейв #", "Статус"]
    WIDTHS = [62, 50, 64, 28, 40, 70, 70, 140]

    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self._max_rows = 200
        self._build()

    def _build(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("T.Treeview", background=BG_ROW, foreground=FG,
                        fieldbackground=BG_ROW, font=FONT_MONO_SM,
                        rowheight=17, borderwidth=0)
        style.configure("T.Treeview.Heading", background=BG_INPUT, foreground=FG_DIM,
                        font=FONT_XS, borderwidth=0, relief="flat")
        style.map("T.Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])
        style.map("T.Treeview.Heading", background=[("active", BG_ROW_HOVER)])

        self.tree = ttk.Treeview(self, columns=self.COLS, show="headings",
                                  style="T.Treeview", height=6)
        for col, hdr, w in zip(self.COLS, self.HEADERS, self.WIDTHS):
            self.tree.heading(col, text=hdr, anchor="w")
            self.tree.column(col, width=w, minwidth=w, anchor="w", stretch=True)

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("ok", foreground=GREEN)
        self.tree.tag_configure("err", foreground=RED)
        self.tree.tag_configure("warn", foreground=YELLOW)
        self.tree.tag_configure("even", background=BG_ROW)
        self.tree.tag_configure("odd", background=BG_DEEP)

    def add_trade(self, time_str: str, slave: str, symbol: str,
                  direction: str, lot: float, master_ticket: str,
                  slave_ticket: str, status: str, tag: str = "ok"):
        # Phase 4: храним сырой список — нужно для фильтра/поиска.
        if not hasattr(self, "_all_trades"):
            self._all_trades = []
            self._filter_status = "all"
            self._filter_query = ""
            self._summary_cb = None
        record = dict(time_str=time_str, slave=slave, symbol=symbol,
                      direction=direction, lot=lot,
                      master_ticket=master_ticket, slave_ticket=slave_ticket,
                      status=status, tag=tag)
        self._all_trades.insert(0, record)
        while len(self._all_trades) > self._max_rows:
            self._all_trades.pop()
        self._render()

    # Phase 4: фильтр + поиск.
    def set_filter(self, status: str = "all", query: str = ""):
        self._filter_status = status or "all"
        self._filter_query = (query or "").strip().lower()
        self._render()

    def set_summary_callback(self, cb):
        """Регистрирует cb(total_ok, total_err) — toolbar обновит сводку."""
        self._summary_cb = cb
        self._fire_summary()

    def _fire_summary(self):
        cb = getattr(self, "_summary_cb", None)
        if not cb:
            return
        ok = sum(1 for t in getattr(self, "_all_trades", []) if t["tag"] == "ok")
        err = sum(1 for t in getattr(self, "_all_trades", []) if t["tag"] == "err")
        try:
            cb(ok, err)
        except Exception:
            pass

    def _match(self, t: Dict) -> bool:
        st = getattr(self, "_filter_status", "all")
        if st == "ok" and t["tag"] != "ok":
            return False
        if st == "err" and t["tag"] != "err":
            return False
        q = getattr(self, "_filter_query", "")
        if q:
            blob = (
                f"{t['time_str']} {t['slave']} {t['symbol']} "
                f"{t['direction']} {t['master_ticket']} {t['slave_ticket']} "
                f"{t['status']}"
            ).lower()
            if q not in blob:
                return False
        return True

    def _render(self):
        # пересоберём дерево с нуля; объёмы небольшие (≤200 строк).
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        idx = 0
        for t in getattr(self, "_all_trades", []):
            if not self._match(t):
                continue
            row_tag = "even" if idx % 2 == 0 else "odd"
            idx += 1
            self.tree.insert("", "end", values=(
                t["time_str"], t["slave"], t["symbol"], t["direction"],
                f"{t['lot']:.2f}", t["master_ticket"], t["slave_ticket"],
                t["status"]
            ), tags=(t["tag"], row_tag))
        self._fire_summary()


# ── ActivationWindow ──────────────────────────────────────────

class ActivationWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("FTH Trade Copier — Активация")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        if os.path.exists(ICON_DEFAULT):
            self.iconbitmap(ICON_DEFAULT)
        self._activated = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.grab_set()
        self._build()
        self._center_on_screen()

    def _on_close(self):
        # Закрытие окна активации без успешной активации = выход из всей программы.
        if self._activated:
            self.destroy()
            return
        app = self.master
        self.destroy()
        try:
            app._real_quit()  # graceful: стоп трейдера, стоп tray, сохранение конфига
        except Exception:
            pass
        os._exit(0)  # страховка: гарантированно завершить процесс

    def _center_on_screen(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{sw // 2 - w // 2}+{sh // 2 - h // 2}")

    def _lbl(self, parent, text, **kw):
        return tk.Label(parent, text=text, bg=BG_DEEP, fg=FG_LABEL, font=FONT_SM, **kw)

    def _paste(self, event=None):
        try:
            clip = self.clipboard_get()
            if clip:
                widget = self.focus_get()
                if isinstance(widget, tk.Entry):
                    widget.insert(tk.INSERT, clip)
        except Exception:
            pass
        return "break"

    def _on_ctrl_key(self, event=None):
        # Срабатывает на любой раскладке: ловим физическую клавишу V по keycode,
        # т.к. при русской раскладке keysym = Cyrillic_em ("м"), а не "v".
        if event is not None and event.keycode == 86:  # V на Windows
            return self._paste(event)

    def _ent(self, parent, var=None, width=28):
        e = tk.Entry(parent, textvariable=var, width=width,
                     bg=BG_INPUT, fg=FG, insertbackground=FG, relief="flat",
                     font=FONT, highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT)
        e.bind("<Control-v>", self._paste)
        e.bind("<Control-V>", self._paste)
        e.bind("<Control-KeyPress>", self._on_ctrl_key)
        return e

    def _build(self):
        frm = tk.Frame(self, bg=BG_DEEP, padx=30, pady=20)
        frm.pack(fill="both", expand=True)

        logo_path = os.path.join(IMG_DIR, "convertico-fth_48x48.png")
        if os.path.exists(logo_path):
            try:
                img = tk.PhotoImage(file=logo_path)
                lbl_logo = tk.Label(frm, image=img, bg=BG_DEEP)
                lbl_logo.image = img
                lbl_logo.grid(row=0, column=0, columnspan=2, pady=(0, 10))
            except Exception:
                pass

        tk.Label(frm, text="Активация", bg=BG_DEEP, fg=ACCENT,
                 font=FONT_TITLE).grid(row=1, column=0, columnspan=2, pady=(0, 15))

        self._lbl(frm, "Telegram ID").grid(row=2, column=0, sticky="w", pady=3)
        self.var_tg_id = tk.StringVar()
        self._ent(frm, self.var_tg_id, 22).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=3)

        btn_code = tk.Button(frm, text="Получить код", command=self._request_code,
                             bg=ACCENT, fg="white", relief="flat", font=FONT_BOLD,
                             activebackground=ACCENT_H, cursor="hand2", padx=12, pady=3)
        btn_code.grid(row=3, column=0, columnspan=2, pady=(8, 4))

        self._lbl(frm, "Код из Telegram").grid(row=4, column=0, sticky="w", pady=3)
        self.var_code = tk.StringVar()
        self._ent(frm, self.var_code, 22).grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=3)

        btn_verify = tk.Button(frm, text="Подтвердить", command=self._verify,
                               bg=GREEN_DIM, fg="white", relief="flat", font=FONT_BOLD,
                               activebackground=GREEN, cursor="hand2", padx=12, pady=3)
        btn_verify.grid(row=5, column=0, columnspan=2, pady=(8, 4))

        self.lbl_status = tk.Label(frm, text="", bg=BG_DEEP, fg=FG_DIM, font=FONT_SM,
                                   wraplength=280)
        self.lbl_status.grid(row=6, column=0, columnspan=2, pady=(4, 0))

    def _request_code(self):
        tg = self.var_tg_id.get().strip()
        if not tg:
            self.lbl_status.config(text="Введите Telegram ID", fg=RED)
            return
        try:
            tg_id = int(tg)
        except ValueError:
            self.lbl_status.config(text="Telegram ID — только цифры", fg=RED)
            return
        if not _LIC_OK:
            self.lbl_status.config(text="Модуль лицензии не найден", fg=RED)
            return
        self.lbl_status.config(text="Отправка кода...", fg=FG_DIM)
        self.update()
        ok, msg = lic_mod.request_code(tg_id)
        if ok:
            self.lbl_status.config(text="Код отправлен в Telegram. Проверьте личные сообщения.", fg=GREEN_DIM)
        else:
            self.lbl_status.config(text=f"Ошибка: {msg}", fg=RED)

    def _verify(self):
        tg = self.var_tg_id.get().strip()
        code = self.var_code.get().strip()
        if not tg or not code:
            self.lbl_status.config(text="Заполните оба поля", fg=RED)
            return
        try:
            tg_id = int(tg)
        except ValueError:
            self.lbl_status.config(text="Telegram ID — только цифры", fg=RED)
            return
        if not _LIC_OK:
            self.lbl_status.config(text="Модуль лицензии не найден", fg=RED)
            return
        self.lbl_status.config(text="Проверка...", fg=FG_DIM)
        self.update()
        ok, result = lic_mod.verify_code(tg_id, code)
        if ok:
            self.lbl_status.config(text="Активация успешна!", fg=GREEN_DIM)
            self._activated = True  # успешная активация закрывает только окно, не прогу
            self.after(500, self.destroy)
        elif result and result.startswith("device_limit"):
            max_d = result.split(":")[-1]
            self.lbl_status.config(
                text=f"Лимит устройств ({max_d}) превышён.\nИспользуйте /reset в боте для сброса.",
                fg=RED)
        else:
            self.lbl_status.config(text=f"Ошибка: {result}", fg=RED)


# ── SettingsDialog ───────────────────────────────────────────

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: 'App'):
        super().__init__(parent)
        self.title("Настройки")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        if os.path.exists(ICON_DEFAULT):
            self.iconbitmap(ICON_DEFAULT)
            self.wm_iconbitmap(ICON_DEFAULT)
        self._app = parent
        self._active = parent._active_profile

        frm = tk.Frame(self, bg=BG, padx=16, pady=12)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="ПРОФИЛИ", bg=BG, fg=FG_DIM, font=FONT_BOLD).pack(anchor="w", pady=(0, 6))

        tabs_f = tk.Frame(frm, bg=BG)
        tabs_f.pack(fill="x")
        self._profile_btns = []
        self._profile_names = []
        for i in range(5):
            name = parent._profiles[i].get("name", f"Профиль {i + 1}")
            self._profile_names.append(tk.StringVar(value=name))
            btn = tk.Button(tabs_f, text=f" {name} ", command=lambda idx=i: self._select(idx),
                            bg=BG_INPUT if i != self._active else ACCENT,
                            fg="white" if i == self._active else FG_DIM,
                            relief="flat", font=FONT_SM, cursor="hand2",
                            activebackground=ACCENT_H, padx=6, pady=3)
            btn.pack(side="left", padx=2)
            self._profile_btns.append(btn)

        tk.Frame(frm, bg=DIVIDER, height=1).pack(fill="x", pady=8)

        row_name = tk.Frame(frm, bg=BG)
        row_name.pack(fill="x", pady=(0, 4))
        tk.Label(row_name, text="Имя профиля:", bg=BG, fg=FG, font=FONT).pack(side="left")
        self._ent_name = tk.Entry(row_name, bg=BG_INPUT, fg=FG, insertbackground=FG,
                                   relief="flat", font=FONT, width=24)
        self._ent_name.pack(side="left", padx=(8, 0))
        self._ent_name.insert(0, self._profile_names[self._active].get())
        self._ent_name.bind("<KeyRelease>", self._on_name_change)

        tk.Frame(frm, bg=DIVIDER, height=1).pack(fill="x", pady=8)

        btn_row = tk.Frame(frm, bg=BG)
        btn_row.pack(fill="x")

        def switch_profile():
            new_name = self._ent_name.get().strip()
            if new_name:
                self._app._profiles[self._active]["name"] = new_name
            self._app._switch_profile(self._active)
            self.destroy()

        btn_switch = tk.Button(btn_row, text="Сохранить", command=switch_profile,
                               bg=ACCENT, fg="white", relief="flat", font=FONT_BOLD,
                               activebackground=ACCENT_H, cursor="hand2", padx=16, pady=4)
        btn_switch.pack(side="left")
        _bind_tip(btn_switch, "Сохранить и переключиться на профиль")

        def check_updates():
            self.destroy()
            parent._check_update(force=True)

        btn_update = tk.Button(btn_row, text="\U0001F504 Проверить обновления", command=check_updates,
                               bg=BG_INPUT, fg=FG_DIM, relief="flat", font=FONT,
                               activebackground=BG_ROW_HOVER, cursor="hand2", padx=10, pady=4)
        btn_update.pack(side="right")
        _bind_tip(btn_update, "Проверить наличие новой версии")

        btn_close = tk.Button(btn_row, text="Закрыть", command=self.destroy,
                              bg=BG_INPUT, fg=FG_DIM, relief="flat", font=FONT,
                              activebackground=BG_ROW_HOVER, cursor="hand2", padx=10, pady=4)
        btn_close.pack(side="right", padx=6)

        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        x = parent.winfo_x() + (parent.winfo_width() - w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{x}+{y}")

    def _select(self, idx):
        old_name = self._ent_name.get().strip()
        if old_name:
            self._app._profiles[self._active]["name"] = old_name
            self._profile_btns[self._active].config(text=f" {old_name} ")
        self._active = idx
        self._ent_name.delete(0, "end")
        self._ent_name.insert(0, self._app._profiles[idx].get("name", f"Профиль {idx + 1}"))
        for i, btn in enumerate(self._profile_btns):
            btn.config(bg=ACCENT if i == idx else BG_INPUT,
                       fg="white" if i == idx else FG_DIM)

    def _on_name_change(self, event=None):
        name = self._ent_name.get().strip()
        if name:
            self._profile_btns[self._active].config(text=f" {name} ")


# ── App ─────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        # CTk-стилизованные диалоги: подменяем gui.SlaveDialog и др. ДО
        # super().__init__, чтобы любая ранняя активация (например, окно
        # лицензии при первом запуске) сразу шла в новом стиле.
        try:
            from dialogs_ctk import install as _install_ctk_dialogs
            _install_ctk_dialogs()
        except Exception:
            # не критично — приложение всё равно стартует, просто диалоги
            # останутся в старом виде.
            pass
        super().__init__()
        # DPI scaling — Hi-DPI/4K-мониторы перестанут выглядеть «крохотно».
        # Применяем ДО первого geometry(), чтобы окно сразу было нужного
        # размера в физических пикселях.
        try:
            theme.apply_dpi_scaling(self, ctk)
        except Exception:
            pass
        self.title(f"FTH Trade Copier v{upd_mod.VERSION}" if _UPD_OK else "FTH Trade Copier")
        self.configure(bg=BG_DEEP)
        self.resizable(True, True)
        # Phase 2: minsize смягчён под более скромные ноуты.
        self.minsize(1024, 680)
        # Геометрия выберется в _build_ui (либо из config.json, либо 70%
        # экрана с зажимом). Здесь — временное значение до отрисовки.
        self.geometry("1140x760")
        if os.path.exists(ICON_DEFAULT):
            self.iconbitmap(ICON_DEFAULT)
            self.wm_iconbitmap(ICON_DEFAULT)

        self._slaves: List[Dict] = []
        self._rows: List[AccountRow] = []
        self._trader = None
        self._check_timer = None
        self._session_stats = {"copied": 0, "failed": 0}
        self._min_lot_mode = False
        self._tray_icon = None
        self._active_profile = 0
        self._profiles: List[Dict] = []

        self._build_ui()
        # Phase 3a: глобальный менеджер тостов (правый-нижний угол окна).
        self.toasts = components.ToastManager(self)
        self._load_config()
        self._start_tray()
        self._schedule_check()
        self._bind_paste()
        self._schedule_license_check()
        self._check_update()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _paste_global(self, event=None):
        try:
            clip = self.clipboard_get()
            if clip:
                widget = self.focus_get()
                if isinstance(widget, tk.Entry):
                    widget.insert(tk.INSERT, clip)
                    return "break"
        except Exception:
            pass

    def _bind_paste(self):
        self.bind_all("<Control-v>", self._paste_global)
        self.bind_all("<Control-V>", self._paste_global)

    def _set_logo_cyan(self, cyan: bool):
        if not hasattr(self, '_logo_label'):
            return
        name = "convertico-fth-cyan_32x32" if cyan else "convertico-fth_32x32"
        path = os.path.join(IMG_DIR, f"{name}.png")
        if os.path.exists(path):
            try:
                img = tk.PhotoImage(file=path)
                self._logo_label.configure(image=img)
                self._logo_img = img
            except Exception:
                pass

    def _start_tray(self):
        if not _PYSTRAY_OK:
            return
        png_path = os.path.join(IMG_DIR, "convertico-fth_256x256.png")
        if not os.path.exists(png_path):
            return
        try:
            pil_img = PILImage.open(png_path)
            menu = pystray.Menu(
                pystray.MenuItem("Показать", self._tray_show, default=True),
                pystray.MenuItem("Стоп + Выход", self._tray_exit),
            )
            self._tray_icon = pystray.Icon("FTHTradeCopier", pil_img, "FTH Trade Copier", menu)
            self._tray_thread = threading.Thread(target=self._tray_icon.run, daemon=True)
            self._tray_thread.start()
        except Exception:
            self._tray_icon = None

    def _tray_show(self, icon=None, item=None):
        self.after(0, self._show_window)

    def _show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_exit(self, icon=None, item=None):
        if self._trader and self._trader.is_running():
            self.after(0, self._stop)
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        self.after(0, self._real_quit)

    def _update_tray_icon(self, cyan: bool):
        if not self._tray_icon or not _PYSTRAY_OK:
            return
        name = "convertico-fth-cyan_256x256" if cyan else "convertico-fth_256x256"
        png_path = os.path.join(IMG_DIR, f"{name}.png")
        if os.path.exists(png_path):
            try:
                pil_img = PILImage.open(png_path)
                self._tray_icon.icon = pil_img
                tip = "FTH Trade Copier — работает" if cyan else "FTH Trade Copier"
                self._tray_icon.title = tip
            except Exception:
                pass

    def _make_btn(self, parent, text, cmd, accent=False, danger=False):
        """Pill-кнопка для master-row и других внутренних мест."""
        if accent:
            variant = "primary"
        elif danger:
            variant = "danger"
        else:
            variant = "ghost"
        return PillButton(parent, text=text, command=cmd, variant=variant)

    def _build_ui(self):
        # CTk-стиль главного окна.
        self.configure(bg=BG_DEEP)
        try:
            ctk.set_appearance_mode("dark")
        except Exception:
            pass

        sans_reg, sans_bold, sans_black = _resolve_fonts()
        self._sans_reg = sans_reg
        self._sans_bold = sans_bold
        self._sans_black = sans_black

        # Верхняя шапка
        self._build_header_new(sans_reg, sans_bold, sans_black)

        # Тело
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(10, 4))

        self._build_master_panel_new(body, sans_reg, sans_bold)
        self._build_kpi_row_new(body, sans_reg, sans_bold)
        self._build_slaves_section_new(body, sans_reg, sans_bold)
        self._build_bottom_notebook_new(body, sans_reg, sans_bold)
        self._build_footer_stats_new(sans_reg)

    # ── HEADER ────────────────────────────────────────────────
    def _build_header_new(self, sans_reg, sans_bold, sans_black):
        # Phase 2: компактнее (76→64px) + StatusPill в центре.
        hdr = ctk.CTkFrame(self, fg_color=BG_HEADER, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=18, pady=10)

        logo_path = os.path.join(IMG_DIR, "convertico-fth_32x32.png")
        if os.path.exists(logo_path):
            try:
                self._logo_img = tk.PhotoImage(file=logo_path)
                self._logo_label = ctk.CTkLabel(left, image=self._logo_img,
                                                 text="")
                self._logo_label.pack(side="left", padx=(0, 12))
            except Exception:
                self._logo_label = None
        else:
            self._logo_label = None

        title_box = ctk.CTkFrame(left, fg_color="transparent")
        title_box.pack(side="left")
        version_suffix = f"  v{upd_mod.VERSION}" if _UPD_OK else ""
        ctk.CTkLabel(title_box, text=f"FTH Trade Copier{version_suffix}",
                     text_color=FG, font=(sans_bold, 15),
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(title_box, text="MT5 · Local copy engine",
                     text_color=FG_DIM, font=(sans_reg, 10),
                     anchor="w").pack(anchor="w")

        # Центр: статус-плюшка
        center = ctk.CTkFrame(hdr, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")
        self.status_pill = StatusPill(center, text="Остановлено", state="stopped")
        self.status_pill.pack()

        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=14, pady=10)

        self.btn_info = IconButton(right, icon=theme.ICON_INFO,
                                     command=self._toggle_info)
        self.btn_info.pack(side="right", padx=(8, 0))
        _bind_tip(self.btn_info, "Режим подсказок")

        btn_settings = IconButton(right, icon=theme.ICON_GEAR,
                                   command=self._open_settings)
        btn_settings.pack(side="right", padx=(8, 0))
        _bind_tip(btn_settings, "Настройки приложения")

        engine = self._header_group(right, "КОПИТРЕЙДЕР", sans_bold)
        engine.pack(side="right", padx=(14, 0))
        self.btn_start = PillButton(engine.row, "Старт", icon="▶",
                                     variant="primary", command=self._start)
        self.btn_start.pack(side="left", padx=4)
        _bind_tip(self.btn_start, "Запустить копирование сделок")
        self.btn_stop = PillButton(engine.row, "Стоп", icon="■",
                                    variant="danger", command=self._stop)
        self.btn_stop.pack(side="left", padx=4)
        _bind_tip(self.btn_stop, "Остановить копирование")
        self.btn_stop.configure(state="disabled")

        terms = self._header_group(right, "ТЕРМИНАЛЫ", sans_bold)
        terms.pack(side="right", padx=(14, 0))
        btn_launch = PillButton(terms.row, "Запустить", icon="▶",
                                 variant="primary", command=self._launch_all)
        btn_launch.pack(side="left", padx=4)
        _bind_tip(btn_launch, "Запустить все терминалы (свёрнутые)")
        btn_shutdown = PillButton(terms.row, "Закрыть", icon="■",
                                   variant="danger", command=self._shutdown_all)
        btn_shutdown.pack(side="left", padx=4)
        _bind_tip(btn_shutdown, "Завершить процессы всех терминалов")

    def _header_group(self, parent, title, sans_bold):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(wrap, text=title, text_color=FG_DIM,
                     font=(sans_bold, 8)).pack(anchor="w", padx=4)
        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x")
        wrap.row = row  # type: ignore[attr-defined]
        return wrap

    # ── MASTER PANEL ─────────────────────────────────────────
    def _build_master_panel_new(self, parent, sans_reg, sans_bold):
        card = _make_card(parent, height=72)
        card.pack(fill="x", pady=(0, 12))
        card.pack_propagate(False)

        strip = ctk.CTkFrame(card, width=3, corner_radius=2, fg_color=ACCENT)
        strip.place(relx=0, rely=0.18, relheight=0.64, x=8)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=10)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="y")
        ctk.CTkLabel(left, text="MASTER", text_color=ACCENT,
                     font=(sans_bold, 10)).pack(anchor="w")

        path_row = ctk.CTkFrame(left, fg_color="transparent")
        path_row.pack(anchor="w", pady=(4, 0))

        self.var_master_path = tk.StringVar()
        self._ent_master = ctk.CTkEntry(
            path_row, textvariable=self.var_master_path,
            width=320, height=28,
            fg_color=BG_INPUT, border_color=SOFT_BORDER, text_color=FG,
            corner_radius=CORNER_SM, font=(sans_reg, 10),
        )
        self._ent_master.pack(side="left")

        btn_browse_m = PillButton(path_row, "...", width=42,
                                    command=self._browse_master)
        btn_browse_m.pack(side="left", padx=(6, 0))
        _bind_tip(btn_browse_m, "Выбрать путь к terminal64.exe мастера")

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(side="left", padx=(14, 0))
        btn_open_master = IconButton(actions, icon=theme.ICON_CHART,
                                       color=ACCENT,
                                       command=self._open_master_terminal,
                                       size=30)
        btn_open_master.pack(side="left", padx=2)
        _bind_tip(btn_open_master, "Открыть терминал мастера")
        btn_close_master = IconButton(actions, icon=theme.ICON_X,
                                        color=RED_DIM,
                                        command=self._close_all_master,
                                        size=30)
        btn_close_master.pack(side="left", padx=2)
        _bind_tip(btn_close_master, "Закрыть все сделки мастера")
        btn_test_master = IconButton(actions, icon=theme.ICON_WARNING,
                                       color=YELLOW,
                                       command=self._test_master,
                                       size=30)
        btn_test_master.pack(side="left", padx=2)
        _bind_tip(btn_test_master, "Тест мастера")

        # 4 ячейки статов master'а в сетке 4×1: фиксированный шаг между
        # колонками, чтобы длинные балансы не сдвигали соседей.
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="right", fill="y")
        for i in range(4):
            right.columnconfigure(i, minsize=92, weight=0, uniform="master_stats")

        self.lbl_master_login = self._stat_cell(right, "ЛОГИН", "—", FG_DIM,
                                                  sans_reg, sans_bold, col=0)
        self.lbl_master_bal = self._stat_cell(right, "БАЛАНС", "—", FG,
                                                sans_reg, sans_bold, col=1)
        self.lbl_master_eq = self._stat_cell(right, "ЭКВИТИ", "—", FG_DIM,
                                               sans_reg, sans_bold, col=2)
        self.lbl_master_pnl = self._stat_cell(right, "P&L", "—", FG_DIM,
                                                sans_reg, sans_bold, col=3)

    def _stat_cell(self, parent, label, value, color, sans_reg, sans_bold,
                   col=None):
        # tk.Label, потому что App._refresh_master_panel зовёт .config(text=..., fg=...).
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        if col is None:
            wrap.pack(side="left", padx=12)
        else:
            wrap.grid(row=0, column=col, padx=(0, 14) if col < 3 else 0,
                      sticky="e")
        tk.Label(wrap, text=label, bg=CARD_BG, fg=FG_DIM,
                  font=(sans_reg, 9)).pack(anchor="e")
        lbl = tk.Label(wrap, text=value, bg=CARD_BG, fg=color,
                        font=(sans_bold, 13))
        lbl.pack(anchor="e", pady=(2, 0))
        return lbl

    # ── KPI ROW ──────────────────────────────────────────────
    def _build_kpi_row_new(self, parent, sans_reg, sans_bold):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 14))

        self._kpi_labels = {}
        cards_data = [
            ("kpi_bal",  "Master Balance", "—", FG,     ACCENT),
            ("kpi_eq",   "Total Equity",   "—", FG,     ACCENT),
            ("kpi_pnl",  "Net P&L",        "—", FG_DIM, GREEN),
            ("kpi_conn", "Connected",      "—", FG_DIM, ACCENT),
        ]
        for i, (key, title, value, color, strip_color) in enumerate(cards_data):
            card = _make_card(row, height=78)
            card.pack(side="left", fill="x", expand=True,
                       padx=(0 if i == 0 else 10, 0))
            card.pack_propagate(False)

            strip = ctk.CTkFrame(card, width=3, corner_radius=2,
                                  fg_color=strip_color)
            strip.place(relx=0, rely=0.18, relheight=0.64, x=8)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=18, pady=10)

            tk.Label(inner, text=title.upper(), bg=CARD_BG, fg=FG_DIM,
                      font=(sans_reg, 9), anchor="w").pack(fill="x")
            lbl = tk.Label(inner, text=value, bg=CARD_BG, fg=color,
                            font=(sans_bold, 18), anchor="w")
            lbl.pack(fill="x", pady=(2, 0))
            self._kpi_labels[key] = lbl

    # ── SLAVES SECTION ───────────────────────────────────────
    def _build_slaves_section_new(self, parent, sans_reg, sans_bold):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(header, text="SLAVE ACCOUNTS", text_color=FG_LABEL,
                     font=(sans_bold, 11)).pack(side="left")
        self.lbl_slave_count = tk.Label(header, text="0/10",
                                          bg=BG_DEEP, fg=FG_DIM,
                                          font=(sans_bold, 10))
        self.lbl_slave_count.pack(side="left", padx=(10, 0))

        PillButton(header, "✖ Закрыть сделки", variant="danger",
                    command=self._close_all_open).pack(side="right", padx=(8, 0))
        PillButton(header, "+ Аккаунт", variant="primary",
                    command=self._add_slave).pack(side="right")

        table_card = _make_card(parent)
        table_card.pack(fill="both", expand=True, pady=(0, 12))

        self._table_frame = tk.Frame(table_card, bg=CARD_BG)
        self._table_frame.pack(fill="both", expand=True, padx=14, pady=10)

        for idx, _, min_w, weight, _ in COL_SPEC:
            self._table_frame.columnconfigure(idx, minsize=min_w, weight=weight)

        for idx, text, _, _, anchor in COL_SPEC:
            tk.Label(self._table_frame, text=text, bg=CARD_BG, fg=FG_DIM,
                      font=(sans_bold, 8), anchor=anchor).grid(
                row=0, column=idx, padx=2, pady=(0, 6), sticky="ew")

        self._next_row = 1
        # stub для совместимости с возможными внешними обращениями
        self.tbl_btns = tk.Frame(self._table_frame, bg=CARD_BG)

    # ── BOTTOM NOTEBOOK ──────────────────────────────────────
    def _build_bottom_notebook_new(self, parent, sans_reg, sans_bold):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # Phase 2: «underline»-индикатор вместо заливки.
        # Выбранная вкладка имеет CARD_BG-фон (сливается с панелью) и
        # ACCENT-цвет текста — это даёт впечатление линии-подчёркивания.
        style.configure("CTkNotebook.TNotebook", background=CARD_BG,
                        borderwidth=0)
        style.configure("CTkNotebook.TNotebook.Tab",
                        background=BG_DEEP, foreground=FG_DIM,
                        padding=[18, 8], font=(sans_bold, 10),
                        borderwidth=0)
        style.map("CTkNotebook.TNotebook.Tab",
                   background=[("selected", CARD_BG),
                               ("active", BG_INPUT)],
                   foreground=[("selected", ACCENT),
                               ("active", FG)])

        nb_card = _make_card(parent)
        nb_card.pack(fill="both", expand=False, pady=(0, 0))

        self.notebook = ttk.Notebook(nb_card, style="CTkNotebook.TNotebook",
                                       height=200)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        trades_tab = tk.Frame(self.notebook, bg=CARD_BG)
        self.notebook.add(trades_tab, text="  Сделки  ")

        # Phase 4: toolbar над таблицей — chips + поиск + сводка справа.
        self._build_trades_toolbar(trades_tab, sans_reg, sans_bold)

        self.trades_table = TradesTable(trades_tab)
        self.trades_table.configure(bg=CARD_BG)
        self.trades_table.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        self.trades_table.set_summary_callback(self._update_trades_summary)

        for t in _load_trades():
            tag = "ok" if t.get("success") else "err"
            self.trades_table.add_trade(
                time_str=t.get("time", ""), slave=t.get("slave", ""),
                symbol=t.get("symbol", ""), direction=t.get("direction", ""),
                lot=t.get("lot", 0.0), master_ticket=t.get("master_ticket", ""),
                slave_ticket=t.get("slave_ticket", ""),
                status=t.get("status", ""), tag=tag)

        log_tab = tk.Frame(self.notebook, bg=CARD_BG)
        self.notebook.add(log_tab, text="  Лог  ")

        # Phase 4: toolbar над логом — chips + copy + auto-scroll.
        self._build_log_toolbar(log_tab, sans_reg, sans_bold)

        log_inner = tk.Frame(log_tab, bg=CARD_BG)
        log_inner.pack(fill="both", expand=True, padx=2, pady=2)
        self.log_text = tk.Text(log_inner, bg=BG, fg=FG, font=FONT_MONO_SM,
                                  relief="flat", state="disabled", wrap="word",
                                  highlightthickness=0, borderwidth=0)
        log_sb = ttk.Scrollbar(log_inner, orient="vertical",
                                 command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True, padx=(8, 0),
                            pady=8)
        self.log_text.tag_config("ok", foreground=GREEN)
        self.log_text.tag_config("err", foreground=RED)
        self.log_text.tag_config("warn", foreground=YELLOW)
        self.log_text.tag_config("info", foreground=FG_DIM)

    # ── Phase 4: trades toolbar ──────────────────────────────
    def _build_trades_toolbar(self, parent, sans_reg, sans_bold):
        bar = tk.Frame(parent, bg=CARD_BG)
        bar.pack(fill="x", padx=2, pady=(2, 6))

        # Чипы-фильтры
        chip_row = tk.Frame(bar, bg=CARD_BG)
        chip_row.pack(side="left")
        self._trades_chips = {}
        for name, label in (("all", "Все"), ("ok", "Успешные"),
                             ("err", "Ошибки")):
            chip = components.FilterChip(
                chip_row, text=label,
                selected=(name == "all"),
                on_click=lambda _c, n=name: self._on_trades_chip(n),
            )
            chip.pack(side="left", padx=(0, 6))
            self._trades_chips[name] = chip

        # Сводка справа
        self.lbl_trades_summary = tk.Label(
            bar, text="✓ 0  ·  ✗ 0",
            bg=CARD_BG, fg=FG_DIM, font=(sans_bold, 10),
        )
        self.lbl_trades_summary.pack(side="right", padx=(8, 4))

        # Поиск
        search_wrap = ctk.CTkFrame(
            bar, fg_color=BG_INPUT, corner_radius=CORNER_SM,
            border_width=1, border_color=SOFT_BORDER, height=26,
        )
        search_wrap.pack(side="right", padx=(8, 8))
        search_wrap.pack_propagate(False)

        icon_family = theme.pick_font(theme.ICON_PREFS)
        tk.Label(search_wrap, text=theme.ICON_SEARCH,
                 bg=BG_INPUT, fg=FG_DIM,
                 font=(icon_family, 11)).pack(side="left", padx=(8, 4))

        self.var_trades_query = tk.StringVar()
        ent = tk.Entry(search_wrap, textvariable=self.var_trades_query,
                       bg=BG_INPUT, fg=FG, insertbackground=FG,
                       relief="flat", font=(sans_reg, 10), width=20,
                       highlightthickness=0, borderwidth=0)
        ent.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.var_trades_query.trace_add("write", lambda *_:
                                          self._on_trades_query_change())

    def _on_trades_chip(self, name: str) -> None:
        for k, chip in self._trades_chips.items():
            chip.set_selected(k == name)
        self.trades_table.set_filter(
            status=name, query=self.var_trades_query.get(),
        )

    def _on_trades_query_change(self) -> None:
        # текущий выбранный чип
        active = "all"
        for k, chip in self._trades_chips.items():
            if chip._selected:
                active = k
                break
        self.trades_table.set_filter(
            status=active, query=self.var_trades_query.get(),
        )

    def _update_trades_summary(self, ok: int, err: int) -> None:
        if hasattr(self, "lbl_trades_summary"):
            self.lbl_trades_summary.config(text=f"✓ {ok}  ·  ✗ {err}")

    # ── Phase 4: log toolbar ─────────────────────────────────
    def _build_log_toolbar(self, parent, sans_reg, sans_bold):
        bar = tk.Frame(parent, bg=CARD_BG)
        bar.pack(fill="x", padx=2, pady=(2, 4))

        chip_row = tk.Frame(bar, bg=CARD_BG)
        chip_row.pack(side="left")
        self._log_chips = {}
        for name, label in (("all", "Все"), ("info", "Инфо"),
                             ("warn", "Warn"), ("err", "Ошибки"),
                             ("ok", "OK")):
            chip = components.FilterChip(
                chip_row, text=label,
                selected=(name == "all"),
                on_click=lambda _c, n=name: self._on_log_chip(n),
            )
            chip.pack(side="left", padx=(0, 6))
            self._log_chips[name] = chip

        # Copy + Auto-scroll справа
        self._log_autoscroll = True

        def _on_autoscroll(v):
            self._log_autoscroll = bool(v)

        self._log_autoscroll_switch = components.ToggleSwitch(
            bar, text="Авто-прокрутка", initial=True,
            on_change=_on_autoscroll,
        )
        self._log_autoscroll_switch.pack(side="right", padx=(8, 4))

        btn_copy = PillButton(bar, "Копировать", variant="subtle",
                                command=self._copy_log)
        btn_copy.pack(side="right", padx=(8, 6))

    def _on_log_chip(self, name: str) -> None:
        for k, chip in self._log_chips.items():
            chip.set_selected(k == name)
        # Скрываем строки не-выбранного уровня через elide.
        try:
            for tag in ("info", "warn", "err", "ok"):
                self.log_text.tag_configure(
                    tag,
                    elide=(name != "all" and name != tag),
                )
        except Exception:
            pass

    def _copy_log(self) -> None:
        try:
            txt = self.log_text.get("1.0", "end-1c")
            self.clipboard_clear()
            self.clipboard_append(txt)
            if hasattr(self, "toasts"):
                self.toasts.show("Лог скопирован в буфер", "ok",
                                  timeout=1800)
        except Exception:
            pass

    # ── FOOTER ───────────────────────────────────────────────
    def _build_footer_stats_new(self, sans_reg):
        bar = ctk.CTkFrame(self, fg_color=BG_DEEP, height=26)
        bar.pack(fill="x", padx=18, pady=(2, 6))

        self.lbl_stats = tk.Label(bar, text="", bg=BG_DEEP, fg=FG_DIM,
                                    font=(sans_reg, 10))
        self.lbl_stats.pack(side="left")

        # Uptime — справа, рядом с версией.
        if _UPD_OK:
            ctk.CTkLabel(bar, text=f"v{upd_mod.VERSION}",
                          text_color=FG_MUTED,
                          font=(sans_reg, 10)).pack(side="right")

        self._uptime_start = time.time()
        self.lbl_uptime = tk.Label(bar, text="uptime 00:00",
                                    bg=BG_DEEP, fg=FG_MUTED,
                                    font=(sans_reg, 10))
        self.lbl_uptime.pack(side="right", padx=(0, 14))
        self._tick_uptime()

    def _tick_uptime(self):
        try:
            elapsed = int(time.time() - getattr(self, "_uptime_start",
                                                time.time()))
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            if h:
                txt = f"uptime {h:d}:{m:02d}:{s:02d}"
            else:
                txt = f"uptime {m:02d}:{s:02d}"
            if hasattr(self, "lbl_uptime"):
                self.lbl_uptime.config(text=txt)
        except Exception:
            pass
        try:
            self.after(1000, self._tick_uptime)
        except Exception:
            pass

    # ── Info toggle ──────────────────────────────────────────
    def _toggle_info(self):
        _Tip.enabled = not _Tip.enabled
        if _Tip.enabled:
            self.btn_info.configure(fg_color=ACCENT, text_color="#FFFFFF")
        else:
            self.btn_info.configure(fg_color=BG_INPUT, text_color=FG_DIM)
            _Tip.hide()

    # ── Мастер ──────────────────────────────────────────────

    def _browse_master(self):
        path = filedialog.askopenfilename(
            title="terminal64.exe мастера",
            filetypes=[("MT5", "terminal64.exe"), ("EXE", "*.exe")],
            initialdir="C:\\")
        if path:
            self.var_master_path.set(path.replace("/", "\\"))
            self._save_config()

    def _open_master_terminal(self):
        path = self.var_master_path.get().strip()
        if not path:
            self._log("\u26A0\uFE0F Путь мастера не задан", "warn")
            return
        self._open_terminal_path(path)

    def _close_all_master(self):
        if not _COPIER_OK:
            self._log("\u274C copier.py не найден", "err")
            return
        path = self.var_master_path.get().strip()
        if not path:
            return
        self._log("\u2716 Закрытие всех позиций [МАСТЕР]...", "warn")
        cfg = self._build_config()
        trader = CopyTrader(
            config=cfg, state_file=STATE_FILE,
            log_callback=self._on_log,
            status_callback=self._on_status,
            config_file=CONFIG_FILE,
        )
        trader.close_all_positions(path, "МАСТЕР")

    def _test_master(self):
        if not _MT5_OK:
            self._log("\u274C MT5 не установлен", "err")
            return
        master_path = self.var_master_path.get().strip()
        if not master_path:
            self._log("\u26A0\uFE0F Путь мастера не задан", "warn")
            return
        if not is_terminal_running(master_path):
            self._log("\u26A0\uFE0F Мастер-терминал не запущен", "warn")
            return
        if not mt5.initialize(path=master_path):
            self._log("\u274C Ошибка подключения к мастеру", "err")
            return
        try:
            acc = mt5.account_info()
            if acc is None:
                self._log("\u274C Нет данных аккаунта мастера", "err")
                return
            test_sym = None
            for s in self._slaves:
                if s.get("enabled", True) and s.get("symbol_map"):
                    for master_sym in s["symbol_map"]:
                        test_sym = master_sym
                        break
                if test_sym:
                    break
            if not test_sym:
                self._log("\u26A0\uFE0F Нет символов в маппинге слейвов — нечего тестировать", "warn")
                return
            info = mt5.symbol_info(test_sym)
            if info is None:
                alt = test_sym.upper().rstrip(".")
                for s in (mt5.symbols_get() or []):
                    if s.name.upper().rstrip(".") == alt:
                        test_sym = s.name
                        info = mt5.symbol_info(test_sym)
                        break
            if info is None:
                self._log(f"\u274C Символ {test_sym} не найден на мастере", "err")
                return
            if info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
                self._log(f"\u274C {test_sym} не торгуется на мастере", "err")
                return
            mt5.symbol_select(test_sym, True)
            tick = mt5.symbol_info_tick(test_sym)
            if not tick:
                self._log(f"\u274C Нет тика для {test_sym}", "err")
                return
            from copier import get_filling_mode, normalize_price, try_send_order
            filling = get_filling_mode(info)
            lot = info.volume_min
            price = normalize_price(tick.ask, info.digits)
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": test_sym,
                "volume": lot,
                "type": mt5.ORDER_TYPE_BUY,
                "price": price,
                "comment": "CT_TEST",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }
            result = try_send_order(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self._log(f"\u2705 Тест BUY {test_sym} lot={lot} на мастере \u2192 #{result.order}", "ok")
                self._log("\u2139\uFE0F Закройте позицию вручную \u2014 копир скопирует закрытие", "info")
            else:
                rc = result.retcode if result else -1
                cmt = result.comment if result else ""
                self._log(f"\u274C Ошибка теста: retcode={rc} {cmt}", "err")
        finally:
            mt5.shutdown()

    def _close_all_open(self):
        self._close_all_master()
        for s in self._slaves:
            if s.get("enabled", True) and s.get("path"):
                self._close_all_slave(s)

    def _close_all_slave(self, data: Dict):
        if not _COPIER_OK:
            self._log("\u274C copier.py не найден", "err")
            return
        sname = data.get("name", "?")
        self._log(f"\u2716 Закрытие всех позиций [{sname}]...", "warn")
        cfg = self._build_config()
        trader = CopyTrader(
            config=cfg, state_file=STATE_FILE,
            log_callback=self._on_log,
            status_callback=self._on_status,
            config_file=CONFIG_FILE,
        )
        trader.close_all_positions(data.get("path", ""), sname)

    # ── Слейвы ──────────────────────────────────────────────

    MAX_SLAVES = 10

    def _update_slave_count(self):
        self.lbl_slave_count.config(text=f"{len(self._slaves)}/{self.MAX_SLAVES}")
        self._update_slaves_empty_state()

    def _update_slaves_empty_state(self):
        # Phase 3a: показываем EmptyState, когда слейв-таблица пустая.
        if not hasattr(self, "_table_frame"):
            return
        is_empty = not self._slaves
        existing = getattr(self, "_slaves_empty", None)
        if is_empty:
            if existing is None or not existing.winfo_exists():
                self._slaves_empty = components.EmptyState(
                    self._table_frame,
                    title="Нет слейв-аккаунтов",
                    subtitle="Добавьте хотя бы один аккаунт, чтобы "
                             "начать копирование сделок с мастера.",
                    icon=theme.ICON_INFO,
                    cta_text="+ Добавить аккаунт",
                    cta_command=self._add_slave,
                )
                # Заголовок таблицы (row=0) занят. Кладём поверх свободной
                # области как overlay: place() со span'ом.
                self._slaves_empty.place(
                    relx=0.5, rely=0.5, anchor="center",
                    relwidth=0.9, relheight=0.85,
                )
        else:
            if existing is not None and existing.winfo_exists():
                try:
                    existing.destroy()
                except Exception:
                    pass
                self._slaves_empty = None

    def _add_slave(self):
        if len(self._slaves) >= self.MAX_SLAVES:
            messagebox.showwarning("Лимит", f"Максимум {self.MAX_SLAVES} слейв-аккаунтов на профиль", parent=self)
            return
        dlg = SlaveDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            data = dlg.result
            data["id"] = str(uuid.uuid4())[:8]
            data["enabled"] = True
            if "max_trades_per_day" not in data:
                data["max_trades_per_day"] = 0
            if "daily_loss_limit" not in data:
                data["daily_loss_limit"] = 0
            self._slaves.append(data)
            self._add_slave_row(data)
            self._update_slave_count()
            self._save_config()

    def _add_slave_row(self, data: Dict):
        row = AccountRow(self._table_frame, self._next_row, data,
                         on_edit=self._edit_slave,
                         on_delete=self._delete_slave,
                         on_toggle=self._toggle_slave,
                         on_test=self._test_slave,
                         on_open=self._open_slave_terminal,
                         on_close_all=self._close_all_slave)
        self._rows.append(row)
        self._next_row += 1

    def _edit_slave(self, data: Dict, row: AccountRow):
        dlg = SlaveDialog(self, data)
        self.wait_window(dlg)
        if dlg.result:
            sid = data.get("id", "")
            enabled = data.get("enabled", True)
            data.clear()
            data.update(dlg.result)
            data["id"] = sid
            data["enabled"] = enabled
            row.refresh(data)
            self._save_config()

    def _delete_slave(self, data: Dict, row: AccountRow):
        if messagebox.askyesno("Удалить", f"Удалить \u00AB{data.get('name', '?')}\u00BB?", parent=self):
            self._slaves.remove(data)
            self._rebuild_rows()
            self._update_slave_count()
            self._save_config()

    def _rebuild_rows(self):
        for r in self._rows:
            r.destroy()
        self._rows.clear()
        self._next_row = 1
        for s in self._slaves:
            self._add_slave_row(s)
        self._update_slave_count()

    def _toggle_slave(self, data: Dict):
        self._save_config()

    def _test_slave(self, data: Dict):
        if not _COPIER_OK:
            self._log("\u274C copier.py не найден", "err")
            return
        symbol_map = data.get("symbol_map", {})
        if not symbol_map:
            self._log("\u26A0\uFE0F Нет символов в маппинге", "warn")
            return
        self._log(f"\U0001F9EA Тест копирования [{data.get('name', '?')}]", "warn")
        cfg = self._build_config()
        trader = CopyTrader(
            config=cfg, state_file=STATE_FILE,
            log_callback=self._on_log,
            status_callback=self._on_status,
            config_file=CONFIG_FILE,
        )
        trader.test_trade(data, cfg)

    def _open_slave_terminal(self, data: Dict):
        path = data.get("path", "")
        if not path:
            self._log("\u26A0\uFE0F Путь к терминалу не задан", "warn")
            return
        self._open_terminal_path(path)

    def _open_terminal_path(self, path: str):
        if not is_terminal_running(path):
            try:
                os.startfile(path)
                self._log(f"\U0001F680 Запуск: {os.path.basename(os.path.dirname(path))}")
            except Exception as e:
                self._log(f"\u274C Ошибка запуска: {e}", "err")
        else:
            if activate_terminal(path):
                self._log(f"\U0001F4C2 Терминал активирован")
            else:
                self._log("\u26A0\uFE0F Не удалось найти окно терминала", "warn")

    # ── Запуск/остановка терминалов ─────────────────────────

    def _launch_all(self):
        paths = []
        master_path = self.var_master_path.get().strip()
        if master_path:
            paths.append(master_path)
        for s in self._slaves:
            if not s.get("enabled", True):
                continue
            p = s.get("path", "")
            if p and p not in paths:
                paths.append(p)
        launched = 0
        for p in paths:
            if not is_terminal_running(p):
                try:
                    si = subprocess.STARTUPINFO()
                    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 6  # SW_MINIMIZE
                    subprocess.Popen([p], startupinfo=si)
                    launched += 1
                    self._log(f"\U0001F680 Запуск: {os.path.basename(os.path.dirname(p))}")
                except Exception as e:
                    self._log(f"\u274C Ошибка запуска {p}: {e}", "err")
            else:
                self._log(f"\u2705 Уже запущен: {os.path.basename(os.path.dirname(p))}")
        if launched > 0:
            self._log(f"\u2705 Запущено {launched} терминалов", "ok")
        else:
            self._log("Все терминалы уже запущены")

    def _shutdown_all(self):
        if not _PSUTIL_OK:
            self._log("\u274C psutil не установлен", "err")
            return
        paths = []
        master_path = self.var_master_path.get().strip()
        if master_path:
            paths.append(master_path)
        for s in self._slaves:
            if not s.get("enabled", True):
                continue
            p = s.get("path", "")
            if p and p not in paths:
                paths.append(p)
        killed = 0
        for p in paths:
            norm = os.path.normcase(os.path.abspath(p))
            for proc in psutil.process_iter(['exe', 'pid']):
                try:
                    exe = proc.info.get('exe')
                    if exe and os.path.normcase(exe) == norm:
                        proc.terminate()
                        killed += 1
                        self._log(f"\u25A0 Завершён: {os.path.basename(os.path.dirname(p))}")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        if killed > 0:
            self._log(f"\u25A0 Завершено {killed} процессов", "warn")
        else:
            self._log("Нет запущенных терминалов")

    # ── Проверка связи / Старт / Стоп ───────────────────────

    def _schedule_check(self):
        if self._check_timer:
            self.after_cancel(self._check_timer)
        if self._trader and self._trader.is_running():
            self._refresh_dashboard()
        else:
            self._update_master_info_silent()
            for row, slave in zip(self._rows, self._slaves):
                self._update_row_info_silent(row, slave)
            self._refresh_dashboard()
        self._check_timer = self.after(3000, self._schedule_check)

    def _check_update(self, force=False):
        if not _UPD_OK:
            if force:
                messagebox.showinfo("Обновления", "Модуль обновлений недоступен")
            return
        upd_mod.check_update(callback=self._on_update_available, no_update=lambda: self._on_no_update() if force else None)

    def _on_no_update(self):
        messagebox.showinfo("Обновления", f"У вас последняя версия (v{upd_mod.VERSION})")

    def _on_update_available(self, version, changelog):
        text = f"Доступна новая версия: v{version}"
        if changelog:
            text += f"\n{changelog}"
        text += "\n\nСкачайте в Telegram: @fth_copier_bot → /download"
        messagebox.showinfo("Обновление", text)

    def _schedule_license_check(self):
        if not _LIC_OK:
            return
        lic = lic_mod.load_license()
        if not lic or not lic.get("token"):
            self._show_activation()
            return
        valid, reason, _ = lic_mod.check_token(lic["token"])
        if not valid and reason != "connection_error":
            self._show_activation()
            return
        self._lic_timer = self.after(600000, self._schedule_license_check)

    def _show_activation(self):
        if not _LIC_OK:
            return
        dlg = ActivationWindow(self)
        self.wait_window(dlg)
        if _LIC_OK:
            lic = lic_mod.load_license()
            if not lic or not lic.get("token"):
                self.destroy()
                return
        self._lic_timer = self.after(600000, self._schedule_license_check)

    def _update_master_info_silent(self):
        if not _MT5_OK:
            return
        master_path = self.var_master_path.get().strip()
        if not master_path:
            self.lbl_master_bal.config(text="\u2014", fg=FG_DIM)
            self.lbl_master_login.config(text="нет пути", fg=RED)
            return
        if not is_terminal_running(master_path):
            self.lbl_master_login.config(text="не запущен", fg=RED)
            return
        if mt5.initialize(path=master_path):
            try:
                acc = mt5.account_info()
                if acc:
                    ti = mt5.terminal_info()
                    pnl = acc.equity - acc.balance
                    pnl_color = GREEN if pnl >= 0 else RED
                    pnl_sign = "+" if pnl >= 0 else ""
                    at_off = ti and not ti.trade_allowed
                    self.lbl_master_login.config(
                        text=f"#{acc.login}" + (" \u26A0AT" if at_off else ""),
                        fg=RED if at_off else FG_DIM)
                    self.lbl_master_bal.config(text=f"${acc.balance:,.2f}")
                    self.lbl_master_eq.config(text=f"${acc.equity:,.2f}")
                    self.lbl_master_pnl.config(text=f"{pnl_sign}${pnl:,.2f}", fg=pnl_color)
                else:
                    self.lbl_master_login.config(text="нет аккаунта", fg=RED)
            finally:
                mt5.shutdown()
        else:
            self.lbl_master_login.config(text="ошибка", fg=RED)

    def _update_row_info_silent(self, row: AccountRow, slave: Dict):
        if not _MT5_OK:
            return
        slave_path = slave.get("path", "")
        if not slave_path:
            row.update_info(0, 0, status="\U0001F534 нет пути")
            return
        if not is_terminal_running(slave_path):
            row.update_info(0, 0, status="\U0001F534 не запущен")
            return
        if mt5.initialize(path=slave_path):
            try:
                acc = mt5.account_info()
                if acc:
                    ti = mt5.terminal_info()
                    at_off = ti and not ti.trade_allowed
                    if at_off:
                        status = f"\U0001F7E1 \u26A0AT #{acc.login}"
                    else:
                        status = f"\U0001F7E2 #{acc.login}"
                    row.update_info(acc.balance, acc.equity, acc.login, status)
                else:
                    row.update_info(0, 0, status="\U0001F534 нет аккаунта")
            finally:
                mt5.shutdown()
        else:
            row.update_info(0, 0, status="\U0001F534 ошибка")

    def _refresh_dashboard(self):
        try:
            bal_text = self.lbl_master_bal.cget("text")
            bal = float(bal_text.replace("$", "").replace(",", "")) if bal_text and bal_text != "\u2014" else 0
        except Exception:
            bal = 0
        self._kpi_labels["kpi_bal"].config(text=f"${bal:,.2f}" if bal > 0 else "\u2014")

        total_eq = bal
        for row in self._rows:
            try:
                eq_text = row.lbl_equity.cget("text")
                eq = float(eq_text.replace("$", "").replace(",", "")) if eq_text and eq_text != "\u2014" else 0
                if eq > 0:
                    total_eq += eq
            except Exception:
                pass
        self._kpi_labels["kpi_eq"].config(text=f"${total_eq:,.2f}" if total_eq > 0 else "\u2014")

        net_pnl = 0.0
        for row in self._rows:
            try:
                pnl_text = row.lbl_pnl.cget("text")
                pnl_text = pnl_text.replace("$", "").replace(",", "").replace("+", "")
                pnl = float(pnl_text) if pnl_text and pnl_text != "\u2014" else 0
                net_pnl += pnl
            except Exception:
                pass
        pnl_color = GREEN if net_pnl >= 0 else RED
        pnl_sign = "+" if net_pnl >= 0 else ""
        self._kpi_labels["kpi_pnl"].config(text=f"{pnl_sign}${net_pnl:,.2f}" if net_pnl != 0 else "\u2014",
                                            fg=pnl_color if net_pnl != 0 else FG_DIM)

        connected = sum(1 for row in self._rows if row.var_enabled.get())
        total = len(self._rows)
        self._kpi_labels["kpi_conn"].config(text=f"{connected}/{total}")

    def _start(self):
        master_path = self.var_master_path.get().strip()
        if not master_path:
            messagebox.showwarning("Ошибка", "Укажите путь мастера", parent=self)
            return
        enabled = [s for s in self._slaves if s.get("enabled", True)]
        if not enabled:
            messagebox.showwarning("Ошибка", "Добавьте включённый аккаунт", parent=self)
            return
        self._save_config()
        if not _COPIER_OK:
            messagebox.showerror("Ошибка", "Не найден copier.py", parent=self)
            return
        self._trader = CopyTrader(
            config=self._build_config(),
            state_file=STATE_FILE,
            log_callback=self._on_log,
            status_callback=self._on_status,
            trade_callback=self._on_trade,
            config_file=CONFIG_FILE,
        )
        self._trader.start()
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        if os.path.exists(ICON_CYAN):
            self.iconbitmap(ICON_CYAN)
            self.wm_iconbitmap(ICON_CYAN)
        self._set_logo_cyan(True)
        self._update_tray_icon(True)
        if hasattr(self, "status_pill"):
            self.status_pill.set_state("running", "Копирование активно")
        self._session_stats = {"copied": 0, "failed": 0}
        self._log("\u2705 Копитрейдер запущен", "ok")
        if hasattr(self, "toasts"):
            self.toasts.show("Копитрейдер запущен", "ok")

    def _stop(self):
        if self._trader:
            self._trader.stop()
            self._trader = None
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        if os.path.exists(ICON_DEFAULT):
            self.iconbitmap(ICON_DEFAULT)
            self.wm_iconbitmap(ICON_DEFAULT)
        self._set_logo_cyan(False)
        self._update_tray_icon(False)
        if hasattr(self, "status_pill"):
            self.status_pill.set_state("stopped", "Остановлено")
        self._log("\u25A0 Копитрейдер остановлен", "warn")
        if hasattr(self, "toasts"):
            self.toasts.show("Копитрейдер остановлен", "info")
        self._schedule_check()

    # ── Колбэки ─────────────────────────────────────────────

    def _on_log(self, msg: str):
        self.after(0, self._log, msg)

    def _on_status(self, terminal_id: str, status: str,
                   balance: float = 0, equity: float = 0,
                   daily_loss: float = 0, daily_loss_limit: float = 0):
        self.after(0, self._update_status, terminal_id, status, balance, equity,
                   daily_loss, daily_loss_limit)

    def _on_trade(self, trade_info: Dict):
        self.after(0, self._add_trade_row, trade_info)

    def _add_trade_row(self, info: Dict):
        tag = "ok" if info.get("success") else "err"
        if tag == "ok":
            self._session_stats["copied"] += 1
        else:
            self._session_stats["failed"] += 1
        self.trades_table.add_trade(
            time_str=info.get("time", ""), slave=info.get("slave", ""),
            symbol=info.get("symbol", ""), direction=info.get("direction", ""),
            lot=info.get("lot", 0.0), master_ticket=info.get("master_ticket", ""),
            slave_ticket=info.get("slave_ticket", ""), status=info.get("status", ""),
            tag=tag)
        self.lbl_stats.config(
            text=f"\u2705 {self._session_stats['copied']}  \u274C {self._session_stats['failed']}")
        _save_trade(info)
        self.notebook.select(0)

    def _update_status(self, terminal_id: str, status: str,
                       balance: float = 0, equity: float = 0,
                       daily_loss: float = 0, daily_loss_limit: float = 0):
        if terminal_id == "master":
            login = 0
            if "#" in status:
                try:
                    login = int(status.split("#")[1].split()[0].split("$")[0])
                except (ValueError, IndexError):
                    pass
            if login:
                self.lbl_master_login.config(text=f"#{login}", fg=FG_DIM)
            if balance > 0:
                self.lbl_master_bal.config(text=f"${balance:,.2f}")
            if equity > 0:
                self.lbl_master_eq.config(text=f"${equity:,.2f}")
                pnl = equity - balance
                pnl_color = GREEN if pnl >= 0 else RED
                pnl_sign = "+" if pnl >= 0 else ""
                self.lbl_master_pnl.config(text=f"{pnl_sign}${pnl:,.2f}", fg=pnl_color)
            return
        for row, slave in zip(self._rows, self._slaves):
            if slave.get("name") == terminal_id or slave.get("id") == terminal_id:
                if balance > 0 and equity > 0:
                    row.update_status_only(status, balance, equity)
                else:
                    row.update_status_only(status)
                if daily_loss_limit > 0:
                    row.update_daily_loss(daily_loss, daily_loss_limit)
                break

    # ── Лог ─────────────────────────────────────────────────

    def _log(self, msg: str, tag: str = "info"):
        if "\u2705" in msg:
            tag = "ok"
        elif "\u274C" in msg:
            tag = "err"
        elif "\u26A0\uFE0F" in msg or "\u25A0" in msg:
            tag = "warn"
        self.log_text.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n", tag)
        # Phase 4: уважаем переключатель «Авто-прокрутка».
        if getattr(self, "_log_autoscroll", True):
            self.log_text.see("end")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 500:
            self.log_text.delete("1.0", f"{lines - 500}.0")
        self.log_text.config(state="disabled")
        self._write_log_file(f"[{ts}] {msg}")

    def _write_log_file(self, msg: str):
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_file = os.path.join(LOGS_DIR, f"{date_str}.log")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    # ── Конфиг ──────────────────────────────────────────────

    def _build_profile(self) -> Dict:
        return {
            "master": {"path": self.var_master_path.get().strip()},
            "slaves": [
                {
                    "id": s.get("id", ""), "name": s.get("name", ""),
                    "enabled": s.get("enabled", True), "path": s.get("path", ""),
                    "symbol_map": s.get("symbol_map", {}),
                    "risk_type": s.get("risk_type", "percent"),
                    "risk_value": s.get("risk_value", 1.0),
                    "default_lot": s.get("default_lot", 0.01),
                    "max_drawdown": s.get("max_drawdown", 0),
                    "max_trades_per_day": s.get("max_trades_per_day", 0),
                    "daily_loss_limit": s.get("daily_loss_limit", 0),
                }
                for s in self._slaves
            ],
        }

    def _build_config(self) -> Dict:
        self._profiles[self._active_profile].update(self._build_profile())
        if "name" not in self._profiles[self._active_profile]:
            self._profiles[self._active_profile]["name"] = f"Профиль {self._active_profile + 1}"
        profile = self._profiles[self._active_profile]
        return {
            "master": profile.get("master", {"path": ""}),
            "slaves": profile.get("slaves", []),
            "poll_interval_seconds": 1,
            "min_lot_mode": self._min_lot_mode,
        }

    def _build_full_config(self) -> Dict:
        self._profiles[self._active_profile].update(self._build_profile())
        if "name" not in self._profiles[self._active_profile]:
            self._profiles[self._active_profile]["name"] = f"Профиль {self._active_profile + 1}"
        return {
            "active_profile": self._active_profile,
            "profiles": self._profiles,
            "poll_interval_seconds": 1,
            "min_lot_mode": self._min_lot_mode,
            "window": self._window_state_dict(),
        }

    def _window_state_dict(self) -> Dict:
        """Снимок геометрии/состояния окна для сохранения в config.json."""
        try:
            maximized = bool(self.state() == "zoomed")
        except Exception:
            maximized = False
        try:
            geom = self.geometry() if not maximized else None
        except Exception:
            geom = None
        out = {"maximized": maximized}
        if geom:
            out["geometry"] = geom
        return out

    def _save_config(self):
        try:
            os.makedirs(APP_DATA_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._build_full_config(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"\u26A0\uFE0F Ошибка конфига: {e}", "warn")

    def _load_config(self):
        self._profiles = []
        for i in range(5):
            self._profiles.append({"name": f"Профиль {i + 1}", "master": {"path": ""}, "slaves": []})
        self._active_profile = 0

        cfg = None
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                cfg = None

        # Сначала окно — чтобы первый кадр уже был в нужном размере.
        self._apply_window_state(cfg.get("window") if isinstance(cfg, dict) else None)

        if not isinstance(cfg, dict):
            self._update_slave_count()
            return

        if "profiles" in cfg:
            for i, p in enumerate(cfg["profiles"]):
                if i < 5:
                    self._profiles[i] = p
            self._active_profile = cfg.get("active_profile", 0)
        else:
            self._profiles[0] = {
                "name": "Профиль 1",
                "master": cfg.get("master", {"path": ""}),
                "slaves": cfg.get("slaves", []),
            }

        self._min_lot_mode = cfg.get("min_lot_mode", False)
        self._load_active_profile()
        self._update_slave_count()

    # ── Геометрия окна (Phase 2) ─────────────────────────────
    def _apply_window_state(self, win_cfg):
        """Применить сохранённую геометрию или подобрать 70% от экрана."""
        if isinstance(win_cfg, dict) and isinstance(win_cfg.get("geometry"), str):
            try:
                self.geometry(win_cfg["geometry"])
            except Exception:
                self._apply_default_geometry()
            if win_cfg.get("maximized"):
                try:
                    # Windows / Linux: 'zoomed' разворачивает на весь экран.
                    self.state("zoomed")
                except Exception:
                    pass
            return
        self._apply_default_geometry()

    def _apply_default_geometry(self):
        """70% экрана, зажато на [1100×720 — 1680×1000], центрировано."""
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
        except Exception:
            sw, sh = 1600, 900
        w = max(1100, min(1680, int(sw * 0.70)))
        h = max(720,  min(1000, int(sh * 0.70)))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        try:
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry(f"{w}x{h}")

    def _load_active_profile(self):
        p = self._profiles[self._active_profile]
        self.var_master_path.set(p.get("master", {}).get("path", ""))
        self._slaves.clear()
        for r in self._rows:
            r.destroy()
        self._rows.clear()
        self._next_row = 1
        for s in p.get("slaves", []):
            if "id" not in s:
                s["id"] = str(uuid.uuid4())[:8]
            if "max_drawdown" not in s:
                s["max_drawdown"] = 0
            if "max_trades_per_day" not in s:
                s["max_trades_per_day"] = 0
            if "daily_loss_limit" not in s:
                s["daily_loss_limit"] = 0
            self._slaves.append(s)
            self._add_slave_row(s)

    def _switch_profile(self, idx: int):
        if self._trader and self._trader.is_running():
            self._stop()
            self._log("\u25A0 Копитрейдер остановлен (смена профиля)", "warn")
        self._profiles[self._active_profile].update(self._build_profile())
        self._save_config()
        self._active_profile = idx
        self._load_active_profile()
        self._update_slave_count()
        self._save_config()
        self._log(f"\U0001F4CB Профиль: {self._profiles[idx].get('name', f'Профиль {idx + 1}')}", "info")

    def _open_settings(self):
        SettingsDialog(self)

    def _on_close(self):
        if self._trader and self._trader.is_running():
            self.withdraw()
            self._log("📋 Сворачивание в tray — копитрейдер продолжает работу", "info")
            return
        self._real_quit()

    def _real_quit(self):
        if self._trader and self._trader.is_running():
            self._stop()
        if self._tray_icon:
            self._tray_icon.stop()
            self._tray_icon = None
        self._save_config()
        self.destroy()


_MUTEX_NAME = "FTHTradeCopier_SingleInstance"


def _activate_existing():
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "FTH Trade Copier")
    if hwnd:
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        return True
    return False


if __name__ == "__main__":
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    already_exists = ctypes.windll.kernel32.GetLastError() == 183
    if already_exists:
        _activate_existing()
        sys.exit(0)

    app = App()
    app.mainloop()
