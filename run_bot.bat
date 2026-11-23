@echo off
echo ======================================================================
echo    YALLA LUDO BOT - AUTO-SYNC FROM GITHUB & LAUNCHER
echo ======================================================================
echo [*] Pulling latest code updates from GitHub...
git pull origin main
echo.
echo [*] Starting Yalla Automation Pipeline with parameters: %*
python "today_downloads/qaiser new test/master_pipeline.py" %*
