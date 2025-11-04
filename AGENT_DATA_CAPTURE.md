# Agent Data Capture System

## Overview

Complete database logging system that captures **ALL** data sent to agents, indicator calculations, and agent responses for later analysis, debugging, and ML training.

## Database Tables Created ✅

### 1. `analysis_sessions`
Main session tracking for each pair analysis cycle:
- `session_id` - Unique ID for this analysis
- `pair` - Currency pair (EUR_USD, GBP_USD, USD_JPY)
- `timestamp` - When analysis started
- `current_price` - Market price at analysis time
- `spread_pips` - Spread in pips
- `trading_hours` - Boolean: was it during trading hours
- `can_trade` - Boolean: were daily limits OK

### 2. `market_snapshots`
Complete market data at analysis time:
- Last 50 candles (OHLCV) as JSON
- Current bid/ask/spread
- Support/resistance levels

### 3. `indicator_values`
ALL calculated indicators:
- EMA Ribbon (3, 6, 12) + alignment
- RSI + zone (overbought/oversold)
- MACD + signal + histogram + cross type
- Bollinger Bands + width + price position
- Volume MA + surge detection
- Momentum strength + direction
- ATR + ATR in pips

### 4. `agent_responses`
Individual agent outputs:
- Fast Momentum Agent
- Technical Agent
- Aggressive Risk Agent
- Conservative Risk Agent
- Full JSON response
- Extracted recommendation
- Confidence score
- Reasoning text
- Execution time

### 5. `judge_decisions`
Judge (validator) decisions:
- Scalp Validator decisions
- Risk Manager decisions
- Approved/rejected
- Direction (BUY/SELL/NONE)
- Entry/TP/SL prices
- Position size
- Confidence + risk tier
- Full reasoning

## Current Status

✅ Tables created in database `forexscalper_dev@pga.bittics.com:5000`
✅ AgentDataLogger class implemented
✅ Integrated into ScalpingEngine
⚠️  Logging calls need to be added to capture data

## Integration Points Needed

The following integration points need to be added to `scalping_engine.py`:

### 1. Start of analyze_pair()
```python
def analyze_pair(self, pair: str) -> Optional[ScalpSetup]:
    # Generate session ID
    session_id = f"{pair}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Log session start
    if self.agent_data_logger:
        self.agent_data_logger.log_analysis_session(
            AnalysisSession(
                session_id=session_id,
                pair=pair,
                timestamp=datetime.now(),
                current_price=market_data['current_price'],
                spread_pips=spread,
                trading_hours=self.check_trading_hours(),
                can_trade=self.check_daily_limits()
            )
        )
```

### 2. After fetching market data
```python
# Log market snapshot
if self.agent_data_logger:
    self.agent_data_logger.log_market_snapshot(
        MarketSnapshot(
            session_id=session_id,
            pair=pair,
            timestamp=datetime.now(),
            candles_json=json.dumps(data[['open', 'high', 'low', 'close', 'volume']].to_dict('records')),
            current_price=current_price,
            bid=bid,
            ask=ask,
            spread=spread,
            nearest_support=market_data.get('nearest_support'),
            nearest_resistance=market_data.get('nearest_resistance')
        )
    )
```

### 3. After calculating indicators
```python
# Log all indicators
if self.agent_data_logger:
    self.agent_data_logger.log_indicators(
        IndicatorValues(
            session_id=session_id,
            pair=pair,
            timestamp=datetime.now(),
            ema_3=data['ema_3'].iloc[-1] if 'ema_3' in data else None,
            ema_6=data['ema_6'].iloc[-1] if 'ema_6' in data else None,
            ema_12=data['ema_12'].iloc[-1] if 'ema_12' in data else None,
            ema_alignment=market_data.get('ema_alignment'),
            rsi=data['rsi'].iloc[-1] if 'rsi' in data else None,
            rsi_zone=market_data.get('rsi_zone'),
            # ... all other indicators
        )
    )
```

### 4. After each agent response
```python
# Log Fast Momentum Agent
if self.agent_data_logger:
    self.agent_data_logger.log_agent_response(
        AgentResponse(
            session_id=session_id,
            agent_name="fast_momentum",
            timestamp=datetime.now(),
            response_json=json.dumps(momentum_analysis),
            recommendation=momentum_analysis.get('setup_type'),
            confidence=momentum_analysis.get('strength'),
            reasoning=momentum_analysis.get('reasoning'),
            execution_time_ms=execution_time
        )
    )
```

