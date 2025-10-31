# Quota Analysis: 28 Pairs

## Indicator Requirements

### Minimum Candles Needed by Indicator

| Indicator | Candles | Critical? |
|-----------|---------|-----------|
| **MA-200** | **200** | ⚠️ Very quota-heavy |
| Ichimoku Senkou B | 78 | Uses 52 + 26 shift |
| VPVR | 90 | Volume profile |
| MA-50 | 50 | ✅ Important |
| OBV Z-Score | 50 | Volume analysis |
| Ultimate Oscillator | 28 | Multi-timeframe |
| Aroon | 25 | Trend detection |
| MA-21 | 21 | ✅ Important |
| RSI/ADX/ATR | 14 | ✅ Critical |
| MA-9 | 9 | ✅ Critical |

**Recommendation:**
- **With MA-200:** Need 200 candles (quota intensive)
- **Without MA-200:** Need 60-80 candles (much more efficient)

Most day traders don't use MA-200 - they focus on MA-9, MA-21, MA-50.

---

## Quota Math: 28 Pairs × 2 Timeframes

### Scenario 1: Current (100 candles)
```
Initial backfill:
28 pairs × 100 candles × 2 timeframes = 5,600 quota points

Remaining for delta updates:
10,000 - 5,600 = 4,400 points

Per cycle (delta update):
28 pairs × 2 candles × 2 TF = 112 points

Cycles possible:
4,400 / 112 = 39 cycles

Runtime before exhaustion:
39 cycles × 5 min = 195 minutes = 3.25 hours ❌
```

### Scenario 2: Reduced to 60 candles (Drop MA-200)
```
Initial backfill:
28 pairs × 60 candles × 2 timeframes = 3,360 quota points ✅

Remaining for delta updates:
10,000 - 3,360 = 6,640 points

Per cycle (delta update):
28 pairs × 2 candles × 2 TF = 112 points

Cycles possible:
6,640 / 112 = 59 cycles

Runtime before exhaustion:
59 cycles × 5 min = 295 minutes = 4.9 hours ⚠️ Better but still limited
```

### Scenario 3: Keep MA-200 (200 candles)
```
Initial backfill:
28 pairs × 200 candles × 2 timeframes = 11,200 quota points ❌ EXCEEDS QUOTA!

This doesn't even fit in the weekly allowance!
```

### Scenario 4: 15min timeframe only (80 candles)
```
Initial backfill:
28 pairs × 80 candles × 1 timeframe = 2,240 quota points ✅✅

Remaining for delta updates:
10,000 - 2,240 = 7,760 points

Per cycle (delta update):
28 pairs × 1 candle × 1 TF = 28 points (!)

Cycles possible:
7,760 / 28 = 277 cycles

Runtime before exhaustion:
277 cycles × 15 min = 4,155 minutes = 69 hours = 2.9 days ✅✅✅
```

---

## Recommendation: WebSocket + Database

### Why REST Polling Doesn't Scale:

**The Problem:**
- 28 pairs is pushing the 10k quota limit
- Can't get enough history for MA-200
- 3-5 hour runtime before exhaustion
- Adding more pairs makes it worse

**The Solution:**
```
┌────────────────────────────────────┐
│  IG WebSocket (Lightstreamer)     │
│  - Subscribe to all 28 pairs      │
│  - Real-time tick data            │
│  - NO quota limits                │
│  - Runs 24/5 continuously         │
└──────────────┬─────────────────────┘
               │
               ▼
┌────────────────────────────────────┐
│  PostgreSQL/TimescaleDB            │
│  - Store all historical candles   │
│  - Can store 1000s of candles     │
│  - Query takes <10ms              │
│  - Perfect for time-series        │
└──────────────┬─────────────────────┘
               │
               ▼
┌────────────────────────────────────┐
│  Trading Bot                       │
│  - Query DB for any # of candles  │
│  - Calculate all indicators       │
│  - No API quota worries           │
└────────────────────────────────────┘
```

---

## Cost-Benefit Analysis

