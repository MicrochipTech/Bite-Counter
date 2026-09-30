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

:: Clone hailo-apps framework (pinned to v26.03.1)
if not exist "deps\hailo-apps" (
    echo Cloning hailo-apps framework...
    mkdir deps 2>nul
    git clone --depth 1 --branch v26.03.1 https://github.com/hailo-ai/hailo-apps.git deps\hailo-apps
    if errorlevel 1 (
        echo Falling back to commit pin...
        git clone https://github.com/hailo-ai/hailo-apps.git deps\hailo-apps
        cd deps\hailo-apps
        git checkout 891ce70
        cd ..\..
    )
) else (
    echo hailo-apps already cloned, skipping.
)

:: Patch cython_bbox dependency (requires C++ compiler — use NumPy fallback instead)
echo Patching BYTETracker to remove C++ build dependency...
python patches\fix_cython_bbox.py

:: Create isolated virtual environment (no --system-site-packages to avoid version conflicts)
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
) else (
    echo Virtual environment already exists, skipping.
)

:: Activate and install
echo Installing dependencies...
call venv\Scripts\activate.bat
pip install -e deps\hailo-apps
pip install pillow pygrabber

echo.
echo ============================================
echo  Setup complete!
echo ============================================
echo.
echo IMPORTANT: Install the HailoRT Python wheel into this venv.
echo The wheel version MUST match your installed HailoRT runtime,
echo and the Python version (cp310, cp312, etc.) must match your Python.
echo.
echo   venv\Scripts\activate
echo   pip install path\to\hailort-X.XX.X-cpXXX-win_amd64.whl
echo.
echo To verify:
echo   python -c "from hailo_platform import VDevice; print('OK')"
echo.
echo Then run:  .\run.bat
echo.
