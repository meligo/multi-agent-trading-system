# Complete Agentic Data Flow - End-to-End Integration Plan

## Current State Analysis

### 📊 **Data Sources Available**
1. **IG WebSocket** ✅ - Real-time ticks & candles
2. **InsightSentry v3** ✅ - Economic calendar, news, sentiment
3. **DataBento** ✅ - CME futures order flow (MBP-10)
4. **Finnhub** ✅ - Technical analysis, patterns, S/R levels
5. **PostgreSQL + TimescaleDB** ✅ - Historical data storage

### 🎯 **Currency Pairs**
**Original**: 24 PRIORITY_PAIRS (from forex_config.py)
- 20 Forex pairs (EUR_USD, GBP_USD, USD_JPY, etc.)
- 4 Commodities (XAU_USD, XAG_USD, OIL_CRUDE, OIL_BRENT)

**Current Scalping**: Only 3 pairs (EUR_USD, GBP_USD, USD_JPY)

### ⚠️ **Missing Integration**
- ❌ Engine has no data fetcher (`⚠️  No data fetcher for EUR_USD`)
- ❌ Not pulling live market data
- ❌ Not using Finnhub technical analysis
- ❌ Not using DataBento order flow
- ❌ Limited to 3 pairs instead of 24

---

## 🔄 Complete Process Flow (What Should Happen)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     1. DATA COLLECTION LAYER                         │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   IG WebSocket   │  │    Finnhub API   │  │   DataBento      │
│                  │  │                  │  │                  │
│ • 1m candles     │  │ • TA consensus   │  │ • Order flow     │
│ • Tick data      │  │ • Patterns       │  │ • CME MBP-10     │
│ • Spreads        │  │ • S/R levels     │  │ • Futures depth  │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                      │
         └─────────────────────┼──────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│              2. DATA AGGREGATION & PERSISTENCE                       │
│                                                                      │
│  • Combine all sources for each pair                                │
│  • Save to PostgreSQL/TimescaleDB                                   │
│  • Calculate scalping indicators (EMA 3/6/12, VWAP, RSI, ADX)      │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    3. AGENT ANALYSIS LAYER                           │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
         ┌────────────────────────────────────────┐
         │   PHASE 1: OPPORTUNITY DETECTION       │
         └────────────────────────────────────────┘
                               ↓
    ┌──────────────────┐              ┌──────────────────┐
    │ FastMomentum     │              │  Technical       │
    │ Agent            │              │  Agent           │
    │                  │              │                  │
    │ • 1m momentum    │              │  • Pattern       │
    │ • EMA crossovers │              │  • S/R levels    │
    │ • Quick signals  │              │  • Structure     │
    └────────┬─────────┘              └────────┬─────────┘
             │                                 │
             └────────────┬────────────────────┘
                          ↓
                 ┌─────────────────┐
                 │ ScalpValidator  │
                 │    (JUDGE)      │
                 │                 │
                 │ • Validates     │
                 │ • Checks spread │
                 │ • Approves/     │
                 │   Rejects       │
                 └────────┬────────┘
                          ↓
              [If Approved] → ScalpSetup Created
                          ↓
         ┌────────────────────────────────────────┐
         │   PHASE 2: RISK MANAGEMENT             │
         └────────────────────────────────────────┘
                          ↓
    ┌──────────────────┐              ┌──────────────────┐
    │  Aggressive      │              │  Conservative    │
    │  Risk Agent      │              │  Risk Agent      │
    │                  │              │                  │
    │ • Max position   │              │  • Min position  │
    │ • Take chances   │              │  • Strict rules  │
    └────────┬─────────┘              └────────┬─────────┘
             │                                 │
             └────────────┬────────────────────┘
                          ↓
                 ┌─────────────────┐
                 │  RiskManager    │
                 │    (JUDGE)      │
                 │                 │
                 │ • Final sizing  │
                 │ • Position mgmt │
                 │ • Approval      │
                 └────────┬────────┘
                          ↓
              [If Approved] → Execute Trade
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    4. EXECUTION & MONITORING                         │
│                                                                      │
│  • Execute via IG API                                               │
│  • Monitor for TP/SL hit                                            │
│  • Force-close after 20 minutes                                     │
│  • Save trade to PostgreSQL                                         │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    5. NEWS GATING OVERLAY                            │
│                                                                      │
│  InsightSentry monitors high-impact events                          │
│  → Close all positions 15 min before NFP, FOMC, etc.               │
│  → Block new trades during gating window                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 What Needs to be Fixed

