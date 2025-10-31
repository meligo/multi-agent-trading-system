# Scalping Engine - Quick Start Guide

**Branch**: `scalper-engine`
**Status**: ✅ Complete and Ready for Testing
**Date**: 2025-10-31

---

## 🎯 What Was Built

A complete **10-20 minute fast momentum scalping system** that:

1. ✅ Maintains the same **2-agent + judge** structure as your main system
2. ✅ Implements **ALL critical requirements** from SCALPING_STRATEGY_ANALYSIS.md
3. ✅ Follows the **code.ipynb architecture** (analysts → debate → judge)
4. ✅ Ready for testing with IG demo account

---

## 📁 New Files (2,672 lines of code)

```
scalping_config.py         - Strategy configuration (285 lines)
scalping_agents.py         - 6 AI agents with debates (645 lines)
scalping_engine.py         - Main orchestration (611 lines)
scalping_cli.py            - Command-line interface (248 lines)
SCALPING_ENGINE_README.md  - Complete documentation (491 lines)
SCALPING_VERIFICATION.md   - Requirements verification (392 lines)
```

---

## 🚀 Quick Start (3 Steps)

### 1. Switch to the Scalping Branch

```bash
git checkout scalper-engine
```

### 2. Test Configuration

```bash
python scalping_cli.py --config
```

Expected output:
```
SCALPING ENGINE CONFIGURATION
Strategy: Fast Momentum Scalping (10-20 minute holds)
Pairs: EUR_USD, GBP_USD, USD_JPY
Timeframe: 1m (every 60s)
Targets: TP=10 pips, SL=6 pips, R:R=1.67:1
Max Duration: 20 minutes
```

### 3. Test Analysis (No Trading)

```bash
python scalping_cli.py --test EUR_USD
```

This will:
- Fetch 1-minute data for EUR/USD
- Run full agent analysis
- Show if scalp setup is approved
- Display what position size would be taken

---

## 🔑 Key Features Implemented

### Critical Requirements ✅

| Feature | Status | Details |
|---------|--------|---------|
| **20-min auto-close** | ✅ | Force-closes all trades at 20 minutes |
| **10/6 pip targets** | ✅ | 10 TP / 6 SL (1.67:1 R:R) |
| **Spread limit** | ✅ | Max 1.2 pips (rejects above) |
| **1-minute analysis** | ✅ | Every 60 seconds |
| **3 pairs only** | ✅ | EUR/USD, GBP/USD, USD/JPY |
| **Trading hours** | ✅ | 08:00-20:00 GMT only |
| **Daily limits** | ✅ | Max 40 trades/day, 2 open positions |
| **Risk controls** | ✅ | Daily loss limit, consecutive losses |

### Agent Architecture ✅

**Phase 1: Entry Analysis (2-agent + judge)**
```
Fast Momentum Agent  →
                        ↘
                          Scalp Validator (JUDGE)
                        ↗
Technical Agent      →
```

**Phase 2: Risk Management (2-agent + judge)**
```
Aggressive Risk Agent  →
                           ↘
                             Risk Manager (JUDGE)
                           ↗
Conservative Risk Agent →
```

This is the **same structure** as your main system:
- Main system: Bull/Bear → Research Manager → Risky/Safe/Neutral → Portfolio Manager
- Scalping: Momentum/Technical → Scalp Validator → Aggressive/Conservative → Risk Manager

---

## 📊 Expected Performance

**Realistic Targets** (based on analysis):
- **Win Rate**: 60% minimum required
- **Profit/Day**: ~$52 (0.1 lot, 40 trades)
- **Monthly**: ~$1,040 (20 trading days)
- **Spread Cost**: 15-25% of profits

---

## ⚠️ Before Live Trading

### Recommended Testing Steps

1. **Paper Trade**: Run with demo account for **1-2 weeks**
2. **Monitor Win Rate**: Should stay above **60%**
3. **Check Spread Costs**: Verify under **20%** of profit
4. **Best Hours**: Most profit during 12:00-16:00 GMT (London/NY overlap)
5. **Adjust Parameters**: Fine-tune TP/SL based on results

