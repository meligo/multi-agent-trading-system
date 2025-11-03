#!/bin/bash

cat << "EOF"
================================================================================
🔧 DATA COLLECTION FIX - QUICK VERIFICATION
================================================================================

This will verify the two critical fixes:
1. Database warm-start implementation
2. Correct initialization order (DataHub → WebSocket)

EOF

echo ""
read -p "Press ENTER to start the dashboard..."

# Kill existing processes
echo ""
echo "🛑 Stopping existing processes..."
pkill -f streamlit 2>/dev/null
sleep 2

# Create a temporary log file with timestamp
LOGFILE="/tmp/data_collection_fix_$(date +%Y%m%d_%H%M%S).log"

echo ""
echo "🚀 Starting dashboard with enhanced logging..."
echo "📝 Log file: $LOGFILE"
echo ""
echo "="*80
echo "WATCH FOR THESE NEW LOG LINES:"
echo "="*80
echo ""
echo "  ✅ DataHub manager started at 127.0.0.1:50000"
echo "  🔥 Warm-starting DataHub from database..."
echo "    ✅ EUR_USD: 100 candles loaded"
echo "    ✅ GBP_USD: 100 candles loaded"
echo "    ✅ USD_JPY: 100 candles loaded"
echo "  ✅ DataHub warm-start complete"
echo "  ✅ WebSocket collector started (connected to DataHub)"
echo ""
echo "="*80
echo "THEN:"
echo "="*80
echo ""
echo "  1. Click 'Force Start' button in dashboard"
echo "  2. Look for: candles=True, spread=X.X (NOT False!)"
echo "  3. Verify: No 'No candle data' warnings"
echo ""
echo "="*80
echo ""
echo "Starting in 3 seconds..."
sleep 3

cd /Users/meligo/multi-agent-trading-system
streamlit run scalping_dashboard.py 2>&1 | tee "$LOGFILE"