### 5. After Scalp Validator decision
```python
# Log Scalp Validator decision
if self.agent_data_logger:
    self.agent_data_logger.log_judge_decision(
        JudgeDecision(
            session_id=session_id,
            judge_name="scalp_validator",
            timestamp=datetime.now(),
            approved=scalp_setup.approved,
            decision_json=json.dumps(asdict(scalp_setup)),
            direction=scalp_setup.direction,
            entry_price=scalp_setup.entry_price,
            take_profit=scalp_setup.take_profit,
            stop_loss=scalp_setup.stop_loss,
            position_size=None,  # Set by Risk Manager
            confidence=scalp_setup.confidence,
            risk_tier=scalp_setup.risk_tier,
            reasoning='; '.join(scalp_setup.reasoning),
            execution_time_ms=None
        )
    )
```

### 6. After Risk Manager decision
```python
# Log Risk Manager decision
if self.agent_data_logger:
    self.agent_data_logger.log_judge_decision(
        JudgeDecision(
            session_id=session_id,
            judge_name="risk_manager",
            timestamp=datetime.now(),
            approved=execute,
            decision_json=json.dumps({'execute': execute, 'size': position_size}),
            direction=scalp_setup.direction,
            entry_price=scalp_setup.entry_price,
            take_profit=scalp_setup.take_profit,
            stop_loss=scalp_setup.stop_loss,
            position_size=position_size,
            confidence=scalp_setup.confidence,
            risk_tier=scalp_setup.risk_tier,
            reasoning=f"Execute: {execute}, Size: {position_size}",
            execution_time_ms=None
        )
    )
```

## Querying the Data

### Get complete analysis for a session
```python
from agent_data_logger import AgentDataLogger
from database_manager import DatabaseManager

db = DatabaseManager()
logger = AgentDataLogger(db.conn_string)

# Get all data for a session
session_data = logger.get_session_data('EUR_USD_20250104_110000')

# Returns:
{
    'session': {...},       # Analysis session record
    'snapshot': {...},      # Market data snapshot
    'indicators': {...},    # All indicator values
    'agents': [{...}],      # All agent responses
    'judges': [{...}]       # All judge decisions
}
```

### SQL Queries

**Get all approved trades:**
```sql
SELECT
    s.session_id,
    s.pair,
    s.timestamp,
    j.direction,
    j.entry_price,
    j.take_profit,
    j.stop_loss,
    j.confidence
FROM analysis_sessions s
JOIN judge_decisions j ON s.session_id = j.session_id
WHERE j.judge_name = 'scalp_validator'
  AND j.approved = true
ORDER BY s.timestamp DESC;
```

**Get agent performance (approval rate):**
```sql
SELECT
    a.agent_name,
    COUNT(*) as total_analyses,
    SUM(CASE WHEN j.approved THEN 1 ELSE 0 END) as approved,
    AVG(a.confidence) as avg_confidence
FROM agent_responses a
JOIN judge_decisions j ON a.session_id = j.session_id
WHERE j.judge_name = 'scalp_validator'
GROUP BY a.agent_name;
```

**Get indicator values for approved trades:**
```sql
SELECT
    i.*,
    j.direction,
    j.approved
FROM indicator_values i
JOIN judge_decisions j ON i.session_id = j.session_id
WHERE j.judge_name = 'scalp_validator'
  AND j.approved = true;
```

**Analyze rejection reasons:**
```sql
SELECT
    j.reasoning,
    COUNT(*) as count
FROM judge_decisions j
WHERE j.judge_name = 'scalp_validator'
  AND j.approved = false
GROUP BY j.reasoning
ORDER BY count DESC;
```

## Benefits

1. **Complete Audit Trail**: Every analysis is captured with full context
2. **ML Training Data**: Perfect dataset for training models
3. **Debugging**: Trace why trades were approved/rejected
4. **Performance Analysis**: Understand which indicators matter most
5. **Agent Optimization**: See which agents have highest approval rates
6. **Backtesting**: Replay exact market conditions and agent decisions
7. **Compliance**: Full regulatory audit trail

## Next Steps

1. ✅ Database tables created
2. ✅ AgentDataLogger class implemented
3. ✅ Integration hooks added to ScalpingEngine
4. ⏳ Add logging calls at key points (see Integration Points above)
5. ⏳ Test data capture with live analysis
6. ⏳ Create analysis notebooks for captured data

## File Locations

- **Logger Implementation**: `agent_data_logger.py`
- **Integration**: `scalping_engine.py` (lines 21-28, 174-175, 184-193)
- **Documentation**: `AGENT_DATA_CAPTURE.md` (this file)

## Testing

```bash
# Test logger initialization
python agent_data_logger.py

# Check tables in database
psql -h pga.bittics.com -p 5000 -U postgres -d forexscalper_dev -c "\dt"

# Test engine with data capture
python scalping_cli.py --test EUR_USD
```

---

**Status**: ✅ Infrastructure Ready - Integration Points Documented
**Version**: 1.0
**Last Updated**: 2025-11-04
