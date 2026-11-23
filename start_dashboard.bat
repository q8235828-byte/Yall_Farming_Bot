@echo off
echo ======================================================================
echo    YALLA LUDO BOT - ENTERPRISE DASHBOARD & CONTROL CENTER
echo ======================================================================
echo [*] Checking dependencies...
python -c "import flask, uiautomator2, cv2, numpy" >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Installing required dashboard dependencies...
    pip install flask uiautomator2 opencv-python numpy
)

echo [*] Launching Dashboard Server on http://127.0.0.1:5000 ...
python "%~dp0dashboard\server.py"
pause
