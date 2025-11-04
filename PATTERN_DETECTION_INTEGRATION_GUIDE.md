# Pattern Detection Integration Guide

## 🎯 Overview

This guide documents the complete integration of professional pattern detection (ORB, SFP, IMPULSE) with the existing multi-agent scalping system.

**Status:** Pattern detection and pre-trade gates complete. Agent integration in progress.

---

## 📦 Completed Components

### 1. `pattern_detectors.py` (1,040 lines) ✅
Professional pattern detection with ATR-normalized thresholds:

**ORB (Opening Range Breakout)**
- 10-minute OR window
- Retest logic (3-bar timeout)
- Volume z-score confirmation (≥1.0)
- Dynamic OR width validation (1.2-4.0×ATR)

**SFP (Stop-Hunt/Failed Pattern)**
- Pivot detection (3L/3R within 30 bars)
- 1-3 bar reclaim requirement
- Wick/body quality scoring

**IMPULSE (Momentum Continuation)**
- 3-bar or single-candle detection
- 15-38% pullback requirement
- Rejection candle confirmation

**Scoring System**
- Pattern Quality: 40/100
- Structure/Location: 35/100
- Volatility/Activity: 25/100
- Threshold: ≥70 to approve

### 2. `pre_trade_gates.py` (470 lines) ✅
Hard filters that must pass before trading:

1. **Spread Gate**: ≤1.5 pips (25% of 6-pip stop)
2. **ATR Regime Gate**: ATR ≥ 5-6 pips, ratio ≥ 0.6
3. **Session Gate**: London (07:00-10:30), NY (13:30-16:00), Tokyo (00:00-02:00 for JPY)
4. **HTF Distance Gate**: ≥6 pips to next resistance/support
5. **News Gate**: Block 5 min before to 10 min after major releases

---

## 🏗️ Integration Architecture (GPT-5 Recommended)

### Tiered Decision System

```
┌─────────────────────────────────────────────────────────┐
│               PRE-TRADE GATES (Central)                 │
│  Spread | ATR | Session | News | HTF Distance           │
└──────────────┬──────────────────────────────────────────┘
               │
          Gates Pass?
               │
      ┌────────┴────────┐
      NO                YES
      │                 │
      v                 v
 ┌─────────┐      ┌──────────────────┐
 │ REJECT  │      │ Pattern Detection│
 │ (Log    │      │  ORB/SFP/IMPULSE │
 │  only)  │      └────────┬──────────┘
 └─────────┘               │
                           v
                    Pattern Score?
                           │
           ┌───────────────┼───────────────┐
           │               │               │
        < 60            60-69          70-84         ≥85
           │               │               │          │
           v               v               v          v
       REJECT          REJECT         Call LLM    Auto-Approve
      (Low Score)    (Borderline)   (Borderline)  (High Score)
                                         │
                                    LLM Confirms?
                                    │          │
                                   YES        NO
                                    │          │
                                APPROVE    REJECT
```

### Decision Thresholds

```python
# From GPT-5 analysis
THRESHOLDS = {
    'REJECT_BELOW': 60,
    'BORDERLINE': (60, 69),  # Log but don't trade
    'LLM_REQUIRED': (70, 84),  # Call LLM for validation
    'AUTO_APPROVE': 85  # Skip LLM (fast path)
}

# Red flags that require LLM even if score ≥85:
RED_FLAGS = [
    'news_proximity_warning',
    'opposite_htf_bias',
    'major_htf_sr_close',
    'abnormal_spread_spike',
    'conflicting_correlations'
]
```

---

## 🔄 Integration Steps

### Step 1: Add Pattern Detection to Fast Momentum Agent

Add to `scalping_agents.py` imports:
```python
from pattern_detectors import get_best_pattern, detect_all_patterns, PatternDetection
from pre_trade_gates import check_all_gates, GateResult
from datetime import datetime
```

Update `FastMomentumAgent.__init__`:
```python
def __init__(self, llm: ChatOpenAI, use_pattern_detection: bool = True, shadow_mode: bool = False):
    self.llm = llm
    self.name = "Fast Momentum Agent"
    self.use_pattern_detection = use_pattern_detection
    self.shadow_mode = shadow_mode  # Run both systems, log comparison
```

