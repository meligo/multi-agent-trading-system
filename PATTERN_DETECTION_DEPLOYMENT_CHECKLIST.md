# Pattern Detection Deployment Checklist

## 🎯 Overview

This checklist ensures safe deployment of the professional pattern detection system (ORB, SFP, IMPULSE) into the live scalping engine.

**Based on GPT-5 Critical Review - January 2025**

---

## ✅ Pre-Deployment Checklist

### 1. Code Integration (COMPLETED ✅)

- [x] pattern_detectors.py created with ORB/SFP/IMPULSE detectors
- [x] pre_trade_gates.py implemented with 5 hard filters
- [x] FastMomentumAgent updated with tiered decision system
- [x] ScalpValidator updated to handle auto-approved patterns
- [x] All modules import without errors
- [x] Backward compatibility maintained (use_pattern_detection flag)

### 2. Critical Edge Cases (TO VERIFY ⚠️)

#### Data Quality
- [ ] **Partial candle protection**: Verify detectors only run on closed bars
- [ ] **Repainting prevention**: Ensure mid-bar updates don't flip scores
- [ ] **Stale data detection**: Block trading if price feed stale > 10 seconds
- [ ] **Missing ticks handling**: Detect gaps in OHLCV data

#### Time & Sessions
- [ ] **DST handling**: Test around DST switch dates (Mar/Nov)
- [ ] **Session boundaries**: Verify London/NY/Tokyo windows work across DST
- [ ] **Friday/Monday gaps**: Test behavior around weekend rollovers
- [ ] **Broker server time**: Confirm UTC vs broker time alignment

#### Units & Precision
- [ ] **Pip calculations**: Test EUR/USD (4-digit), USD/JPY (2-digit)
- [ ] **ATR normalization**: Verify ATR in pips across all 3 pairs
- [ ] **Spread units**: Confirm spread always in pips
- [ ] **HTF distance**: Verify distance calculations use consistent units

#### Signal Management
- [ ] **Duplicate prevention**: Add per-symbol signal fingerprinting
- [ ] **Cooldown periods**: Implement 5-min cooldown after trade/stop-out
- [ ] **Concurrency locks**: Add per-symbol lock in analyze()
- [ ] **Idempotency**: Ensure order submission uses unique trade IDs

#### LLM Pathway
- [ ] **Timeout handling**: 60s timeout on LLM calls (already set)
- [ ] **Retry logic**: Max 2 retries (already set)
- [ ] **Fallback behavior**: Default reject if LLM unavailable
- [ ] **Schema validation**: Strict JSON parsing with error handling

### 3. Safety Checks (TO IMPLEMENT ⚠️)

#### Circuit Breakers (CRITICAL)
- [ ] **Daily loss limit**: -2% max (check ScalpingConfig)
- [ ] **Consecutive losses**: Max 5 (check ScalpingConfig)
- [ ] **Daily trade limit**: 40/day (check ScalpingConfig)
- [ ] **Spread spike breaker**: Pause if spread > 2.5 pips or > 3×ATR

#### Canary Constraints (Week 1)
- [ ] **Symbol restriction**: Only EUR/USD, GBP/USD initially
- [ ] **Session restriction**: Only London core + NY core (no Tokyo)
- [ ] **Friday/Monday blocks**: Disable first/last hour Friday, first hour Monday
- [ ] **Position sizing**: 0.05 lots max during canary period

#### Execution Validation
- [ ] **Stop distance check**: SL ≥ broker minimum (typically 1-2 pips)
- [ ] **TP distance check**: TP ≥ broker minimum
- [ ] **Position size check**: ≤ 0.3 lots per trade
- [ ] **Pre-execution sanity**: Verify all values before order submission

### 4. Configuration Updates (TO DO 📝)

#### Enable Shadow Mode
```python
# In scalping_engine.py or initialization:
FastMomentumAgent(
    llm=llm,
    use_pattern_detection=True,
    shadow_mode=True  # Enable for Week 1
)
```

#### Adjust Thresholds (Conservative Start)
```python
# Consider raising auto-approve threshold for Week 1:
# - Auto-approve: ≥88 (instead of ≥85)
# - LLM validation: 70-87 (instead of 70-84)
```

#### Add Cooldown Config
```python
# scalping_config.py
PATTERN_DETECTION = {
    'use_pattern_detection': True,
    'shadow_mode': True,
    'auto_approve_threshold': 88,  # Conservative
    'llm_validation_min': 70,
    'llm_validation_max': 87,
    'pattern_weights': {
        'pattern': 0.7,
        'momentum': 0.3
    },
    'cooldown_seconds': 300,  # 5 min cooldown per symbol
}
```

