@echo off
chcp 65001 >nul
echo ============================================
echo   FTH Trade Copier — Nuitka Build (standalone/portable)
echo ============================================
echo.

REM --- Python path ---
set "PYTHON=C:\Users\bu4ukeec\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не найден
    pause
    exit /b 1
)

echo [1/3] Установка зависимостей...
"%PYTHON%" -m pip install -r requirements.txt nuitka ordered-set zstandard pystray Pillow
if %errorlevel% neq 0 (
    echo ОШИБКА: не удалось установить зависимости
    pause
    exit /b 1
)

echo.
echo [2/3] Компиляция Nuitka standalone (5-15 мин)...
echo.

"%PYTHON%" -m nuitka ^
    --standalone ^
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
echo [3/3] Переименование папки...
if exist "dist\FTHTradeCopier" rmdir /s /q "dist\FTHTradeCopier"
rename "dist\gui.dist" "FTHTradeCopier"
if %errorlevel% neq 0 (
    echo ВНИМАНИЕ: не удалось переименовать gui.dist ^> FTHTradeCopier
    echo Папка сборки: dist\gui.dist
) else (
    echo Папка: dist\FTHTradeCopier
)

echo.
echo ============================================
echo   Готово! Portable: dist\FTHTradeCopier\
echo   EXE: dist\FTHTradeCopier\FTHTradeCopier.exe
echo ============================================
echo.
pause
