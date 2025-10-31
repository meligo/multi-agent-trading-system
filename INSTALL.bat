@echo off
echo ========================================
echo  Forex Trading System - Installation
echo ========================================
echo.
echo Installing Python dependencies...
echo This may take a few minutes...
echo.

pip install -r requirements.txt

echo.
echo ========================================
echo Installation complete!
echo ========================================
echo.
echo Next steps:
echo 1. Create .env file with your API keys
echo 2. Run START_DASHBOARD.bat
echo.
pause
