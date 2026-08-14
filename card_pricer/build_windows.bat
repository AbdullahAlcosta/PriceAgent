@echo off
REM ============================================================
REM  BUILD SCRIPT - run this ONCE, on a Windows machine, to
REM  produce the final self-contained .exe for your client.
REM
REM  This is a developer-side script. Your CLIENT never runs
REM  this file and never sees it. After this finishes, you zip
REM  up the "dist\CardPricingAgent" folder and send THAT to
REM  your client -- it's fully self-contained (Python + the
REM  Chromium browser Playwright needs are both bundled inside).
REM ============================================================

cd /d "%~dp0"

echo ============================================
echo   Building Card Pricing Agent .exe
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Make sure Python 3.12 is installed and "Add Python to PATH" was checked during install.
    pause
    exit /b 1
)

python --version

echo [1/5] Creating build environment...
if exist build_venv rmdir /s /q build_venv
python -m venv build_venv
call build_venv\Scripts\activate.bat

echo [2/5] Installing dependencies + PyInstaller...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo ERROR during pip upgrade. See message above.
    pause
    exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR installing requirements.txt. See message above.
    pause
    exit /b 1
)

pip install pyinstaller
if errorlevel 1 (
    echo.
    echo ERROR installing PyInstaller. See message above.
    pause
    exit /b 1
)

echo [3/5] Downloading the Chromium browser Playwright will bundle...
set PW_BROWSERS_DIR=%~dp0pw-browsers
set PLAYWRIGHT_BROWSERS_PATH=%PW_BROWSERS_DIR%
playwright install chromium
if errorlevel 1 (
    echo.
    echo ERROR downloading Chromium. Check your internet connection and try again.
    pause
    exit /b 1
)

if not exist "%PW_BROWSERS_DIR%" (
    echo.
    echo ERROR: Chromium download folder not found at:
    echo   %PW_BROWSERS_DIR%
    echo Something went wrong with the playwright install step above.
    pause
    exit /b 1
)

echo [4/5] Building the .exe with PyInstaller...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

pyinstaller --noconfirm --onedir --console ^
    --name CardPricingAgent ^
    --add-data "%PW_BROWSERS_DIR%;ms-playwright" ^
    --hidden-import=playwright.sync_api ^
    launcher.py

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed. See message above.
    pause
    exit /b 1
)

if not exist "dist\CardPricingAgent\CardPricingAgent.exe" (
    echo.
    echo ERROR: Build finished but CardPricingAgent.exe was not created.
    echo Check the PyInstaller output above for the real error.
    pause
    exit /b 1
)

echo [5/5] Done!
echo.
echo ============================================
echo   Build complete.
echo ============================================
echo.
echo Your client-ready package is in:
echo   dist\CardPricingAgent\
echo.
echo Zip that whole folder and send it to your client.
echo They just unzip it and double-click CardPricingAgent.exe --
echo no Python, no pip, no separate browser download needed.
echo.
pause
