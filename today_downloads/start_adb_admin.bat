@echo off
set LOGFILE=%~dp0start_adb.log
echo Starting ADB setup at %date% %time% > "%LOGFILE%"

:: Check for Administrator privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Not running as Administrator. Requesting elevation... >> "%LOGFILE%"
    powershell -Command "Start-Process '%~f0' -ArgumentList 'elevated' -Verb RunAs"
    exit /b
)

echo [+] Elevated privileges confirmed (Administrator). >> "%LOGFILE%"

echo [*] Registering WinUSB ADB DeviceInterfaceGUID for all Motorola devices... >> "%LOGFILE%"
reg add "HKLM\SYSTEM\CurrentControlSet\Enum\USB\VID_22B8&PID_2E84&MI_01\6&33e827bf&0&0001\Device Parameters" /v DeviceInterfaceGUID /t REG_SZ /d "{F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}" /f >> "%LOGFILE%" 2>&1
reg add "HKLM\SYSTEM\CurrentControlSet\Enum\USB\VID_22B8&PID_2E76&MI_01\6&b29bf27&0&0001\Device Parameters" /v DeviceInterfaceGUID /t REG_SZ /d "{F72FE0D4-CBCB-407D-8814-9ED673D0DD6B}" /f >> "%LOGFILE%" 2>&1
pnputil /restart-device "USB\VID_22B8&PID_2E84&MI_01\6&33E827BF&0&0001" >> "%LOGFILE%" 2>&1
pnputil /restart-device "USB\VID_22B8&PID_2E76&MI_01\6&B29BF27&0&0001" >> "%LOGFILE%" 2>&1
pnputil /restart-device "USB\VID_22B8&PID_2E84\ZY22KNB2KW" >> "%LOGFILE%" 2>&1
pnputil /restart-device "USB\VID_22B8&PID_2E76\ZY22KNB2KW" >> "%LOGFILE%" 2>&1

cd /d "%~dp0platform-tools"

echo [1/3] Killing existing ADB instances... >> "%LOGFILE%"
taskkill /F /IM adb.exe >> "%LOGFILE%" 2>&1
adb.exe kill-server >> "%LOGFILE%" 2>&1

echo [2/3] Starting ADB server... >> "%LOGFILE%"
set ADB_TRACE=all
adb.exe start-server >> "%LOGFILE%" 2>&1

echo [3/3] Listing devices: >> "%LOGFILE%"
adb.exe devices -l >> "%LOGFILE%" 2>&1

echo Done at %time% >> "%LOGFILE%"
type "%LOGFILE%"
echo.
echo ========================================================
echo Check phone screen: Agar "Allow USB debugging" aye to
echo "Always allow" tick kar k OK karein.
echo ========================================================
pause
