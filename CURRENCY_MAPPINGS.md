# Currency Pair Mappings - Multi-Source Architecture

**Date**: 2025-11-03
**Status**: Complete Mapping for 28 Forex Pairs
**Sources**: IG Markets, Finnhub, DataBento

---

## Overview

The system integrates data from 3 sources for 28 forex currency pairs:

| Source | Coverage | Format | Data Type |
|--------|----------|--------|-----------|
| **IG Markets** | All 28 pairs | `EUR_USD` | Real-time tick data (tick volume) |
| **Finnhub** | All 28 pairs | `OANDA:EUR_USD` | Historical OHLCV, news, fundamentals |
| **DataBento** | 7 USD majors only | `6E.c.0` | CME futures with real volume |

---

## Complete Mapping Table

### Major Pairs (7 USD pairs)

| # | IG Markets | Finnhub | DataBento CME | Notes |
|---|------------|---------|---------------|-------|
| 1 | `EUR_USD` | `OANDA:EUR_USD` | `6E.c.0` (6E) | ✅ All sources |
| 2 | `USD_JPY` | `OANDA:USD_JPY` | `6J.c.0` (6J) | ⚠️ Inverted on CME |
| 3 | `GBP_USD` | `OANDA:GBP_USD` | `6B.c.0` (6B) | ✅ All sources |
| 4 | `AUD_USD` | `OANDA:AUD_USD` | `6A.c.0` (6A) | ✅ All sources |
| 5 | `USD_CAD` | `OANDA:USD_CAD` | `6C.c.0` (6C) | ⚠️ Inverted on CME |
| 6 | `USD_CHF` | `OANDA:USD_CHF` | `6S.c.0` (6S) | ⚠️ Inverted on CME |
| 7 | `NZD_USD` | `OANDA:NZD_USD` | `6N.c.0` (6N) | ✅ All sources |

**Micro Contracts**: M6E, M6J, M6B, M6A, M6C, M6S, M6N (1/10th size)

---

### EUR Cross Pairs (6 pairs) - IG + Finnhub Only

| # | IG Markets | Finnhub | DataBento | Notes |
|---|------------|---------|-----------|-------|
| 8 | `EUR_GBP` | `OANDA:EUR_GBP` | ❌ N/A | Spot only |
| 9 | `EUR_JPY` | `OANDA:EUR_JPY` | ❌ N/A | Spot only |
| 10 | `EUR_AUD` | `OANDA:EUR_AUD` | ❌ N/A | Spot only |
| 11 | `EUR_CAD` | `OANDA:EUR_CAD` | ❌ N/A | Spot only |
| 12 | `EUR_CHF` | `OANDA:EUR_CHF` | ❌ N/A | Spot only |
| 13 | `EUR_NZD` | `OANDA:EUR_NZD` | ❌ N/A | Spot only |

---

### GBP Cross Pairs (5 pairs) - IG + Finnhub Only

| # | IG Markets | Finnhub | DataBento | Notes |
|---|------------|---------|-----------|-------|
| 14 | `GBP_JPY` | `OANDA:GBP_JPY` | ❌ N/A | Spot only |
| 15 | `GBP_AUD` | `OANDA:GBP_AUD` | ❌ N/A | Spot only |
| 16 | `GBP_CAD` | `OANDA:GBP_CAD` | ❌ N/A | Spot only |
| 17 | `GBP_CHF` | `OANDA:GBP_CHF` | ❌ N/A | Spot only |
| 18 | `GBP_NZD` | `OANDA:GBP_NZD` | ❌ N/A | Spot only |

---

### AUD Cross Pairs (4 pairs) - IG + Finnhub Only

| # | IG Markets | Finnhub | DataBento | Notes |
|---|------------|---------|-----------|-------|
| 19 | `AUD_JPY` | `OANDA:AUD_JPY` | ❌ N/A | Spot only |
| 20 | `AUD_CAD` | `OANDA:AUD_CAD` | ❌ N/A | Spot only |
| 21 | `AUD_CHF` | `OANDA:AUD_CHF` | ❌ N/A | Spot only |
| 22 | `AUD_NZD` | `OANDA:AUD_NZD` | ❌ N/A | Spot only |

---

### CAD Cross Pairs (3 pairs) - IG + Finnhub Only

| # | IG Markets | Finnhub | DataBento | Notes |
|---|------------|---------|-----------|-------|
| 23 | `CAD_JPY` | `OANDA:CAD_JPY` | ❌ N/A | Spot only |
| 24 | `CAD_CHF` | `OANDA:CAD_CHF` | ❌ N/A | Spot only |
| 25 | `CAD_NZD` | `OANDA:CAD_NZD` | ❌ N/A | Spot only (may need inversion) |

---

### CHF Cross Pairs (2 pairs) - IG + Finnhub Only

| # | IG Markets | Finnhub | DataBento | Notes |
|---|------------|---------|-----------|-------|
| 26 | `CHF_JPY` | `OANDA:CHF_JPY` | ❌ N/A | Spot only |
| 27 | `CHF_NZD` | `OANDA:CHF_NZD` | ❌ N/A | Spot only (may need inversion) |

