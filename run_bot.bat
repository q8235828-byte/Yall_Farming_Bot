@echo off
setlocal enabledelayedexpansion

echo ======================================================================
echo    YALLA LUDO BOT - SYSTEM ENVIRONMENT CHECK & AUTO-LAUNCHER
echo ======================================================================

:: 1. CHECK PYTHON
echo [*] Checking Python installation...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python is NOT installed or NOT added to system PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [+] Python Detected: !PY_VER! [OK]

:: 2. CHECK & AUTO-LOCATE ADB
echo [*] Checking ADB (Android Debug Bridge)...
where adb >nul 2>nul
if %errorlevel% equ 0 (
    echo [+] System ADB Detected in PATH [OK]
) else (
    echo [!] ADB not found in system PATH. Checking local project tools...
    if exist "%~dp0today_downloads\platform-tools\adb.exe" (
        echo [+] Local Portable ADB found in project folder!
        set "PATH=%~dp0today_downloads\platform-tools;!PATH!"
        echo [+] Local ADB added to current session PATH [OK]
    ) else if exist "C:\Program Files\Microvirt\MEmu\adb.exe" (
        echo [+] MEmu built-in ADB detected!
        set "PATH=C:\Program Files\Microvirt\MEmu;!PATH!"
    ) else (
        echo [WARNING] ADB could not be found automatically!
        echo Please ensure MEmu is running or ADB is installed.
    )
)

:: 3. CHECK REQUIRED PYTHON LIBRARIES
echo [*] Checking required Python dependencies...
python -c "import uiautomator2, cv2, numpy" >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Missing Python packages detected. Auto-installing dependencies...
    pip install uiautomator2 opencv-python numpy
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies via pip.
        pause
        exit /b 1
    )
    echo [+] Dependencies installed successfully [OK]!
) else (
    echo [+] All required libraries (uiautomator2, opencv, numpy) verified [OK]
)

:: 4. AUTO-SYNC FROM GITHUB
echo.
echo [*] Checking for online updates from GitHub...
where git >nul 2>nul
if %errorlevel% equ 0 (
    git pull origin main
) else (
    echo [!] Git not in PATH, skipping online sync.
)

:: 5. LAUNCH AUTOMATION PIPELINE
echo.
echo ======================================================================
echo [*] Starting Yalla Automation Pipeline with parameters: %*
echo ======================================================================
python "%~dp0today_downloads\qaiser new test\master_pipeline.py" %*

if %errorlevel% neq 0 (
    echo.
    echo [!] Script exited with code %errorlevel%.
)
