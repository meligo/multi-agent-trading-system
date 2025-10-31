@echo off
REM Start IG Real Trading Dashboard (Windows)
REM This launches the Streamlit dashboard which will automatically start the trading worker

echo ==================================
echo IG REAL TRADING DASHBOARD
echo ==================================
echo.
echo Starting dashboard on http://localhost:8501
echo.
echo WARNING:
echo - Dashboard starts in SIGNAL-ONLY mode (no auto-trading)
echo - Click 'Start' button in sidebar to begin scanning
echo - Enable 'Auto-Trading' checkbox to execute REAL trades
echo.
echo Press Ctrl+C to stop
echo.

REM Launch Streamlit
streamlit run ig_trading_dashboard.py --server.port 8501 --server.headless true
