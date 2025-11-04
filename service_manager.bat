@echo off
REM =========================================
REM   Multi-Agent Trading System
REM   Service Manager for Windows
REM =========================================

setlocal enabledelayedexpansion

set "LOGS_DIR=logs"
set "PID_DIR=pids"

REM Color codes (limited in batch)
set "BLUE=[34m"
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "RESET=[0m"

REM Create directories if they don't exist
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
if not exist "%PID_DIR%" mkdir "%PID_DIR%"

REM Parse command
if "%1"=="" goto usage
if "%1"=="start" goto start_services
if "%1"=="stop" goto stop_services
if "%1"=="restart" goto restart_services
if "%1"=="status" goto show_status
goto usage

:usage
echo.
echo %BLUE%==========================================%RESET%
echo %BLUE%  Multi-Agent Trading System Manager%RESET%
echo %BLUE%==========================================%RESET%
echo.
echo Usage: service_manager.bat [command] [service]
echo.
echo Commands:
echo   start [all^|datahub^|websocket^|databento^|scalper^|dashboard]
echo   stop [all^|datahub^|websocket^|databento^|scalper^|dashboard]
echo   restart [all^|datahub^|websocket^|databento^|scalper^|dashboard]
echo   status
echo.
echo Examples:
echo   service_manager.bat start all
echo   service_manager.bat stop scalper
echo   service_manager.bat restart dashboard
echo   service_manager.bat status
echo.
exit /b 0

:start_services
if "%2"=="all" goto start_all
if "%2"=="datahub" goto start_datahub
if "%2"=="websocket" goto start_websocket
if "%2"=="databento" goto start_databento
if "%2"=="scalper" goto start_scalper
if "%2"=="dashboard" goto start_dashboard
echo %RED%Error: Unknown service '%2'%RESET%
goto usage

:start_all
echo.
echo %BLUE%==========================================%RESET%
echo %BLUE%  Starting All Services%RESET%
echo %BLUE%==========================================%RESET%
echo.
call :start_datahub
timeout /t 3 /nobreak >nul
call :start_websocket
timeout /t 3 /nobreak >nul
call :start_databento
timeout /t 3 /nobreak >nul
call :start_scalper
timeout /t 3 /nobreak >nul
call :start_dashboard
echo.
echo %GREEN%All services started!%RESET%
echo %BLUE%Dashboard URL: http://localhost:8505%RESET%
echo %BLUE%Logs directory: %LOGS_DIR%%RESET%
echo.
exit /b 0

:start_datahub
echo %BLUE%Starting datahub...%RESET%
start /B python start_datahub_server.py > "%LOGS_DIR%\datahub.log" 2>&1
echo %GREEN%datahub started%RESET%
exit /b 0

:start_websocket
echo %BLUE%Starting websocket...%RESET%
start /B python -u websocket_collector_modern.py > "%LOGS_DIR%\websocket.log" 2>&1
echo %GREEN%websocket started%RESET%
exit /b 0

:start_databento
echo %BLUE%Starting databento...%RESET%
start /B python -u start_databento_client.py > "%LOGS_DIR%\databento.log" 2>&1
echo %GREEN%databento started%RESET%
exit /b 0

:start_scalper
echo %BLUE%Starting scalper...%RESET%
start /B python scalping_cli.py --run > "%LOGS_DIR%\scalping_engine.log" 2>&1
echo %GREEN%scalper started%RESET%
exit /b 0

:start_dashboard
echo %BLUE%Starting dashboard...%RESET%
start /B streamlit run dashboard_v2.py --server.port 8505 > "%LOGS_DIR%\dashboard.log" 2>&1
echo %GREEN%dashboard started%RESET%
exit /b 0

:stop_services
if "%2"=="all" goto stop_all
echo %RED%Stopping individual services not yet implemented%RESET%
echo %RED%Use Task Manager or: taskkill /F /IM python.exe%RESET%
exit /b 1

:stop_all
echo.
echo %BLUE%==========================================%RESET%
echo %BLUE%  Stopping All Services%RESET%
echo %BLUE%==========================================%RESET%
echo.
echo %YELLOW%Stopping all Python processes...%RESET%
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM streamlit.exe >nul 2>&1
echo %GREEN%All services stopped!%RESET%
echo.
exit /b 0

:restart_services
echo %BLUE%Restarting services...%RESET%
call :stop_all
timeout /t 3 /nobreak >nul
call :start_all
exit /b 0

:show_status
echo.
echo %BLUE%==========================================%RESET%
echo %BLUE%  Service Status%RESET%
echo %BLUE%==========================================%RESET%
echo.

REM Check if Python processes are running
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo %GREEN%Python services: RUNNING%RESET%
    tasklist /FI "IMAGENAME eq python.exe"
) else (
    echo %RED%Python services: NOT RUNNING%RESET%
)

echo.
echo Recent log activity:
echo.
echo --- DataHub ---
if exist "%LOGS_DIR%\datahub.log" (
    powershell -Command "Get-Content '%LOGS_DIR%\datahub.log' -Tail 3"
) else (
    echo No log file
)
echo.
echo --- Scalper ---
if exist "%LOGS_DIR%\scalping_engine.log" (
    powershell -Command "Get-Content '%LOGS_DIR%\scalping_engine.log' -Tail 3"
) else (
    echo No log file
)
echo.
exit /b 0
