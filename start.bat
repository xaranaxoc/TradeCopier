@echo off
rem ============================================================
rem  Trade Copier — запуск без консоли (через pythonw.exe).
rem  Если запускать gui.py напрямую через py.exe или python.exe,
rem  Windows открывает чёрное окно консоли с предупреждениями
rem  CustomTkinter. pythonw.exe — это тот же интерпретатор, но
rem  без attached console.
rem ============================================================
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYW=C:\Users\bu4ukeec\AppData\Local\Programs\Python\Python314\pythonw.exe"

rem Fallback chain: if our pinned pythonw is missing, try the py
rem launcher in -w mode, then plain pythonw on PATH.
if exist "%PYW%" (
    start "" "%PYW%" "%SCRIPT_DIR%gui.py"
    goto :eof
)

where pyw >nul 2>&1
if %errorlevel% == 0 (
    start "" pyw "%SCRIPT_DIR%gui.py"
    goto :eof
)

where pythonw >nul 2>&1
if %errorlevel% == 0 (
    start "" pythonw "%SCRIPT_DIR%gui.py"
    goto :eof
)

echo Не нашёл pythonw.exe / pyw.exe — установи Python с галкой "Add to PATH" или подправь путь в start.bat
pause