---

### NZD Cross Pairs (1 pair) - IG + Finnhub Only

| # | IG Markets | Finnhub | DataBento | Notes |
|---|------------|---------|-----------|-------|
| 28 | `NZD_JPY` | `OANDA:NZD_JPY` | ❌ N/A | Spot only |

---

## Symbol Format Reference

### IG Markets Format
```
Pattern: BASE_QUOTE (underscore separated)
Examples: EUR_USD, GBP_JPY, AUD_NZD

Epic Format: CS.D.{PAIR}.MINI.IP
Examples:
  - CS.D.EURUSD.MINI.IP
  - CS.D.GBPJPY.MINI.IP
```

### Finnhub Format
```
Pattern: EXCHANGE:BASE_QUOTE (with underscore)
Exchange: OANDA or FXCM

Examples:
  - OANDA:EUR_USD
  - OANDA:GBP_JPY
  - FXCM:EUR_USD

API Endpoints:
  - List symbols: GET /forex/symbol?exchange=oanda
  - Get candles: GET /forex/candle?symbol=OANDA:EUR_USD&resolution=5
```

### DataBento Format
```
Dataset: CME.MDP3 (CME Globex FX Futures)
Pattern: {ROOT}.c.0 (continuous front-month)

Available Roots:
  - 6E = EUR/USD futures
  - 6J = JPY/USD futures (inverted vs USD/JPY spot)
  - 6B = GBP/USD futures
  - 6A = AUD/USD futures
  - 6C = CAD/USD futures (inverted vs USD_CAD spot)
  - 6S = CHF/USD futures (inverted vs USD_CHF spot)
  - 6N = NZD/USD futures

Micro Contracts (1/10th size):
  - M6E, M6J, M6B, M6A, M6C, M6S, M6N

Examples:
  - 6E.c.0 (front-month EUR/USD continuous)
  - 6EH5 (EUR/USD March 2025 explicit contract)
  - M6E.c.0 (micro EUR/USD continuous)
```

---

## Inverted Pairs on CME

⚠️ **Important**: Some CME futures quote the INVERSE of spot forex convention:

| Spot Pair | CME Futures | Inversion Required |
|-----------|-------------|-------------------|
| USD/JPY | 6J (JPY/USD) | ✅ Yes - invert |
| USD/CAD | 6C (CAD/USD) | ✅ Yes - invert |
| USD/CHF | 6S (CHF/USD) | ✅ Yes - invert |
| EUR/USD | 6E (EUR/USD) | ❌ No - direct |
| GBP/USD | 6B (GBP/USD) | ❌ No - direct |
| AUD/USD | 6A (AUD/USD) | ❌ No - direct |
| NZD/USD | 6N (NZD/USD) | ❌ No - direct |

**Inversion Formula**: `spot_rate = 1 / futures_rate`

Example: If 6J (JPY/USD) trades at 0.00667, then USD/JPY = 1/0.00667 ≈ 150.00

---

## Data Source Strategy

### For 7 USD Major Pairs (EUR_USD, USD_JPY, GBP_USD, AUD_USD, USD_CAD, USD_CHF, NZD_USD):

```python
# Real-time streaming (all pairs)
ig_markets_websocket = {
    "source": "IG Markets WebSocket",
    "data": "tick-by-tick prices, bid/ask/mid, tick volume",
    "latency": "<100ms",
    "usage": "Real-time trading signals, spread monitoring"
}

# Real volume from futures (7 majors only)
databento_stream = {
    "source": "DataBento CME.MDP3",
    "data": "trades with real volume, level 10 book depth",
    "latency": "<50ms",
    "usage": "VWAP calculation, order flow, volume delta, VPIN"
}

# Historical data + fundamentals (all pairs)
finnhub_api = {
    "source": "Finnhub OANDA/FXCM",
    "data": "Historical OHLCV, forex news, economic calendar",
    "latency": "API polling (not streaming)",
    "usage": "Backtesting, historical analysis, fundamental data"
}
```

### For 21 Cross Pairs (EUR_GBP, GBP_JPY, etc.):

```python
# Real-time streaming (all pairs)
ig_markets_websocket = {
    "source": "IG Markets WebSocket",
    "data": "tick-by-tick prices, bid/ask/mid, tick volume",
    "usage": "Primary real-time data source"
}

# Historical data + fundamentals (all pairs)
finnhub_api = {
    "source": "Finnhub OANDA/FXCM",
    "data": "Historical OHLCV, forex news",
    "usage": "Historical analysis, fundamentals"
}

# No DataBento support for cross pairs
databento_stream = None  # Use IG tick volume for volume-based indicators
```

---

## Implementation Checklist

### ✅ Completed
- [x] IG Markets websocket streaming (28 pairs)
- [x] DataBento CME futures streaming (7 USD majors)
- [x] Symbol mapping system (continuous → raw → instrument_id)
- [x] Spread checking before trades
- [x] Multi-source data architecture (DataHub)