### 5. Logging & Monitoring (TO IMPLEMENT 📊)

#### Pattern Performance Metrics
```python
# Log for each trade:
{
    'timestamp': datetime,
    'symbol': str,
    'pattern_type': 'ORB'|'SFP'|'IMPULSE',
    'pattern_score': 0-100,
    'momentum_score': 0-100,
    'final_score': 0-100,
    'tier': '<60'|'60-69'|'70-84'|'≥85',
    'auto_approved': bool,
    'llm_called': bool,
    'llm_latency_ms': int,
    'gate_results': {
        'spread': pass/fail,
        'atr_regime': pass/fail,
        'session': pass/fail,
        'news': pass/fail,
        'htf_distance': pass/fail
    },
    'entry_spread': float,
    'slippage': float,
    'outcome': 'win'|'loss'|'breakeven',
    'pnl_pips': float,
    'mae_pips': float,  # Max Adverse Excursion
    'mfe_pips': float   # Max Favorable Excursion
}
```

#### Aggregate Metrics (Track Daily)
- **Score bucket distribution**: Count by <60, 60-69, 70-84, ≥85
- **Win rate by pattern**: ORB, SFP, IMPULSE win rates
- **Win rate by score range**: 70-74, 75-79, 80-84, 85-89, 90+
- **Gate rejection reasons**: Count by gate type
- **LLM usage**: % of signals calling LLM, avg latency
- **Shadow comparison**: Pattern vs LLM agreement rate

#### Alerts to Configure
- Spike in rejections for single gate (>80% in 1 hour)
- LLM error rate >10% in 15 minutes
- Score distribution collapse (80%+ in single bucket)
- Slippage >2 pips on >50% of fills
- Any circuit breaker triggered

### 6. Testing Protocol (BEFORE LIVE 🧪)

#### Unit Tests
- [ ] **Threshold boundaries**: Test exact 59.9, 60, 69.9, 70, 84.9, 85
- [ ] **Float precision**: Ensure no rounding surprises in comparisons
- [ ] **DST switch**: Test session gates on DST change dates
- [ ] **ORB first bar**: Test behavior on session's first candle

#### Integration Tests
- [ ] **End-to-end flow**: Pattern detection → gates → scoring → LLM → validator
- [ ] **Rejection paths**: Test all rejection scenarios (gates, low score, spread)
- [ ] **Auto-approve path**: Test ≥85 score without LLM call
- [ ] **Shadow mode**: Verify both systems run in parallel

#### Replay Testing (CRITICAL)
- [ ] **3-month replay**: Run pattern detector on historical 1m data
- [ ] **Score calibration**: Build calibration curves (score → win rate)
- [ ] **Gate statistics**: Measure rejection rates by gate type
- [ ] **Performance simulation**: Estimate expected trades/day, win rate, P&L

---

## 🚀 Deployment Plan (3-Week Canary)

### Week 1: 100% Shadow Mode
**Goal:** Collect calibration data without trading

**Configuration:**
- `shadow_mode=True`
- All 3 pairs (EUR/USD, GBP/USD, USD/JPY)
- All sessions (London, NY, Tokyo)
- No live orders executed

**Metrics to Validate:**
- Pattern detection rate (expect ~20-30 signals/day)
- Score distribution (should be bell curve, not skewed)
- LLM latency (should be <2s p95)
- Gate rejection reasons (spread should be ~20-30%)
- Shadow decisions vs current system (agreement rate)

**Go/No-Go for Week 2:**
- [ ] Score distribution looks reasonable
- [ ] No major bugs/crashes in pattern detectors
- [ ] LLM latency acceptable
- [ ] At least 50 shadow signals collected for analysis

### Week 2: Canary Live (Conservative)
**Goal:** Trade with strict constraints

**Configuration:**
- `shadow_mode=False`
- `auto_approve_threshold=88` (conservative)
- **Only EUR/USD and GBP/USD**
- **Only London + NY core sessions**
- **Max 0.05 lots per trade**
- **Daily loss limit: -1%** (stricter than normal -2%)
- **Max 10 trades/day** (stricter than normal 40)

**Metrics to Validate:**
- Win rate by score bucket (70-79, 80-87, 88+)
- Expected value per pattern type
- Slippage vs backtested expectations
- LLM override rate (should be <20%)
- Auto-approve performance (should have >60% win rate)

