# Scalping Engine - Fast Momentum Scalping System

**Branch**: `scalper-engine`
**Version**: 1.0
**Date**: 2025-10-31

## 🎯 Overview

This is a complete implementation of a **10-20 minute fast momentum scalping system** built on the same multi-agent architecture as the main trading system but optimized for high-frequency scalping.

### Key Features

- ⚡ **Fast Analysis**: 1-minute timeframe, 60-second scan interval
- 🎯 **Tight Targets**: 10 pip TP / 6 pip SL (1.67:1 R:R)
- ⏱️  **20-Minute Auto-Close**: All trades force-closed at 20 minutes
- 📊 **3 Pairs Only**: EUR/USD, GBP/USD, USD/JPY (lowest spreads)
- 🛡️  **Spread Protection**: Reject trades if spread > 1.2 pips
- ⏰ **Trading Hours**: 08:00-20:00 GMT (London + NY sessions)
- 🤖 **2-Agent + Judge**: Maintains proven debate structure

---

## 🏗️ Architecture

### Agent System (Mirrors code.ipynb structure)

**Phase 1: Entry Analysis**
```
Fast Momentum Agent  →
                        ↘
                          Scalp Validator (JUDGE) → Approved Setup
                        ↗
Technical Agent      →
```

**Phase 2: Risk Management**
```
Aggressive Risk Agent  →
                           ↘
                             Risk Manager (JUDGE) → Final Decision
                           ↗
Conservative Risk Agent →
```

### Components

1. **scalping_config.py** - All strategy parameters
2. **scalping_agents.py** - 6 AI agents with debate structure
3. **scalping_engine.py** - Main orchestration engine
4. **scalping_cli.py** - Command-line interface

---

## 📋 Implementation Checklist

Based on `SCALPING_STRATEGY_ANALYSIS.md`:

### ✅ Critical Changes (System Won't Work Without These)

- [x] **Trade Duration Auto-Exit** ⭐⭐⭐
  - 20-minute force-close implemented in `monitor_trades()`
  - Checks every 30 seconds for duration timeout
  - Logs exit reason as "MAX_DURATION"

- [x] **Profit/Loss Targets Overhaul** ⭐⭐⭐
  - Changed from 40/20 to 10/6 pips (TP/SL)
  - 1.67:1 Risk:Reward ratio
  - Configurable in `ScalpingConfig`

- [x] **Spread Becomes CRITICAL** ⭐⭐⭐
  - Max spread: 1.2 pips (reject above)
  - Spread checked before EVERY trade
  - Position size reduced if spread 1.0-1.2 pips
  - Real-time spread verification

- [x] **Analysis Frequency** ⭐⭐⭐
  - Changed from 5-minute to 1-minute scans
  - 60-second analysis interval
  - Fast enough for scalping without overwhelming API

### ✅ High-Priority Changes

- [x] **Pair Selection** ⭐⭐
  - Reduced from 24 pairs to 3 pairs
  - EUR/USD, GBP/USD, USD/JPY only
  - All have spreads 0.6-1.5 pips

- [x] **Trading Hours** ⭐⭐
  - Strict 08:00-20:00 GMT enforcement
  - `is_trading_hours()` checks every cycle
  - Avoids low-liquidity Asian session

- [x] **Claude Validator Speed** ⭐⭐
  - Using GPT-4 with 3-second timeout
  - Fast enough for 1-minute cycles
  - Can be switched to "background" mode if needed

### ✅ Nice-to-Have Changes

- [x] **Trailing Stops** - Configurable (TRAILING_STOP_ENABLED)
- [x] **Tiered Position Sizing** - Tier 1/2/3 based on setup quality
- [x] **Daily Trade Limits** - Max 40 trades/day, max 2 open positions
- [x] **Real-Time Spread Monitor** - Checked before every trade
- [ ] **WebSocket Data** - Not implemented (1-min REST API sufficient)

### ✅ Things Removed

- [x] **Multi-Timeframe Confirmation** - Now uses 1-minute only
- [x] **Complex Indicators** - Removed Ichimoku, ADX, divergence, FVG, VPVR
- [x] **Low-Liquidity Pairs** - Removed all except EUR/USD, GBP/USD, USD/JPY

### ✅ New Components

- [x] **Auto-Close Timer System** - Monitors every 30 seconds
- [x] **Rapid Entry Signal Generator** - Fast Momentum Agent
- [x] **Daily Trade Limits** - Comprehensive tracking
- [x] **Risk Controls** - Consecutive loss pause, daily loss limit

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.8+
pip install langchain langchain-openai openai python-dotenv

# Required environment variables in .env:
OPENAI_API_KEY=your_key_here
IG_API_KEY=your_ig_key
IG_USERNAME=your_username
IG_PASSWORD=your_password
IG_ACC_NUMBER=your_account_number
IG_DEMO=true  # Set to false for live trading
```

### Installation

```bash
# Switch to scalper-engine branch
git checkout scalper-engine