Update `FastMomentumAgent.analyze`:
```python
def analyze(self, market_data: Dict) -> Dict:
    """
    Enhanced with professional pattern detection.

    Modes:
    - use_pattern_detection=False: Original LLM-only behavior
    - use_pattern_detection=True, shadow_mode=True: Run both, log comparison
    - use_pattern_detection=True, shadow_mode=False: Tiered integration
    """
    pair = market_data['pair']
    current_price = market_data['current_price']
    data = market_data.get('data')  # DataFrame with OHLCV
    spread = market_data.get('spread', 0)

    if not self.use_pattern_detection:
        # Original LLM-only path
        return self._analyze_llm_only(market_data)

    # 1. Check pre-trade gates
    gates_passed, gate_results = check_all_gates(
        data=data,
        pair=pair,
        current_spread=spread,
        current_time=datetime.utcnow()
    )

    # 2. Run pattern detection (even if gates failed, for logging)
    best_pattern = get_best_pattern(data, pair) if data is not None else None

    # 3. Gates failed? Reject but log pattern
    if not gates_passed:
        failed_gates = [r.gate_name for r in gate_results if not r.passed]
        logger.info(f"❌ Gates failed for {pair}: {failed_gates}")

        return {
            'setup_type': 'NONE',
            'direction': 'NONE',
            'pattern_score': best_pattern.score if best_pattern else 0,
            'momentum_score': None,
            'final_score': 0,
            'confidence': 0,
            'reasoning': [r.reason for r in gate_results if not r.passed],
            'blocked_by_gates': True,
            'gates_failed': failed_gates,
            'pattern_detected': best_pattern.pattern_type if best_pattern else 'NONE'
        }

    # 4. No pattern or score too low?
    if not best_pattern or best_pattern.score < 60:
        logger.info(f"❌ No valid pattern for {pair} (score: {best_pattern.score if best_pattern else 0})")

        return {
            'setup_type': 'NONE',
            'direction': 'NONE',
            'pattern_score': best_pattern.score if best_pattern else 0,
            'momentum_score': None,
            'final_score': best_pattern.score if best_pattern else 0,
            'confidence': 0,
            'reasoning': ['No pattern detected with score ≥60'],
            'blocked_by_gates': False
        }

    # 5. Borderline (60-69)? Reject but log
    if 60 <= best_pattern.score < 70:
        logger.info(f"⚠️ Borderline pattern for {pair}: {best_pattern.pattern_type} (score: {best_pattern.score})")

        return {
            'setup_type': best_pattern.pattern_type,
            'direction': best_pattern.direction,
            'pattern_score': best_pattern.score,
            'momentum_score': None,
            'final_score': best_pattern.score,
            'confidence': best_pattern.confidence,
            'reasoning': best_pattern.reasoning + ['Score 60-69: Borderline, rejected'],
            'blocked_by_gates': False,
            'entry': best_pattern.entry_price,
            'stop': best_pattern.stop_loss,
            'target': best_pattern.take_profit
        }

    # 6. High score (≥85)? Auto-approve (skip LLM unless red flags)
    if best_pattern.score >= 85:
        # Check for red flags
        has_red_flags = self._check_red_flags(best_pattern, market_data)

        if not has_red_flags:
            logger.info(f"✅ AUTO-APPROVE: {pair} {best_pattern.pattern_type} (score: {best_pattern.score})")

            return {
                'setup_type': best_pattern.pattern_type,
                'direction': best_pattern.direction,
                'pattern_score': best_pattern.score,
                'momentum_score': None,  # Skipped LLM
                'final_score': best_pattern.score,
                'confidence': best_pattern.confidence,
                'reasoning': best_pattern.reasoning + ['Auto-approved (score ≥85)'],
                'blocked_by_gates': False,
                'entry': best_pattern.entry_price,
                'stop': best_pattern.stop_loss,
                'target': best_pattern.take_profit,
                'auto_approved': True
            }

    # 7. Score 70-84 OR high score with red flags → Call LLM
    logger.info(f"🤔 Calling LLM for validation: {pair} {best_pattern.pattern_type} (score: {best_pattern.score})")

    llm_result = self._analyze_with_llm(market_data, best_pattern)

    # 8. Blend scores
    pattern_weight = 0.7
    momentum_weight = 0.3

    momentum_score = llm_result.get('confidence', 50)  # LLM confidence 0-100
    final_score = (pattern_weight * best_pattern.score) + (momentum_weight * momentum_score)

    # 9. Shadow mode? Log both systems
    if self.shadow_mode:
        self._log_shadow_comparison(best_pattern, llm_result, final_score)

    return {
        'setup_type': best_pattern.pattern_type,
        'direction': best_pattern.direction,
        'pattern_score': best_pattern.score,
        'momentum_score': momentum_score,
        'final_score': final_score,
        'confidence': final_score / 100.0,
        'reasoning': best_pattern.reasoning + [f"LLM: {llm_result.get('reasoning', '')}"],
        'blocked_by_gates': False,
        'entry': best_pattern.entry_price,
        'stop': best_pattern.stop_loss,
        'target': best_pattern.take_profit,
        'llm_analysis': llm_result.get('reasoning'),
        'pattern_metadata': best_pattern.metadata,
        'auto_approved': False
    }

def _check_red_flags(self, pattern: PatternDetection, market_data: Dict) -> bool:
    """Check for conditions that require LLM validation even for high scores."""
    # TODO: Implement red flag detection
    # - News proximity check
    # - HTF structure conflicts
    # - Abnormal spread spikes
    return False

def _analyze_with_llm(self, market_data: Dict, pattern: PatternDetection) -> Dict:
    """Call LLM with pattern detection as context (hypothesis to challenge)."""
    pair = market_data['pair']
    current_price = market_data['current_price']

    prompt = f"""You are validating a SYSTEM-DETECTED pattern for {pair} scalping.

DETECTED PATTERN:
- Type: {pattern.pattern_type}
- Score: {pattern.score}/100
- Direction: {pattern.direction}
- Entry: {pattern.entry_price:.5f}
- Stop: {pattern.stop_loss:.5f} | Target: {pattern.take_profit:.5f}
- Reasoning: {', '.join(pattern.reasoning)}

PATTERN SUB-SCORES:
{json.dumps(pattern.sub_scores, indent=2)}

YOUR TASK: Challenge this pattern hypothesis. Confirm or reject based on:
1. HTF structure alignment
2. Liquidity/structure context
3. Risk/reward feasibility
4. Any conflicting signals

Respond in JSON:
{{
    "confirms": true/false,
    "confidence": 0-100,
    "reasoning": "brief explanation"
}}"""

    response = self.llm.invoke([HumanMessage(content=prompt)])

    try:
        content = response.content.strip()
        if content.startswith('```'):
            lines = content.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].startswith('```'):
                lines = lines[:-1]
            content = '\n'.join(lines).strip()
        result = json.loads(content)
    except Exception as e:
        logger.warning(f"⚠️ LLM validation parse error: {e}")
        result = {"confirms": False, "confidence": 0, "reasoning": f"Parse error: {e}"}

    return result

