@echo off
chcp 65001 >nul
echo ============================================
echo   FTH Trade Copier — Сборка EXE (PyInstaller)
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

echo [1/2] Установка зависимостей...
"%PYTHON%" -m pip install -r requirements.txt pyinstaller
if %errorlevel% neq 0 (
    echo ОШИБКА: не удалось установить зависимости (см. текст ошибки выше)
    pause
    exit /b 1
)

echo.
echo [2/2] Сборка EXE по FTHTradeCopier.spec (1-2 минуты)...
"%PYTHON%" -m PyInstaller --noconfirm FTHTradeCopier.spec
if %errorlevel% neq 0 (
    echo ОШИБКА: сборка не удалась
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Готово! Файл: dist\FTHTradeCopier.exe
echo   Скопируйте его куда угодно и запускайте
echo ============================================
echo.
pause
