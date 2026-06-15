"""
FTH Trade Copier — ПРОТОТИП главного окна на CustomTkinter (Фаза 1).

Цель: показать тёмную тему + настоящие скругления/ховеры, не переписывая весь
gui.py. Это статичный макет с демо-данными — без MT5/копира. Вся логика
по-прежнему живёт в gui.py / copier.py.

Запуск (Windows / любой ПК с дисплеем):
    python prototype_ctk.py

Дизайн собирается из theme.py + ui_kit.py + fth_theme.json.
"""

import os

import customtkinter as ctk

import theme as T
import ui_kit as kit

IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")


# ── Демо-данные (только для прототипа) ──────────────────────
DEMO_SLAVES = [
    {"on": True,  "name": "Prop-01",  "login": "5012834", "balance": "10 250.00",
     "equity": "10 311.40", "pnl": "+61.40",  "pnl_ok": True,
     "symbols": "EURUSD→EURUSD  XAUUSD→GOLD", "risk": "1%", "tpd": "8", "loss": "$250"},
    {"on": True,  "name": "Prop-02",  "login": "5012999", "balance": "25 000.00",
     "equity": "24 870.10", "pnl": "-129.90", "pnl_ok": False,
     "symbols": "EURUSD→EURUSD  +3", "risk": "0.5%", "tpd": "12", "loss": "$500"},
    {"on": False, "name": "Personal", "login": "—", "balance": "—",
     "equity": "—", "pnl": "—", "pnl_ok": None,
     "symbols": "EURUSD→EUR.m", "risk": "$50", "tpd": "—", "loss": "—"},
]

COLS = [
    ("ON", 44, "center"), ("", 24, "center"), ("ИМЯ", 90, "w"),
    ("ЛОГИН", 80, "w"), ("БАЛАНС", 100, "e"), ("ЭКВИТИ", 100, "e"),
    ("P&L", 80, "e"), ("СИМВОЛЫ", 200, "w"), ("РИСК", 56, "e"),
    ("СДЕЛ/Д", 56, "center"), ("УБЫТ/Д", 70, "center"), ("", 170, "e"),
]