# Install dependencies (if not already)
pip install -r requirements.txt
```

### Usage

**1. View Configuration**
```bash
python scalping_cli.py --config
```

**2. Test Analysis (No Trading)**
```bash
python scalping_cli.py --test EUR_USD
```

**3. Run Scalping Engine (Demo Mode)**
```bash
python scalping_cli.py --run
```

**4. Validate Configuration**
```bash
python scalping_cli.py --validate
```

---

## ⚙️ Configuration

Edit `scalping_config.py` to customize:

```python
# Trade Parameters
TAKE_PROFIT_PIPS = 10.0       # Target
STOP_LOSS_PIPS = 6.0          # Stop loss
MAX_TRADE_DURATION_MINUTES = 20  # Force close

# Spread Limits
MAX_SPREAD_PIPS = 1.2         # Reject if wider
IDEAL_SPREAD_PIPS = 0.8       # Full size

# Pairs
SCALPING_PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY"]

# Trading Hours
TRADING_START_TIME = time(8, 0)   # 08:00 GMT
TRADING_END_TIME = time(20, 0)    # 20:00 GMT

# Daily Limits
MAX_TRADES_PER_DAY = 40
MAX_OPEN_POSITIONS = 2
MAX_DAILY_LOSS_PERCENT = 1.5

# Position Sizing
TIER1_SIZE = 0.2  # High confidence (100%)
TIER2_SIZE = 0.15 # Medium confidence (75%)
TIER3_SIZE = 0.0  # Skip low confidence
```

---

## 📊 Expected Performance

### Realistic Targets (Based on Analysis)

**Per Trade (0.1 lot)**:
- Winning trade: 8 pips = $8.00
- Losing trade: 5 pips = -$5.00
- Spread cost: 1.5 pips = -$1.50
- Net win: $6.50 per winning trade
- Net loss: -$6.50 per losing trade

**Daily Performance (60% win rate, 40 trades/day)**:
- 24 wins × $6.50 = $156.00
- 16 losses × -$6.50 = -$104.00
- **Net daily profit: $52.00/day**
- **Monthly profit: $1,040/month** (20 trading days)

**Key Metrics**:
- Minimum win rate required: **60%**
- Spread eats **15-25%** of gross profits
- Higher frequency = higher stress
- Need tight risk management

---

## 🎓 Comparison to Main System

| Feature | Main System | Scalping Engine |
|---------|-------------|-----------------|
| **Timeframe** | 5-minute | 1-minute |
| **Trade Duration** | Hours | 10-20 minutes |
| **TP/SL** | 40/20 pips | 10/6 pips |
| **Pairs** | 24 forex + 4 commodities | 3 forex only |
| **Scan Interval** | 5 minutes | 60 seconds |
| **Max Trades/Day** | Unlimited | 40 |
| **Trading Hours** | 24/5 | 12 hours (08:00-20:00 GMT) |
| **Spread Limit** | 2-3 pips OK | Max 1.2 pips |
| **Agents** | 4 analysts + debate | 2 + judge (simplified) |
| **Structure** | Bull/Bear + Risk debate | Momentum/Technical + Risk |

---

## 🔍 Code Structure

### Main Files

```
scalping_config.py       - Strategy configuration (272 lines)
scalping_agents.py       - 6 AI agents with debate structure (623 lines)
scalping_engine.py       - Main orchestration engine (586 lines)
scalping_cli.py          - Command-line interface (252 lines)
```

### Key Classes

**scalping_agents.py**:
- `FastMomentumAgent` - Analyzes 1-minute momentum
- `TechnicalAgent` - Validates technical structure
- `ScalpValidator` - **JUDGE**: Approves/rejects setups
- `AggressiveRiskAgent` - Push for larger positions
- `ConservativeRiskAgent` - Protect capital
- `RiskManager` - **JUDGE**: Final position sizing

**scalping_engine.py**:
- `ScalpingEngine` - Main orchestrator
- `ActiveTrade` - Trade record with P&L tracking
- `DailyStats` - Daily performance tracking

---

## 🧪 Testing

### Manual Testing

**Test Single Pair**:
```bash
python scalping_cli.py --test EUR_USD
```

This will:
1. Fetch 1-minute data for EUR/USD
2. Run full agent analysis
3. Show if setup is approved
4. Simulate risk management
5. Display what position size would be taken

**Expected Output**:
```
📊 Analyzing EUR_USD...
🚀 Fast Momentum Agent analyzing...
🔧 Technical Agent analyzing...
⚖️  Scalp Validator (Judge) deciding...
   ✅ APPROVED: BUY EUR_USD
   Confidence: 75%, Tier: 1

⚠️  RISK MANAGEMENT DEBATE
💪 Aggressive Risk Agent...
🛡️  Conservative Risk Agent...
⚖️  Risk Manager (Judge)...
   ✅ WOULD EXECUTE: 0.20 lots