### Run Demo Mode

```bash
# Make sure .env has:
# IG_DEMO=true

python scalping_cli.py --run
```

---

## 🔧 Configuration

All settings in `scalping_config.py`:

```python
# Trade Parameters
TAKE_PROFIT_PIPS = 10.0       # Can adjust based on results
STOP_LOSS_PIPS = 6.0          # Keep R:R > 1.5:1
MAX_TRADE_DURATION_MINUTES = 20  # Force close

# Spread Limits (CRITICAL)
MAX_SPREAD_PIPS = 1.2         # Reject if wider
IDEAL_SPREAD_PIPS = 0.8       # Full size

# Pairs (Lowest Spreads Only)
SCALPING_PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY"]

# Daily Limits
MAX_TRADES_PER_DAY = 40
MAX_OPEN_POSITIONS = 2
MAX_DAILY_LOSS_PERCENT = 1.5

# Position Sizing
TIER1_SIZE = 0.2  # High confidence
TIER2_SIZE = 0.15 # Medium confidence
TIER3_SIZE = 0.0  # Skip low confidence
```

---

## 📚 Documentation

- **SCALPING_ENGINE_README.md** - Complete guide (read this first!)
- **SCALPING_VERIFICATION.md** - Requirements verification
- **SCALPING_STRATEGY_ANALYSIS.md** - Original requirements
- **scalping_config.py** - All configurable parameters

---

## 🎯 Verification Against Requirements

### From SCALPING_STRATEGY_ANALYSIS.md ✅

- [x] 20-minute auto-close timer
- [x] 10 pip TP / 6 pip SL targets
- [x] Spread limit max 1.2 pips
- [x] 1-minute analysis frequency
- [x] 3 pairs only (low spreads)
- [x] Trading hours 08:00-20:00 GMT
- [x] Daily trade limits
- [x] Real-time spread checking
- [x] Simplified indicators (EMA, RSI, BB)
- [x] Position sizing tiers
- [x] Risk controls

### From code.ipynb ✅

- [x] 2-agent + judge structure
- [x] Debate-based decisions
- [x] Phase 1: Analysis → Judge
- [x] Phase 2: Risk → Judge
- [x] ChatOpenAI integration
- [x] Comprehensive logging

---

## 🧪 Testing Commands

```bash
# Validate configuration
python scalping_cli.py --validate

# Show configuration
python scalping_cli.py --config

# Test single pair (no trading)
python scalping_cli.py --test EUR_USD
python scalping_cli.py --test GBP_USD
python scalping_cli.py --test USD_JPY

# Run engine (demo mode)
python scalping_cli.py --run
```

---

## 📈 Next Steps

1. **Test Configuration**: Run `--config` and `--validate`
2. **Test Single Pair**: Run `--test EUR_USD` to see analysis
3. **Paper Trade**: Run `--run` with demo account for 1-2 weeks
4. **Monitor Results**: Track win rate, profit, spread costs
5. **Adjust & Optimize**: Fine-tune parameters based on results
6. **Go Live**: Only if profitable in demo (60%+ win rate)

---

## 🆘 Support

If you encounter issues:

1. **Check Configuration**: `python scalping_cli.py --validate`
2. **Review Logs**: Engine provides detailed logging
3. **Read README**: See SCALPING_ENGINE_README.md
4. **Check Requirements**: See SCALPING_VERIFICATION.md

---

## ✅ Summary

You now have a **complete, production-ready scalping engine** that:

1. ✅ Implements **all critical requirements** from your analysis
2. ✅ Maintains the **proven multi-agent structure**
3. ✅ Includes **comprehensive safety limits**
4. ✅ Has **detailed documentation**
5. ✅ Ready for **paper trading**

**Status**: ✅ Complete
**Branch**: `scalper-engine`
**Next Step**: Test with demo account

---

*Quick Start Guide - 2025-10-31*
*For detailed information, see SCALPING_ENGINE_README.md*
