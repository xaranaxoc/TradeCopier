"""
MT5 Local Copy Trader — GUI (customtkinter)

This module mixes CTk and tk on purpose:

* Top-level windows and most container/control widgets use customtkinter
  via the wrappers in `ctk_compat` (Frame/Label/Button/Entry/Toplevel).
  Those wrappers translate tk-style kwargs (``bg=``/``fg=``/``width=N``-chars)
  to CTk-style kwargs, so the existing FTH palette and idioms keep
  working without rewriting every call site.
* Plain tk/ttk widgets are kept where CTk has no equivalent or where
  emulation would change behaviour: `_Tip` (overrideredirect tooltip),
  the slave table `ttk.Treeview`, the bottom `ttk.Notebook` tabs,
  `tk.PanedWindow`, `tk.Listbox`, `tk.Text` (log), `tk.Canvas` (status
  dot in AccountRow), `tk.Menu`, and all `tk.*Var` variables.
* `theme.apply_theme()` is called **after** the root `ctk.CTk()` is
  created — calling it earlier raises a TclError inside CTk (this was
  one of the regressions during the previous CTk attempt; see the
  rollback notes).
"""

import os
import sys
import json
import uuid
import subprocess
import threading
import ctypes
import warnings

# Silence CustomTkinter's noisy HighDPI warning about tk.PhotoImage. We
# use tk.PhotoImage in a handful of places (header logo, slave-row
# avatars, etc.) where the loss of HighDPI scaling is irrelevant —
# converting them all to CTkImage would pull Pillow into the import
# graph for no visible benefit, and the warning floods the console when
# running gui.py from py.exe.
warnings.filterwarnings(
    "ignore",
    message=r".*Given image is not CTkImage.*",
    category=UserWarning,
)

import tkinter as tk
import customtkinter as ctk
from datetime import datetime, timedelta
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Optional, Tuple

from ctk_compat import Label, Button, Entry, Frame, Toplevel
from theme import apply_theme

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

import ui_scaling

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

import palette as _palette_mod
from palette import (
    get_palette, get_fonts, apply_ttk_styles,
    set_theme, get_theme_name, available_themes, THEME_LABELS,
    palette_proxy, fonts_proxy,
    load_custom_themes, save_custom_themes,
    build_remap, remap_widget_colors,
)

# ── Custom themes + saved theme ─────────────────────────────────
# Custom (user-defined) themes live next to config.json so they survive
# upgrades.  Loading them BEFORE _apply_saved_theme() means a config
# pointing at a user theme will resolve correctly on startup.
CUSTOM_THEMES_FILE = os.path.join(APP_DATA_DIR, "custom_themes.json")


def _load_custom_themes():
    """Pull user-defined themes from disk (no-op if file missing/invalid)."""
    try:
        load_custom_themes(CUSTOM_THEMES_FILE)
    except Exception:
        pass