```

### Paper Trading

1. Set `IG_DEMO=true` in `.env`
2. Run: `python scalping_cli.py --run`
3. Monitor for at least 1 week
4. Analyze results before going live

---

## ⚠️ Warnings & Considerations

### 1. Spread Cost Reality
- With 10-pip targets and 1.5-pip spreads, **15%** of every winning trade goes to spread
- Need **58%+ win rate** just to break even
- Commission costs add additional drag

### 2. Trade Frequency Stress
- 40 trades/day means a trade every 15-20 minutes
- Requires constant monitoring
- Higher psychological pressure
- More potential for mistakes

### 3. Broker Limitations
Check IG Markets policies:
- Maximum trades per day?
- Scalping restrictions?
- Commission structure for high frequency?

### 4. Risk of Overtrading
- More trades ≠ more profit
- Quality over quantity
- **Daily loss limits are CRITICAL**
- System will pause after 5 consecutive losses

---

## 📈 Monitoring & Logs

### Real-Time Monitoring

The engine provides detailed logging:
```
📊 Analyzing EUR_USD at 14:23:15
🚀 Fast Momentum Agent analyzing...
   Result: EMA_BREAKOUT - BUY
🔧 Technical Agent analyzing...
   Result: Supports trade
⚖️  Scalp Validator (Judge) deciding...
   ✅ APPROVED: BUY EUR_USD
   Confidence: 78%, Tier: 1

⚠️  RISK MANAGEMENT DEBATE
   ✅ WOULD EXECUTE: 0.20 lots

✅ TRADE EXECUTED: EUR_USD_142320
   BUY EUR_USD @ 1.08450
   TP: 1.08550 | SL: 1.08390
   Size: 0.20 lots
   Max Duration: 20 minutes
```

### Daily Summary

At end of session:
```
📊 DAILY SUMMARY
Trades: 32
Wins: 20
Losses: 12
Win Rate: 62.5%
Total P&L: +1.2%
```

---

## 🔧 Troubleshooting

### Common Issues

**1. "Spread too wide" errors**
- Normal during low-liquidity hours
- System correctly rejects bad entries
- Wait for London/NY sessions

**2. "No tradeable setup found"**
- System is working correctly
- Better to miss trades than take bad ones
- Scalping requires HIGH probability setups

**3. "Daily trade limit reached"**
- Hit 40 trades for the day
- This is a safety feature
- Review performance before adjusting limit

**4. Agent timeout errors**
- Claude/GPT taking too long
- Increase `CLAUDE_TIMEOUT_SECONDS` in config
- Or switch to "background" mode

---

## 🚀 Future Enhancements

### Phase 2 (Optional)

- [ ] WebSocket integration for real-time data
- [ ] Advanced trailing stops (ATR-based)
- [ ] ML-based entry signal optimization
- [ ] Backtesting framework
- [ ] Live performance dashboard (web UI)
- [ ] Multi-account support
- [ ] Telegram alerts

### Backtest Integration

To integrate with existing backtest framework:
```python
from scalping_engine import ScalpingEngine
from backtesting import Backtest

# TODO: Implement ScalpStrategy class
# bt = Backtest(data, ScalpStrategy)
# results = bt.run()
```

---

## 📚 References

- **Main System**: See `main.py` for swing trading implementation
- **Strategy Analysis**: See `SCALPING_STRATEGY_ANALYSIS.md` for full requirements
- **Original Architecture**: See `code.ipynb` for multi-agent design
- **Forex Config**: See `forex_config.py` for IG API setup

---

## 🤝 Contributing

This is a specialized implementation. To modify:

1. **Change strategy parameters**: Edit `scalping_config.py`
2. **Adjust agent logic**: Edit `scalping_agents.py`
3. **Modify execution flow**: Edit `scalping_engine.py`
4. **Add features**: Create feature branch from `scalper-engine`

---

## 📝 License

Same as main project.

---

## ✅ Verification Checklist

From `SCALPING_STRATEGY_ANALYSIS.md` and `code.ipynb`:

- [x] Uses 2-agent + judge structure (like Bull/Bear + Manager)
- [x] Maintains debate-based decision making
- [x] Implements 20-minute auto-close timer
- [x] Enforces spread limits (< 1.2 pips)
- [x] Restricts to 3 pairs (EUR/USD, GBP/USD, USD/JPY)
- [x] Uses 1-minute timeframe
- [x] 10 pip TP / 6 pip SL targets
- [x] Trading hours 08:00-20:00 GMT
- [x] Daily trade limits (40/day)
- [x] Risk management (consecutive losses, daily loss)
- [x] Real-time spread checking
- [x] Simplified indicators (EMA, RSI, BB)
- [x] Position sizing tiers
- [x] Comprehensive logging

---

**Status**: ✅ COMPLETE
**Ready for Testing**: Paper trading recommended before live deployment
**Branch**: `scalper-engine`
**Next Steps**: Test with IG demo account for 1-2 weeks

---

*Generated: 2025-10-31*
*Version: 1.0*
*Maintainer: Multi-Agent Trading System Team*
