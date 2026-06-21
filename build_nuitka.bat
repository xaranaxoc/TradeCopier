@echo off
chcp 65001 >nul
echo ============================================
echo   FTH Trade Copier — Nuitka Build (onefile)
echo ============================================
echo.

set PYTHON=python

echo [1/3] Установка зависимостей...
%PYTHON% -m pip install nuitka ordered-set zstandard MetaTrader5 psutil pystray Pillow requests customtkinter
if %errorlevel% neq 0 (
    echo ОШИБКА: не удалось установить зависимости
    pause
    exit /b 1
)

echo.
echo [2/3] Компиляция Nuitka (5-15 мин, первый раз дольше — скачает MinGW)...
echo.

%PYTHON% -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=img/convertico-fth.ico ^
    --output-filename=FTHTradeCopier.exe ^
    --include-data-dir=img=img ^
    --include-data-dir=assets=assets ^
    --include-module=widgets ^
    --include-module=lucide ^
    --include-package-data=customtkinter ^
    --include-package-data=MetaTrader5 ^
    --enable-plugin=tk-inter ^
    --enable-plugin=numpy ^
    --include-module=copier ^
    --include-module=license ^
    --include-module=updater ^
    --include-module=ctk_compat ^
    --include-module=theme ^
    --include-module=palette ^
    --include-module=ui_scaling ^
    --include-module=psutil ^
    --include-module=pystray ^
    --include-module=pystray._win32 ^
    --include-module=PIL ^
    --include-module=PIL.Image ^
    --include-module=requests ^
    --include-module=MetaTrader5 ^
    --remove-output ^
    --output-dir=dist ^
    --assume-yes-for-downloads ^
    gui.py

if %errorlevel% neq 0 (
    echo ОШИБКА: сборка не удалась
    pause
    exit /b 1
)

echo.
echo [3/3] Готово!
echo ============================================
echo   Файл: dist\FTHTradeCopier.exe
echo ============================================
echo.
pause
