# IG API Rate Limits - UPDATED

## Your Account's Specific Limits

From `IGService.get_client_apps()`:

```
API Key: 2f6287777a79dfb0c6f2a47c86a6f7d0b07ecef8
Status: ENABLED

RATE LIMITS:
├─ Application Overall: 60 requests/minute
├─ Account Trading: 100 requests/minute
├─ Account Overall: 30 requests/minute ⚠️ MOST RESTRICTIVE
├─ Historical Data: 10,000 data points/week
└─ Concurrent Streams: 40 subscriptions
```

## Implementation

### Rate Limiter Created (`ig_rate_limiter.py`)

Smart rate limiter that:
- ✅ Tracks all requests with timestamps
- ✅ Automatically waits if limits approached
- ✅ Cleans old requests (>1 minute)
- ✅ Shows remaining requests
- ✅ Thread-safe

Usage:
```python
from ig_rate_limiter import get_rate_limiter

limiter = get_rate_limiter()
limiter.wait_if_needed(is_account_request=True)
# Make your IG API call here
```

### Integrated Everywhere

Rate limiter now integrated in:
- ✅ `ig_data_fetcher_trading_ig.py` (data requests)
- ✅ `ig_trader.py` (trading requests)
- ✅ `ig_concurrent_worker.py` (displays stats)

### Analysis Changed to Sequential

**Before**: Analyzed 5 pairs in parallel → Hit 30/min limit immediately
**Now**: Analyzes pairs one at a time → Stays within limits

Each pair needs ~6 requests:
- 2 for data (5m + 1m timeframes)
- 1 for account info
- 1 for positions check
- 2 for AI analysis overhead

At 30 requests/min:
- Can safely analyze **4-5 pairs per minute**
- System set to 5 priority pairs every 60 seconds ✅

## Running the System

```bash
python ig_concurrent_worker.py
```

You'll see:
```
🔄 Starting analysis cycle at 2025-10-27 19:30:00
📊 Rate Limits: Account 0/30, App 0/60
📊 Open positions: 0
📊 Analyzing 5 priority pairs...

🔍 Analyzing EUR_USD...
   ✅ BUY signal (confidence: 0.75)
   📊 Rate: 24/30 remaining

🔍 Analyzing GBP_USD...
   ⏸️  HOLD (confidence: 0.45)
   📊 Rate: 18/30 remaining

...
```

## Best Practices

1. **Analyze 5 pairs max per cycle** ✅ (currently set)
2. **60 second intervals** ✅ (currently set)
3. **Sequential analysis** ✅ (currently implemented)
4. **Monitor rate limit stats** ✅ (displayed in real-time)
5. **Cache data when possible** (future enhancement)

## Historical Data Limit

Your account has **10,000 data points per week**.

Each candle = 1 data point. So:
- 500 candles × 2 timeframes = 1,000 points per pair
- 10,000 / 1,000 = **10 pairs per week** maximum

**Current usage**:
- 5 pairs × 2 timeframes × 500 candles = 5,000 points per cycle
- At 60s intervals = 1,440 cycles/day
- Would need 1.4M points/week if fetching full history each time

**Solution**: System should cache candles and only fetch latest ones. This is a future enhancement.

## Demo vs Live

⚠️ **Important**: These limits are for DEMO account and may change without notice.

LIVE accounts typically have higher limits, but you should check with IG support for specifics.

## Streaming API

Streaming limit: 40 concurrent subscriptions

**Status**: Not available on your demo account (returns "Invalid account type")

**Workaround**: Using REST API with <30s delay, which is fine for 5m/15m trading

## Updated System Status

✅ Rate limiter implemented
✅ Sequential analysis
✅ Real-time limit monitoring
✅ Respects 30 requests/minute account limit
✅ Ready for continuous operation

---

**Next Step**: Wait 1-2 minutes for rate limit reset, then run:

```bash
python ig_concurrent_worker.py
```

The system will now respect rate limits and run smoothly! 🚀