### 🔄 To Complete
- [ ] Finnhub integration for all 28 pairs
- [ ] Historical data fetching from Finnhub
- [ ] News/fundamental data integration
- [ ] Volume indicator logic (use DataBento for majors, IG for crosses)
- [ ] VWAP calculation (true VWAP for majors, TWAP for crosses)

---

## Python Mapping Configuration

```python
# Complete mapping dictionary
CURRENCY_MAPPINGS = {
    # Major Pairs (7) - All sources available
    "EUR_USD": {
        "ig_epic": "CS.D.EURUSD.MINI.IP",
        "finnhub": "OANDA:EUR_USD",
        "databento": "6E.c.0",
        "databento_micro": "M6E.c.0",
        "inverted": False,
        "has_real_volume": True
    },
    "USD_JPY": {
        "ig_epic": "CS.D.USDJPY.MINI.IP",
        "finnhub": "OANDA:USD_JPY",
        "databento": "6J.c.0",
        "databento_micro": "M6J.c.0",
        "inverted": True,  # 6J quotes JPY/USD
        "has_real_volume": True
    },
    "GBP_USD": {
        "ig_epic": "CS.D.GBPUSD.MINI.IP",
        "finnhub": "OANDA:GBP_USD",
        "databento": "6B.c.0",
        "databento_micro": "M6B.c.0",
        "inverted": False,
        "has_real_volume": True
    },
    "AUD_USD": {
        "ig_epic": "CS.D.AUDUSD.MINI.IP",
        "finnhub": "OANDA:AUD_USD",
        "databento": "6A.c.0",
        "databento_micro": "M6A.c.0",
        "inverted": False,
        "has_real_volume": True
    },
    "USD_CAD": {
        "ig_epic": "CS.D.USDCAD.MINI.IP",
        "finnhub": "OANDA:USD_CAD",
        "databento": "6C.c.0",
        "databento_micro": "M6C.c.0",
        "inverted": True,  # 6C quotes CAD/USD
        "has_real_volume": True
    },
    "USD_CHF": {
        "ig_epic": "CS.D.USDCHF.MINI.IP",
        "finnhub": "OANDA:USD_CHF",
        "databento": "6S.c.0",
        "databento_micro": "M6S.c.0",
        "inverted": True,  # 6S quotes CHF/USD
        "has_real_volume": True
    },
    "NZD_USD": {
        "ig_epic": "CS.D.NZDUSD.MINI.IP",
        "finnhub": "OANDA:NZD_USD",
        "databento": "6N.c.0",
        "databento_micro": "M6N.c.0",
        "inverted": False,
        "has_real_volume": True
    },

    # EUR Cross Pairs (6) - IG + Finnhub only
    "EUR_GBP": {
        "ig_epic": "CS.D.EURGBP.MINI.IP",
        "finnhub": "OANDA:EUR_GBP",
        "databento": None,
        "has_real_volume": False
    },
    "EUR_JPY": {
        "ig_epic": "CS.D.EURJPY.MINI.IP",
        "finnhub": "OANDA:EUR_JPY",
        "databento": None,
        "has_real_volume": False
    },
    "EUR_AUD": {
        "ig_epic": "CS.D.EURAUD.MINI.IP",
        "finnhub": "OANDA:EUR_AUD",
        "databento": None,
        "has_real_volume": False
    },
    "EUR_CAD": {
        "ig_epic": "CS.D.EURCAD.MINI.IP",
        "finnhub": "OANDA:EUR_CAD",
        "databento": None,
        "has_real_volume": False
    },
    "EUR_CHF": {
        "ig_epic": "CS.D.EURCHF.MINI.IP",
        "finnhub": "OANDA:EUR_CHF",
        "databento": None,
        "has_real_volume": False
    },
    "EUR_NZD": {
        "ig_epic": "CS.D.EURNZD.MINI.IP",
        "finnhub": "OANDA:EUR_NZD",
        "databento": None,
        "has_real_volume": False
    },

    # ... (continue for all 28 pairs)
}

# Quick lookup functions
def get_pairs_with_real_volume():
    """Get pairs that have DataBento real volume."""
    return [k for k, v in CURRENCY_MAPPINGS.items() if v.get("has_real_volume")]

def get_pairs_tick_volume_only():
    """Get pairs that only have IG tick volume."""
    return [k for k, v in CURRENCY_MAPPINGS.items() if not v.get("has_real_volume")]

def needs_inversion(pair):
    """Check if CME futures quotes need inversion."""
    return CURRENCY_MAPPINGS.get(pair, {}).get("inverted", False)
```

---

## Next Steps

1. **Implement Finnhub integration** for historical data across all 28 pairs
2. **Add volume source detection** in indicator calculations
3. **Update VWAP logic**: Use DataBento for majors, IG tick volume for crosses
4. **Add news/fundamentals** from Finnhub to enhance agent decisions
5. **Optimize indicator calculations** based on available data sources

---

**Version**: 1.0
**Last Updated**: 2025-11-03
**Status**: Complete mapping ready for implementation