def _analyze_llm_only(self, market_data: Dict) -> Dict:
    """Original LLM-only analysis (backward compatibility)."""
    # Copy existing analyze logic here
    pass

def _log_shadow_comparison(self, pattern: PatternDetection, llm_result: Dict, final_score: float):
    """Log comparison between pattern detector and LLM for analysis."""
    logger.info(f"🔍 SHADOW MODE COMPARISON:")
    logger.info(f"   Pattern: {pattern.pattern_type} (score: {pattern.score})")
    logger.info(f"   LLM: {llm_result.get('confirms')} (conf: {llm_result.get('confidence')})")
    logger.info(f"   Final: {final_score:.1f}")
    # TODO: Write to comparison database for later analysis
```

### Step 2: Update Scalp Validator

Update `ScalpValidator.validate` in `scalping_agents.py`:

```python
def validate(self, momentum_analysis: Dict, technical_analysis: Dict, market_data: Dict) -> ScalpSetup:
    """
    Enhanced validator with tiered decision logic.

    Tiers:
    - Score ≥85: Auto-approved by Fast Momentum Agent (validator just packages)
    - Score 70-84: Validate with LLM
    - Score <70: Already rejected by Fast Momentum Agent
    """

    # Check if this was auto-approved
    if momentum_analysis.get('auto_approved', False):
        logger.info(f"✅ Validator: Auto-approved pattern (score: {momentum_analysis['pattern_score']})")

        return ScalpSetup(
            approved=True,
            direction=momentum_analysis['direction'],
            entry_price=momentum_analysis['entry'],
            stop_loss=momentum_analysis['stop'],
            take_profit=momentum_analysis['target'],
            confidence=momentum_analysis['confidence'],
            risk_tier=1,  # Highest confidence
            reasoning=momentum_analysis['reasoning']
        )

    # Check if blocked by gates
    if momentum_analysis.get('blocked_by_gates', False):
        return ScalpSetup(
            approved=False,
            direction='NONE',
            reasoning=momentum_analysis['reasoning']
        )

    # Score 70-84: Validate with LLM
    final_score = momentum_analysis.get('final_score', 0)

    if final_score >= 70:
        # Call LLM validator with both agent inputs
        # (existing logic here)
        pass
    else:
        # Score too low
        return ScalpSetup(
            approved=False,
            direction='NONE',
            reasoning=[f"Final score too low: {final_score:.0f} < 70"]
        )
