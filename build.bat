@echo off
chcp 65001 >nul
echo ============================================
echo   FTH Trade Copier — Сборка EXE
echo ============================================
echo.

REM --- Поиск Python: сначала привычный путь, иначе python из PATH ---
set "PYTHON=C:\Users\bu4ukeec\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Python не найден. Укажите путь к python.exe в переменной PYTHON
    echo в начале build.bat либо добавьте Python в PATH.
    pause
    exit /b 1
)
echo Использую Python:
"%PYTHON%" --version
echo.

echo [1/3] Установка зависимостей...
"%PYTHON%" -m pip install -r requirements.txt pyinstaller
if %errorlevel% neq 0 (
    echo ОШИБКА: не удалось установить зависимости (см. текст ошибки выше)
    pause
    exit /b 1
)

echo.
echo [2/3] Сборка EXE (может занять 1-2 минуты)...
"%PYTHON%" -m PyInstaller --onefile --windowed --name FTHTradeCopier --icon=img/convertico-fth.ico --add-data "img;img" --add-data "fth_theme.json;." --collect-all customtkinter --collect-all MetaTrader5 --collect-all numpy --hidden-import customtkinter --hidden-import theme --hidden-import ui_kit --hidden-import copier --hidden-import license --hidden-import updater --hidden-import psutil --hidden-import tkinter --hidden-import tkinter.ttk --hidden-import tkinter.filedialog --hidden-import tkinter.messagebox --hidden-import pystray --hidden-import pystray._win32 --hidden-import six gui.py

if %errorlevel% neq 0 (
    echo ОШИБКА: сборка не удалась
    pause
    exit /b 1
)

echo.
echo [3/3] Готово!
echo ============================================
echo   Файл: dist\FTHTradeCopier.exe
echo   Скопируйте его куда угодно и запускайте
echo ============================================
echo.
pause