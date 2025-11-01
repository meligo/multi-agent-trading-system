#!/bin/bash

# Scalping Engine Dashboard Launcher
# Auto-starts all services and launches dashboard

echo "⚡ Starting Scalping Engine Dashboard..."
echo "======================================="
echo ""

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "✅ Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "✅ Activating virtual environment..."
    source .venv/bin/activate
else
    echo "⚠️  No virtual environment found. Using system Python."
fi

# Check Python dependencies
echo ""
echo "Checking dependencies..."
python3 -c "import streamlit" 2>/dev/null || {
    echo "❌ Streamlit not installed. Installing..."
    pip install streamlit plotly pandas numpy
}

python3 -c "import plotly" 2>/dev/null || {
    echo "❌ Plotly not installed. Installing..."
    pip install plotly
}

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export LANGCHAIN_TRACING_V2=false  # Disable LangSmith for speed

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  WARNING: .env file not found!"
    echo "Please create .env with your API keys:"
    echo "  - OPENAI_API_KEY=your_key"
    echo "  - IG_API_KEY=your_key"
    echo "  - IG_USERNAME=your_username"
    echo "  - IG_PASSWORD=your_password"
    echo "  - IG_ACC_NUMBER=your_account"
    echo ""
    read -p "Press Enter to continue anyway..."
fi

echo ""
echo "🚀 Launching Scalping Dashboard..."
echo "Dashboard will open in your browser automatically"
echo ""
echo "📊 Features:"
echo "  ✅ Real-time WebSocket data (1-minute)"
echo "  ✅ Auto-start engines"
echo "  ✅ Optimized indicators (EMA, VWAP, Donchian, RSI(7), ADX(7))"
echo "  ✅ Agent debates and signals"
echo "  ✅ 20-minute trade timer"
echo "  ✅ Spread monitoring"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo "======================================="
echo ""

# Launch Streamlit dashboard
streamlit run scalping_dashboard.py \
    --server.port 8502 \
    --server.headless false \
    --browser.gatherUsageStats false \
    --theme.base dark \
    --theme.primaryColor "#00ff00" \
    --theme.backgroundColor "#0e1117" \
    --theme.secondaryBackgroundColor "#262730"
