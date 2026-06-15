# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build spec for FTH Trade Copier.
#
# Сборка (на Windows):
#     pip install -r requirements.txt pyinstaller
#     pyinstaller --noconfirm FTHTradeCopier.spec
#
# Результат: dist\FTHTradeCopier.exe (один файл, всё внутри).
#
# Почему spec, а не длинная команда: customtkinter тащит за собой data-ассеты
# (тема dark-blue.json + шрифт CustomTkinter_shapes_font.otf). Без них собранный
# exe падает на старте. collect_all('customtkinter') собирает их автоматически.

from PyInstaller.utils.hooks import collect_all

# customtkinter: его JSON-темы, шрифт фигур и подмодули
ctk_datas, ctk_binaries, ctk_hidden = collect_all('customtkinter')

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=ctk_binaries,
    datas=ctk_datas + [
        ('fth_theme.json', '.'),   # наша CTk-тема
        ('img', 'img'),            # иконки окна и трея
    ],
    hiddenimports=ctk_hidden + [
        # собственные модули проекта (импортируются динамически в try/except)
        'theme', 'ui_kit', 'copier', 'license', 'updater',
        # рантайм-зависимости
        'customtkinter', 'psutil', 'requests',
        'MetaTrader5',
        'pystray', 'pystray._win32',
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
        'PIL', 'PIL.Image', 'PIL.ImageTk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FTHTradeCopier',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                      # --windowed: без чёрного окна консоли
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='img/convertico-fth.ico',
)