**Go/No-Go for Week 3:**
- [ ] Overall win rate ≥55%
- [ ] Auto-approved trades (≥88) have win rate ≥60%
- [ ] No unexplained losses >2 pips from slippage
- [ ] System stable (no crashes/hangs)

### Week 3+: Full Deployment
**Goal:** Gradually expand to full capacity

**Configuration:**
- Add USD/JPY (Tokyo session)
- Lower auto-approve threshold to 85 (if Week 2 data supports)
- Increase position size to 0.1 lots
- Expand daily trade limit to 20, then 30, then 40
- Expand daily loss limit to -2%

**Ongoing Monitoring:**
- Weekly review of calibration curves
- Monthly pattern performance audit
- Threshold adjustments based on data

---

## 📋 Final Pre-Launch Checklist

### Code & Config
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Shadow mode enabled by default
- [ ] Conservative thresholds set (88 for auto-approve)
- [ ] Canary constraints configured (symbols, sessions, size)

### Safety
- [ ] Circuit breakers enabled and tested
- [ ] Idempotent order submission confirmed
- [ ] Per-symbol locks implemented
- [ ] Stale data detection active
- [ ] LLM fallback behavior = reject

### Monitoring
- [ ] Pattern performance logging active
- [ ] Gate rejection logging active
- [ ] Tier pipeline metrics logging active
- [ ] Latency tracking active
- [ ] Alert rules configured and tested

### Documentation
- [ ] Version and git commit tagged
- [ ] Config parameters documented
- [ ] Detector versions logged
- [ ] Deployment plan shared with stakeholders
- [ ] Rollback plan documented

### Validation
- [ ] 3-month replay completed
- [ ] Calibration curves generated
- [ ] Expected trades/day estimated
- [ ] Risk per trade calculated
- [ ] Worst-case scenario modeled

---

## 🔄 Rollback Plan

**If Week 1 shadow mode shows issues:**
- Continue shadow mode, fix issues, restart Week 1

**If Week 2 canary shows negative expectancy:**
- Disable pattern detection (`use_pattern_detection=False`)
- Revert to original LLM-only system
- Analyze shadow logs to identify issues
- Re-calibrate thresholds or detector logic

**Emergency stop conditions:**
- 10 consecutive losses with pattern detection
- Win rate <40% over 50+ trades
- System crash/hang requiring restart >2 times/day
- LLM unavailable >30% of the time

**Rollback command:**
```bash
# Disable pattern detection immediately
python -c "
from scalping_config import ScalpingConfig
ScalpingConfig.USE_PATTERN_DETECTION = False
print('✅ Pattern detection DISABLED - reverted to LLM-only')
"

# Restart scalping engine
./service_manager.sh restart scalper
```

---

## 📊 Success Criteria (4-Week Review)

After 4 weeks of deployment:

**Minimum Acceptable Performance:**
- [ ] Overall win rate ≥55%
- [ ] Auto-approved (≥85) win rate ≥60%
- [ ] LLM-validated (70-84) win rate ≥50%
- [ ] Expected value per trade ≥0.5 pips (after spread)
- [ ] System uptime ≥99%

**Ideal Performance:**
- [ ] Overall win rate ≥60%
- [ ] Auto-approved win rate ≥65%
- [ ] 75% reduction in LLM usage vs original system
- [ ] 50% faster decisions (via auto-approve lane)
- [ ] Expected value per trade ≥1.0 pips

**If success criteria met:**
- Declare pattern detection system production-ready
- Disable shadow mode
- Consider expanding to more pairs/timeframes

**If success criteria not met:**
- Analyze failure modes
- Re-calibrate thresholds
- Consider per-symbol calibration
- May revert to LLM-only if no path to profitability

---

## 📝 Notes

**Created:** January 2025
**Last Updated:** January 2025
**Status:** Pre-deployment
**Next Review:** After Week 1 shadow mode

**Critical Contacts:**
- Pattern Detection Issues: Check logs/scalping_agents.log
- Gate Failures: Check logs/pre_trade_gates.log
- LLM Issues: Check logs/scalping_engine.log

**Emergency Commands:**
```bash
# Check current status
tail -f logs/scalping_agents.log | grep "Pattern"

# View gate rejections
grep "Gates failed" logs/pre_trade_gates.log | tail -20

# Monitor auto-approvals
grep "AUTO-APPROVE" logs/scalping_agents.log | tail -20

# Disable pattern detection (emergency)
# Edit scalping_engine.py, set use_pattern_detection=False
./service_manager.sh restart scalper
```