### 1. **Integrate Data Fetcher into Engine**

**Problem**: Engine shows `⚠️  No data fetcher for EUR_USD`

**Solution**: Create a unified data fetcher that combines all sources

```python
# Create: unified_data_fetcher.py
class UnifiedDataFetcher:
    """Fetches and aggregates data from all sources."""

    def __init__(self):
        self.ig_websocket = WebSocketCollector()
        self.finnhub = FinnhubIntegration()
        self.databento = DataBentoClient()
        self.insightsentry = InsightSentryClient()
        self.db = DatabaseManager()

    async def fetch_market_data(self, pair: str, timeframe: str) -> Dict:
        """
        Fetch complete market picture for a pair.

        Returns:
            {
                'candles': [...],  # 1m OHLC from IG
                'spread': 1.0,     # Current spread
                'ta_consensus': {...},  # Finnhub TA
                'patterns': [...],      # Finnhub patterns
                'support_resistance': {...},  # S/R levels
                'order_flow': {...},   # DataBento futures flow
                'news_sentiment': {...},  # InsightSentry
            }
        """
        # Aggregate all data sources
        pass
```

### 2. **Inject Data Fetcher into Engine**

```python
# In scalping_dashboard.py or main startup:

# Initialize unified fetcher
data_fetcher = UnifiedDataFetcher()
await data_fetcher.initialize()

# Inject into engine
engine = ScalpingEngine()
engine.set_data_fetcher(data_fetcher)

# Start engine
engine_thread = threading.Thread(target=engine.run, daemon=True)
engine_thread.start()
```

### 3. **Expand to More Pairs**

**Option A**: Keep scalping focused (3-5 pairs)
- Current 3: EUR_USD, GBP_USD, USD_JPY ✅
- Add 2 more: EUR_JPY, GBP_JPY

**Option B**: Scale to 12 major pairs
- Add: EUR_GBP, AUD_USD, USD_CAD, USD_CHF, EUR_AUD, EUR_CAD, GBP_AUD, AUD_JPY, CAD_JPY

**Option C**: Full 24 pairs (as user wants)
- All PRIORITY_PAIRS from forex_config.py

### 4. **Update Engine's analyze_pair() to Use All Data**

```python
# In scalping_engine.py

def analyze_pair(self, pair: str) -> Optional[ScalpSetup]:
    """Analyze pair using ALL data sources."""

    # 1. Fetch complete market data
    if not self.data_fetcher:
        print(f"⚠️  No data fetcher for {pair}")
        return None

    market_data = self.data_fetcher.fetch_market_data(pair, "1m")

    # 2. Check spread (critical for scalping)
    if market_data['spread'] > self.config.MAX_SPREAD_PIPS:
        return None

    # 3. Run FastMomentum analysis
    momentum_signal = self.agents['fast_momentum'].analyze({
        'candles': market_data['candles'],
        'indicators': market_data['indicators']
    })

    # 4. Run Technical analysis
    technical_signal = self.agents['technical'].analyze({
        'patterns': market_data['patterns'],
        'support_resistance': market_data['support_resistance'],
        'ta_consensus': market_data['ta_consensus']
    })

    # 5. Validator judges (approve/reject)
    scalp_setup = self.agents['scalp_validator'].judge(
        momentum_signal,
        technical_signal,
        market_data
    )

    return scalp_setup
```

---

## 📋 Implementation Steps

