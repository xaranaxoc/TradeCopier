"""
FTH Trade Copier — модернизированный UI на CustomTkinter.

Этот модуль предоставляет `AppCtk`, наследника от `App` из `gui.py`:
вся бизнес-логика (CopyTrader, конфиги, профили, лицензия, трей, апдейтер)
переиспользуется один-в-один — переопределяется только построение интерфейса.

Запускается через `python gui.py --new-ui` (или `python gui_new.py`).
Старый `gui.py` без флага продолжает работать как раньше.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, font as tkfont
from typing import Dict, Optional

import customtkinter as ctk

import gui
from gui import (
    App, AccountRow, TradesTable,
    BG_DEEP, BG, BG_ROW, BG_ROW_HOVER, BG_INPUT, BG_HEADER,
    FG, FG_DIM, FG_LABEL, FG_MUTED,
    ACCENT, ACCENT_H, ACCENT_DIM,
    GREEN, RED, RED_DIM, YELLOW, BORDER, BORDER_LIGHT, DIVIDER,
    FONT, FONT_BOLD, FONT_SM, FONT_XS,
    FONT_TITLE, FONT_VAL, FONT_VAL_BOLD, FONT_MONO_SM,
    IMG_DIR, ICON_DEFAULT, COL_SPEC,
    _bind_tip, _UPD_OK,
)

if _UPD_OK:
    upd_mod = gui.upd_mod  # type: ignore[attr-defined]


# ── CTk глобально ──────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Палитра / радиусы / отступы — единый источник правды для нового UI
CORNER_LG = 14
CORNER_MD = 10
CORNER_SM = 8

# Чуть более «премиальные» фоны (немного светлее, чем у старого UI,
# чтобы скругления и тени читались на тёмном)
CARD_BG       = "#11111C"
CARD_BG_HOVER = "#181826"
SOFT_BORDER   = "#1F1F30"


def _pick_font(prefs, fallback="TkDefaultFont"):
    try:
        available = set(tkfont.families())
    except Exception:
        return prefs[0] if prefs else fallback
    for name in prefs:
        if name in available:
            return name
    return fallback


# ── Шрифты с автоподбором (Linux preview / Windows production) ─────
def _resolve_fonts():
    sans_reg  = _pick_font(["Segoe UI", "Inter", "Roboto", "DejaVu Sans", "Arial"])
    sans_bold = _pick_font(["Segoe UI Semibold", "Inter Semi Bold", "Roboto Medium",
                            "DejaVu Sans", "Arial"])
    sans_black = _pick_font(["Segoe UI Black", "Inter Black", "Arial Black"])
    return sans_reg, sans_bold, sans_black


# ─────────────────────────────────────────────────────────────────
#                    КОМПОНЕНТЫ НОВОГО UI
# ─────────────────────────────────────────────────────────────────

class PillButton(ctk.CTkButton):
    """Скруглённая «pill»-кнопка с тремя вариантами.

    Добавлен shim `config(...)`, чтобы старый код вида
    `btn.config(state="disabled")` работал на CTkButton.
    """

    def __init__(self, master, text, command=None, variant="ghost",
                 icon=None, width=None, **kw):
        if variant == "primary":
            fg, hover, txt = ACCENT, ACCENT_H, "#FFFFFF"
        elif variant == "danger":
            fg, hover, txt = RED_DIM, RED, "#FFFFFF"
        else:
            fg, hover, txt = BG_INPUT, CARD_BG_HOVER, FG_LABEL
        label = f"{icon}  {text}" if icon else text
        kwargs = dict(
            master=master, text=label, command=command,
            fg_color=fg, hover_color=hover, text_color=txt,
            corner_radius=CORNER_MD, height=32,
        )
        if width is not None:
            kwargs["width"] = width
        kwargs.update(kw)
        super().__init__(**kwargs)

    # tk.Button-совместимый shim
    def config(self, **kw):  # type: ignore[override]
        # `bg`/`fg` -> CTk-эквиваленты
        if "bg" in kw:
            kw["fg_color"] = kw.pop("bg")
        if "fg" in kw:
            kw["text_color"] = kw.pop("fg")
        self.configure(**kw)


class IconButton(ctk.CTkButton):
    """Квадратная иконка-кнопка."""

    def __init__(self, master, glyph, command=None, color=FG_DIM,
                 hover_color=None, size=34, **kw):
        super().__init__(
            master,
            text=glyph, command=command,
            width=size, height=size,
            fg_color=BG_INPUT,
            hover_color=hover_color or CARD_BG_HOVER,
            text_color=color,
            corner_radius=CORNER_MD,
            **kw,
        )


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


# ─────────────────────────────────────────────────────────────────
#                       НОВЫЙ APP
# ─────────────────────────────────────────────────────────────────

class AppCtk(App):
    """Новый UI поверх той же логики, что и App.

    При импорте автоматически устанавливает CTk-стилизованные диалоги
    через `dialogs_ctk.install()` (monkey-patch на gui.SlaveDialog и др.),
    чтобы методы базового `App._add_slave / _open_settings / _show_activation`
    использовали новые диалоги без дополнительных оверрайдов.
    """

    def __init__(self):
        # Подменяем ссылки на диалоги ДО построения UI, чтобы любая
        # ранняя активация / setup использовала уже новый стиль.
        try:
            from dialogs_ctk import install as _install_ctk_dialogs
            _install_ctk_dialogs()
        except Exception:
            # если что-то пошло не так — остаются старые tk-диалоги,
            # главное окно всё равно построится.
            pass
        super().__init__()

    # ── переопределяем единственный entry-point построения UI ────
    def _build_ui(self):
        # Приводим окно к тёмному фону и применяем дефолтную CTk-стилизацию.
        self.configure(bg=BG_DEEP)
        try:
            ctk.set_appearance_mode("dark")
        except Exception:
            pass

        # Заголовки шрифтов (резолвятся один раз).
        sans_reg, sans_bold, sans_black = _resolve_fonts()
        self._sans_reg  = sans_reg
        self._sans_bold = sans_bold
        self._sans_black = sans_black

        # ── Верхняя шапка ─────────────────────────────────────
        self._build_header_new(sans_reg, sans_bold, sans_black)

        # ── Master + KPI + Slave таблица + Notebook идут в общем
        #    контейнере с воздушными отступами.
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(10, 4))

        self._build_master_panel_new(body, sans_reg, sans_bold)
        self._build_kpi_row_new(body, sans_reg, sans_bold)
        self._build_slaves_section_new(body, sans_reg, sans_bold)
        self._build_bottom_notebook_new(body, sans_reg, sans_bold)
        self._build_footer_stats_new(sans_reg)

    # ── _make_btn используется в hot-paths (Master row buttons и т.п.)
    def _make_btn(self, parent, text, cmd, accent=False, danger=False):
        if accent:
            variant = "primary"
        elif danger:
            variant = "danger"
        else:
            variant = "ghost"
        return PillButton(parent, text=text, command=cmd, variant=variant)

    # ────────────────────────────────────────────────────────
    #                  HEADER
    # ────────────────────────────────────────────────────────
    def _build_header_new(self, sans_reg, sans_bold, sans_black):
        hdr = ctk.CTkFrame(self, fg_color=BG_HEADER, corner_radius=0, height=76)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Логотип + название
        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=20, pady=14)

        logo_path = os.path.join(IMG_DIR, "convertico-fth_48x48.png")
        if os.path.exists(logo_path):
            try:
                self._logo_img = tk.PhotoImage(file=logo_path)
                self._logo_label = ctk.CTkLabel(left, image=self._logo_img, text="")
                self._logo_label.pack(side="left", padx=(0, 12))
            except Exception:
                self._logo_label = None
        else:
            self._logo_label = None

        title_box = ctk.CTkFrame(left, fg_color="transparent")
        title_box.pack(side="left")
        version_suffix = f"  v{upd_mod.VERSION}" if _UPD_OK else ""
        ctk.CTkLabel(title_box, text=f"FTH Trade Copier{version_suffix}",
                     text_color=FG, font=(sans_bold, 17),
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(title_box, text="MT5 · Local copy engine",
                     text_color=FG_DIM, font=(sans_reg, 11),
                     anchor="w").pack(anchor="w")

        # Правая группа действий
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=16, pady=14)

        # Сначала icon-кнопки — будут крайними справа
        self.btn_info = IconButton(right, "i", command=self._toggle_info)
        self.btn_info.pack(side="right", padx=(8, 0))
        _bind_tip(self.btn_info, "Режим подсказок")

        btn_settings = IconButton(right, "⚙", command=self._open_settings)
        btn_settings.pack(side="right", padx=(8, 0))
        _bind_tip(btn_settings, "Настройки приложения")

        # Группа КОПИТРЕЙДЕР
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

        # Группа ТЕРМИНАЛЫ
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

    # ────────────────────────────────────────────────────────
    #                  MASTER PANEL
    # ────────────────────────────────────────────────────────
    def _build_master_panel_new(self, parent, sans_reg, sans_bold):
        card = _make_card(parent, height=72)
        card.pack(fill="x", pady=(0, 12))
        card.pack_propagate(False)

        # Цветная боковая полоса
        strip = ctk.CTkFrame(card, width=3, corner_radius=2, fg_color=ACCENT)
        strip.place(relx=0, rely=0.18, relheight=0.64, x=8)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=10)

        # Слева — лейбл и путь
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="y")
        ctk.CTkLabel(left, text="MASTER", text_color=ACCENT,
                     font=(sans_bold, 10)).pack(anchor="w")

        path_row = ctk.CTkFrame(left, fg_color="transparent")
        path_row.pack(anchor="w", pady=(4, 0))

        self.var_master_path = tk.StringVar()
        self._ent_master = ctk.CTkEntry(
            path_row, textvariable=self.var_master_path, width=320, height=28,
            fg_color=BG_INPUT, border_color=SOFT_BORDER, text_color=FG,
            corner_radius=CORNER_SM, font=(sans_reg, 10),
        )
        self._ent_master.pack(side="left")

        btn_browse_m = PillButton(path_row, "...", width=42,
                                   command=self._browse_master)
        btn_browse_m.pack(side="left", padx=(6, 0))
        _bind_tip(btn_browse_m, "Выбрать путь к terminal64.exe мастера")

        # Кнопки-иконки (открыть терминал / закрыть все / тест)
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(side="left", padx=(14, 0))
        IconButton(actions, "📈", color=ACCENT,
                   command=self._open_master_terminal, size=30).pack(side="left", padx=2)
        IconButton(actions, "✖", color=RED_DIM,
                   command=self._close_all_master, size=30).pack(side="left", padx=2)
        IconButton(actions, "⚠", color=YELLOW,
                   command=self._test_master, size=30).pack(side="left", padx=2)

        # Правая часть — статистика мастера
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="right", fill="y")

        self.lbl_master_login = self._stat_cell(right, "ЛОГИН", "—", FG_DIM,
                                                  sans_reg, sans_bold)
        self.lbl_master_bal   = self._stat_cell(right, "БАЛАНС", "—", FG,
                                                  sans_reg, sans_bold)
        self.lbl_master_eq    = self._stat_cell(right, "ЭКВИТИ", "—", FG_DIM,
                                                  sans_reg, sans_bold)
        self.lbl_master_pnl   = self._stat_cell(right, "P&L", "—", FG_DIM,
                                                  sans_reg, sans_bold)

    def _stat_cell(self, parent, label, value, color, sans_reg, sans_bold):
        # value-лейбл — обычный tk.Label, потому что App._refresh_master_panel
        # обновляет его через `.config(text=..., fg=...)`.
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(side="left", padx=12)
        tk.Label(wrap, text=label, bg=CARD_BG, fg=FG_DIM,
                  font=(sans_reg, 9)).pack(anchor="e")
        lbl = tk.Label(wrap, text=value, bg=CARD_BG, fg=color,
                        font=(sans_bold, 13))
        lbl.pack(anchor="e", pady=(2, 0))
        return lbl

    # ────────────────────────────────────────────────────────
    #                  KPI ROW
    # ────────────────────────────────────────────────────────
    def _build_kpi_row_new(self, parent, sans_reg, sans_bold):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 14))

        self._kpi_labels = {}
        cards_data = [
            ("kpi_bal",  "Master Balance",  "—", FG,     ACCENT),
            ("kpi_eq",   "Total Equity",    "—", FG,     ACCENT),
            ("kpi_pnl",  "Net P&L",         "—", FG_DIM, GREEN),
            ("kpi_conn", "Connected",       "—", FG_DIM, ACCENT),
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
            # KPI value — tk.Label: App._refresh_kpi_cards() делает .config(text=...).
            lbl = tk.Label(inner, text=value, bg=CARD_BG, fg=color,
                            font=(sans_bold, 18), anchor="w")
            lbl.pack(fill="x", pady=(2, 0))
            self._kpi_labels[key] = lbl

    # ────────────────────────────────────────────────────────
    #                  SLAVES SECTION
    # ────────────────────────────────────────────────────────
    def _build_slaves_section_new(self, parent, sans_reg, sans_bold):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(header, text="SLAVE ACCOUNTS", text_color=FG_LABEL,
                     font=(sans_bold, 11)).pack(side="left")
        # tk.Label: App._update_slave_count делает .config(text=...).
        self.lbl_slave_count = tk.Label(header, text="0/10",
                                          bg=BG_DEEP, fg=FG_DIM,
                                          font=(sans_bold, 10))
        self.lbl_slave_count.pack(side="left", padx=(10, 0))

        # Кнопки справа: добавить слейв / закрыть все сделки
        PillButton(header, "✖ Закрыть сделки", variant="danger",
                   command=self._close_all_open).pack(side="right", padx=(8, 0))
        PillButton(header, "+ Аккаунт", variant="primary",
                   command=self._add_slave).pack(side="right")

        # Карточка-контейнер для таблицы. AccountRow ожидает обычный tk.Frame
        # с настроенной grid-сеткой по COL_SPEC.
        table_card = _make_card(parent)
        table_card.pack(fill="both", expand=True, pady=(0, 12))

        self._table_frame = tk.Frame(table_card, bg=CARD_BG)
        self._table_frame.pack(fill="both", expand=True, padx=14, pady=10)

        for idx, _, min_w, weight, _ in COL_SPEC:
            self._table_frame.columnconfigure(idx, minsize=min_w, weight=weight)

        # Заголовки колонок — row=0, чтобы автоматически выравниваться
        # под AccountRow grid (row=1+).
        for idx, text, _, _, anchor in COL_SPEC:
            tk.Label(self._table_frame, text=text, bg=CARD_BG, fg=FG_DIM,
                      font=(sans_bold, 8), anchor=anchor).grid(
                row=0, column=idx, padx=2, pady=(0, 6), sticky="ew")

        # AccountRow стартует с row=1.
        self._next_row = 1

        # tbl_btns — старый App создавал в углу row=0,col=11. В новом дизайне
        # действия вынесены в шапку секции. Делаем пустой stub чтобы атрибут
        # существовал (на случай внешних наследников / dialog code).
        self.tbl_btns = tk.Frame(self._table_frame, bg=CARD_BG)

    # ────────────────────────────────────────────────────────
    #                  BOTTOM NOTEBOOK
    # ────────────────────────────────────────────────────────
    def _build_bottom_notebook_new(self, parent, sans_reg, sans_bold):
        # Используем ttk.Notebook (как в App) — он совместим с TradesTable
        # и логикой self.notebook.select(0). Стилизуем под CTk.
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("CTkNotebook.TNotebook", background=BG_DEEP,
                        borderwidth=0)
        style.configure("CTkNotebook.TNotebook.Tab",
                        background=BG_INPUT, foreground=FG_DIM,
                        padding=[16, 6], font=(sans_bold, 9),
                        borderwidth=0)
        style.map("CTkNotebook.TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])

        nb_card = _make_card(parent)
        nb_card.pack(fill="both", expand=False, pady=(0, 0))

        self.notebook = ttk.Notebook(nb_card, style="CTkNotebook.TNotebook",
                                      height=200)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # ── Сделки ─────────────────────────────────────────
        trades_tab = tk.Frame(self.notebook, bg=CARD_BG)
        self.notebook.add(trades_tab, text="  Сделки  ")
        self.trades_table = TradesTable(trades_tab)
        self.trades_table.configure(bg=CARD_BG)
        self.trades_table.pack(fill="both", expand=True, padx=2, pady=2)

        # подкрашиваем существующий список из истории
        for t in gui._load_trades():
            tag = "ok" if t.get("success") else "err"
            self.trades_table.add_trade(
                time_str=t.get("time", ""), slave=t.get("slave", ""),
                symbol=t.get("symbol", ""), direction=t.get("direction", ""),
                lot=t.get("lot", 0.0), master_ticket=t.get("master_ticket", ""),
                slave_ticket=t.get("slave_ticket", ""), status=t.get("status", ""),
                tag=tag)

        # ── Лог ────────────────────────────────────────────
        log_tab = tk.Frame(self.notebook, bg=CARD_BG)
        self.notebook.add(log_tab, text="  Лог  ")
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

    # ────────────────────────────────────────────────────────
    #                  FOOTER STATS
    # ────────────────────────────────────────────────────────
    def _build_footer_stats_new(self, sans_reg):
        bar = ctk.CTkFrame(self, fg_color=BG_DEEP, height=24)
        bar.pack(fill="x", padx=18, pady=(2, 6))

        # tk.Label: App._refresh_session_stats делает .config(text=...).
        self.lbl_stats = tk.Label(bar, text="", bg=BG_DEEP, fg=FG_DIM,
                                    font=(sans_reg, 10))
        self.lbl_stats.pack(side="left")

        if _UPD_OK:
            ctk.CTkLabel(bar, text=f"v{upd_mod.VERSION}",
                         text_color=FG_MUTED,
                         font=(sans_reg, 10)).pack(side="right")

    # ── Подсветка info-кнопки (старая логика проверяла bg/fg) ──
    def _toggle_info(self):
        from gui import _Tip
        _Tip.enabled = not _Tip.enabled
        if _Tip.enabled:
            self.btn_info.configure(fg_color=ACCENT, text_color="#FFFFFF")
        else:
            self.btn_info.configure(fg_color=BG_INPUT, text_color=FG_DIM)
            _Tip.hide()


def main():
    """Запуск нового UI напрямую (без флага)."""
    # Защита от двойного запуска — переиспользуем тот же мьютекс из gui.py.
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, gui._MUTEX_NAME)  # type: ignore[attr-defined]
    if ctypes.windll.kernel32.GetLastError() == 183:
        gui._activate_existing()
        sys.exit(0)
    app = AppCtk()
    app.mainloop()


if __name__ == "__main__":
    main()
