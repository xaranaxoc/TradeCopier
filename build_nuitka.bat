@echo off
chcp 65001 >nul
echo ============================================
echo   FTH Trade Copier — Nuitka Build
echo ============================================
echo.

REM --- Поиск Python: сначала привычный путь, иначе python из PATH ---
set "PYTHON=C:\Users\bu4ukeec\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не найден. Укажите путь к python.exe в переменной PYTHON
    echo в начале build_nuitka.bat либо добавьте Python в PATH.
    pause
    exit /b 1
)
echo Использую Python:
"%PYTHON%" --version
echo.

echo [1/2] Установка зависимостей...
"%PYTHON%" -m pip install -r requirements.txt nuitka ordered-set zstandard pystray
if %errorlevel% neq 0 (
    echo ОШИБКА: не удалось установить зависимости (см. текст ошибки выше)
    pause
    exit /b 1
)

echo.
echo [2/2] Компиляция Nuitka (5-15 мин, первый раз дольше — скачает MinGW)...
echo.

"%PYTHON%" -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=img/convertico-fth.ico ^
    --output-filename=FTHTradeCopier.exe ^
    --include-data-dir=img=img ^
    --include-data-files=fth_theme.json=fth_theme.json ^
    --enable-plugin=tk-inter ^
    --enable-plugin=numpy ^
    --include-package=customtkinter ^
    --include-package-data=customtkinter ^
    --include-module=theme ^
    --include-module=ui_kit ^
    --include-module=copier ^
    --include-module=license ^
    --include-module=psutil ^
    --include-module=pystray ^
    --include-module=pystray._win32 ^
    --include-module=PIL ^
    --include-module=PIL.Image ^
    --include-module=requests ^
    --include-module=MetaTrader5 ^
    --output-dir=dist ^
    --assume-yes-for-downloads ^
    gui.py

if %errorlevel% neq 0 (
    echo ОШИБКА: сборка не удалась
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Готово! Файл: dist\FTHTradeCopier.exe
echo ============================================
echo.
pause