### Option A: REST + Reduced Candles (60)
- **Pros:**
  - Quick fix (1 day)
  - Works with existing code
  - 5-hour runtime (vs 3 hours)

- **Cons:**
  - Still quota limited
  - Can't use MA-200
  - Not scalable
  - Not real-time
  - Band-aid solution

### Option B: WebSocket + Database (RECOMMENDED)
- **Pros:**
  - ✅ Unlimited quota
  - ✅ Real-time data (<1 sec)
  - ✅ All 200 candles for MA-200
  - ✅ Can add more pairs
  - ✅ Industry standard
  - ✅ Permanent solution

- **Cons:**
  - Requires 1-2 weeks to implement
  - Need to set up PostgreSQL
  - More complex architecture
  - But: This is how ALL professional platforms work

---

## Implementation Priority

### Immediate (Today):
```python
# Reduce to 60 candles temporarily in forex_data.py
df_primary = self.ig_fetcher.get_candles(pair, primary_tf, count=60)  # Was 100
df_secondary = self.ig_fetcher.get_candles(pair, secondary_tf, count=60)  # Was 100

# This gives you 5 hours runtime while you build WebSocket
```

### Week 1-2: WebSocket Collector
- Set up IG Lightstreamer connection
- Subscribe to 28 pairs
- Stream data to PostgreSQL
- Let it accumulate data

### Week 3: Migration
- Update bot to query database
- Test with historical data
- Verify all indicators work

### Week 4: Production
- Fully migrate to WebSocket
- Remove REST polling
- Run 24/5 without quota limits

---

## Your Questions Answered

### 1. "What's the minimum amount of candles we need?"

**Answer:** Depends on indicators:
- **With MA-200:** 200 candles (but exceeds quota for 28 pairs!)
- **Without MA-200:** 60 candles (most indicators work fine)
- **Optimal:** 80-100 candles (good balance)

### 2. "Perhaps we need to go to 20 or 15 even?"

**Answer:** 20 is too few - most indicators would fail:
- MA-50 needs 50 candles
- OBV Z-Score needs 50 candles
- Ichimoku needs 78 candles
- VPVR needs 90 candles

**Absolute minimum:** 60 candles

### 3. "Wouldn't it be more logical to go to WebSocket?"

**Answer:** YES! 100% correct! ✅

WebSocket is the **proper architecture** for forex trading:
- Real-time data
- No quota limits
- Industry standard
- Scalable to 100+ pairs
- Can store 1000s of candles

### 4. "Save it to a database instead of cache?"

**Answer:** YES! You're right - it IS a database, not just a cache:
- SQLite/PostgreSQL is a permanent database
- It's the source of truth for historical data
- "Cache" was just emphasizing the caching behavior

**Better terminology:**
- ❌ "Cache" (implies temporary)
- ✅ "Historical database" (correct)
- ✅ "Time-series database" (even better)

---

## Final Recommendation

### Short-term (This Week):
```python
# Reduce to 60 candles to buy time
# 28 pairs × 60 × 2 TF = 3,360 quota
# Runtime: ~5 hours
```

### Long-term (Next 2-4 Weeks):
```
Build WebSocket + PostgreSQL architecture
- Unlimited operation
- Real-time data
- All indicators work
- Can use MA-200
- Proper production system
```

**This is the correct path forward.** The WebSocket approach is not over-engineering - it's **how forex trading systems should be built**.

---

## Next Decision Point

To proceed with WebSocket implementation, answer:

1. **Database choice?**
   - PostgreSQL + TimescaleDB (recommended)
   - SQLite (simpler but limited)

2. **Deployment environment?**
   - Local machine
   - Cloud (AWS/Azure/GCP)
   - VPS

3. **Timeline?**
   - Full migration (1 month)
   - Hybrid approach (2 weeks)
   - Interim fix while building (reduce to 60 candles)

**I recommend: PostgreSQL + TimescaleDB + 2-week hybrid approach**
- Reduce to 60 candles NOW (buys time)
- Build WebSocket in parallel
- Migrate when data accumulated
- Best of both worlds