class Prototype(ctk.CTk):
    def __init__(self):
        super().__init__()
        kit.apply_theme()
        self.title("FTH Trade Copier — прототип (CustomTkinter)")
        self.geometry(T.WINDOW_DEFAULT)
        self.minsize(*T.WINDOW_MIN)
        self.configure(fg_color=T.BG_DEEP)

        self._logo_img = None
        self._build_header()
        kit.make_divider(self).pack(fill="x", padx=T.PAD_WINDOW, pady=(8, 0))
        self._build_master()
        self._build_kpis()
        self._build_slave_header()
        self._build_table()
        self._build_tabs()
        self._build_statusbar()

    # ── Шапка ───────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=T.BG_HEADER, corner_radius=0, height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=16)
        logo = os.path.join(IMG_DIR, "convertico-fth-cyan_48x48.png")
        if os.path.exists(logo):
            try:
                from PIL import Image
                self._logo_img = ctk.CTkImage(Image.open(logo), size=(34, 34))
                ctk.CTkLabel(left, image=self._logo_img, text="").pack(side="left", padx=(0, 10))
            except Exception:
                pass
        ctk.CTkLabel(left, text="Trade Copier",
                     font=ctk.CTkFont(T.FONT_FAMILY, 17, "bold"),
                     text_color=T.FG).pack(side="left")
        ctk.CTkLabel(left, text="MT5", font=ctk.CTkFont(T.FONT_FAMILY, 12, "bold"),
                     text_color=T.ACCENT).pack(side="left", padx=(8, 0), pady=(6, 0))

        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=16)

        kit.make_icon_button(right, "i", color=T.FG_DIM).pack(side="right", padx=(8, 0))
        kit.make_icon_button(right, "\u2699", color=T.FG_DIM).pack(side="right", padx=(4, 0))

        self._group(right, "ТЕРМИНАЛЫ",
                    ("\u25B6 Запустить", "accent"), ("\u25A0 Закрыть", "danger"))
        self._group(right, "КОПИТРЕЙДЕР",
                    ("\u25B6 Старт", "accent"), ("\u25A0 Стоп", "danger"))

    def _group(self, parent, title, *btns):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(side="right", padx=(14, 0))
        ctk.CTkLabel(box, text=title, font=ctk.CTkFont(T.FONT_FAMILY, 9),
                     text_color=T.FG_DIM).pack(side="left", padx=(0, 6))
        for text, kind in btns:
            kit.make_button(box, text, kind=kind, width=104).pack(side="left", padx=2)

    # ── Панель «Мастер» ─────────────────────────────────────
    def _build_master(self):
        wrap, body = kit.make_accent_panel(self, accent=T.ACCENT)
        wrap.pack(fill="x", padx=T.PAD_WINDOW, pady=(8, 4))

        kit.make_label(body, "МАСТЕР", "accent").pack(side="left", padx=(2, 12))
        kit.make_entry(body, placeholder="C:\\...\\terminal64.exe",
                       width=360).pack(side="left", padx=(0, 6))
        kit.make_button(body, "...", kind="neutral", width=42).pack(side="left", padx=2)
        for glyph, color in (("\U0001F4C8", T.ACCENT), ("\u2716", T.RED_DIM),
                             ("\u26A0", T.YELLOW)):
            kit.make_icon_button(body, glyph, color=color).pack(side="left", padx=2)

        ctk.CTkLabel(body, text="#48213355", text_color=T.FG_DIM,
                     font=ctk.CTkFont(T.FONT_MONO_FAMILY, 10)).pack(side="left", padx=(16, 0))
        ctk.CTkLabel(body, text="50 000.00", text_color=T.FG,
                     font=ctk.CTkFont(T.FONT_FAMILY, 13, "bold")).pack(side="right", padx=(8, 2))
        ctk.CTkLabel(body, text="+312.55", text_color=T.GREEN,
                     font=ctk.CTkFont(T.FONT_FAMILY, 11)).pack(side="right", padx=8)

    # ── KPI ─────────────────────────────────────────────────
    def _build_kpis(self):
        dash = ctk.CTkFrame(self, fg_color="transparent")
        dash.pack(fill="x", padx=T.PAD_WINDOW, pady=6)
        data = [
            ("Master Balance", "50 000.00", T.FG),
            ("Total Equity",   "85 181.50", T.FG),
            ("Net P&L",        "+243.05", T.GREEN),
            ("Connected",      "3 / 4", T.ACCENT),
        ]
        for i, (title, val, color) in enumerate(data):
            card, _ = kit.make_kpi(dash, title, val, color)
            card.pack(side="left", fill="x", expand=True,
                      padx=(0 if i == 0 else 8, 0))

    # ── Заголовок таблицы слейвов ───────────────────────────
    def _build_slave_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=T.PAD_WINDOW, pady=(6, 0))
        kit.make_label(head, "SLAVE ACCOUNTS", "label").pack(side="left")
        kit.make_pill(head, "2 / 10", T.FG_DIM).pack(side="left", padx=8)
        kit.make_button(head, "\u2716 Закрыть сделки", kind="danger",
                        width=150).pack(side="right")
        kit.make_button(head, "+ Аккаунт", kind="accent",
                        width=110).pack(side="right", padx=8)

    def _build_table(self):
        frame = ctk.CTkFrame(self, fg_color=T.BG, corner_radius=T.RADIUS_CARD,
                             border_width=1, border_color=T.BORDER)
        frame.pack(fill="both", expand=True, padx=T.PAD_WINDOW, pady=4)

        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=8, pady=8)
        for c, (_, w, _) in enumerate(COLS):
            grid.columnconfigure(c, minsize=w, weight=(1 if c == 7 else 0))

        for c, (text, _, anchor) in enumerate(COLS):
            ctk.CTkLabel(grid, text=text, text_color=T.FG_DIM,
                         font=ctk.CTkFont(T.FONT_FAMILY, 9),
                         anchor=anchor).grid(row=0, column=c, padx=4, pady=(0, 6), sticky="ew")

        for r, s in enumerate(DEMO_SLAVES, start=1):
            self._slave_row(grid, r, s)

    def _slave_row(self, grid, r, s):
        on = s["on"]
        # фон-строка (скруглённая карточка под виджетами)
        row_bg = ctk.CTkFrame(grid, fg_color=T.BG_ROW, corner_radius=8,
                              border_width=1, border_color=T.BORDER, height=T.ROW_HEIGHT)
        row_bg.grid(row=r, column=0, columnspan=len(COLS), sticky="nsew", pady=3)
        strip = ctk.CTkFrame(row_bg, width=3, corner_radius=2,
                             fg_color=(T.GREEN if on else T.FG_MUTED))
        strip.place(x=2, y=8, relheight=0.6)

        chk = ctk.CTkCheckBox(grid, text="", width=24, checkbox_width=18,
                              checkbox_height=18)
        if on:
            chk.select()
        chk.grid(row=r, column=0, padx=(8, 0), pady=8)

        dot = ctk.CTkLabel(grid, text="\u25CF", width=24,
                           text_color=(T.GREEN if on else T.FG_MUTED),
                           font=ctk.CTkFont(T.FONT_FAMILY, 12))
        dot.grid(row=r, column=1, pady=8)

        cells = [
            (2, s["name"], T.FG, "w", ctk.CTkFont(T.FONT_FAMILY, 11, "bold")),
            (3, s["login"], T.FG_DIM, "w", ctk.CTkFont(T.FONT_MONO_FAMILY, 10)),
            (4, s["balance"], T.FG, "e", ctk.CTkFont(T.FONT_FAMILY, 11, "bold")),
            (5, s["equity"], T.FG_DIM, "e", ctk.CTkFont(T.FONT_MONO_FAMILY, 10)),
        ]
        for c, text, color, anchor, font in cells:
            ctk.CTkLabel(grid, text=text, text_color=color, anchor=anchor,
                         font=font).grid(row=r, column=c, padx=4, pady=8, sticky="ew")

        pnl_color = T.FG_DIM if s["pnl_ok"] is None else (T.GREEN if s["pnl_ok"] else T.RED)
        ctk.CTkLabel(grid, text=s["pnl"], text_color=pnl_color, anchor="e",
                     font=ctk.CTkFont(T.FONT_FAMILY, 11)).grid(row=r, column=6, padx=4, sticky="ew")
        ctk.CTkLabel(grid, text=s["symbols"], text_color=T.FG_DIM, anchor="w",
                     font=ctk.CTkFont(T.FONT_FAMILY, 9)).grid(row=r, column=7, padx=4, sticky="ew")
        ctk.CTkLabel(grid, text=s["risk"], text_color=T.YELLOW, anchor="e",
                     font=ctk.CTkFont(T.FONT_FAMILY, 10)).grid(row=r, column=8, padx=4, sticky="ew")
        ctk.CTkLabel(grid, text=s["tpd"], text_color=T.FG_DIM, anchor="center",
                     font=ctk.CTkFont(T.FONT_FAMILY, 10)).grid(row=r, column=9, padx=4, sticky="ew")
        kit.make_pill(grid, s["loss"], T.FG_DIM).grid(row=r, column=10, padx=4, sticky="")

        actions = ctk.CTkFrame(grid, fg_color="transparent")
        actions.grid(row=r, column=11, padx=4, sticky="e")
        for glyph, color in (("\U0001F4C8", T.FG_DIM), ("\u2716", T.RED_DIM),
                             ("\u26A0", T.YELLOW), ("\u2699", T.FG_DIM), ("\u2715", T.FG_DIM)):
            b = ctk.CTkButton(actions, text=glyph, width=26, height=26,
                              corner_radius=6, fg_color="transparent",
                              hover_color=T.BG_ROW_HOVER, text_color=color,
                              font=ctk.CTkFont(T.FONT_FAMILY, 12))
            b.pack(side="left", padx=1)

    # ── Вкладки Сделки / Лог ────────────────────────────────
    def _build_tabs(self):
        tabs = ctk.CTkTabview(self, fg_color=T.BG, segmented_button_fg_color=T.BG_INPUT,
                              segmented_button_selected_color=T.ACCENT,
                              segmented_button_selected_hover_color=T.ACCENT_H,
                              segmented_button_unselected_color=T.BG_INPUT,
                              text_color=T.FG, height=150, corner_radius=T.RADIUS_CARD)
        tabs.pack(fill="x", padx=T.PAD_WINDOW, pady=(4, 4))
        tabs.add("Сделки")
        tabs.add("Лог")
        demo = "11:42:08  Prop-01  EURUSD  BUY 0.12  #88231 → #2310044  OK"
        ctk.CTkLabel(tabs.tab("Сделки"), text=demo, text_color=T.GREEN,
                     font=ctk.CTkFont(T.FONT_MONO_FAMILY, 10),
                     anchor="w").pack(anchor="w", padx=10, pady=6)
        ctk.CTkLabel(tabs.tab("Лог"), text="11:42:08  Копир запущен. Подключено 3/4.",
                     text_color=T.FG_DIM, font=ctk.CTkFont(T.FONT_MONO_FAMILY, 10),
                     anchor="w").pack(anchor="w", padx=10, pady=6)

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=T.PAD_WINDOW, pady=(0, 8))
        ctk.CTkLabel(bar, text="Скопировано: 14   •   Ошибок: 0",
                     text_color=T.FG_DIM,
                     font=ctk.CTkFont(T.FONT_FAMILY, 9)).pack(side="left")
        ctk.CTkLabel(bar, text="v1.0.0", text_color=T.FG_MUTED,
                     font=ctk.CTkFont(T.FONT_FAMILY, 9)).pack(side="right")


if __name__ == "__main__":
    Prototype().mainloop()
