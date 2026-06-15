"""
FTH Trade Copier — пилот нового GUI на CustomTkinter.

Цель: показать как может выглядеть редизайн (сглаженные углы, более
современная типографика и отступы, плавные hover-состояния), сохраняя
фирменную neon-cyan палитру и общую структуру экрана.

Это автономный preview: запускается отдельно, использует dummy-данные,
не трогает реальный CopyTrader / MT5 / лицензию.

Запуск:
    python gui_ctk_pilot.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import customtkinter as ctk
from tkinter import font as tkfont


def _pick_font(preferences: list[str], fallback: str = "TkDefaultFont") -> str:
    """Возвращает первый доступный шрифт из списка. На Linux Segoe UI нет —
    пилот сам подберёт читаемый кириллический аналог, чтобы preview-скриншот
    не ломался."""
    try:
        available = set(tkfont.families())
    except Exception:
        return preferences[0] if preferences else fallback
    for name in preferences:
        if name in available:
            return name
    return fallback

# ── Палитра (сохраняем фирменный neon-cyan из gui.py) ──────────────
BG_DEEP        = "#080810"
BG             = "#0C0C14"
BG_CARD        = "#11111C"
BG_CARD_HOVER  = "#181826"
BG_INPUT       = "#191924"
BG_HEADER      = "#0E0E18"
FG             = "#E4E4EE"
FG_DIM         = "#7E7E96"
FG_LABEL       = "#9090A8"
FG_MUTED       = "#3A3A50"
ACCENT         = "#00B4D8"
ACCENT_H       = "#00D0F0"
ACCENT_DIM     = "#006E88"
GREEN          = "#00E676"
GREEN_DIM      = "#00B85E"
RED            = "#FF3D57"
RED_DIM        = "#CC3044"
YELLOW         = "#FFB020"
BORDER         = "#1F1F30"
BORDER_LIGHT   = "#2A2A40"

# ── CTk глобально ──────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── Шрифты ─────────────────────────────────────────────────────────
# На Windows используется Segoe UI (родной), на других ОС подберётся
# доступный sans-serif с поддержкой кириллицы.
import tkinter as _tk  # noqa: E402
_bootstrap = _tk.Tk()
_bootstrap.withdraw()
try:
    _SANS_REG  = _pick_font(["Segoe UI", "Inter", "Roboto", "DejaVu Sans", "Lato", "Noto Sans", "Arial"])
    _SANS_BOLD = _pick_font(["Segoe UI Semibold", "Inter Semi Bold", "Roboto Medium",
                              "DejaVu Sans", "Lato Medium", "Noto Sans", "Arial"])
    _SANS_BLACK = _pick_font(["Segoe UI Black", "Inter Black", "Roboto Black",
                               "DejaVu Sans", "Lato Black", "Arial Black"])
    _MONO       = _pick_font(["Cascadia Mono", "JetBrains Mono", "Consolas",
                               "Fira Code", "DejaVu Sans Mono", "Courier"])
finally:
    _bootstrap.destroy()

F_TITLE       = (_SANS_BOLD,  18)
F_SUBTITLE    = (_SANS_REG,   11)
F_KPI_LABEL   = (_SANS_REG,   10)
F_KPI_VALUE   = (_SANS_BOLD,  20)
F_SECTION     = (_SANS_BOLD,  11)
F_BODY        = (_SANS_REG,   11)
F_BODY_BOLD   = (_SANS_BOLD,  11)
F_MONO        = (_MONO,       10)
F_MONO_SM     = (_MONO,        9)
F_SMALL       = (_SANS_REG,    9)
F_HEADER_COL  = (_SANS_BOLD,   9)
F_LOGO        = (_SANS_BLACK, 18)


# ── Dummy-модель slave-аккаунта ────────────────────────────────────
@dataclass
class SlaveAccount:
    enabled: bool
    name: str
    login: str
    balance: float
    equity: float
    pnl: float
    symbols: str
    risk: float
    deals_today: int
    loss_today: float
    connected: bool = True


SAMPLE_SLAVES: List[SlaveAccount] = [
    SlaveAccount(True,  "FTMO 200K",     "1023144",  205_412.50, 206_120.30,  +707.80, "EURUSD, XAUUSD, US30",        1.00, 4, -120.00, True),
    SlaveAccount(True,  "MFF Phase 2",   "9011553",   99_840.00,  99_620.10,  -219.90, "GBPUSD, NAS100",              0.75, 2,  -45.00, True),
    SlaveAccount(True,  "5%ers HRP",     "5004411",   24_950.00,  25_180.50,  +230.50, "EURUSD, US30, XAUUSD",        0.50, 6,   0.00,  True),
    SlaveAccount(False, "TopStep $50K",  "TS-50442",  50_000.00,  50_000.00,   0.00,   "—",                           0.00, 0,   0.00,  False),
    SlaveAccount(True,  "Personal Live", "843009",    12_310.55,  12_307.10,   -3.45,  "EURUSD, GBPUSD, USDJPY",      0.25, 1, -10.00,  True),
]


# ─────────────────────────────────────────────────────────────────
#                       МЕЛКИЕ КОМПОНЕНТЫ
# ─────────────────────────────────────────────────────────────────

class PillButton(ctk.CTkButton):
    """Скруглённая кнопка с тремя вариантами: primary / danger / ghost."""

    def __init__(self, master, text, command=None, variant="ghost", icon=None, **kw):
        if variant == "primary":
            fg, hover, txt = ACCENT, ACCENT_H, "#FFFFFF"
        elif variant == "danger":
            fg, hover, txt = RED_DIM, RED, "#FFFFFF"
        else:  # ghost
            fg, hover, txt = BG_INPUT, BG_CARD_HOVER, FG_LABEL
        label = f"{icon}  {text}" if icon else text
        super().__init__(
            master,
            text=label,
            command=command,
            fg_color=fg,
            hover_color=hover,
            text_color=txt,
            corner_radius=10,
            height=32,
            font=F_BODY_BOLD if variant == "primary" else F_BODY,
            **kw,
        )


class IconButton(ctk.CTkButton):
    """Маленькая квадратная кнопка-иконка (settings / info / etc)."""

    def __init__(self, master, glyph, command=None, color=FG_DIM, **kw):
        super().__init__(
            master,
            text=glyph,
            command=command,
            width=34,
            height=34,
            fg_color=BG_INPUT,
            hover_color=BG_CARD_HOVER,
            text_color=color,
            corner_radius=10,
            font=(_SANS_BOLD, 13),
            **kw,
        )


class KpiCard(ctk.CTkFrame):
    """KPI-карточка: метка сверху, крупное значение снизу, тонкая полоса слева."""

    def __init__(self, master, title: str, value: str, accent: str = ACCENT, trend: Optional[str] = None):
        super().__init__(
            master,
            corner_radius=14,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER,
        )
        # цветная полоса слева
        strip = ctk.CTkFrame(self, width=3, corner_radius=2, fg_color=accent)
        strip.place(relx=0, rely=0.15, relheight=0.7, x=8)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=14)

        ctk.CTkLabel(body, text=title.upper(),
                     text_color=FG_DIM, font=F_KPI_LABEL,
                     anchor="w").pack(fill="x")
        self.value_lbl = ctk.CTkLabel(body, text=value,
                                       text_color=FG, font=F_KPI_VALUE,
                                       anchor="w")
        self.value_lbl.pack(fill="x", pady=(2, 0))

        if trend:
            ctk.CTkLabel(body, text=trend,
                         text_color=accent, font=F_SMALL,
                         anchor="w").pack(fill="x")

    def set_value(self, value: str):
        self.value_lbl.configure(text=value)


# ─────────────────────────────────────────────────────────────────
#                        ВЕРХНЯЯ ШАПКА
# ─────────────────────────────────────────────────────────────────

class HeaderBar(ctk.CTkFrame):
    def __init__(self, master, on_start=None, on_stop=None,
                 on_launch_all=None, on_shutdown_all=None,
                 on_settings=None, on_info=None):
        super().__init__(master, corner_radius=0, fg_color=BG_HEADER, height=72)
        self.pack_propagate(False)

        # ── Логотип + название ───────────────────────────────
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=22, pady=14)

        logo_dot = ctk.CTkFrame(left, width=36, height=36,
                                fg_color=ACCENT, corner_radius=10)
        logo_dot.pack(side="left")
        logo_dot.pack_propagate(False)
        ctk.CTkLabel(logo_dot, text="F", text_color="#001018",
                     font=F_LOGO).place(relx=0.5, rely=0.5, anchor="center")

        title_box = ctk.CTkFrame(left, fg_color="transparent")
        title_box.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(title_box, text="FTH Trade Copier",
                     text_color=FG, font=F_TITLE,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(title_box, text="MT5 · Local copy engine",
                     text_color=FG_DIM, font=F_SUBTITLE,
                     anchor="w").pack(anchor="w")

        # ── Правая часть: блоки действий ─────────────────────
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=18, pady=14)

        # Icon buttons (settings / info) — справа от всего
        IconButton(right, "⚙", command=on_settings).pack(side="right", padx=(8, 0))
        IconButton(right, "i", command=on_info).pack(side="right", padx=(8, 0))

        # Group: copy engine
        engine = self._group(right, "КОПИТРЕЙДЕР")
        engine.pack(side="right", padx=(14, 0))
        PillButton(engine.row, "Старт", icon="▶", variant="primary",
                   command=on_start).pack(side="left", padx=4)
        PillButton(engine.row, "Стоп",  icon="■", variant="danger",
                   command=on_stop).pack(side="left", padx=4)

        # Group: terminals
        terms = self._group(right, "ТЕРМИНАЛЫ")
        terms.pack(side="right", padx=(14, 0))
        PillButton(terms.row, "Запустить", icon="▶",
                   command=on_launch_all).pack(side="left", padx=4)
        PillButton(terms.row, "Закрыть",   icon="■",
                   command=on_shutdown_all).pack(side="left", padx=4)

    @staticmethod
    def _group(parent, title):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(wrap, text=title, text_color=FG_DIM,
                     font=(_SANS_BOLD, 8)).pack(anchor="w", padx=4)
        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x")
        wrap.row = row  # type: ignore[attr-defined]
        return wrap


# ─────────────────────────────────────────────────────────────────
#                       MASTER-ПАНЕЛЬ
# ─────────────────────────────────────────────────────────────────

class MasterPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(
            master,
            corner_radius=14,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER,
            height=80,
        )
        self.pack_propagate(False)

        strip = ctk.CTkFrame(self, width=3, corner_radius=2, fg_color=ACCENT)
        strip.place(relx=0, rely=0.15, relheight=0.7, x=8)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=12)

        # Левая часть: метка MASTER + путь
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="y")
        ctk.CTkLabel(left, text="MASTER", text_color=ACCENT,
                     font=(_SANS_BLACK, 10)).pack(anchor="w")
        ctk.CTkLabel(left, text="C:\\MT5\\FTMO\\terminal64.exe",
                     text_color=FG_DIM, font=F_MONO_SM).pack(anchor="w", pady=(2, 0))

        # Кнопки действий по мастеру
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(side="left", padx=(18, 0))
        IconButton(actions, "📈", color=ACCENT).pack(side="left", padx=2)
        IconButton(actions, "✖", color=RED_DIM).pack(side="left", padx=2)
        IconButton(actions, "⚠", color=YELLOW).pack(side="left", padx=2)

        # Правая часть: цифры
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="right", fill="y")

        self._stat(right, "Логин",     "843001",        FG_DIM)
        self._stat(right, "Баланс",    "$208 412.50",   FG)
        self._stat(right, "Эквити",    "$209 102.30",   FG_DIM)
        self._stat(right, "P&L",       "+$689.80",      GREEN)

    @staticmethod
    def _stat(parent, label, value, color):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(side="left", padx=14)
        ctk.CTkLabel(wrap, text=label.upper(), text_color=FG_DIM,
                     font=F_KPI_LABEL).pack(anchor="e")
        ctk.CTkLabel(wrap, text=value, text_color=color,
                     font=F_BODY_BOLD).pack(anchor="e")


# ─────────────────────────────────────────────────────────────────
#                       ТАБЛИЦА СЛЕЙВОВ
# ─────────────────────────────────────────────────────────────────

class SlaveTable(ctk.CTkFrame):
    COLS = [
        ("on",       "ON",       0.05, "center"),
        ("status",   "",         0.03, "center"),
        ("name",     "ИМЯ",      0.13, "w"),
        ("login",    "ЛОГИН",    0.10, "w"),
        ("balance",  "БАЛАНС",   0.11, "e"),
        ("equity",   "ЭКВИТИ",   0.11, "e"),
        ("pnl",      "P&L",      0.09, "e"),
        ("symbols",  "СИМВОЛЫ",  0.20, "w"),
        ("risk",     "РИСК",     0.05, "e"),
        ("deals",    "СДЕЛОК",   0.05, "center"),
        ("actions",  "",         0.08, "e"),
    ]

    def __init__(self, master, slaves: List[SlaveAccount]):
        super().__init__(
            master,
            corner_radius=14,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER,
        )
        self._slaves = slaves
        self._build_header()
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=BORDER_LIGHT,
            scrollbar_button_hover_color=ACCENT_DIM,
        )
        self._scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        for s in slaves:
            SlaveRow(self._scroll, s).pack(fill="x", pady=3)

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=34)
        hdr.pack(fill="x", padx=18, pady=(10, 4))
        for key, text, weight, anchor in self.COLS:
            ctk.CTkLabel(hdr, text=text, text_color=FG_DIM,
                         font=F_HEADER_COL, anchor=anchor).pack(
                side="left", fill="x", expand=True)


class SlaveRow(ctk.CTkFrame):
    def __init__(self, master, slave: SlaveAccount):
        super().__init__(
            master,
            corner_radius=10,
            fg_color=BG_CARD_HOVER if slave.enabled else BG,
            border_width=1,
            border_color=BORDER,
            height=52,
        )
        self.pack_propagate(False)
        self._slave = slave

        # цветная полоса слева — по статусу
        side = ACCENT if (slave.enabled and slave.connected) else (
            YELLOW if slave.enabled else FG_MUTED)
        strip = ctk.CTkFrame(self, width=3, corner_radius=2, fg_color=side)
        strip.place(relx=0, rely=0.2, relheight=0.6, x=6)

        cell = lambda parent, **kw: ctk.CTkFrame(parent, fg_color="transparent", **kw)

        # ON toggle
        on_w = cell(self); on_w.pack(side="left", fill="both", expand=True)
        sw = ctk.CTkSwitch(on_w, text="", switch_width=32, switch_height=16,
                           progress_color=ACCENT, fg_color=BG_INPUT,
                           button_color=FG_LABEL, button_hover_color=FG)
        sw.pack(padx=4)
        if slave.enabled:
            sw.select()

        # status dot
        dot_w = cell(self); dot_w.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(dot_w, text="●",
                     text_color=GREEN if slave.connected else FG_MUTED,
                     font=(_SANS_REG, 14)).pack()

        # name
        nm_w = cell(self); nm_w.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(nm_w, text=slave.name, anchor="w",
                     text_color=FG, font=F_BODY_BOLD).pack(fill="x", padx=8)

        # login
        lg_w = cell(self); lg_w.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(lg_w, text=slave.login, anchor="w",
                     text_color=FG_DIM, font=F_MONO_SM).pack(fill="x", padx=4)

        # balance
        bal_w = cell(self); bal_w.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(bal_w, text=f"${slave.balance:,.2f}", anchor="e",
                     text_color=FG, font=F_BODY_BOLD).pack(fill="x", padx=4)

        # equity
        eq_w = cell(self); eq_w.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(eq_w, text=f"${slave.equity:,.2f}", anchor="e",
                     text_color=FG_DIM, font=F_MONO_SM).pack(fill="x", padx=4)

        # pnl
        pnl_color = GREEN if slave.pnl > 0 else (RED if slave.pnl < 0 else FG_DIM)
        pnl_sign  = "+" if slave.pnl > 0 else ""
        pnl_w = cell(self); pnl_w.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(pnl_w, text=f"{pnl_sign}${slave.pnl:,.2f}", anchor="e",
                     text_color=pnl_color, font=F_BODY_BOLD).pack(fill="x", padx=4)

        # symbols
        sym_w = cell(self); sym_w.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(sym_w, text=slave.symbols, anchor="w",
                     text_color=FG_LABEL, font=F_BODY).pack(fill="x", padx=8)

        # risk
        rk_w = cell(self); rk_w.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(rk_w, text=f"{slave.risk:.2f}x", anchor="e",
                     text_color=FG, font=F_BODY_BOLD).pack(fill="x", padx=4)

        # deals
        dl_w = cell(self); dl_w.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(dl_w, text=str(slave.deals_today), anchor="center",
                     text_color=FG_DIM, font=F_BODY).pack(fill="x")

        # actions
        act_w = cell(self); act_w.pack(side="left", fill="both", expand=True)
        bar = ctk.CTkFrame(act_w, fg_color="transparent")
        bar.pack(padx=4)
        IconButton(bar, "✎", color=ACCENT).pack(side="left", padx=2)
        IconButton(bar, "🗑", color=RED_DIM).pack(side="left", padx=2)


# ─────────────────────────────────────────────────────────────────
#                       НИЖНЯЯ ВКЛАДКА (Сделки/Логи)
# ─────────────────────────────────────────────────────────────────

class BottomTabs(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        tabview = ctk.CTkTabview(
            self, fg_color=BG_CARD,
            segmented_button_fg_color=BG,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_H,
            segmented_button_unselected_color=BG_INPUT,
            segmented_button_unselected_hover_color=BG_CARD_HOVER,
            text_color=FG, corner_radius=14, border_width=1, border_color=BORDER,
        )
        tabview.pack(fill="both", expand=True)

        tabview.add("Сделки")
        tabview.add("Логи")
        tabview.add("Статистика")

        # ── вкладка Сделки ────────────────────────────────
        deals = tabview.tab("Сделки")
        sample = [
            ("12:34:21", "OK",   "EURUSD",  "BUY",  "0.20", "FTMO 200K",   "+$48.20"),
            ("12:34:21", "OK",   "EURUSD",  "BUY",  "0.10", "MFF Phase 2", "+$24.10"),
            ("12:21:09", "FAIL", "XAUUSD",  "SELL", "0.05", "MFF Phase 2", "Symbol not found"),
            ("12:18:55", "OK",   "US30",    "SELL", "0.50", "5%ers HRP",   "-$22.40"),
            ("12:10:02", "OK",   "GBPUSD",  "BUY",  "0.30", "FTMO 200K",   "+$15.80"),
        ]
        headers = ["ВРЕМЯ", "СТАТУС", "СИМВОЛ", "СТОР.", "ЛОТ", "СЛЕЙВ", "РЕЗУЛЬТАТ"]
        hdr = ctk.CTkFrame(deals, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(10, 6))
        for h in headers:
            ctk.CTkLabel(hdr, text=h, text_color=FG_DIM,
                         font=F_HEADER_COL, anchor="w").pack(side="left",
                                                              expand=True, fill="x")

        rows = ctk.CTkScrollableFrame(deals, fg_color="transparent",
                                       scrollbar_button_color=BORDER_LIGHT)
        rows.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        for t, status, sym, side, lot, slv, result in sample:
            r = ctk.CTkFrame(rows, fg_color=BG_CARD_HOVER, corner_radius=8,
                             border_width=1, border_color=BORDER, height=34)
            r.pack(fill="x", pady=2)
            r.pack_propagate(False)
            color = GREEN if status == "OK" else RED
            for col, txt, c in zip(headers, (t, status, sym, side, lot, slv, result),
                                    (FG_DIM, color, FG, ACCENT, FG, FG_LABEL,
                                     GREEN if result.startswith("+") else (RED if result.startswith("-") else YELLOW))):
                ctk.CTkLabel(r, text=txt, text_color=c, font=F_MONO_SM,
                             anchor="w").pack(side="left", expand=True, fill="x", padx=8)

        # ── вкладка Логи ──────────────────────────────────
        logs = tabview.tab("Логи")
        log_box = ctk.CTkTextbox(logs, fg_color=BG, text_color=FG_LABEL,
                                  font=F_MONO_SM, border_width=0, corner_radius=10)
        log_box.pack(fill="both", expand=True, padx=14, pady=12)
        log_box.insert("end",
            "[12:34:21] master signal received: EURUSD BUY 0.5 @ 1.08412\n"
            "[12:34:21]   → slave FTMO 200K: opened ticket 88203121, lot 0.20\n"
            "[12:34:21]   → slave MFF Phase 2: opened ticket 41200299, lot 0.10\n"
            "[12:34:21]   → slave 5%ers HRP: opened ticket 70011233, lot 0.05\n"
            "[12:33:55] heartbeat: master OK, 3/4 slaves connected\n"
            "[12:33:50] state saved (5 trades pending)\n"
        )
        log_box.configure(state="disabled")

        # ── вкладка Статистика ────────────────────────────
        stats = tabview.tab("Статистика")
        ctk.CTkLabel(stats, text="Сделок сегодня: 13   •   Успешных: 11   •   Ошибок: 2",
                     text_color=FG, font=F_BODY).pack(pady=18, padx=14, anchor="w")
        ctk.CTkLabel(stats, text="Сумма копированных лотов: 8.45 lot",
                     text_color=FG_DIM, font=F_BODY).pack(padx=14, anchor="w")


# ─────────────────────────────────────────────────────────────────
#                       SAMPLE-ДИАЛОГ (Slave)
# ─────────────────────────────────────────────────────────────────

class SlaveDialogPreview(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Slave account")
        self.geometry("420x520")
        self.configure(fg_color=BG)
        self.transient(master)
        self.grab_set()

        wrap = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=14,
                            border_width=1, border_color=BORDER)
        wrap.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(wrap, text="Новый slave-аккаунт",
                     text_color=FG, font=F_TITLE).pack(anchor="w",
                                                        padx=20, pady=(18, 4))
        ctk.CTkLabel(wrap, text="Заполните настройки подключения к терминалу",
                     text_color=FG_DIM, font=F_SUBTITLE).pack(anchor="w",
                                                                padx=20, pady=(0, 16))

        form = ctk.CTkFrame(wrap, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20, pady=4)

        def field(label):
            ctk.CTkLabel(form, text=label.upper(), text_color=FG_DIM,
                         font=F_KPI_LABEL).pack(anchor="w", pady=(10, 4))
            entry = ctk.CTkEntry(form, fg_color=BG_INPUT, border_color=BORDER_LIGHT,
                                 text_color=FG, height=36, corner_radius=10,
                                 font=F_BODY)
            entry.pack(fill="x")
            return entry

        field("Имя профиля").insert(0, "FTMO 200K")
        field("Путь к terminal64.exe").insert(0, "C:\\MT5\\FTMO\\terminal64.exe")
        field("Логин").insert(0, "1023144")

        ctk.CTkLabel(form, text="РИСК", text_color=FG_DIM,
                     font=F_KPI_LABEL).pack(anchor="w", pady=(14, 4))
        ctk.CTkSlider(form, from_=0, to=2, number_of_steps=20,
                      progress_color=ACCENT, button_color=ACCENT,
                      button_hover_color=ACCENT_H).pack(fill="x")

        btns = ctk.CTkFrame(wrap, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=18)
        PillButton(btns, "Отмена", command=self.destroy).pack(side="right", padx=(8, 0))
        PillButton(btns, "Сохранить", variant="primary",
                   command=self.destroy).pack(side="right")


# ─────────────────────────────────────────────────────────────────
#                       ГЛАВНОЕ ОКНО
# ─────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FTH Trade Copier — пилот нового UI")
        self.geometry("1280x820")
        self.minsize(1180, 720)
        self.configure(fg_color=BG_DEEP)

        # Header
        HeaderBar(
            self,
            on_start=lambda: print("start"),
            on_stop=lambda: print("stop"),
            on_settings=lambda: SlaveDialogPreview(self),
            on_info=lambda: print("info"),
        ).pack(fill="x")

        # Main content
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=14)

        # Master
        MasterPanel(body).pack(fill="x", pady=(0, 14))

        # KPI cards
        kpi_row = ctk.CTkFrame(body, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 14))
        kpis = [
            ("Master Balance",  "$208 412.50",  ACCENT,  "+0.34% сегодня"),
            ("Total Equity",    "$393 130.50",  ACCENT,  "5 счетов"),
            ("Net P&L",         "+$714.95",     GREEN,   "за сессию"),
            ("Сделок скопир.",  "13 / 14",      ACCENT,  "1 пропущена"),
        ]
        for i, (t, v, c, tr) in enumerate(kpis):
            card = KpiCard(kpi_row, t, v, accent=c, trend=tr)
            card.pack(side="left", fill="both", expand=True,
                      padx=(0 if i == 0 else 10, 0))

        # Section: slaves
        sec = ctk.CTkFrame(body, fg_color="transparent")
        sec.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(sec, text="SLAVE ACCOUNTS", text_color=FG_LABEL,
                     font=F_SECTION).pack(side="left")
        ctk.CTkLabel(sec, text=f"{sum(1 for s in SAMPLE_SLAVES if s.enabled)}/{len(SAMPLE_SLAVES)} активны",
                     text_color=FG_DIM, font=F_SMALL).pack(side="left", padx=(10, 0))
        PillButton(sec, "Закрыть все сделки",
                   variant="danger", icon="✖").pack(side="right", padx=(8, 0))
        PillButton(sec, "Добавить slave",
                   variant="primary", icon="+",
                   command=lambda: SlaveDialogPreview(self)).pack(side="right")

        # Slave table (~40% of remaining)
        SlaveTable(body, SAMPLE_SLAVES).pack(fill="both", expand=True, pady=(8, 12))

        # Bottom tabs
        BottomTabs(body).pack(fill="both", expand=False)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