```

---

## 📊 Expected Improvements

### Before (Current System)
- Rejection rate: ~80% ("absence of professional setup")
- Looking for perfect indicator alignment
- Binary pass/fail
- High LLM usage (every analysis)

### After (Pattern Detection)
- Rejection rate: ~40-50% (gates + scoring threshold)
- Detects actual price action events
- Graded scoring with explanations
- Reduced LLM usage (only borderline 70-84)
- Faster decisions (auto-approve ≥85)

### Performance Estimate
**Assuming 100 analysis cycles/day:**
- Gates block: ~30 (30%)
- Pattern score <60: ~20 (20%)
- Pattern score 60-69: ~10 (10%)
- Pattern score 70-84: ~25 (25%) → LLM calls
- Pattern score ≥85: ~15 (15%) → Auto-approve

**LLM reduction: 75% fewer calls** (25 vs 100)
**Decision speed: 50% faster** (for auto-approved setups)

---

## 🧪 Testing Plan

### Phase 1: Shadow Mode (2-4 weeks)
```python
# Enable in scalping_engine.py
engine = ScalpingEngine()
engine.agents["momentum"] = FastMomentumAgent(
    llm=llm,
    use_pattern_detection=True,
    shadow_mode=True  # Log both systems
)
```

**Metrics to track:**
- Pattern vs LLM agreement rate
- Score distribution by outcome (win/loss)
- Gate failure reasons
- False positive/negative analysis

### Phase 2: Integrated Mode (Gradual Rollout)
```python
# Start with one pair
engine.agents["momentum"] = FastMomentumAgent(
    llm=llm,
    use_pattern_detection=True,
    shadow_mode=False
)
```

**Monitor:**
- Win rate by score bucket (70-74, 75-79, 80-84, 85+)
- Average profit by pattern type (ORB/SFP/IMPULSE)
- LLM veto rate (rejects high scores)
- Auto-approve performance

### Phase 3: Threshold Tuning
After 2-4 weeks of data:
- Adjust score thresholds if needed
- Calibrate score-to-probability curves
- Fine-tune pattern weights
- Optimize LLM usage tier (maybe 65-79 instead of 70-84)

---

## 📝 Configuration

Add to `scalping_config.py`:
```python
# Pattern Detection Settings
USE_PATTERN_DETECTION = True
PATTERN_SHADOW_MODE = False  # Set True for testing
PATTERN_SCORE_THRESHOLDS = {
    'reject_below': 60,
    'borderline_max': 69,
    'llm_required_min': 70,
    'llm_required_max': 84,
    'auto_approve': 85
}
PATTERN_WEIGHTS = {
    'pattern': 0.7,  # Pattern detector weight
    'momentum': 0.3  # LLM momentum weight
}
```

---

## 🔍 Debugging & Monitoring

### Log Analysis
```bash
# Check pattern detection performance
grep "Pattern.*score:" logs/scalping_agents.log

# Check gate failures
grep "Gates failed" logs/scalping_agents.log

# Check auto-approvals
grep "AUTO-APPROVE" logs/scalping_agents.log

# Shadow mode comparisons
grep "SHADOW MODE" logs/scalping_agents.log
```

### Database Queries (from agent_data_logger)
```sql
-- Pattern performance by score bucket
SELECT
    CASE
        WHEN confidence*100 >= 85 THEN '85+'
        WHEN confidence*100 >= 80 THEN '80-84'
        WHEN confidence*100 >= 75 THEN '75-79'
        WHEN confidence*100 >= 70 THEN '70-74'
        ELSE '<70'
    END as score_bucket,
    COUNT(*) as trades,
    SUM(CASE WHEN approved THEN 1 ELSE 0 END) as approved,
    AVG(confidence) as avg_conf
FROM judge_decisions
WHERE judge_name = 'scalp_validator'
GROUP BY score_bucket
ORDER BY score_bucket DESC;
```

---

## 🚀 Next Steps

1. ✅ Pattern detectors complete
2. ✅ Pre-trade gates complete
3. ⏳ **Update Fast Momentum Agent** (add code from Step 1 above)
4. ⏳ **Update Scalp Validator** (add code from Step 2 above)
5. ⏳ Test in shadow mode
6. ⏳ Analyze shadow mode results
7. ⏳ Deploy integrated mode
8. ⏳ Tune thresholds based on performance

---

## 📚 References

- `pattern_detectors.py` - Pattern detection implementation
- `pre_trade_gates.py` - Pre-trade gate system
- GPT-5 Integration Analysis (in conversation history)
- Research: ORB strategy 400% returns with strict rules

---

**Last Updated:** 2025-01-04
**Version:** 1.0
**Status:** Ready for agent integration
