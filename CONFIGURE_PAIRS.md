# Configure Which Pairs to Analyze

## Current Setup

**Currently analyzing**: 5 priority pairs
- EUR_USD
- GBP_USD
- USD_JPY
- EUR_GBP
- AUD_USD

**Total available**: 28 forex pairs

## Why Only 5 Pairs?

Your IG demo account has API rate limits:
- **30 requests per minute** (most restrictive)
- Each pair needs ~6 API requests to analyze
- 5 pairs × 6 requests = ~30 requests per cycle ✅

**If you analyze all 28 pairs**:
- 28 pairs × 6 requests = 168 requests
- Would exceed the 30/minute limit
- API would block your requests

## Options to Analyze More Pairs

### Option 1: Increase Scan Interval (Recommended)

Analyze more pairs by spacing out the scans:

**Edit `ig_concurrent_worker.py` line 323:**

```python
# For 10 pairs - scan every 2 minutes
worker = IGConcurrentWorker(
    auto_trading=False,
    max_workers=1,
    interval_seconds=120  # Change from 60 to 120
)
```

Then edit `forex_config.py` line 113-119:

```python
PRIORITY_PAIRS: List[str] = [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "EUR_GBP",
    "AUD_USD",
    "NZD_USD",    # Add more pairs
    "USD_CAD",
    "USD_CHF",
    "AUD_JPY",
    "EUR_JPY",
]
```

**Trade-offs**:
- ✅ Can analyze 10 pairs
- ❌ Updates every 2 minutes instead of 1 minute
- ✅ Still within rate limits

### Option 2: Analyze All 28 Pairs (Slow)

To analyze ALL 28 pairs, you need a much longer interval:

**Edit `ig_concurrent_worker.py`:**

```python
# For ALL 28 pairs - scan every 6 minutes
worker = IGConcurrentWorker(
    auto_trading=False,
    max_workers=1,
    interval_seconds=360  # 6 minutes
)
```

**Edit `forex_config.py`:**

```python
PRIORITY_PAIRS: List[str] = ForexConfig.ALL_PAIRS  # Use all 28 pairs
```

**Trade-offs**:
- ✅ Analyzes all 28 pairs
- ❌ Only updates every 6 minutes
- ❌ May miss short-term opportunities
- ✅ Good for longer timeframe strategies (15m+)

### Option 3: Multiple Accounts (Advanced)

Use multiple IG API keys:
- Account 1: Analyzes pairs 1-14
- Account 2: Analyzes pairs 15-28
- Each has its own 30 req/min limit

### Option 4: Upgrade to Live Account

IG Live accounts typically have higher rate limits than demo accounts. Contact IG support for specifics.

## Recommended Setup by Strategy

### Day Trading (1m-5m timeframes)
- **Pairs**: 3-5 pairs
- **Interval**: 60 seconds
- **Why**: Need fast updates for quick decisions

### Swing Trading (15m-1h timeframes)
- **Pairs**: 10-15 pairs
- **Interval**: 2-3 minutes
- **Why**: Longer timeframes = less urgent updates needed

### Position Trading (4h-1d timeframes)
- **Pairs**: All 28 pairs
- **Interval**: 5-10 minutes
- **Why**: Positions held for hours/days, less time-sensitive

## Current Recommendation

**Stick with 5 pairs at 60 seconds for now**:
- Perfect for 5-minute forex trading
- Real-time updates
- Stays within all rate limits
- Most reliable setup

Once comfortable, gradually add more pairs and increase the interval.

## How to Change Priority Pairs

Edit `forex_config.py` line 113:

```python
PRIORITY_PAIRS: List[str] = [
    "EUR_USD",    # Keep your favorites
    "GBP_USD",
    "USD_JPY",
    "EUR_GBP",
    "AUD_USD",
    # "NZD_USD",  # Uncomment to add
    # "USD_CAD",
]
```

Save, restart dashboard, done!

## All 28 Available Pairs

### Major Pairs (7)
- EUR_USD, USD_JPY, GBP_USD, AUD_USD
- USD_CAD, USD_CHF, NZD_USD

### EUR Cross Pairs (6)
- EUR_GBP, EUR_JPY, EUR_AUD, EUR_CAD
- EUR_CHF, EUR_NZD

### GBP Cross Pairs (5)
- GBP_JPY, GBP_AUD, GBP_CAD, GBP_CHF, GBP_NZD

### AUD Cross Pairs (4)
- AUD_JPY, AUD_CAD, AUD_CHF, AUD_NZD

### Other Crosses (6)
- CAD_JPY, CAD_CHF, CAD_NZD
- CHF_JPY, CHF_NZD
- NZD_JPY

---

**Bottom Line**: The dashboard shows all 28 pairs, but only analyzes 5 to respect API limits. This is by design for your 5-minute trading strategy.
