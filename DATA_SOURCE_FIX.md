# Data Source Architecture Fix

## Current Problem

**Multiple data sources with inconsistent volume data**:

1. **IG Markets** (WebSocket)
   - Provides: Real-time OHLC candles
   - Volume: ❌ FAKE (tick count proxy)
   - Usage: Currently primary for EUR/USD, GBP/USD, USD/JPY

2. **DataBento** (Futures)
   - Provides: CME futures order flow (6E, 6B, 6J)
   - Volume: ✅ REAL (actual trade volume)
   - Usage: Currently order flow only, NO candles

3. **Finnhub**
   - Provides: Technical analysis, patterns
   - Volume: N/A
   - Usage: Supplementary

## Solution

### Option A: Use DataBento Candles (BEST)

**Switch to DataBento for primary candle data**:

```python
# In UnifiedDataFetcher._fetch_ig_websocket_data()
if pair in self.futures_map:
    # Try DataBento first (real volume)
    databento_candles = self._fetch_databento_candles(pair, bars)
    if databento_candles is not None:
        return databento_candles

# Fallback to IG (tick volume)
ig_candles = self.data_hub.get_latest_candles(pair, limit=bars)
```

**Requires**:
1. Add DataBento bar aggregation to databento_client.py
2. Stream 1-minute OHLCV bars from CME futures
3. Store in DataHub with REAL volume

### Option B: Hybrid Approach (CURRENT)

**Keep current setup but mark volume quality**:

```python
candles_df['volume_type'] = 'tick'  # or 'real'
candles_df['volume_quality'] = 'low'  # or 'high'
```

**Benefits**:
- No major changes needed
- Indicators aware of volume quality
- Can disable VWAP when volume_quality='low'

### Option C: Separate Indicators (RECOMMENDED SHORT-TERM)

**Use different indicators based on data source**:

```python
# For IG data (no real volume):
- EMA Ribbon ✅
- RSI, ADX ✅
- Donchian ✅
- SuperTrend ✅
- Bollinger Squeeze ✅
- Price patterns ✅
- VWAP ❌ (disabled or marked as TWAP)

# For DataBento data (real volume):
- All above ✅
- VWAP ✅ (true VWAP)
- Volume Profile ✅
- Order Flow ✅