def _apply_saved_theme():
    """Read theme name from config.json and activate it (if valid)."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                _cfg = json.load(fh)
            _name = _cfg.get("theme")
            if _name:
                set_theme(_name)
    except Exception:
        pass  # keep default theme on any error


_load_custom_themes()
_apply_saved_theme()

# ── Theme aliases: lazy proxies ─────────────────────────────────
# Every ``p.X`` / ``f.X`` access is resolved against the CURRENT theme,
# so widgets built after a hot theme switch transparently pick up the
# new colours and fonts without any rebinding.
p = palette_proxy
f = fonts_proxy


# ── Persistence: trades ─────────────────────────────────────

def _save_trade(trade: Dict):
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        trades = []
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, "r", encoding="utf-8") as fh:
                trades = json.load(fh)
        trade["date"] = datetime.now().strftime("%Y-%m-%d")
        trades.append(trade)
        cutoff = (datetime.now() - timedelta(days=TRADES_KEEP_DAYS)).strftime("%Y-%m-%d")
        trades = [t for t in trades if t.get("date", "") >= cutoff]
        with open(TRADES_FILE, "w", encoding="utf-8") as fh:
            json.dump(trades, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _load_trades() -> List[Dict]:
    if not os.path.exists(TRADES_FILE):
        return []
    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as fh:
            trades = json.load(fh)
        cutoff = (datetime.now() - timedelta(days=TRADES_KEEP_DAYS)).strftime("%Y-%m-%d")
        return [t for t in trades if t.get("date", "") >= cutoff]
    except Exception:
        return []

# ── Tooltip (info mode) ────────────────────────────────────

class _Tip:
    enabled = False
    _active = None

    @classmethod
    def show(cls, widget, text):
        cls.hide()
        tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)
        tw.configure(bg=p.ACCENT)
        tw.wm_attributes("-topmost", True)
        lbl = tk.Label(tw, text=text, bg=p.ACCENT, fg=p.ACCENT_FG,
                       font=("Segoe UI", 9), padx=8, pady=4)
        lbl.pack()
        tw.update_idletasks()
        tw_w = tw.winfo_width()
        tw_h = tw.winfo_height()
        wx = widget.winfo_rootx() + widget.winfo_width() // 2 - tw_w // 2
        wy = widget.winfo_rooty() + widget.winfo_height() + 2
        # Clamp into the work area of the widget's monitor so the tooltip
        # never spills off-screen on small displays or when the parent sits
        # near the right/bottom edge of a secondary monitor.
        try:
            wa = ui_scaling.get_work_area_for_window(widget)
            wx, wy, _, _ = ui_scaling.clamp_to_work_area(wx, wy, tw_w, tw_h, wa)
        except Exception:
            pass
        tw.wm_geometry(f"+{wx}+{wy}")
        cls._active = tw

    @classmethod
    def hide(cls):
        if cls._active:
            try:
                cls._active.destroy()
            except Exception:
                pass
            cls._active = None


def _bind_tip(widget, text):
    widget.bind("<Enter>", lambda e: _Tip.show(widget, text) if _Tip.enabled else None)
    widget.bind("<Leave>", lambda e: _Tip.hide())

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

class SymbolPickerDialog(Toplevel):
    def __init__(self, parent, symbols: List[str], title_text: str = "Выбор символа"):
        super().__init__(parent)
        self.selected: Optional[str] = None
        self._all_symbols = symbols
        self.title(title_text)
        self.configure(fg_color=p.BG)
        self.resizable(False, False)
        icon = ICON_CYAN if (hasattr(parent, '_parent_app') and
            getattr(parent._parent_app, '_trader', None) and
            parent._parent_app._trader.is_running()) else ICON_DEFAULT
        if os.path.exists(icon):
            try:
                self.after(250, lambda: self.iconbitmap(icon))
            except Exception:
                pass
        self.grab_set()
        self._build()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        pw, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw2, py2 = parent.winfo_width(), parent.winfo_height()
        w = ui_scaling.scale(300)
        h = ui_scaling.scale(380)
        x = pw + (pw2 - w) // 2
        y = py + (py2 - h) // 2
        # Clamp into the work area of the parent's monitor so the dialog never
        # opens off-screen on multi-monitor setups or tiny laptops.
        wa = ui_scaling.get_work_area_for_window(parent)
        x, y, w, h = ui_scaling.clamp_to_work_area(x, y, w, h, wa)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        frm = Frame(self, bg=p.BG)
        frm.pack(fill="x", padx=10, pady=8)
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *_: self._filter())
        ent = Entry(frm, textvariable=self.var_search, width=28,
                    bg=p.BG_INPUT, fg=p.FG, font=f.DEFAULT,
                    highlightthickness=1,
                    highlightbackground=p.BORDER, highlightcolor=p.ACCENT)
        ent.pack(fill="x")
        ent.focus_set()

        frm_list = Frame(self, bg=p.BG)
        frm_list.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        # tk.Listbox stays — CTk has no equivalent.
        self.listbox = tk.Listbox(frm_list, bg=p.BG_ROW, fg=p.FG, font=f.DEFAULT,
                                   selectbackground=p.ACCENT, selectforeground=p.ACCENT_FG,
                                   relief="flat", highlightthickness=0, activestyle="none",
                                   borderwidth=0)
        sb = ttk.Scrollbar(frm_list, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<Double-1>", lambda e: self._pick())
        self.listbox.bind("<Return>", lambda e: self._pick())
        for s in self._all_symbols:
            self.listbox.insert("end", s)

        btn_frame = Frame(self, bg=p.BG)
        btn_frame.pack(fill="x", padx=10, pady=(0, 8))
        self._btn(btn_frame, "Выбрать", self._pick, accent=True).pack(side="left", padx=(0, 6))
        self._btn(btn_frame, "Отмена", self.destroy).pack(side="left")

    def _btn(self, parent, text, cmd, accent=False):
        bg = p.ACCENT if accent else p.BG_INPUT
        fg = p.ACCENT_FG if accent else p.FG_DIM
        abg = p.ACCENT_H if accent else p.BG_ROW_HOVER
        return Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                      font=f.BOLD if accent else f.DEFAULT,
                      activebackground=abg, padx=12, pady=2)

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

class SlaveDialog(Toplevel):
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
        # Horizontal-only resize. The form is sized vertically to its content
        # so vertical growth would just create empty space below the buttons;
        # horizontally the user may want extra width for long symbol pairs
        # ("US500.cash → SPX500") or terminal paths. minsize is set below from
        # the layout's requested size so the dialog can never be shrunk
        # smaller than what fits its widgets.
        self.resizable(True, False)
        self.configure(fg_color=p.BG)
        self.withdraw()
        icon = ICON_CYAN if getattr(parent, '_trader', None) and parent._trader.is_running() else ICON_DEFAULT
        if os.path.exists(icon):
            # CTkToplevel sets its own icon late, overriding any earlier
            # iconbitmap. Defer ours so it sticks.
            try:
                self.after(250, lambda: self.iconbitmap(icon))
            except Exception:
                pass
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
        # Dialog is .withdraw()'n at this point, so winfo_width/height return
        # 1×1. Use the layout's *requested* size instead, otherwise we set the
        # geometry to "1x1+x+y" and the dialog opens as a tiny strip.
        w = max(self.winfo_reqwidth(), self.winfo_width())
        h = max(self.winfo_reqheight(), self.winfo_height())
        # Lock minimum size to the requested size so user-resize can grow but
        # never shrink below what fits the form fields.
        try:
            self.minsize(w, h)
        except Exception:
            pass
        x = pw + (pw2 - w) // 2
        y = py + (py2 - h) // 2
        wa = ui_scaling.get_work_area_for_window(parent)
        x, y, w, h = ui_scaling.clamp_to_work_area(x, y, w, h, wa)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _lbl(self, parent, text, **kw):
        return Label(parent, text=text, bg=p.BG, fg=p.FG_LABEL, font=f.SM, **kw)

    def _ent(self, parent, var=None, width=28, **kw):
        return Entry(parent, textvariable=var, width=width,
                     bg=p.BG_INPUT, fg=p.FG, font=f.DEFAULT,
                     highlightthickness=1, highlightbackground=p.BORDER,
                     highlightcolor=p.ACCENT, **kw)

    def _btn(self, parent, text, cmd, accent=False, small=False):
        bg = p.ACCENT if accent else p.BG_INPUT
        fg = p.ACCENT_FG if accent else p.FG_DIM
        abg = p.ACCENT_H if accent else p.BG_ROW_HOVER
        fnt = f.XS if small else (f.BOLD if accent else f.SM)
        return Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                      font=fnt, activebackground=abg, padx=10, pady=2)

    def _build(self, data: Dict):
        pad = {"padx": 12, "pady": 3}
        frm_top = Frame(self, bg=p.BG)
        frm_top.pack(fill="x", **pad)
        # Make the input column take all extra horizontal space when the user
        # widens the dialog (so the "Имя" / "terminal64.exe" entries stretch
        # instead of leaving an empty strip on the right).
        frm_top.columnconfigure(1, weight=1)

        self._lbl(frm_top, "Имя").grid(row=0, column=0, sticky="w", pady=2)
        self.var_name = tk.StringVar(value=data.get("name", ""))
        self._ent(frm_top, self.var_name, 26).grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=2)

        self._lbl(frm_top, "terminal64.exe").grid(row=1, column=0, sticky="w", pady=2)
        self.var_path = tk.StringVar(value=data.get("path", ""))
        path_frame = Frame(frm_top, bg=p.BG)
        path_frame.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=2)
        self._ent(path_frame, self.var_path, 20).pack(side="left", fill="x", expand=True)
        btn_browse_s = self._btn(path_frame, "...", self._browse, small=True)
        btn_browse_s.pack(side="left", padx=(4, 0))
        _bind_tip(btn_browse_s, "Выбрать путь к terminal64.exe слейва")

        Frame(self, bg=p.DIVIDER, height=1).pack(fill="x", padx=12, pady=6)

        sym_header = Frame(self, bg=p.BG)
        sym_header.pack(fill="x", padx=12, pady=(2, 0))
        self._lbl(sym_header, "Символы (мастер \u2192 слейв)").pack(side="left")
        btn_load = self._btn(sym_header, "\u21E9 Загрузить", self._load_symbols, small=True)
        btn_load.pack(side="right")
        _bind_tip(btn_load, "Загрузить символы из запущенных терминалов")

        self.lbl_sym_status = Label(self, text="", bg=p.BG, fg=p.FG_DIM, font=f.XS)
        self.lbl_sym_status.pack(anchor="w", padx=12)

        self.sym_frame = Frame(self, bg=p.BG)
        self.sym_frame.pack(fill="x", padx=12, pady=2)

        symbol_map = data.get("symbol_map", {})
        for master_sym, slave_sym in symbol_map.items():
            self._add_symbol_row(master_sym, slave_sym)

        btn_add_sym = self._btn(self, "+ Символ", self._add_symbol_row, small=True)
        btn_add_sym.pack(anchor="w", padx=12, pady=(0, 2))
        _bind_tip(btn_add_sym, "Добавить строку маппинга символов")

        Frame(self, bg=p.DIVIDER, height=1).pack(fill="x", padx=12, pady=6)

        # ── Риск ─────────────────────────────────────────────
        frm_risk = Frame(self, bg=p.BG)
        frm_risk.pack(fill="x", padx=12, pady=2)

        self.var_risk_type = tk.StringVar(value=data.get("risk_type", "percent"))

        risk_value = data.get("risk_value", 1.0)
        risk_type = data.get("risk_type", "percent")

        self._lbl(frm_risk, "Риск %").grid(row=0, column=0, sticky="w", pady=2)
        pct_frame = Frame(frm_risk, bg=p.BG)
        pct_frame.grid(row=0, column=1, sticky="w", padx=(6, 0), pady=2)
        self.var_risk_pct = tk.StringVar(
            value=str(risk_value) if risk_type == "percent" else "")
        self._ent(pct_frame, self.var_risk_pct, 8).pack(side="left")

        self._lbl(frm_risk, "Риск $").grid(row=1, column=0, sticky="w", pady=2)
        doll_frame = Frame(frm_risk, bg=p.BG)
        doll_frame.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=2)
        self.var_risk_doll = tk.StringVar(
            value=str(risk_value) if risk_type == "fixed" else "")
        self._ent(doll_frame, self.var_risk_doll, 8).pack(side="left")

        self.lbl_risk_hint = Label(frm_risk, text="", bg=p.BG, fg=p.FG_DIM, font=f.XS)
        self.lbl_risk_hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        self.var_risk_pct.trace_add("write", lambda *_: self._sync_risk("percent"))
        self.var_risk_doll.trace_add("write", lambda *_: self._sync_risk("fixed"))

        self._lbl(frm_risk, "Лот без SL").grid(row=3, column=0, sticky="w", pady=2)
        self.var_default_lot = tk.StringVar(value=str(data.get("default_lot", "0.01")))
        self._ent(frm_risk, self.var_default_lot, 8).grid(row=3, column=1, sticky="w", padx=(6, 0), pady=2)

        self._lbl(frm_risk, "Макс. просадка %").grid(row=4, column=0, sticky="w", pady=2)
        self.var_max_drawdown = tk.StringVar(value=str(data.get("max_drawdown", 0)))
        self._ent(frm_risk, self.var_max_drawdown, 8).grid(row=4, column=1, sticky="w", padx=(6, 0), pady=2)
        Label(frm_risk, text="0 = выкл", bg=p.BG, fg=p.FG_DIM, font=f.XS).grid(
            row=5, column=1, sticky="w", padx=(6, 0))

        self._lbl(frm_risk, "Макс. сделок/день").grid(row=6, column=0, sticky="w", pady=2)
        self.var_max_trades = tk.StringVar(value=str(data.get("max_trades_per_day", 0)))
        self._ent(frm_risk, self.var_max_trades, 8).grid(row=6, column=1, sticky="w", padx=(6, 0), pady=2)
        Label(frm_risk, text="0 = выкл", bg=p.BG, fg=p.FG_DIM, font=f.XS).grid(
            row=7, column=1, sticky="w", padx=(6, 0))

        self._lbl(frm_risk, "Макс. убыт/день $").grid(row=8, column=0, sticky="w", pady=2)
        self.var_daily_loss = tk.StringVar(value=str(data.get("daily_loss_limit", 0)))
        self._ent(frm_risk, self.var_daily_loss, 8).grid(row=8, column=1, sticky="w", padx=(6, 0), pady=2)
        Label(frm_risk, text="0 = выкл", bg=p.BG, fg=p.FG_DIM, font=f.XS).grid(
            row=9, column=1, sticky="w", padx=(6, 0))

        Frame(self, bg=p.DIVIDER, height=1).pack(fill="x", padx=12, pady=6)

        btn_frame = Frame(self, bg=p.BG)
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
                    self.lbl_risk_hint.config(text=f"{pct_val}% от баланса", fg=p.ACCENT)
                except (ValueError, tk.TclError):
                    pass
            elif source == "fixed":
                try:
                    doll_val = float(self.var_risk_doll.get())
                    self.var_risk_type.set("fixed")
                    bal = self._get_ref_balance()
                    if bal > 0:
                        self.var_risk_pct.set(f"{doll_val / bal * 100.0:.2f}")
                    self.lbl_risk_hint.config(text=f"${doll_val:.2f} фиксированный", fg=p.ACCENT)
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
            self.lbl_sym_status.config(text="MT5 не установлен", fg=p.RED)
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
            self.lbl_sym_status.config(text="Загружено: " + ", ".join(parts), fg=p.GREEN_DIM)
        else:
            self.lbl_sym_status.config(text="Символы не загружены — запустите терминалы", fg=p.FG_DIM)

    def _get_master_path(self) -> str:
        parent = self.master
        if hasattr(parent, "var_master_path"):
            return parent.var_master_path.get().strip()
        return ""

    def _fetch_symbols(self, path: str, label: str) -> List[str]:
        if not path or not is_terminal_running(path):
            self.lbl_sym_status.config(text=f"Терминал {label} не запущен", fg=p.YELLOW)
            return []
        if not mt5.initialize(path=path):
            self.lbl_sym_status.config(text=f"Ошибка подключения к {label}", fg=p.YELLOW)
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
        row_frame = Frame(self.sym_frame, bg=p.BG)
        row_frame.pack(fill="x", pady=1)
        var_master = tk.StringVar(value=master_sym)
        var_slave = tk.StringVar(value=slave_sym)
        # width=8 sets the natural request size; fill+expand lets the entries
        # grow horizontally when the dialog is widened (long symbol names like
        # "EURUSD.r" or "US500.cash" become fully visible).
        self._ent(row_frame, var_master, 8).pack(side="left", fill="x", expand=True)

        var_master.trace_add("write", lambda *_: self._auto_suggest(var_master, var_slave))

        def pick_m():
            dlg = SymbolPickerDialog(self, self._master_symbols, "Мастер")
            self.wait_window(dlg)
            if dlg.selected:
                var_master.set(dlg.selected)

        btn_pick_m = self._btn(row_frame, "...", pick_m, small=True)
        btn_pick_m.pack(side="left", padx=1)
        _bind_tip(btn_pick_m, "Выбрать символ мастера из списка")
        Label(row_frame, text="\u2192", bg=p.BG, fg=p.FG_DIM, font=f.SM).pack(side="left", padx=3)
        self._ent(row_frame, var_slave, 8).pack(side="left", fill="x", expand=True)

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
        return p.BG_ROW_HOVER if self._hover else p.BG_ROW

    def _build(self):
        d = self.slave_data
        bg = p.BG_ROW
        r = self._row

        self._bg_frame = Frame(self._parent, bg=bg, highlightbackground=p.BORDER,
                               highlightthickness=1 if not self._hover else 1)
        self._bg_frame.grid(row=r, column=0, columnspan=12, sticky="nsew", pady=(1, 1))
        self._bg_frame.lower()

        self._accent_strip = Frame(self._bg_frame, bg=p.FG_DIM, width=3)
        self._accent_strip.place(x=0, y=0, relheight=1.0)

        enabled = d.get("enabled", True)
        self.var_enabled = tk.BooleanVar(value=enabled)
        self.lbl_check = Label(self._parent, text="\u2611" if enabled else "\u2610",
                               bg=bg, fg=p.GREEN if enabled else p.FG_DIM,
                               font=f.BOLD)
        self.lbl_check.grid(row=r, column=0, padx=(8, 2), pady=6, sticky="ew")
        self.lbl_check.bind("<Button-1>", lambda e: self._toggle())
        _bind_tip(self.lbl_check, "Включить / выключить аккаунт")
        self._widgets.append(self.lbl_check)

        dot_frame = Frame(self._parent, bg=bg, width=20, height=20)
        dot_frame.grid(row=r, column=1, padx=2, pady=6, sticky="")
        # tk.Canvas kept as plain tk — CTk has no canvas equivalent and
        # the status dot uses raw create_oval / itemconfigure.
        self._dot_canvas = tk.Canvas(dot_frame, width=14, height=14, bg=bg,
                                      highlightthickness=0, bd=0)
        self._dot_canvas.pack(padx=2, pady=2)
        self._dot_oval = self._dot_canvas.create_oval(3, 3, 11, 11, fill=p.FG_DIM, outline="")
        self._widgets.append(dot_frame)

        self.lbl_name = Label(self._parent, text=d.get("name", "\u2014"), bg=bg, fg=p.FG,
                              font=f.BOLD, anchor="w")
        self.lbl_name.grid(row=r, column=2, padx=(4, 4), pady=6, sticky="ew")
        self._widgets.append(self.lbl_name)

        # Empty-state placeholders are blank strings rather than em-dashes
        # so the row reads cleaner against a light background (em-dashes
        # in slim Segoe UI look like multiple underscores on Light Pro).
        # Values are populated from MT5 polling as soon as the slave
        # connects; columns that never get filled simply stay blank.
        self.lbl_login = Label(self._parent, text="", bg=bg, fg=p.FG_DIM,
                               font=f.MONO_SM, anchor="w")
        self.lbl_login.grid(row=r, column=3, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_login)

        self.lbl_balance = Label(self._parent, text="", bg=bg, fg=p.FG,
                                 font=f.VAL_BOLD, anchor="e")
        self.lbl_balance.grid(row=r, column=4, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_balance)

        self.lbl_equity = Label(self._parent, text="", bg=bg, fg=p.FG_DIM,
                                font=f.MONO_SM, anchor="e")
        self.lbl_equity.grid(row=r, column=5, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_equity)

        self.lbl_pnl = Label(self._parent, text="", bg=bg, fg=p.FG_DIM,
                             font=f.VAL, anchor="e")
        self.lbl_pnl.grid(row=r, column=6, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_pnl)

        sym_map = d.get("symbol_map", {})
        sym_text = "  ".join(f"{k}\u2192{v}" for k, v in list(sym_map.items())[:3])
        if len(sym_map) > 3:
            sym_text += f" +{len(sym_map) - 3}"
        self.lbl_symbols = Label(self._parent, text=sym_text, bg=bg, fg=p.FG_DIM,
                                 font=f.XS, anchor="w")
        self.lbl_symbols.grid(row=r, column=7, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_symbols)

        rt = d.get("risk_type", "percent")
        rv = d.get("risk_value", 1.0)
        risk_text = f"{rv}{'%' if rt == 'percent' else '$'}"
        self.lbl_risk = Label(self._parent, text=risk_text, bg=bg, fg=p.YELLOW,
                              font=f.SM, anchor="e")
        self.lbl_risk.grid(row=r, column=8, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_risk)

        mtd = d.get("max_trades_per_day", 0)
        self.lbl_trades_day = Label(self._parent, text=str(mtd) if mtd else "",
                                    bg=bg, fg=p.FG_DIM, font=f.SM, anchor="center")
        self.lbl_trades_day.grid(row=r, column=9, padx=4, pady=6, sticky="ew")
        self._widgets.append(self.lbl_trades_day)

        dll = d.get("daily_loss_limit", 0)
        bar_w = 100
        self._loss_canvas = tk.Canvas(self._parent, width=bar_w, height=16,
                                       bg=p.BG_INPUT, highlightthickness=0, bd=0)
        self._loss_canvas.grid(row=r, column=10, padx=4, pady=6, sticky="ew")
        self._loss_fill = self._loss_canvas.create_rectangle(0, 0, 0, 16, fill="", outline="")
        self._loss_text = self._loss_canvas.create_text(bar_w // 2, 8, text="",
                                                         fill=p.FG_DIM, font=f.XS)
        if dll > 0:
            self._loss_canvas.itemconfigure(self._loss_text, text=f"${dll:.0f}",
                                             fill=p.FG_DIM)
        self._widgets.append(self._loss_canvas)

        bf = Frame(self._parent, bg=bg)
        bf.grid(row=r, column=11, padx=(2, 6), pady=6, sticky="e")

        btn_open = Button(bf, text="\U0001F4C8", command=self._open_terminal,
                          bg=bg, fg=p.FG_DIM, font=f.SM,
                          activebackground=p.BG_ROW_HOVER, width=2)
        btn_open.pack(side="left", padx=1)
        _bind_tip(btn_open, "Открыть терминал")

        btn_close = Button(bf, text="\u2716", command=self._close_all,
                           bg=bg, fg=p.RED_DIM, font=f.SM,
                           activebackground=p.BG_ROW_HOVER, width=2)
        btn_close.pack(side="left", padx=1)
        _bind_tip(btn_close, "Закрыть все позиции")

        btn_test = Button(bf, text="\u26A0", command=self._test,
                          bg=bg, fg=p.YELLOW, font=f.SM,
                          activebackground=p.BG_ROW_HOVER, width=2)
        btn_test.pack(side="left", padx=1)
        _bind_tip(btn_test, "Тест: BUY 0.01 лот")

        btn_edit = Button(bf, text="\u2699", command=self._edit,
                          bg=bg, fg=p.FG_DIM, font=f.SM,
                          activebackground=p.BG_ROW_HOVER, width=2)
        btn_edit.pack(side="left", padx=1)
        _bind_tip(btn_edit, "Настройки")

        btn_del = Button(bf, text="\u2715", command=self._delete,
                         bg=bg, fg=p.FG_DIM, font=f.SM,
                         activebackground=p.BG_ROW_HOVER, width=2)
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
            return p.FG_DIM

    def _set_hover(self, hover: bool):
        if self._hover == hover:
            return
        self._hover = hover
        if hasattr(self, '_bg_frame') and self._bg_frame:
            if hover:
                self._bg_frame.configure(highlightbackground=p.ACCENT_DIM)
            else:
                self._bg_frame.configure(highlightbackground=p.BORDER)


    def update_info(self, balance: float, equity: float, login: int = 0,
                    status: str = ""):
        bg = p.BG_ROW
        self.lbl_balance.config(text=f"${balance:,.2f}", bg=bg)
        self.lbl_equity.config(text=f"${equity:,.2f}", bg=bg)
        if login:
            self.lbl_login.config(text=f"#{login}", bg=bg)

        pnl = equity - balance
        pnl_color = p.GREEN if pnl >= 0 else p.RED
        pnl_sign = "+" if pnl >= 0 else ""
        self.lbl_pnl.config(text=f"{pnl_sign}${pnl:,.2f}", fg=pnl_color, bg=bg)

        if status:
            dot_color = p.GREEN if "\U0001F7E2" in status else p.RED if "\U0001F534" in status else p.YELLOW if "\U0001F7E1" in status else p.FG_DIM
            self._dot_canvas.itemconfigure(self._dot_oval, fill=dot_color)
            self._dot_canvas.configure(bg=bg)

    def update_status_only(self, status: str, balance: float = 0, equity: float = 0):
        bg = p.BG_ROW
        dot_color = p.GREEN if "\U0001F7E2" in status else p.RED if "\U0001F534" in status else p.YELLOW if "\U0001F7E1" in status else p.FG_DIM
        self._dot_canvas.itemconfigure(self._dot_oval, fill=dot_color)
        self._dot_canvas.configure(bg=bg)
        if balance > 0:
            self.lbl_balance.config(text=f"${balance:,.2f}", bg=bg)
        if equity > 0:
            self.lbl_equity.config(text=f"${equity:,.2f}", bg=bg)
            pnl = equity - balance
            pnl_color = p.GREEN if pnl >= 0 else p.RED
            pnl_sign = "+" if pnl >= 0 else ""
            self.lbl_pnl.config(text=f"{pnl_sign}${pnl:,.2f}", fg=pnl_color, bg=bg)

    def update_daily_loss(self, daily_loss: float, daily_loss_limit: float):
        if daily_loss_limit <= 0:
            self._loss_canvas.coords(self._loss_fill, 0, 0, 0, 16)
            self._loss_canvas.itemconfigure(self._loss_fill, fill="")
            self._loss_canvas.itemconfigure(self._loss_text, text="\u2014", fill=p.FG_DIM)
            return
        bar_w = 100
        pct = min(daily_loss / daily_loss_limit, 1.0) if daily_loss_limit > 0 else 0
        fill_w = int(bar_w * pct)
        exceeded = daily_loss >= daily_loss_limit
        fill_color = p.RED if exceeded else p.ACCENT
        text_color = p.ACCENT_FG if pct > 0.5 else p.FG
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
                               fg=p.GREEN if new_val else p.FG_DIM, bg=bg)
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
        super().__init__(parent, bg=p.BG)
        self._max_rows = 200
        self._build()

    def _build(self):
        apply_ttk_styles(scale_fn=ui_scaling.scale)

        self.tree = ttk.Treeview(self, columns=self.COLS, show="headings",
                                  style="T.Treeview", height=6)
        for col, hdr, w in zip(self.COLS, self.HEADERS, self.WIDTHS):
            self.tree.heading(col, text=hdr, anchor="w")
            sw = ui_scaling.scale(w)
            self.tree.column(col, width=sw, minwidth=sw, anchor="w", stretch=True)

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("ok", foreground=p.GREEN)
        self.tree.tag_configure("err", foreground=p.RED)
        self.tree.tag_configure("warn", foreground=p.YELLOW)
        self.tree.tag_configure("even", background=p.BG_ROW)
        self.tree.tag_configure("odd", background=p.BG_DEEP)

    def add_trade(self, time_str: str, slave: str, symbol: str,
                  direction: str, lot: float, master_ticket: str,
                  slave_ticket: str, status: str, tag: str = "ok"):
        children = self.tree.get_children()
        row_idx = len(children)
        row_tag = "even" if row_idx % 2 == 0 else "odd"
        self.tree.insert("", 0, values=(
            time_str, slave, symbol, direction,
            f"{lot:.2f}", master_ticket, slave_ticket, status
        ), tags=(tag, row_tag))
        children = self.tree.get_children()
        while len(children) > self._max_rows:
            self.tree.delete(children[-1])
            children = self.tree.get_children()


# ── ActivationWindow ──────────────────────────────────────────

class ActivationWindow(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("FTH Trade Copier — Активация")
        self.configure(fg_color=p.BG_DEEP)
        self.resizable(False, False)
        if os.path.exists(ICON_DEFAULT):
            try:
                self.after(250, lambda: self.iconbitmap(ICON_DEFAULT))
            except Exception:
                pass
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
        w = max(self.winfo_reqwidth(), self.winfo_width())
        h = max(self.winfo_reqheight(), self.winfo_height())
        wa = ui_scaling.get_work_area_for_window(self.master or self)
        wl, wt, wr, wb = wa
        x = wl + ((wr - wl) - w) // 2
        y = wt + ((wb - wt) - h) // 2
        x, y, w, h = ui_scaling.clamp_to_work_area(x, y, w, h, wa)
        self.geometry(f"{w}x{h}+{x}+{y}")
        # Now that the window has its final width, set wraplength on the
        # status label so long messages wrap inside the visible area.
        self.update_idletasks()
        try:
            fw = self._status_frm.winfo_width()
            if fw > 20:
                self.lbl_status.config(wraplength=fw - 8)
        except Exception:
            pass

    def _set_status(self, text, fg=None):
        """Update status label (space is pre-reserved, wraplength is dynamic)."""
        self.lbl_status.config(text=text, fg=fg or p.FG_DIM)

    def _lbl(self, parent, text, **kw):
        return Label(parent, text=text, bg=p.BG_DEEP, fg=p.FG_LABEL, font=f.SM, **kw)

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
        e = Entry(parent, textvariable=var, width=width,
                  bg=p.BG_INPUT, fg=p.FG, font=f.DEFAULT,
                  highlightthickness=1, highlightbackground=p.BORDER,
                  highlightcolor=p.ACCENT)
        e.bind("<Control-v>", self._paste)
        e.bind("<Control-V>", self._paste)
        e.bind("<Control-KeyPress>", self._on_ctrl_key)
        return e

    def _build(self):
        # tk.Frame's padx/pady set internal padding; CTkFrame doesn't have that
        # so we apply the padding to the .pack() call instead.
        frm = Frame(self, bg=p.BG_DEEP)
        frm.pack(fill="both", expand=True, padx=30, pady=20)

        logo_path = os.path.join(IMG_DIR, "convertico-fth_48x48.png")
        if os.path.exists(logo_path):
            try:
                img = tk.PhotoImage(file=logo_path)
                lbl_logo = Label(frm, image=img, bg=p.BG_DEEP, text="")
                lbl_logo.image = img
                lbl_logo.grid(row=0, column=0, columnspan=2, pady=(0, 10))
            except Exception:
                pass

        Label(frm, text="Активация", bg=p.BG_DEEP, fg=p.ACCENT,
              font=f.TITLE).grid(row=1, column=0, columnspan=2, pady=(0, 15))

        self._lbl(frm, "Telegram ID").grid(row=2, column=0, sticky="w", pady=3)
        self.var_tg_id = tk.StringVar()
        self._ent(frm, self.var_tg_id, 22).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=3)

        btn_code = Button(frm, text="Получить код", command=self._request_code,
                          bg=p.ACCENT, fg=p.ACCENT_FG, font=f.BOLD,
                          activebackground=p.ACCENT_H, padx=12, pady=3)
        btn_code.grid(row=3, column=0, columnspan=2, pady=(8, 4))

        self._lbl(frm, "Код из Telegram").grid(row=4, column=0, sticky="w", pady=3)
        self.var_code = tk.StringVar()
        self._ent(frm, self.var_code, 22).grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=3)

        btn_verify = Button(frm, text="Подтвердить", command=self._verify,
                            bg=p.GREEN_DIM, fg=p.ACCENT_FG, font=f.BOLD,
                            activebackground=p.GREEN, padx=12, pady=3)
        btn_verify.grid(row=5, column=0, columnspan=2, pady=(8, 4))

        self.lbl_status = Label(frm, text="", bg=p.BG_DEEP, fg=p.FG_DIM, font=f.SM)
        self.lbl_status.grid(row=6, column=0, columnspan=2, pady=(4, 0), sticky="ew")
        # Reserve 3 lines of height so the window never resizes when status
        # text appears. Actual wraplength is set in _center_on_screen once
        # the window has its final width.
        import tkinter.font as tkfont
        _sm_h = tkfont.Font(font=f.SM).metrics("linespace")
        frm.grid_rowconfigure(6, minsize=_sm_h * 3 + 8)
        self._status_frm = frm

    def _request_code(self):
        tg = self.var_tg_id.get().strip()
        if not tg:
            self._set_status("Введите Telegram ID", fg=p.RED)
            return
        try:
            tg_id = int(tg)
        except ValueError:
            self._set_status("Telegram ID — только цифры", fg=p.RED)
            return
        if not _LIC_OK:
            self._set_status("Модуль лицензии не найден", fg=p.RED)
            return
        self._set_status("Отправка кода...", fg=p.FG_DIM)
        self.update()
        ok, msg = lic_mod.request_code(tg_id)
        if ok:
            self._set_status("Код отправлен в Telegram. Проверьте личные сообщения.", fg=p.GREEN_DIM)
        else:
            self._set_status(f"Ошибка: {msg}", fg=p.RED)

    def _verify(self):
        tg = self.var_tg_id.get().strip()
        code = self.var_code.get().strip()
        if not tg or not code:
            self._set_status("Заполните оба поля", fg=p.RED)
            return
        try:
            tg_id = int(tg)
        except ValueError:
            self._set_status("Telegram ID — только цифры", fg=p.RED)
            return
        if not _LIC_OK:
            self._set_status("Модуль лицензии не найден", fg=p.RED)
            return
        self._set_status("Проверка...", fg=p.FG_DIM)
        self.update()
        ok, result = lic_mod.verify_code(tg_id, code)
        if ok:
            self._set_status("Активация успешна!", fg=p.GREEN_DIM)
            self._activated = True  # успешная активация закрывает только окно, не прогу
            self.after(500, self.destroy)
        elif result and result.startswith("device_limit"):
            max_d = result.split(":")[-1]
            self._set_status(
                f"Лимит устройств ({max_d}) превышён.\nИспользуйте /reset в боте для сброса.",
                fg=p.RED)
        else:
            self._set_status(f"Ошибка: {result}", fg=p.RED)


# ── SettingsDialog ───────────────────────────────────────────

class SettingsDialog(Toplevel):
    def __init__(self, parent: 'App'):
        super().__init__(parent)
        self.title("Настройки")
        self.configure(fg_color=p.BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        if os.path.exists(ICON_DEFAULT):
            try:
                self.after(250, lambda: self.iconbitmap(ICON_DEFAULT))
            except Exception:
                pass
        self._app = parent
        self._active = parent._active_profile

        frm = Frame(self, bg=p.BG)
        frm.pack(fill="both", expand=True, padx=16, pady=12)

        Label(frm, text="ПРОФИЛИ", bg=p.BG, fg=p.FG_DIM, font=f.BOLD).pack(anchor="w", pady=(0, 6))

        tabs_f = Frame(frm, bg=p.BG)
        tabs_f.pack(fill="x")
        self._profile_btns = []
        self._profile_names = []
        for i in range(5):
            name = parent._profiles[i].get("name", f"Профиль {i + 1}")
            self._profile_names.append(tk.StringVar(value=name))
            btn = Button(tabs_f, text=f" {name} ", command=lambda idx=i: self._select(idx),
                         bg=p.BG_INPUT if i != self._active else p.ACCENT,
                         fg=p.ACCENT_FG if i == self._active else p.FG_DIM,
                         font=f.SM, activebackground=p.ACCENT_H, padx=6, pady=3)
            btn.pack(side="left", padx=2)
            self._profile_btns.append(btn)

        Frame(frm, bg=p.DIVIDER, height=1).pack(fill="x", pady=8)

        row_name = Frame(frm, bg=p.BG)
        row_name.pack(fill="x", pady=(0, 4))
        Label(row_name, text="Имя профиля:", bg=p.BG, fg=p.FG, font=f.DEFAULT).pack(side="left")
        self._ent_name = Entry(row_name, bg=p.BG_INPUT, fg=p.FG, font=f.DEFAULT, width=24)
        self._ent_name.pack(side="left", padx=(8, 0))
        self._ent_name.insert(0, self._profile_names[self._active].get())
        self._ent_name.bind("<KeyRelease>", self._on_name_change)

        Frame(frm, bg=p.DIVIDER, height=1).pack(fill="x", pady=8)

        # ── Theme picker ───────────────────────────────────────────
        Label(frm, text="ТЕМА", bg=p.BG, fg=p.FG_DIM, font=f.BOLD).pack(anchor="w", pady=(0, 6))

        row_theme = Frame(frm, bg=p.BG)
        row_theme.pack(fill="x", pady=(0, 4))
        Label(row_theme, text="Оформление:", bg=p.BG, fg=p.FG, font=f.DEFAULT).pack(side="left")

        self._theme_names = available_themes()
        self._initial_theme = get_theme_name()
        labels = [THEME_LABELS.get(n, n) for n in self._theme_names]
        cur_label = THEME_LABELS.get(self._initial_theme, self._initial_theme)
        self._var_theme = tk.StringVar(value=cur_label)

        om = tk.OptionMenu(row_theme, self._var_theme, *labels)
        om.config(bg=p.BG_INPUT, fg=p.FG, font=f.DEFAULT,
                  activebackground=p.BG_ROW_HOVER, activeforeground=p.FG,
                  highlightthickness=0, bd=0, relief="flat")
        om["menu"].config(bg=p.BG_INPUT, fg=p.FG, font=f.DEFAULT,
                          activebackground=p.ACCENT, activeforeground=p.ACCENT_FG,
                          bd=0)
        om.pack(side="left", padx=(8, 0))

        self._lbl_theme_hint = Label(
            frm, text="Сохраните чтобы применить тему.",
            bg=p.BG, fg=p.FG_DIM, font=f.SM,
        )
        self._lbl_theme_hint.pack(anchor="w", pady=(2, 0))

        Frame(frm, bg=p.DIVIDER, height=1).pack(fill="x", pady=8)

        btn_row = Frame(frm, bg=p.BG)
        btn_row.pack(fill="x")

        def switch_profile():
            new_name = self._ent_name.get().strip()
            if new_name:
                self._app._profiles[self._active]["name"] = new_name
            # Resolve chosen theme by label → internal name.
            chosen_label = self._var_theme.get()
            chosen_name = self._initial_theme
            for _n in self._theme_names:
                if THEME_LABELS.get(_n, _n) == chosen_label:
                    chosen_name = _n
                    break
            theme_changed = chosen_name != self._initial_theme

            # Apply theme LIVE (hot-swap), capturing old palette first so we
            # can remap every widget colour in the running UI.
            if theme_changed:
                from palette import get_palette as _gp
                old_pal = _gp()
                try:
                    set_theme(chosen_name)
                except Exception:
                    theme_changed = False
                if theme_changed:
                    try:
                        self._app._apply_runtime_theme(old_pal)
                    except Exception:
                        pass

            self._app._switch_profile(self._active)

            if theme_changed:
                # Persist new theme into config.json.
                try:
                    self._app._save_config()
                except Exception:
                    pass
            self.destroy()

        btn_switch = Button(btn_row, text="Сохранить", command=switch_profile,
                            bg=p.ACCENT, fg=p.ACCENT_FG, font=f.BOLD,
                            activebackground=p.ACCENT_H, padx=16, pady=4)
        btn_switch.pack(side="left")
        _bind_tip(btn_switch, "Сохранить и переключиться на профиль")

        def open_config_folder():
            try:
                os.makedirs(APP_DATA_DIR, exist_ok=True)
                # On Windows os.startfile on a directory opens it in Explorer
                # and selects nothing. Pass the folder path itself so users
                # land in the right directory and can spot config.json.
                os.startfile(APP_DATA_DIR)
            except Exception as e:
                messagebox.showerror(
                    "Ошибка",
                    f"Не удалось открыть папку:\n{APP_DATA_DIR}\n\n{e}",
                    parent=self,
                )

        btn_open_cfg = Button(
            btn_row, text="\U0001F4C2 Папка config", command=open_config_folder,
            bg=p.BG_INPUT, fg=p.FG_DIM, font=f.DEFAULT,
            activebackground=p.BG_ROW_HOVER, padx=10, pady=4,
        )
        btn_open_cfg.pack(side="left", padx=(8, 0))
        _bind_tip(btn_open_cfg, f"Открыть папку с config.json в проводнике\n({APP_DATA_DIR})")

        def check_updates():
            self.destroy()
            parent._check_update(force=True)

        btn_update = Button(btn_row, text="\U0001F504 Проверить обновления", command=check_updates,
                            bg=p.BG_INPUT, fg=p.FG_DIM, font=f.DEFAULT,
                            activebackground=p.BG_ROW_HOVER, padx=10, pady=4)
        btn_update.pack(side="right")
        _bind_tip(btn_update, "Проверить наличие новой версии")

        btn_close = Button(btn_row, text="Закрыть", command=self.destroy,
                           bg=p.BG_INPUT, fg=p.FG_DIM, font=f.DEFAULT,
                           activebackground=p.BG_ROW_HOVER, padx=10, pady=4)
        btn_close.pack(side="right", padx=6)

        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        # Use rootx/rooty (screen coords) instead of x/y (parent-relative) and
        # clamp into parent's monitor so the dialog never opens off-screen.
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        wa = ui_scaling.get_work_area_for_window(parent)
        x, y, w, h = ui_scaling.clamp_to_work_area(x, y, w, h, wa)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _select(self, idx):
        old_name = self._ent_name.get().strip()
        if old_name:
            self._app._profiles[self._active]["name"] = old_name
            self._profile_btns[self._active].config(text=f" {old_name} ")
        self._active = idx
        self._ent_name.delete(0, "end")
        self._ent_name.insert(0, self._app._profiles[idx].get("name", f"Профиль {idx + 1}"))
        for i, btn in enumerate(self._profile_btns):
            btn.config(bg=p.ACCENT if i == idx else p.BG_INPUT,
                       fg=p.ACCENT_FG if i == idx else p.FG_DIM)

    def _on_name_change(self, event=None):
        name = self._ent_name.get().strip()
        if name:
            self._profile_btns[self._active].config(text=f" {name} ")


# ── App ─────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Variant B (off-screen pre-map): we let Tk map the window
        # naturally, but at a position far off-screen and at the saved
        # *size*, so Windows can never show it at the CW_USEDEFAULT
        # placeholder size. Once everything is built we move it to the
        # actual saved position in _first_show. Alpha=0 is kept as
        # belt-and-braces in case any code path briefly maps before our
        # off-screen geometry is set. We deliberately do NOT call
        # self.withdraw() — that prevented the window from ever showing
        # in earlier attempts because CTk's titlebar dance in mainloop
        # ends up leaving us withdrawn (see d3beffb for details).
        try:
            self.attributes("-alpha", 0.0)
        except Exception:
            pass
        # Install CTk appearance/theme *after* super().__init__() — calling
        # ctk.set_appearance_mode("dark") before a Tk root exists raises a
        # TclError. This was rollback pitfall #2 during the previous CTk
        # attempt; keep this ordering.
        apply_theme()
        # Configure Tk to the current display DPI so Hi-DPI users get crisp
        # rendering instead of OS bitmap-scaling. DPI awareness itself is
        # enabled in __main__ before this Tk root is created.
        ui_scaling.init_root_scaling(self)
        self.title(f"FTH Trade Copier v{upd_mod.VERSION}" if _UPD_OK else "FTH Trade Copier")
        self.configure(fg_color=p.BG_DEEP)
        self.resizable(True, True)
        self.minsize(ui_scaling.scale(960), ui_scaling.scale(640))

        # Resolve the window geometry to use for the *first* mapping of the
        # window. If we have a saved geometry on disk (from a previous
        # run) we want to use it immediately — otherwise the user sees
        # the adaptive default size flash up before _apply_window_state
        # resizes the window to its remembered size.
        saved_window = self._peek_saved_window_state()
        initial_geom: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
        if saved_window and saved_window.get("geometry"):
            import re as _re
            geom = saved_window["geometry"]
            m = _re.match(r"^(\d+)x(\d+)([+\-]\d+)([+\-]\d+)$", geom)
            if m:
                try:
                    sw_ = int(m.group(1)); sh_ = int(m.group(2))
                    sx_ = int(m.group(3)); sy_ = int(m.group(4))
                    wa = ui_scaling.get_cursor_work_area(self)
                    sx_, sy_, sw_, sh_ = ui_scaling.clamp_to_work_area(
                        sx_, sy_, sw_, sh_, wa)
                    mw_ = ui_scaling.scale(960)
                    mh_ = ui_scaling.scale(640)
                    sw_ = max(sw_, mw_); sh_ = max(sh_, mh_)
                    initial_geom = (sx_, sy_, sw_, sh_)
                except Exception:
                    saved_window = None  # fall through to adaptive
            else:
                saved_window = None
        if not saved_window or not saved_window.get("geometry"):
            # Adaptive initial geometry: 78% of the work area on the monitor
            # under the cursor, clamped to a sensible range and DPI-scaled.
            # minsize is lowered so 1366x768 laptops (~728 px usable height)
            # actually fit.
            work_area = ui_scaling.get_cursor_work_area(self)
            w, h, x, y = ui_scaling.compute_initial_geometry(
                work_area, frac=0.78, min_w=960, min_h=640, max_w=1400, max_h=900
            )
            initial_geom = (x, y, w, h)

        # Remember the resolved initial geometry for _first_show — that
        # callback will move the window from off-screen to this real
        # position once everything is built.
        self._initial_geom: Optional[Tuple[int, int, int, int]] = initial_geom
        # Variant B: place the window at the saved *size* but far
        # off-screen so any first-map activity (Tk's, CTk's, Windows'
        # CW_USEDEFAULT placeholder, anything) happens out of sight.
        # We pick a coordinate well past any conceivable virtual-screen
        # bottom-right so it's invisible on multimonitor setups too.
        sx_, sy_, sw_, sh_ = initial_geom
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
        except Exception:
            screen_w, screen_h = 1920, 1080
        off_x = screen_w + 2000
        off_y = screen_h + 2000
        try:
            self.geometry(f"{sw_}x{sh_}+{off_x}+{off_y}")
        except Exception:
            # Fall back to in-place geometry if the off-screen string is
            # rejected — alpha=0 will still mask any flash.
            self.geometry(f"{sw_}x{sh_}+{sx_}+{sy_}")

        # Zoomed state has to be applied AFTER initial geometry so Tk
        # remembers the un-zoomed size for the user's next restore.
        if saved_window and saved_window.get("zoomed"):
            try:
                self.state("zoomed")
            except Exception:
                pass
        if os.path.exists(ICON_DEFAULT):
            # ctk.CTk schedules its own icon setup on a 200 ms after-callback,
            # which overrides any iconbitmap we call here. Defer ours so it
            # wins. (See CTk issue #1709 — the same workaround appears in
            # multiple downstream apps.)
            try:
                self.after(250, lambda: self.iconbitmap(ICON_DEFAULT))
                self.after(250, lambda: self.wm_iconbitmap(ICON_DEFAULT))
            except Exception:
                pass

        self._slaves: List[Dict] = []
        self._rows: List[AccountRow] = []
        self._trader = None
        self._check_timer = None
        self._session_stats = {"copied": 0, "failed": 0}
        self._min_lot_mode = False
        self._tray_icon = None
        self._active_profile = 0
        self._profiles: List[Dict] = []
        self._window_state: Dict = {}

        self._build_ui()
        self._load_config()
        # _load_config populated self._window_state from config.json (if any).
        # Apply it after _build_ui so the PanedWindow exists for sash restore.
        self._apply_window_state()
        self._bind_paste()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Flush pending layout so the first paint happens at the final size.
        self.update_idletasks()
        # CTk.mainloop() runs an internal _windows_set_titlebar_color dance
        # that calls super().withdraw() and then tries to restore the
        # previous state via self._state_before_windows_set_titlebar_color.
        # Because that attribute is only populated when _window_exists is
        # True, the restore falls through to self.state(None) (no-op) on
        # first start and leaves the window withdrawn. Prime it so CTk's
        # restore branch deiconifies us automatically.
        self._state_before_windows_set_titlebar_color = "normal"
        # Reveal the window on the first idle of the event loop, after
        # CTk's titlebar dance has finished. See _first_show for the
        # full Win32 ShowWindow + alpha=1 sequence.
        self.after(0, self._first_show)
        # Defer all blocking start-up tasks (MT5 polling, license check,
        # update check, tray init) until *after* mainloop has started.
        # Running these synchronously inside __init__ would block the Tk
        # event loop before the window was even mapped — that was rollback
        # pitfall #1 during the previous CTk attempt (sync MT5/license in
        # __init__ blocks mainloop and prevents the window from appearing).
        self.after(100, self._start_tray)
        self.after(300, self._schedule_license_check)
        self.after(500, self._schedule_check)
        self.after(800, self._check_update)

    def _first_show(self) -> None:
        """Idle-queue callback that teleports the off-screen window to
        its real saved position and fades it in.

        Variant B: ``__init__`` mapped the window at the saved size but
        far past the bottom-right corner of every monitor, so the user
        never saw the initial frame. Now that the event loop is running
        and layout has settled we move it to the actual saved position
        and set alpha back to 1.0.
        """
        # Re-prime the CTk titlebar-restore attribute in case the
        # appearance mode is changed later (mode change re-runs the
        # titlebar dance, which saves/restores around it).
        try:
            self._state_before_windows_set_titlebar_color = "normal"
        except Exception:
            pass
        geom = getattr(self, "_initial_geom", None)
        if geom is not None:
            x, y, w, h = geom
            try:
                self.geometry(f"{w}x{h}+{x}+{y}")
            except Exception:
                pass
        # If anything left us in withdrawn state, deiconify so the
        # widget tree gets shown.
        try:
            if str(self.state()) == "withdrawn":
                self.deiconify()
        except Exception:
            try:
                self.deiconify()
            except Exception:
                pass
        # Restore visibility of the layered-window contents.
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass

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
        name = "convertico-fth-cyan_48x48" if cyan else "convertico-fth_48x48"
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
        if accent:
            bg, fg, abg = p.ACCENT, p.ACCENT_FG, p.ACCENT_H
        elif danger:
            bg, fg, abg = p.RED_DIM, p.ACCENT_FG, p.RED
        else:
            bg, fg, abg = p.BG_INPUT, p.FG_LABEL, p.BG_ROW_HOVER
        return Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                      font=f.BOLD if accent else f.DEFAULT,
                      activebackground=abg, padx=10, pady=3)

    def _build_ui(self):
        # ── Header bar ───────────────────────────────────────
        hdr = Frame(self, bg=p.BG_HEADER)
        hdr.pack(fill="x", padx=0, pady=0)

        hdr_left = Frame(hdr, bg=p.BG_HEADER)
        hdr_left.pack(side="left", padx=14, pady=(10, 8))

        logo_path = os.path.join(IMG_DIR, "convertico-fth_48x48.png")
        if os.path.exists(logo_path):
            try:
                self._logo_img = tk.PhotoImage(file=logo_path)
                self._logo_label = Label(hdr_left, image=self._logo_img, bg=p.BG_HEADER, text="")
                self._logo_label.pack(side="left", padx=(0, 8))
            except Exception:
                pass
        Label(hdr_left, text="Trade Copier", bg=p.BG_HEADER, fg=p.FG,
              font=f.TITLE).pack(side="left")
        Label(hdr_left, text="  MT5", bg=p.BG_HEADER, fg=p.ACCENT,
              font=("Segoe UI", 12)).pack(side="left", anchor="s")

        hdr_right = Frame(hdr, bg=p.BG_HEADER)
        hdr_right.pack(side="right", padx=14, pady=(10, 8))

        self.btn_info = Button(hdr_right, text="i", command=self._toggle_info,
                               bg=p.BG_INPUT, fg=p.FG_DIM,
                               font=("Segoe UI", 10, "bold"),
                               activebackground=p.BG_ROW_HOVER, padx=8, pady=1,
                               width=2)
        self.btn_info.pack(side="right", padx=(8, 0))
        _bind_tip(self.btn_info, "Режим подсказок")

        btn_settings = Button(hdr_right, text="\u2699", command=self._open_settings,
                              bg=p.BG_INPUT, fg=p.FG_DIM,
                              font=("Segoe UI", 10, "bold"),
                              activebackground=p.BG_ROW_HOVER, padx=8, pady=1,
                              width=2)
        btn_settings.pack(side="right", padx=(4, 0))
        _bind_tip(btn_settings, "Настройки приложения")

        block_term = Frame(hdr_right, bg=p.BG_HEADER)
        block_term.pack(side="right", padx=(12, 0))
        Label(block_term, text="ТЕРМИНАЛЫ", bg=p.BG_HEADER, fg=p.FG_DIM,
              font=f.XS).pack(side="left", padx=(0, 4))
        btn_launch = self._make_btn(block_term, "\u25B6 Запустить", self._launch_all, accent=True)
        btn_launch.pack(side="left", padx=2)
        _bind_tip(btn_launch, "Запустить все терминалы (свёрнутые)")
        btn_shutdown = self._make_btn(block_term, "\u25A0 Закрыть", self._shutdown_all, danger=True)
        btn_shutdown.pack(side="left", padx=2)
        _bind_tip(btn_shutdown, "Завершить процессы всех терминалов")

        block_ct = Frame(hdr_right, bg=p.BG_HEADER)
        block_ct.pack(side="right", padx=(12, 0))
        Label(block_ct, text="КОПИТРЕЙДЕР", bg=p.BG_HEADER, fg=p.FG_DIM,
              font=f.XS).pack(side="left", padx=(0, 4))
        self.btn_start = self._make_btn(block_ct, "\u25B6  Старт", self._start, accent=True)
        self.btn_start.pack(side="left", padx=2)
        _bind_tip(self.btn_start, "Запустить копирование сделок")
        self.btn_stop = self._make_btn(block_ct, "\u25A0  Стоп", self._stop, danger=True)
        self.btn_stop.pack(side="left", padx=2)
        _bind_tip(self.btn_stop, "Остановить копирование")
        self.btn_stop.configure(state="disabled")

        # ── Мастер ──────────────────────────────────────────
        Frame(self, bg=p.DIVIDER, height=1).pack(fill="x", padx=14, pady=(6, 0))

        master_outer = Frame(self, bg=p.BG_ROW, highlightbackground=p.BORDER,
                             highlightthickness=1)
        master_outer.pack(fill="x", padx=14, pady=1)

        master_strip = Frame(master_outer, bg=p.ACCENT, width=3)
        master_strip.place(x=0, y=0, relheight=1.0)

        master_f = Frame(master_outer, bg=p.BG_ROW)
        master_f.pack(fill="x", padx=(6, 8), pady=6)

        Label(master_f, text="МАСТЕР", bg=p.BG_ROW, fg=p.ACCENT, font=f.BOLD).grid(row=0, column=0, padx=(4, 8))

        self.var_master_path = tk.StringVar()
        # Path is set via the "..." browse button; keeping the entry
        # read-only avoids accidental edits to a value that needs to
        # point at a real terminal64.exe on disk.
        Entry(master_f, textvariable=self.var_master_path, width=36,
              bg=p.BG_INPUT, fg=p.FG, font=f.SM, highlightthickness=1,
              highlightbackground=p.BORDER, highlightcolor=p.ACCENT,
              state="readonly").grid(row=0, column=1, padx=4, sticky="ew")
        btn_browse_m = self._make_btn(master_f, "...", self._browse_master)
        btn_browse_m.grid(row=0, column=2, padx=2)
        _bind_tip(btn_browse_m, "Выбрать путь к terminal64.exe мастера")

        btn_open_m = Button(master_f, text="\U0001F4C8", command=self._open_master_terminal,
                            bg=p.BG_ROW, fg=p.ACCENT, font=f.SM,
                            activebackground=p.BG_ROW_HOVER, width=2)
        btn_open_m.grid(row=0, column=3, padx=(8, 4))
        _bind_tip(btn_open_m, "Открыть терминал мастера")

        btn_close_master = Button(master_f, text="\u2716", command=self._close_all_master,
                                  bg=p.BG_ROW, fg=p.RED_DIM, font=f.SM,
                                  activebackground=p.BG_ROW_HOVER, width=2)
        btn_close_master.grid(row=0, column=4, padx=2)
        _bind_tip(btn_close_master, "Закрыть все позиции мастера")

        btn_test_master = Button(master_f, text="\u26A0", command=self._test_master,
                                 bg=p.BG_ROW, fg=p.YELLOW, font=f.SM,
                                 activebackground=p.BG_ROW_HOVER, width=2)
        btn_test_master.grid(row=0, column=5, padx=2)
        _bind_tip(btn_test_master, "Тест: BUY 0.01 лот на мастере")

        self.lbl_master_login = Label(master_f, text="", bg=p.BG_ROW, fg=p.FG_DIM,
                                      font=f.MONO_SM, anchor="w")
        self.lbl_master_login.grid(row=0, column=6, padx=6, sticky="ew")

        self.lbl_master_bal = Label(master_f, text="", bg=p.BG_ROW, fg=p.FG,
                                    font=f.VAL_BOLD, anchor="e")
        self.lbl_master_bal.grid(row=0, column=7, padx=4, sticky="ew")

        self.lbl_master_eq = Label(master_f, text="", bg=p.BG_ROW, fg=p.FG_DIM,
                                   font=f.MONO_SM, anchor="e")
        self.lbl_master_eq.grid(row=0, column=8, padx=4, sticky="ew")

        self.lbl_master_pnl = Label(master_f, text="", bg=p.BG_ROW, fg=p.FG_DIM,
                                    font=f.VAL, anchor="e")
        self.lbl_master_pnl.grid(row=0, column=9, padx=4, sticky="ew")

        master_f.columnconfigure(1, weight=1)

        # ── Dashboard KPI ───────────────────────────────────
        dash = Frame(self, bg=p.BG_DEEP)
        dash.pack(fill="x", padx=14, pady=6)

        cards_data = [
            ("kpi_bal", "Master Balance", "\u2014", p.FG),
            ("kpi_eq", "Total Equity", "\u2014", p.FG),
            ("kpi_pnl", "Net P&L", "\u2014", p.FG_DIM),
            ("kpi_conn", "Connected", "\u2014", p.FG_DIM),
        ]
        self._kpi_labels: Dict[str, Label] = {}
        for i, (key, title, default, color) in enumerate(cards_data):
            # tk.Frame's internal padx/pady on a card translates to .pack()
            # padding here; CTkFrame doesn't have a per-widget padx/pady.
            card_outer = Frame(dash, bg=p.BG_DEEP)
            card_outer.pack(side="left", fill="x", expand=True, padx=(0 if i == 0 else 6, 0))
            card = Frame(card_outer, bg=p.BG_ROW, highlightbackground=p.BORDER,
                         highlightthickness=1)
            card.pack(fill="both", expand=True)
            Label(card, text=title, bg=p.BG_ROW, fg=p.FG_DIM, font=f.SM).pack(anchor="w", padx=14, pady=(8, 0))
            lbl = Label(card, text=default, bg=p.BG_ROW, fg=color, font=f.VAL_BOLD)
            lbl.pack(anchor="w", padx=14, pady=(0, 8))
            self._kpi_labels[key] = lbl

        self._refresh_dashboard()

        # ── Таблица аккаунтов ────────────────────────────────
        tbl_header = Frame(self, bg=p.BG_DEEP)
        tbl_header.pack(fill="x", padx=14, pady=(4, 0))
        Label(tbl_header, text="SLAVE ACCOUNTS", bg=p.BG_DEEP, fg=p.FG_DIM,
              font=f.BOLD).pack(side="left")
        self.lbl_slave_count = Label(tbl_header, text="0/10", bg=p.BG_DEEP, fg=p.FG_DIM,
                                     font=f.BOLD)
        self.lbl_slave_count.pack(side="left", padx=(8, 0))

        self._paned = tk.PanedWindow(self, orient="vertical", bg=p.BG_DEEP,
                                     sashwidth=4, sashrelief="flat",
                                     opaqueresize=True)
        self._paned.pack(fill="both", expand=True, padx=14, pady=2)

        self._table_frame = tk.Frame(self._paned, bg=p.BG_DEEP)
        self._paned.add(self._table_frame, minsize=ui_scaling.scale(80),
                        height=ui_scaling.scale(200))

        for idx, _, min_w, weight, _ in COL_SPEC:
            self._table_frame.columnconfigure(idx, minsize=ui_scaling.scale(min_w), weight=weight)

        for idx, text, _, _, anchor in COL_SPEC:
            # Headers are CTk Labels but the parent stays tk.Frame because
            # tk.PanedWindow can't manage a CTkFrame child (the CTk widget
            # doesn't expose the .panedwindow_* options PanedWindow needs).
            lbl_h = Label(self._table_frame, text=text, bg=p.BG_DEEP, fg=p.FG_DIM,
                          font=f.XS, anchor=anchor)
            lbl_h.grid(row=0, column=idx, padx=2, pady=(2, 0), sticky="ew")

        self.tbl_btns = Frame(self._table_frame, bg=p.BG_DEEP)
        self.tbl_btns.grid(row=0, column=11, sticky="ew", padx=2, pady=(2, 0))

        btn_add = self._make_btn(self.tbl_btns, "+ Аккаунт", self._add_slave,
                       accent=True)
        btn_add.pack(side="left")
        _bind_tip(btn_add, "Добавить новый слейв-аккаунт")
        btn_close_all = self._make_btn(self.tbl_btns, "\u2716 Закрыть сделки", self._close_all_open,
                       danger=True)
        btn_close_all.pack(side="right", padx=6)
        _bind_tip(btn_close_all, "Закрыть все позиции на мастере и слейвах")

        self._next_row = 1

        # ── Notebook ────────────────────────────────────────
        # ttk styles are configured centrally via apply_ttk_styles()
        # (called in TradesTable._build which runs before this point).

        nb_frame = tk.Frame(self._paned, bg=p.BG_DEEP)
        self._paned.add(nb_frame, minsize=ui_scaling.scale(60),
                        height=ui_scaling.scale(180))

        self.notebook = ttk.Notebook(nb_frame, style="TNotebook")
        self.notebook.pack(fill="both", expand=True)

        trades_tab = tk.Frame(self.notebook, bg=p.BG)
        self.notebook.add(trades_tab, text="  Сделки  ")
        self.trades_table = TradesTable(trades_tab)
        self.trades_table.pack(fill="both", expand=True, padx=1, pady=1)

        for t in _load_trades():
            tag = "ok" if t.get("success") else "err"
            self.trades_table.add_trade(
                time_str=t.get("time", ""), slave=t.get("slave", ""),
                symbol=t.get("symbol", ""), direction=t.get("direction", ""),
                lot=t.get("lot", 0.0), master_ticket=t.get("master_ticket", ""),
                slave_ticket=t.get("slave_ticket", ""), status=t.get("status", ""),
                tag=tag)

        log_tab = tk.Frame(self.notebook, bg=p.BG)
        self.notebook.add(log_tab, text="  Лог  ")
        log_inner = tk.Frame(log_tab, bg=p.BG)
        log_inner.pack(fill="both", expand=True, padx=1, pady=1)

        self.log_text = tk.Text(log_inner, bg=p.BG_ROW, fg=p.FG, font=f.MONO_SM,
                                relief="flat", state="disabled", wrap="word",
                                highlightthickness=0)
        log_sb = ttk.Scrollbar(log_inner, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.log_text.tag_config("ok", foreground=p.GREEN)
        self.log_text.tag_config("err", foreground=p.RED)
        self.log_text.tag_config("warn", foreground=p.YELLOW)
        self.log_text.tag_config("info", foreground=p.FG_DIM)

        # Статистика
        stats_f = Frame(self, bg=p.BG_DEEP)
        stats_f.pack(fill="x", padx=14, pady=(0, 2))
        self.lbl_stats = Label(stats_f, text="", bg=p.BG_DEEP, fg=p.FG_DIM, font=f.SM)
        self.lbl_stats.pack(side="left")
        if _UPD_OK:
            # Version uses the theme ACCENT color (cyan on Neon, blue on
            # Light Pro) so the build tag has a bit of brand identity.
            Label(stats_f, text=f"v{upd_mod.VERSION}", bg=p.BG_DEEP, fg=p.ACCENT,
                  font=f.SM).pack(side="right")

    # ── Info toggle ─────────────────────────────────────────

    def _toggle_info(self):
        _Tip.enabled = not _Tip.enabled
        if _Tip.enabled:
            # When info-mode is ON, the button stays solid-accent on hover
            # so the active state remains obvious (no fade-to-row-hover).
            self.btn_info.configure(bg=p.ACCENT, fg=p.ACCENT_FG,
                                    activebackground=p.ACCENT)
        else:
            self.btn_info.configure(bg=p.BG_INPUT, fg=p.FG_DIM,
                                    activebackground=p.BG_ROW_HOVER)
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
            pth = s.get("path", "")
            if pth and pth not in paths:
                paths.append(pth)
        launched = 0
        for pth in paths:
            if not is_terminal_running(pth):
                try:
                    si = subprocess.STARTUPINFO()
                    si.dwFlags = subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 6  # SW_MINIMIZE
                    subprocess.Popen([pth], startupinfo=si)
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
            pth = s.get("path", "")
            if pth and pth not in paths:
                paths.append(pth)
        killed = 0
        for pth in paths:
            norm = os.path.normcase(os.path.abspath(pth))
            for proc in psutil.process_iter(['exe', 'pid']):
                try:
                    exe = proc.info.get('exe')
                    if exe and os.path.normcase(exe) == norm:
                        proc.terminate()
                        killed += 1
                        self._log(f"\u25A0 Завершён: {os.path.basename(os.path.dirname(pth))}")
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
            self.lbl_master_bal.config(text="\u2014", fg=p.FG_DIM)
            self.lbl_master_login.config(text="нет пути", fg=p.RED)
            return
        if not is_terminal_running(master_path):
            self.lbl_master_login.config(text="не запущен", fg=p.RED)
            return
        if mt5.initialize(path=master_path):
            try:
                acc = mt5.account_info()
                if acc:
                    ti = mt5.terminal_info()
                    pnl = acc.equity - acc.balance
                    pnl_color = p.GREEN if pnl >= 0 else p.RED
                    pnl_sign = "+" if pnl >= 0 else ""
                    at_off = ti and not ti.trade_allowed
                    self.lbl_master_login.config(
                        text=f"#{acc.login}" + (" \u26A0AT" if at_off else ""),
                        fg=p.RED if at_off else p.FG_DIM)
                    self.lbl_master_bal.config(text=f"${acc.balance:,.2f}")
                    self.lbl_master_eq.config(text=f"${acc.equity:,.2f}")
                    self.lbl_master_pnl.config(text=f"{pnl_sign}${pnl:,.2f}", fg=pnl_color)
                else:
                    self.lbl_master_login.config(text="нет аккаунта", fg=p.RED)
            finally:
                mt5.shutdown()
        else:
            self.lbl_master_login.config(text="ошибка", fg=p.RED)

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
        pnl_color = p.GREEN if net_pnl >= 0 else p.RED
        pnl_sign = "+" if net_pnl >= 0 else ""
        self._kpi_labels["kpi_pnl"].config(text=f"{pnl_sign}${net_pnl:,.2f}" if net_pnl != 0 else "\u2014",
                                            fg=pnl_color if net_pnl != 0 else p.FG_DIM)

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
        self._session_stats = {"copied": 0, "failed": 0}
        self._log("\u2705 Копитрейдер запущен", "ok")

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
        self._log("\u25A0 Копитрейдер остановлен", "warn")
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
                self.lbl_master_login.config(text=f"#{login}", fg=p.FG_DIM)
            if balance > 0:
                self.lbl_master_bal.config(text=f"${balance:,.2f}")
            if equity > 0:
                self.lbl_master_eq.config(text=f"${equity:,.2f}")
                pnl = equity - balance
                pnl_color = p.GREEN if pnl >= 0 else p.RED
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
            with open(log_file, "a", encoding="utf-8") as fh:
                fh.write(msg + "\n")
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
        self._capture_window_state()
        return {
            "active_profile": self._active_profile,
            "profiles": self._profiles,
            "poll_interval_seconds": 1,
            "min_lot_mode": self._min_lot_mode,
            "theme": get_theme_name(),
            "window": self._window_state,
        }

    # ── Window state persistence ────────────────────────────────
    @staticmethod
    def _peek_saved_window_state() -> Optional[Dict]:
        """Read just the ``window`` key from config.json without parsing
        the rest. Used during __init__ to set the right geometry on the
        FIRST mapping of the window, avoiding the visual flash of the
        adaptive-default size resizing to the saved size after build.
        Returns ``None`` if no config exists or the key is missing."""
        try:
            if not os.path.exists(CONFIG_FILE):
                return None
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
            win = cfg.get("window")
            return win if isinstance(win, dict) else None
        except Exception:
            return None

    def _capture_window_state(self) -> None:
        """Snapshot current main-window geometry/zoom/sash into self._window_state."""
        try:
            geom = self.geometry()
            try:
                st = self.state()
            except Exception:
                st = "normal"
            sash_y = None
            try:
                paned = getattr(self, "_paned", None)
                if paned is not None:
                    coord = paned.sash_coord(0)
                    if coord:
                        sash_y = int(coord[1])
            except Exception:
                sash_y = None
            # If currently zoomed, geometry() reports the maximised size — keep the
            # last known "normal" geometry so we restore to a sensible window when
            # the user un-maximises later.
            if st == "zoomed":
                prev = (self._window_state or {}).get("geometry")
                if prev:
                    geom = prev
            self._window_state = {
                "geometry": geom,
                "zoomed": st == "zoomed",
                "sash_y": sash_y,
            }
        except Exception:
            # Don't let UI state capture ever break config save.
            pass

    def _apply_window_state(self) -> None:
        """Apply self._window_state (geometry/zoom/sash) restored from config."""
        st = getattr(self, "_window_state", None) or {}
        import re
        geom = st.get("geometry")
        if isinstance(geom, str):
            m = re.match(r"^(\d+)x(\d+)([+\-]\d+)([+\-]\d+)$", geom)
            if m:
                try:
                    w = int(m.group(1)); h = int(m.group(2))
                    x = int(m.group(3)); y = int(m.group(4))
                    wa = ui_scaling.get_cursor_work_area(self)
                    x, y, w, h = ui_scaling.clamp_to_work_area(x, y, w, h, wa)
                    mw = ui_scaling.scale(960)
                    mh = ui_scaling.scale(640)
                    w = max(w, mw); h = max(h, mh)
                    self.geometry(f"{w}x{h}+{x}+{y}")
                except Exception:
                    pass
        if st.get("zoomed"):
            try:
                self.state("zoomed")
            except Exception:
                pass
        sash_y = st.get("sash_y")
        if isinstance(sash_y, int) and sash_y > 0:
            paned = getattr(self, "_paned", None)
            if paned is not None:
                # Defer to after layout finishes, otherwise sash_place is ignored.
                self.after(80, lambda y=sash_y: self._safe_set_sash(y))

    def _safe_set_sash(self, y: int) -> None:
        try:
            self._paned.sash_place(0, 0, int(y))
        except Exception:
            pass

    def _save_config(self):
        try:
            os.makedirs(APP_DATA_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
                json.dump(self._build_full_config(), fh, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"\u26A0\uFE0F Ошибка конфига: {e}", "warn")

    # ── Hot theme switch ────────────────────────────────────────
    def _apply_runtime_theme(self, old_palette) -> int:
        """Hot-swap theme by REBUILDING the UI in-place.

        The earlier widget-tree-remap path had blind spots — some CTk
        widgets (notably the header bar and CTk Buttons in the toolbars)
        don't reliably repaint when their ``fg_color`` is changed via
        ``configure()`` from outside CTk's own initialization path.

        Rebuild is bullet-proof: every widget is re-constructed using
        the ``p`` / ``f`` proxies, which read from the *active* theme,
        so the new palette and fonts are applied uniformly.

        Volatile state (master-path entry, log text, paned sash
        positions, active notebook tab, trader-running state) is
        captured before destroying widgets and restored after rebuild.
        Persistent state (profiles, slaves, trades, window geometry)
        lives in ``config.json`` / ``trades.json`` and is reloaded by
        the standard ``_load_config()`` / trades-restore paths called
        from ``_build_ui``.
        """
        from palette import get_palette as _gp

        # 1. Snapshot volatile widget-bound state.
        saved_master_path = ""
        try:
            saved_master_path = self.var_master_path.get()
        except Exception:
            pass

        saved_log = ""
        if hasattr(self, "log_text"):
            try:
                saved_log = self.log_text.get("1.0", "end-1c")
            except Exception:
                pass

        saved_sash: list = []
        if hasattr(self, "_paned"):
            try:
                # PanedWindow exposes sash coordinates per gap.
                for i in range(max(0, len(self._paned.panes()) - 1)):
                    try:
                        saved_sash.append(self._paned.sash_coord(i)[1])
                    except Exception:
                        pass
            except Exception:
                pass

        saved_active_tab = 0
        if hasattr(self, "notebook"):
            try:
                saved_active_tab = self.notebook.index(self.notebook.select())
            except Exception:
                pass

        # 2. Persist current config so the rebuild re-creates the same
        #    profile/slaves layout out of disk.
        try:
            self._save_config()
        except Exception:
            pass

        # 3. Re-apply CTk appearance for the NEW theme (light/dark mode).
        try:
            apply_theme()
        except Exception:
            pass

        # 4. Tear down every child widget of the root.
        self._rows = []
        self._next_row = 1
        for child in list(self.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        # 5. Bring the CTk root background up to date (the root canvas
        #    isn't re-created, so explicitly set its fg_color).
        try:
            new_pal = _gp()
            self.configure(fg_color=new_pal.BG_DEEP)
        except Exception:
            pass

        # 6. Re-apply ttk styles (Treeview / Notebook) for the new theme
        #    BEFORE _build_ui so TradesTable picks up the right palette.
        try:
            apply_ttk_styles(scale_fn=ui_scaling.scale)
        except Exception:
            pass

        # 7. Rebuild the whole UI from scratch.
        try:
            self._build_ui()
        except Exception:
            pass

        # 8. Restore state.
        try:
            self.var_master_path.set(saved_master_path)
        except Exception:
            pass
        try:
            self._load_config()
        except Exception:
            pass

        # 9. Restore log buffer.
        if saved_log and hasattr(self, "log_text"):
            try:
                self.log_text.configure(state="normal")
                self.log_text.insert("1.0", saved_log)
                self.log_text.configure(state="disabled")
                self.log_text.see("end")
            except Exception:
                pass

        # 10. Restore paned sash positions (after geometry settles).
        if hasattr(self, "_paned") and saved_sash:
            try:
                self.update_idletasks()
                for i, y in enumerate(saved_sash):
                    try:
                        self._paned.sash_place(i, 0, y)
                    except Exception:
                        pass
            except Exception:
                pass

        # 11. Restore active notebook tab.
        if hasattr(self, "notebook"):
            try:
                self.notebook.select(saved_active_tab)
            except Exception:
                pass

        # 12. Re-derive trader running state on Start/Stop buttons.
        if getattr(self, "_trader", None) is not None and getattr(self._trader, "is_running", lambda: False)():
            try:
                self.btn_start.configure(state="disabled")
                self.btn_stop.configure(state="normal")
            except Exception:
                pass

        return 1

    @staticmethod
    def _iter_widgets(root):
        """Generator: every descendant widget of *root* (root excluded).
        Kept as a small util for callers that want a flat walk."""
        stack = list(getattr(root, "winfo_children", lambda: [])())
        while stack:
            w = stack.pop()
            yield w
            try:
                stack.extend(w.winfo_children())
            except Exception:
                pass

    def _load_config(self):
        self._profiles = []
        for i in range(5):
            self._profiles.append({"name": f"Профиль {i + 1}", "master": {"path": ""}, "slaves": []})
        self._active_profile = 0

        if not os.path.exists(CONFIG_FILE):
            self._update_slave_count()
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
        except Exception:
            self._update_slave_count()
            return

        if "profiles" in cfg:
            for i, prof in enumerate(cfg["profiles"]):
                if i < 5:
                    self._profiles[i] = prof
            self._active_profile = cfg.get("active_profile", 0)
        else:
            self._profiles[0] = {
                "name": "Профиль 1",
                "master": cfg.get("master", {"path": ""}),
                "slaves": cfg.get("slaves", []),
            }

        self._min_lot_mode = cfg.get("min_lot_mode", False)
        win = cfg.get("window")
        if isinstance(win, dict):
            self._window_state = win
        self._load_active_profile()
        self._update_slave_count()

    def _load_active_profile(self):
        prof = self._profiles[self._active_profile]
        self.var_master_path.set(prof.get("master", {}).get("path", ""))
        self._slaves.clear()
        for r in self._rows:
            r.destroy()
        self._rows.clear()
        self._next_row = 1
        for s in prof.get("slaves", []):
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
    # Must run BEFORE any Tk window is created so Windows doesn't bitmap-scale us.
    ui_scaling.enable_dpi_awareness()
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    already_exists = ctypes.windll.kernel32.GetLastError() == 183
    if already_exists:
        _activate_existing()
        sys.exit(0)
    app = App()
    app.mainloop()
