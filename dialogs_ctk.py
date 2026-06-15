"""
CTk-стилизованные диалоги: SymbolPicker / Slave / Settings / Activation.

Каждый класс держит тот же *публичный* API, что и оригинал из `gui.py`
(конструктор, атрибуты `.result` / `.selected`, методы), чтобы можно
было сделать drop-in замену через monkey-patch:

    gui.SlaveDialog = SlaveDialogCtk
    gui.SymbolPickerDialog = SymbolPickerDialogCtk
    gui.SettingsDialog = SettingsDialogCtk
    gui.ActivationWindow = ActivationWindowCtk
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional

import customtkinter as ctk

import gui
from gui import (
    BG, BG_DEEP, BG_INPUT, BG_ROW, BG_ROW_HOVER, BG_HEADER,
    FG, FG_DIM, FG_LABEL, FG_MUTED,
    ACCENT, ACCENT_H, ACCENT_DIM,
    GREEN, GREEN_DIM, RED, RED_DIM, YELLOW, BORDER, DIVIDER,
    FONT, FONT_BOLD, FONT_SM, FONT_XS, FONT_TITLE,
    IMG_DIR, ICON_DEFAULT,
    _bind_tip, _LIC_OK,
)
if _LIC_OK:
    lic_mod = gui.lic_mod  # type: ignore[attr-defined]

from gui import (
    PillButton, IconButton, _make_card,
    CARD_BG, SOFT_BORDER, CORNER_LG, CORNER_MD, CORNER_SM,
)


# ── helpers общие для всех диалогов ─────────────────────────────────

def _ctk_entry(parent, var=None, width_chars=20, **kw):
    """CTkEntry с шириной в «символах» (приблизительно)."""
    px = max(60, int(width_chars * 8))
    return ctk.CTkEntry(
        parent, textvariable=var, width=px, height=28,
        fg_color=BG_INPUT, border_color=SOFT_BORDER, border_width=1,
        text_color=FG, corner_radius=CORNER_SM, font=("Segoe UI", 10),
        **kw,
    )


def _dialog_header(parent, title: str, subtitle: str = ""):
    """Шапка с акцентной полосой и заголовком."""
    hdr = ctk.CTkFrame(parent, fg_color=BG_HEADER, corner_radius=0, height=46)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    strip = ctk.CTkFrame(hdr, width=3, corner_radius=2, fg_color=ACCENT)
    strip.place(relx=0, rely=0.18, relheight=0.64, x=10)
    inner = ctk.CTkFrame(hdr, fg_color="transparent")
    inner.pack(side="left", padx=22, pady=6)
    tk.Label(inner, text=title, bg=BG_HEADER, fg=FG,
              font=("Segoe UI", 11, "bold")).pack(anchor="w")
    if subtitle:
        tk.Label(inner, text=subtitle, bg=BG_HEADER, fg=FG_DIM,
                  font=("Segoe UI", 9)).pack(anchor="w")
    return hdr


def _safe_iconbitmap(top: tk.Toplevel, path: str):
    """Безопасный iconbitmap — глотает TclError на Linux/headless."""
    if not os.path.exists(path):
        return
    try:
        top.iconbitmap(path)
    except Exception:
        pass


# ────────────────────────────────────────────────────────────────────
#                  SymbolPickerDialogCtk
# ────────────────────────────────────────────────────────────────────

class SymbolPickerDialogCtk(tk.Toplevel):
    """Выбор символа из списка — CTk-стиль."""

    def __init__(self, parent, symbols: List[str],
                 title_text: str = "Выбор символа"):
        super().__init__(parent)
        self.selected: Optional[str] = None
        self._all_symbols = symbols
        self.title(title_text)
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        _safe_iconbitmap(self, ICON_DEFAULT)
        self.grab_set()

        _dialog_header(self, title_text, "Найдите и выберите символ")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=10)

        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *_: self._filter())
        ent = _ctk_entry(body, self.var_search, 30,
                         placeholder_text="🔎 поиск...")
        ent.pack(fill="x")
        ent.focus_set()

        list_card = _make_card(body, fg_color=BG_INPUT)
        list_card.pack(fill="both", expand=True, pady=(10, 10))

        self.listbox = tk.Listbox(
            list_card, bg=BG_INPUT, fg=FG, font=("Segoe UI", 10),
            selectbackground=ACCENT, selectforeground="white",
            relief="flat", highlightthickness=0, activestyle="none", bd=0,
        )
        sb = ttk.Scrollbar(list_card, orient="vertical",
                            command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.listbox.pack(side="left", fill="both", expand=True,
                           padx=(4, 0), pady=4)
        self.listbox.bind("<Double-1>", lambda e: self._pick())
        self.listbox.bind("<Return>", lambda e: self._pick())
        for s in self._all_symbols:
            self.listbox.insert("end", s)

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x")
        PillButton(btn_row, "Выбрать", variant="primary",
                    command=self._pick).pack(side="left", padx=(0, 6))
        PillButton(btn_row, "Отмена", variant="ghost",
                    command=self.destroy).pack(side="left")

        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        w, h = 320, 420
        try:
            pw = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
            self.geometry(f"{w}x{h}+{pw}+{py}")
        except Exception:
            self.geometry(f"{w}x{h}")

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


# ────────────────────────────────────────────────────────────────────
#                  SlaveDialogCtk
# ────────────────────────────────────────────────────────────────────

class SlaveDialogCtk(gui.SlaveDialog):
    """SlaveDialog с CTk-стилизованными хелперами `_btn` и `_ent`.

    Само построение (`_build`, `_save`, `_load_symbols` и т.д.) полностью
    наследуется из оригинала — переопределяются только фабрики виджетов.
    """

    # CTk-кнопка вместо tk.Button
    def _btn(self, parent, text, cmd, accent=False, small=False):
        variant = "primary" if accent else "ghost"
        h = 24 if small else 30
        # для крошечных «...» / «×» — не растягиваем
        width = 36 if (small and len(text) <= 2) else None
        kw = dict(master=parent, text=text, command=cmd, variant=variant,
                  height=h)
        if width is not None:
            kw["width"] = width
        return PillButton(**kw)

    # CTkEntry вместо tk.Entry
    def _ent(self, parent, var=None, width=28, **kw):
        return _ctk_entry(parent, var=var, width_chars=width, **kw)


# ────────────────────────────────────────────────────────────────────
#                  SettingsDialogCtk
# ────────────────────────────────────────────────────────────────────

class SettingsDialogCtk(tk.Toplevel):
    """Настройки + профили — CTk-стиль."""

    def __init__(self, parent: "gui.App"):
        super().__init__(parent)
        self.title("Настройки")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        _safe_iconbitmap(self, ICON_DEFAULT)
        self._app = parent
        self._active = parent._active_profile

        _dialog_header(self, "Настройки", "Профили и обновления")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=14)

        tk.Label(body, text="ПРОФИЛИ", bg=BG_DEEP, fg=FG_LABEL,
                  font=("Segoe UI", 9, "bold")).pack(anchor="w",
                                                       pady=(0, 6))

        tabs_f = ctk.CTkFrame(body, fg_color="transparent")
        tabs_f.pack(fill="x")
        self._profile_btns: List[ctk.CTkButton] = []
        self._profile_names: List[tk.StringVar] = []
        for i in range(5):
            name = parent._profiles[i].get("name", f"Профиль {i + 1}")
            self._profile_names.append(tk.StringVar(value=name))
            is_active = (i == self._active)
            btn = ctk.CTkButton(
                tabs_f, text=f" {name} ",
                command=lambda idx=i: self._select(idx),
                fg_color=ACCENT if is_active else BG_INPUT,
                hover_color=ACCENT_H if is_active else BG_ROW_HOVER,
                text_color="white" if is_active else FG_DIM,
                corner_radius=CORNER_MD, height=28, width=70,
                font=("Segoe UI", 9),
            )
            btn.pack(side="left", padx=2)
            self._profile_btns.append(btn)

        ctk.CTkFrame(body, fg_color=DIVIDER, height=1).pack(fill="x",
                                                               pady=10)

        row_name = ctk.CTkFrame(body, fg_color="transparent")
        row_name.pack(fill="x", pady=(0, 4))
        tk.Label(row_name, text="Имя профиля:", bg=BG_DEEP, fg=FG,
                  font=("Segoe UI", 10)).pack(side="left")
        self._ent_name = _ctk_entry(row_name, width_chars=24)
        self._ent_name.pack(side="left", padx=(8, 0))
        self._ent_name.insert(0, self._profile_names[self._active].get())
        self._ent_name.bind("<KeyRelease>", self._on_name_change)

        ctk.CTkFrame(body, fg_color=DIVIDER, height=1).pack(fill="x",
                                                               pady=10)

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x")

        def switch_profile():
            new_name = self._ent_name.get().strip()
            if new_name:
                self._app._profiles[self._active]["name"] = new_name
            self._app._switch_profile(self._active)
            self.destroy()

        btn_switch = PillButton(btn_row, "Сохранить", icon="✓",
                                  variant="primary", command=switch_profile)
        btn_switch.pack(side="left")
        _bind_tip(btn_switch, "Сохранить и переключиться на профиль")

        def check_updates():
            self.destroy()
            parent._check_update(force=True)

        btn_update = PillButton(btn_row, "Проверить обновления", icon="🔄",
                                  variant="ghost", command=check_updates)
        btn_update.pack(side="right")
        _bind_tip(btn_update, "Проверить наличие новой версии")

        btn_close = PillButton(btn_row, "Закрыть", variant="ghost",
                                 command=self.destroy)
        btn_close.pack(side="right", padx=6)

        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        try:
            x = parent.winfo_x() + (parent.winfo_width() - w) // 2
            y = parent.winfo_y() + (parent.winfo_height() - h) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _select(self, idx):
        old_name = self._ent_name.get().strip()
        if old_name:
            self._app._profiles[self._active]["name"] = old_name
            self._profile_btns[self._active].configure(
                text=f" {old_name} ")
        self._active = idx
        self._ent_name.delete(0, "end")
        self._ent_name.insert(
            0, self._app._profiles[idx].get("name", f"Профиль {idx + 1}"))
        for i, btn in enumerate(self._profile_btns):
            is_a = (i == idx)
            btn.configure(
                fg_color=ACCENT if is_a else BG_INPUT,
                hover_color=ACCENT_H if is_a else BG_ROW_HOVER,
                text_color="white" if is_a else FG_DIM,
            )

    def _on_name_change(self, event=None):
        name = self._ent_name.get().strip()
        if name:
            self._profile_btns[self._active].configure(text=f" {name} ")


# ────────────────────────────────────────────────────────────────────
#                  ActivationWindowCtk
# ────────────────────────────────────────────────────────────────────

class ActivationWindowCtk(tk.Toplevel):
    """Активация лицензии — CTk-стиль."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("FTH Trade Copier — Активация")
        self.configure(bg=BG_DEEP)
        self.resizable(False, False)
        _safe_iconbitmap(self, ICON_DEFAULT)
        self._activated = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.grab_set()
        self._build()
        self._center_on_screen()

    def _on_close(self):
        if self._activated:
            self.destroy()
            return
        app = self.master
        self.destroy()
        try:
            app._real_quit()
        except Exception:
            pass
        os._exit(0)

    def _center_on_screen(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{sw // 2 - w // 2}+{sh // 2 - h // 2}")

    def _paste(self, event=None):
        try:
            clip = self.clipboard_get()
            if clip:
                widget = self.focus_get()
                if hasattr(widget, "insert"):
                    widget.insert("insert", clip)
        except Exception:
            pass
        return "break"

    def _on_ctrl_key(self, event=None):
        if event is not None and event.keycode == 86:
            return self._paste(event)

    def _ent(self, parent, var=None, width_chars=22):
        e = _ctk_entry(parent, var, width_chars)
        e.bind("<Control-v>", self._paste)
        e.bind("<Control-V>", self._paste)
        e.bind("<Control-KeyPress>", self._on_ctrl_key)
        return e

    def _build(self):
        _dialog_header(self, "Активация",
                       "Введите Telegram ID и код из бота")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=30, pady=20)

        logo_path = os.path.join(IMG_DIR, "convertico-fth_48x48.png")
        if os.path.exists(logo_path):
            try:
                img = tk.PhotoImage(file=logo_path)
                lbl_logo = tk.Label(body, image=img, bg=BG_DEEP)
                lbl_logo.image = img  # type: ignore[attr-defined]
                lbl_logo.grid(row=0, column=0, columnspan=2, pady=(0, 10))
            except Exception:
                pass

        tk.Label(body, text="Активация лицензии", bg=BG_DEEP, fg=ACCENT,
                  font=("Segoe UI", 14, "bold")).grid(
            row=1, column=0, columnspan=2, pady=(0, 15))

        # Telegram ID
        tk.Label(body, text="Telegram ID", bg=BG_DEEP, fg=FG_LABEL,
                  font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="w", pady=3)
        self.var_tg_id = tk.StringVar()
        self._ent(body, self.var_tg_id, 22).grid(
            row=2, column=1, sticky="ew", padx=(8, 0), pady=3)

        PillButton(body, "Получить код", variant="primary",
                    command=self._request_code).grid(
            row=3, column=0, columnspan=2, pady=(10, 4), sticky="ew")

        # Код
        tk.Label(body, text="Код из Telegram", bg=BG_DEEP, fg=FG_LABEL,
                  font=("Segoe UI", 9)).grid(
            row=4, column=0, sticky="w", pady=3)
        self.var_code = tk.StringVar()
        self._ent(body, self.var_code, 22).grid(
            row=4, column=1, sticky="ew", padx=(8, 0), pady=3)

        # Подтвердить
        btn_verify = PillButton(body, "Подтвердить", icon="✓",
                                  variant="primary", command=self._verify)
        # перекрашиваем в зелёный
        btn_verify.configure(fg_color=GREEN_DIM, hover_color=GREEN)
        btn_verify.grid(row=5, column=0, columnspan=2,
                         pady=(10, 4), sticky="ew")

        self.lbl_status = tk.Label(body, text="", bg=BG_DEEP, fg=FG_DIM,
                                     font=("Segoe UI", 9), wraplength=300)
        self.lbl_status.grid(row=6, column=0, columnspan=2, pady=(8, 0))

    def _request_code(self):
        tg = self.var_tg_id.get().strip()
        if not tg:
            self.lbl_status.config(text="Введите Telegram ID", fg=RED)
            return
        try:
            tg_id = int(tg)
        except ValueError:
            self.lbl_status.config(text="Telegram ID — только цифры",
                                    fg=RED)
            return
        if not _LIC_OK:
            self.lbl_status.config(text="Модуль лицензии не найден",
                                    fg=RED)
            return
        self.lbl_status.config(text="Отправка кода...", fg=FG_DIM)
        self.update()
        ok, msg = lic_mod.request_code(tg_id)
        if ok:
            self.lbl_status.config(
                text="Код отправлен в Telegram. Проверьте личные сообщения.",
                fg=GREEN_DIM)
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
            self.lbl_status.config(text="Telegram ID — только цифры",
                                    fg=RED)
            return
        if not _LIC_OK:
            self.lbl_status.config(text="Модуль лицензии не найден",
                                    fg=RED)
            return
        self.lbl_status.config(text="Проверка...", fg=FG_DIM)
        self.update()
        ok, result = lic_mod.verify_code(tg_id, code)
        if ok:
            self.lbl_status.config(text="Активация успешна!",
                                    fg=GREEN_DIM)
            self._activated = True
            self.after(500, self.destroy)
        elif result and str(result).startswith("device_limit"):
            max_d = str(result).split(":")[-1]
            self.lbl_status.config(
                text=(f"Лимит устройств ({max_d}) превышён.\n"
                      "Используйте /reset в боте для сброса."),
                fg=RED)
        else:
            self.lbl_status.config(text=f"Ошибка: {result}", fg=RED)


# ────────────────────────────────────────────────────────────────────
#                  monkey-patch helper
# ────────────────────────────────────────────────────────────────────

def install():
    """Подменяет ссылки в `gui` на CTk-варианты диалогов.

    После вызова `App._add_slave()`, `App._open_settings()` и т.д.
    автоматически используют новые классы — без оверрайдов в AppCtk.
    """
    gui.SymbolPickerDialog = SymbolPickerDialogCtk
    gui.SlaveDialog = SlaveDialogCtk
    gui.SettingsDialog = SettingsDialogCtk
    gui.ActivationWindow = ActivationWindowCtk
