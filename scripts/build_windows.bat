@echo off
rem ==============================================================================
rem orang3D - Windows Standalone Executable Export Script
rem Builds portable Windows x64 distribution bundle (dist\orang3d-windows-amd64.zip)
rem ==============================================================================

setlocal enabledelayedexpansion

echo ========================================================
echo Building orang3D Standalone Executable for Windows
echo ========================================================

rem Navigate to project root
cd /d "%~dp0\.."

rem Check python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH. Please install Python 3.10+ (x64).
    exit /b 1
)

rem Install pyinstaller and build if missing
python -m pip install --upgrade pyinstaller build

rem Run packaging engine
python scripts\build_executable.py --clean --archive %*

if %errorlevel% neq 0 (
    echo [ERROR] Windows build failed!
    exit /b %errorlevel%
)

echo ========================================================
echo Windows Build Completed Successfully!
echo Output zip located in: dist\
echo ========================================================

endlocal