### Step 1: Create Unified Data Fetcher ✅ (Priority 1)
- [ ] Create `unified_data_fetcher.py`
- [ ] Integrate IG WebSocket
- [ ] Integrate Finnhub
- [ ] Integrate DataBento
- [ ] Integrate InsightSentry
- [ ] Add caching layer

### Step 2: Connect to Engine ✅ (Priority 1)
- [ ] Inject data fetcher on engine init
- [ ] Update `analyze_pair()` to use fetcher
- [ ] Test with 3 pairs first

### Step 3: Expand Pairs ⏸️ (Priority 2)
- [ ] Decision: Keep 3, expand to 12, or go full 24?
- [ ] Update `scalping_config.py` with selected pairs
- [ ] Ensure DB has instruments for all pairs

### Step 4: PostgreSQL Integration ✅ (Already Done)
- [x] Save IG ticks
- [x] Save Finnhub data
- [x] Save economic events
- [x] Save agent signals

### Step 5: Dashboard Updates 🔄 (Priority 2)
- [ ] Show data source status for each pair
- [ ] Display Finnhub TA consensus
- [ ] Show order flow metrics
- [ ] News gating indicators

### Step 6: Testing 🧪 (Priority 1)
- [ ] Test data fetching for each pair
- [ ] Verify agent analysis works
- [ ] Confirm trades execute
- [ ] Validate data persistence

---

## 🎯 Immediate Next Actions

1. **Create unified_data_fetcher.py**
   - Combines all data sources
   - Returns complete market picture

2. **Fix "No data fetcher" error**
   - Inject fetcher into engine
   - Test with 3 pairs

3. **Decide on pairs**
   - Keep 3 (fast, focused)
   - Or expand to 12-24 (comprehensive)

4. **Document complete flow**
   - Data → Agents → Execution
   - Show in dashboard

---

## 🔍 Data Source Details

### IG WebSocket (Primary Price Data)
```python
# Already running in dashboard
websocket_collector = WebSocketCollector()
websocket_collector.start_streaming(['EUR_USD', 'GBP_USD', 'USD_JPY'])

# Provides:
- Real-time 1m candles
- Tick data
- Current spreads
- Bid/ask prices
```

### Finnhub API (Technical Analysis)
```python
finnhub = FinnhubIntegration(api_key=API_KEY)

# Provides:
- Aggregate TA consensus (30+ indicators)
- Chart patterns (head & shoulders, triangles, etc.)
- Support/resistance levels
- Trend strength
```

### DataBento (Order Flow)
```python
databento = DataBentoClient(['6E', '6B', '6J'])  # EUR, GBP, JPY futures

# Provides:
- CME futures order book (MBP-10)
- Institutional order flow
- Depth imbalances
- Volume profile
```

### InsightSentry (News & Events)
```python
insightsentry = InsightSentryClient()

# Provides:
- Economic calendar
- High-impact event detection
- News sentiment
- Gating signals
```

---

## 💡 Optimization Ideas

### Short-term
1. Start with 3 pairs, verify everything works
2. Add comprehensive logging
3. Monitor performance metrics

### Medium-term
1. Expand to 12 most liquid pairs
2. Add ML models for pattern recognition
3. Implement adaptive position sizing

### Long-term
1. Scale to full 24 pairs
2. Add multi-strategy support
3. Implement portfolio optimization

---

## 📊 Expected Performance (with full data)

### With Current 3 Pairs
- Signals/day: 10-15
- Trades/day: 5-8 (after filtering)
- Win rate target: 60%+
- Daily profit target: $50-100 (0.1 lot)

### With 12 Pairs
- Signals/day: 40-60
- Trades/day: 20-30
- Win rate target: 60%+
- Daily profit target: $200-400

### With 24 Pairs
- Signals/day: 80-120
- Trades/day: 40-60
- Win rate target: 60%+
- Daily profit target: $400-800

---

**Status**: 📝 Plan Created - Ready for Implementation

**Next File to Create**: `unified_data_fetcher.py`
