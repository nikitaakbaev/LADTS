@echo off
setlocal

set "ROOT=%~dp0.."
pushd "%ROOT%"

rem Reuse existing broker if WebSocket listener (:9001) is already up.
set "NEED_BROKER=1"
netstat -an | findstr ":9001" | findstr "LISTENING" >nul
if not errorlevel 1 (
    set "NEED_BROKER=0"
    echo [start-all] :9001 already listening, reusing existing broker
)

rem If only :1883 is bound it's the default Mosquitto Windows service —
rem warn the user, since it has no WebSocket and the dashboard won't work.
if "%NEED_BROKER%"=="1" (
    netstat -an | findstr ":1883" | findstr "LISTENING" >nul
    if not errorlevel 1 (
        echo [start-all] WARNING: Windows mosquitto service holds :1883 without WebSocket.
        echo [start-all]          Run as Administrator: net stop mosquitto
        echo [start-all]          and then re-run this script.
        pause
        exit /b 1
    )
)

rem Prefer Windows Terminal — opens 3 tabs in one window.
where wt.exe >nul 2>&1
if not errorlevel 1 (
    if "%NEED_BROKER%"=="1" (
        start "" wt -w 0 new-tab --title "broker"    powershell -NoExit -ExecutionPolicy Bypass -File "%ROOT%\scripts\run_broker.ps1" ^
            ; new-tab --title "simulator" powershell -NoExit -ExecutionPolicy Bypass -File "%ROOT%\scripts\run_simulator.ps1" ^
            ; new-tab --title "dashboard" powershell -NoExit -ExecutionPolicy Bypass -File "%ROOT%\scripts\run_dashboard.ps1"
    ) else (
        start "" wt -w 0 new-tab --title "simulator" powershell -NoExit -ExecutionPolicy Bypass -File "%ROOT%\scripts\run_simulator.ps1" ^
            ; new-tab --title "dashboard" powershell -NoExit -ExecutionPolicy Bypass -File "%ROOT%\scripts\run_dashboard.ps1"
    )
    timeout /t 4 /nobreak >nul
    start "" "http://localhost:8080"
    popd
    endlocal
    exit /b 0
)

rem Fallback for systems without Windows Terminal — separate windows.
echo [start-all] wt.exe not found, falling back to separate windows
if "%NEED_BROKER%"=="1" (
    start "LADTS broker" powershell -NoExit -ExecutionPolicy Bypass -File "scripts\run_broker.ps1"
    timeout /t 3 /nobreak >nul
)
start "LADTS simulator" powershell -NoExit -ExecutionPolicy Bypass -File "scripts\run_simulator.ps1"
timeout /t 1 /nobreak >nul
start "LADTS dashboard" powershell -NoExit -ExecutionPolicy Bypass -File "scripts\run_dashboard.ps1"
timeout /t 1 /nobreak >nul
start "" "http://localhost:8080"

popd
endlocal
