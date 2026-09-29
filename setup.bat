@echo off
echo ============================================
echo  Meal Monitoring Dashboard - Setup
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from https://python.org
    exit /b 1
)

:: Check Git
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git not found. Install Git from https://git-scm.com
    exit /b 1
)

:: Check HailoRT
hailortcli fw-control identify >nul 2>&1
if errorlevel 1 (
    echo WARNING: Hailo device not detected. Install HailoRT from https://hailo.ai/developer-zone/
    echo          Setup will continue, but the app won't run without HailoRT.
    echo.
)

:: Clone hailo-apps framework
if not exist "deps\hailo-apps" (
    echo Cloning hailo-apps framework...
    mkdir deps 2>nul
    git clone https://github.com/hailo-ai/hailo-apps.git deps\hailo-apps
) else (
    echo hailo-apps already cloned, skipping.
)

:: Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv --system-site-packages venv
) else (
    echo Virtual environment already exists, skipping.
)

:: Activate and install
echo Installing dependencies...
call venv\Scripts\activate.bat
pip install -e deps\hailo-apps

echo.
echo ============================================
echo  Setup complete!
echo ============================================
echo.
echo Next steps:
echo   1. Install HailoRT Python wheel (if not done):
echo      venv\Scripts\activate
echo      pip install path\to\hailort-X.XX.X-cpXXX-win_amd64.whl
echo.
echo   2. Run the app:
echo      run.bat
echo.
