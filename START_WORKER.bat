@echo off
echo ========================================
echo  Forex Trading System - Worker
echo ========================================
echo.
echo Starting concurrent worker...
echo Analyzing all pairs every 60 seconds
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

python concurrent_worker.py

pause
