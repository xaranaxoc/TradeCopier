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

echo [1/4] Установка зависимостей...
"%PYTHON%" -m pip install -r requirements.txt nuitka ordered-set zstandard pystray Pillow numpy
if %errorlevel% neq 0 (
    echo ОШИБКА: не удалось установить зависимости
    pause
    exit /b 1
)

echo.
echo [2/4] Определение пути numpy...
for /f "delims=" %%i in ('"%PYTHON%" -c "import numpy, os; print(os.path.dirname(numpy.__file__))"') do set "NUMPY_DIR=%%i"
if not exist "%NUMPY_DIR%" (
    echo ОШИБКА: numpy не найден
    pause
    exit /b 1
)
echo numpy: %NUMPY_DIR%

echo.
echo [2b/4] Определение пути MetaTrader5...
for /f "delims=" %%i in ('"%PYTHON%" -c "import MetaTrader5, os; print(os.path.dirname(MetaTrader5.__file__))"') do set "MT5_DIR=%%i"
if not exist "%MT5_DIR%" (
    echo ОШИБКА: MetaTrader5 не найден
    pause
    exit /b 1
)
echo MetaTrader5: %MT5_DIR%

echo.
echo [3/4] Компиляция Nuitka standalone (5-15 мин)...
echo.

"%PYTHON%" -m nuitka ^
    --standalone ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=img/convertico-fth.ico ^
    --output-filename=FTHTradeCopier.exe ^
    --include-data-dir=img=img ^
    --include-data-dir=assets=assets ^
    --include-data-dir="%NUMPY_DIR%=numpy" ^
    --include-data-dir="%MT5_DIR%=MetaTrader5" ^
    --include-module=widgets ^
    --include-module=lucide ^
    --include-package-data=customtkinter ^
    --enable-plugin=tk-inter ^
    --include-module=copier ^
    --include-module=copier_worker ^
    --include-module=license ^
    --include-module=updater ^
    --include-module=ctk_compat ^
    --include-module=theme ^
    --include-module=palette ^
    --include-module=ui_scaling ^
    --include-package=psutil ^
    --include-module=pystray ^
    --include-module=pystray._win32 ^
    --include-module=PIL ^
    --include-module=PIL.Image ^
    --include-module=requests ^
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
echo [3b/4] Копирование MetaTrader5 __init__.py...
if not exist "dist\gui.dist\MetaTrader5" mkdir "dist\gui.dist\MetaTrader5"
copy /Y "%MT5_DIR%\__init__.py" "dist\gui.dist\MetaTrader5\__init__.py" >nul

echo.
echo [4/4] Переименование папки...
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
