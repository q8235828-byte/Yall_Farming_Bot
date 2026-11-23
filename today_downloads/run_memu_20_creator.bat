@echo off
title YALLA LUDO MEMU 20-INSTANCE HIGH-SPEED CREATOR
cd /d "%~dp0"

echo ======================================================================
echo    YALLA LUDO HIGH-SPEED MEMU MULTI-INSTANCE (20x) ORCHESTRATOR
echo ======================================================================
echo  - Auto-scans MEmu instances (Ports 21503 to 21693)
echo  - Calibrates 1080x2400 (DPI 480) display resolution
echo  - Rotates live verified IPs via GitHub Proxy Pool (monosans/TheSpeedX)
echo  - Randomizes Android ID & device fingerprint
echo  - Concurrent Multi-Threading Execution
echo ======================================================================
echo.

python yalla_multi_worker.py %*

echo.
echo ======================================================================
echo Execution finished. Check created_accounts.csv for generated accounts.
echo ======================================================================
pause
