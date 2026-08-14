@echo off
REM Card Pricing Agent -- double-click launcher for Windows.
REM First run: sets everything up (takes a few minutes).
REM Every run after: starts instantly.

cd /d "%~dp0"

set VENV_DIR=venv
set SETUP_MARKER=%VENV_DIR%\.setup_complete

if not exist "%SETUP_MARKER%" (
    echo ==========================================
    echo   First-time setup -- this only happens once
    echo ==========================================
    echo.

    where python >nul 2>nul
    if errorlevel 1 (
        echo Python isn't installed on this computer.
        echo Please install it from https://www.python.org/downloads/
        echo IMPORTANT: check "Add Python to PATH" during install.
        echo Then run this file again.
        pause
        exit /b 1
    )

    echo Setting up ^(this can take a few minutes^)...
    python -m venv "%VENV_DIR%"
    call "%VENV_DIR%\Scripts\activate.bat"
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    playwright install chromium

    echo done > "%SETUP_MARKER%"
    echo.
    echo Setup complete!
    echo.
) else (
    call "%VENV_DIR%\Scripts\activate.bat"
)

python launcher.py
